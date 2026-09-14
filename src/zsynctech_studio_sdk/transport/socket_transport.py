"""Low-level Socket.IO transport for the platform's `/robot` namespace.

Owns the connection lifecycle, the automatic heartbeat loop, and translating the gateway's
`connected`/`error`/`exception` events into this SDK's own exceptions. Knows nothing about
execution/queue *semantics* - `client.py` builds those on top of :meth:`SocketTransport.call`
and :meth:`SocketTransport.emit`.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

import socketio

from zsynctech_studio_sdk.exceptions import (
    AuthenticationError,
    ConcurrencyLimitError,
    ExecutionError,
    SdkError,
)
from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.models.connection import ConnectResult
from zsynctech_studio_sdk.utils.logging import get_logger

_NAMESPACE = "/robot"
_CONCURRENCY_LIMIT_MARKER = "máximo de instâncias"
"""Substring the gateway's error message uses for a concurrency rejection.

See `RobotGateway.handleConnection`'s catch block (`robot.gateway.ts`) - the server doesn't
send a structured error code today, only this human-readable Portuguese message, so that's
what distinguishes a concurrency rejection from every other connection failure.
"""

logger = get_logger(__name__)


def _build_auth_payload(config: RobotClientConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "apiKey": config.api_key,
        "hostname": config.hostname,
        "platform": config.platform.value,
    }
    if config.version is not None:
        payload["version"] = config.version
    return payload


def _map_connect_error(message: str) -> SdkError:
    if _CONCURRENCY_LIMIT_MARKER in message:
        return ConcurrencyLimitError(message)
    return AuthenticationError(message)


class SocketTransport:
    """Wraps a `python-socketio` sync client around the `/robot` protocol."""

    def __init__(self, config: RobotClientConfig, on_start: Callable[[], None] | None = None) -> None:
        """Create a transport bound to ``config``.

        Args:
            config: Connection settings, including the heartbeat cadence.
            on_start: Called (with no arguments) whenever the platform pushes
                `automation:start` to this instance. Optional - a transport with no callback
                simply ignores the push.
        """
        self._config = config
        self._on_start = on_start
        self._sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False)
        self._ready = threading.Event()
        self._connect_result: ConnectResult | None = None
        self._connect_error: SdkError | None = None
        self._last_exception_message: str | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        # Registered via plain calls rather than `@self._sio.on(...)` decorator syntax -
        # `python-socketio` ships no type stubs, so under `mypy --strict` a decorator coming
        # from an untyped library taints the decorated function too; calling `.on()` directly
        # sidesteps that while behaving identically at runtime.
        self._sio.on("connected", self._on_connected, namespace=_NAMESPACE)
        self._sio.on("error", self._on_error, namespace=_NAMESPACE)
        self._sio.on("exception", self._on_exception, namespace=_NAMESPACE)
        if self._on_start is not None:
            self._sio.on("automation:start", self._on_automation_start, namespace=_NAMESPACE)

    def _on_connected(self, data: dict[str, Any]) -> None:
        self._connect_result = ConnectResult.model_validate(data)
        self._ready.set()

    def _on_error(self, data: dict[str, Any] | str) -> None:
        message = data.get("message", "Connection rejected") if isinstance(data, dict) else str(data)
        self._connect_error = _map_connect_error(message)
        self._ready.set()

    def _on_exception(self, data: dict[str, Any] | str) -> None:
        # NestJS's WsExceptionFilter emits a thrown WsException as its own `exception` event
        # rather than via the failed call's ack - a call() that raised
        # socketio.exceptions.TimeoutError checks this to give a real error message instead
        # of a bare timeout. See SocketTransport.call.
        message = data.get("message") if isinstance(data, dict) else str(data)
        self._last_exception_message = str(message) if message else None

    def _on_automation_start(self, _data: dict[str, Any]) -> None:
        if self._on_start is not None:
            self._on_start()

    def connect(self, timeout: float = 10.0) -> ConnectResult:
        """Open the connection and wait for the platform's `connected`/`error` reply.

        Raises:
            AuthenticationError: The API key is invalid or the robot is inactive.
            ConcurrencyLimitError: This robot already has `max_concurrency` instances connected.
            SdkError: The platform never replied within ``timeout`` seconds.
        """
        self._ready.clear()
        self._connect_result = None
        self._connect_error = None

        self._sio.connect(
            self._config.base_url,
            namespaces=[_NAMESPACE],
            auth=_build_auth_payload(self._config),
            wait_timeout=timeout,
        )

        if not self._ready.wait(timeout):
            self._sio.disconnect()
            raise SdkError("Timed out waiting for the platform to acknowledge the connection")

        if self._connect_error is not None:
            raise self._connect_error

        assert self._connect_result is not None
        self._start_heartbeat()
        return self._connect_result

    def disconnect(self) -> None:
        """Stop the heartbeat loop and close the socket, if open."""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None
        if self._sio.connected:
            self._sio.disconnect()

    def call(self, event: str, data: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        """Emit ``event`` and wait for its ack, raising on a server-side rejection.

        A handler that throws server-side never sends an ack, so a rejection surfaces here as
        a `TimeoutError` from the underlying client - this looks for a matching `exception`
        event received just before the timeout to raise a meaningful :class:`ExecutionError`
        instead of a bare timeout whenever possible.
        """
        self._last_exception_message = None
        try:
            response = self._sio.call(event, data, namespace=_NAMESPACE, timeout=timeout)
        except socketio.exceptions.TimeoutError as exc:
            if self._last_exception_message:
                raise ExecutionError(self._last_exception_message) from exc
            raise ExecutionError(f"Timed out waiting for a response to '{event}'") from exc
        return response if isinstance(response, dict) else {}

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget emit, for high-frequency events with no ack payload worth awaiting."""
        self._sio.emit(event, data, namespace=_NAMESPACE)

    def wait(self) -> None:
        """Block the calling thread until the connection closes or Ctrl+C is pressed.

        Polls on a short interval instead of delegating to the underlying client's own
        `wait()`, which blocks on a plain `Thread.join()` with no timeout - that join is
        known to swallow `KeyboardInterrupt` on some platforms (Windows in particular),
        leaving a script that can't be stopped with Ctrl+C. A `KeyboardInterrupt` here is
        treated as a normal request to stop rather than re-raised, so callers using
        `RobotClient` as a context manager still get a clean `disconnect()` afterward.
        """
        try:
            while self._sio.connected:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("wait() interrupted - stopping")

    @property
    def connected(self) -> bool:
        """Whether the underlying Socket.IO client currently holds an open connection."""
        return bool(self._sio.connected)

    def _start_heartbeat(self) -> None:
        self._heartbeat_stop.clear()
        interval = self._config.heartbeat_interval_seconds

        def _loop() -> None:
            while not self._heartbeat_stop.wait(interval):
                try:
                    self._sio.call("heartbeat", namespace=_NAMESPACE, timeout=interval)
                except Exception as exc:  # noqa: BLE001 - background loop must never crash silently
                    logger.warning("Heartbeat failed: %s", exc)

        self._heartbeat_thread = threading.Thread(target=_loop, daemon=True, name="robot-heartbeat")
        self._heartbeat_thread.start()


__all__ = ["SocketTransport"]
