"""Low-level Socket.IO link to the `/robot` gateway.

`SocketConnection` owns the handshake, reconnection, the periodic app-level heartbeat, and
the raw `call`/`emit` primitives. It knows nothing about executions or queues - see
`execution.py` and `queue.py` for the layers built on top of it. Keeping this
separation means `ExecutionManager`/`QueueConsumer` depend only on this class's small public
surface (SRP/DIP), not on `python-socketio` directly.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

import socketio

from .exceptions import AckTimeoutError, NotConnectedError, RobotConnectionError
from .loggers import logger
from .models.config import RobotClientConfig
from .models.enums import RobotInstanceStatus
from .models.robot import RobotConnection, RobotInfo
from .protocol import NAMESPACE, ClientEvent, ServerEvent

AutomationStartHandler = Callable[[], None]


class SocketConnection:
    """Wraps a `socketio.Client` connected to `NAMESPACE`."""

    def __init__(self, config: RobotClientConfig) -> None:
        self._config = config
        self._sio = socketio.Client(
            reconnection=config.reconnection,
            reconnection_attempts=config.reconnection_attempts,
            reconnection_delay=config.reconnection_delay,
            logger=False,
            engineio_logger=False,
        )
        self._connection_info: RobotConnection | None = None
        self._connected_event = threading.Event()
        self._stopped_event = threading.Event()
        self._handshake_error: str | None = None
        self._automation_start_handlers: list[AutomationStartHandler] = []
        self._register_handlers()

    def _register_handlers(self) -> None:
        self._sio.on(ServerEvent.CONNECTED, self._on_connected, namespace=NAMESPACE)
        self._sio.on(ServerEvent.ERROR, self._on_error, namespace=NAMESPACE)
        self._sio.on(ServerEvent.EXCEPTION, self._on_exception, namespace=NAMESPACE)
        self._sio.on(ServerEvent.AUTOMATION_START, self._on_automation_start, namespace=NAMESPACE)
        self._sio.on(ServerEvent.DISCONNECT, self._on_disconnect, namespace=NAMESPACE)
        self._sio.on(ServerEvent.CONNECT_ERROR, self._on_connect_error, namespace=NAMESPACE)
        # Internal python-socketio event, fired once reconnection has definitively ended: the
        # server sent an explicit disconnect (bad api key, concurrency limit, kicked), disconnect()
        # was called, or (with a finite reconnection_attempts) every retry failed. Unlike the public
        # `disconnect` event above, it never fires for a transient drop the client is about to
        # retry - see wait() below, which relies on that distinction to stay blocked through an
        # API restart instead of giving up on the first dropped socket.
        self._sio.on("__disconnect_final", self._on_disconnect_final, namespace=NAMESPACE)

    # -- server -> robot event handlers -----------------------------------------------------

    def _on_connected(self, payload: dict[str, Any]) -> None:
        self._connection_info = RobotConnection.model_validate(payload)
        logger.success(
            "Conectado à plataforma: robô '{}' (instância {})",
            self._connection_info.name,
            self._connection_info.instance_code,
        )
        # Started here (once per successful handshake) rather than only from connect(), so an
        # automatic reconnection after an API restart gets a fresh heartbeat loop too - the one
        # from the previous connection already exited when its socket dropped.
        self._sio.start_background_task(self._heartbeat_loop)
        self._connected_event.set()

    def _on_error(self, payload: dict[str, Any] | None) -> None:
        message = (payload or {}).get("message", "Erro desconhecido retornado pelo servidor")
        if self._connection_info is None:
            # Handshake still in flight - connect() is blocked waiting on _connected_event.
            self._handshake_error = message
            logger.error("Servidor rejeitou a conexão: {}", message)
            self._connected_event.set()
        else:
            # Already connected - the platform is reporting a problem with the live session
            # (e.g. this robot's api key was just regenerated). A disconnect from the server
            # normally follows right after, logged separately by _on_disconnect.
            logger.warning("Erro reportado pela plataforma: {}", message)

    def _on_exception(self, payload: Any) -> None:
        logger.error("Exceção recebida do servidor: {}", payload)

    def _on_automation_start(self, payload: dict[str, Any] | None = None) -> None:
        logger.info("Plataforma solicitou início da automação")
        for handler in list(self._automation_start_handlers):
            self._sio.start_background_task(self._run_handler_safely, handler)

    def _run_handler_safely(self, handler: AutomationStartHandler) -> None:
        try:
            handler()
        except Exception:
            logger.exception("Handler de automation:start levantou uma exceção não tratada")

    def _on_disconnect(self, *_args: Any) -> None:
        logger.warning("Desconectado da plataforma - tentando reconectar automaticamente...")
        self._connection_info = None

    def _on_connect_error(self, data: Any = None) -> None:
        logger.error("Falha ao conectar: {}", data)

    def _on_disconnect_final(self, *_args: Any) -> None:
        logger.error("Conexão encerrada definitivamente (sem novas tentativas de reconexão)")
        self._stopped_event.set()

    # -- lifecycle ----------------------------------------------------------------------------

    def connect(self) -> RobotConnection:
        """Perform the handshake and block until the server confirms via `connected`."""
        self._handshake_error = None
        self._connected_event.clear()
        self._stopped_event.clear()
        auth = {
            "apiKey": self._config.api_key,
            "hostname": self._config.hostname,
            "pid": os.getpid(),
            "version": self._config.version,
            "platform": self._config.platform.value,
        }
        try:
            self._sio.connect(
                self._config.backend_url,
                auth=auth,
                namespaces=[NAMESPACE],
                wait_timeout=self._config.ack_timeout,
            )
        except socketio.exceptions.ConnectionError as exc:
            raise RobotConnectionError(str(exc)) from exc

        if not self._connected_event.wait(timeout=self._config.ack_timeout):
            self._sio.disconnect()
            raise RobotConnectionError("Servidor não confirmou a conexão a tempo (evento 'connected' ausente)")
        if self._handshake_error:
            raise RobotConnectionError(self._handshake_error)

        assert self._connection_info is not None
        return self._connection_info

    def disconnect(self) -> None:
        """Stop the connection for good: closes it if live, aborts an in-progress reconnection
        attempt otherwise. Always a final disconnect - unblocks any thread in wait()."""
        self._sio.shutdown()
        self._connection_info = None
        self._stopped_event.set()

    def wait(self, poll_interval: float = 0.5) -> None:
        """Block the calling thread until the connection is closed for good - i.e. until
        disconnect() is called, or python-socketio gives up reconnecting (server sent an explicit
        disconnect, or a finite `reconnection_attempts` was exhausted). Server-pushed events (like
        `automation:start`) keep being handled on background threads while blocked.

        A transient drop that the client is actively retrying (e.g. the API process restarting)
        does NOT unblock this - python-socketio keeps reconnecting in the background for as long
        as `reconnection` is enabled, and _on_connected restarts the heartbeat once it succeeds.

        Polls `_stopped_event` on a short interval instead of delegating to python-socketio's own
        `wait()` (a bare `Thread.join()` with no timeout) - on Windows that join is a single
        uninterruptible OS wait, so Ctrl+C never gets a chance to run until the retry loop itself
        ends.
        """
        while not self._stopped_event.is_set():
            self._sio.sleep(poll_interval)

    def _heartbeat_loop(self) -> None:
        while self.is_connected:
            self._sio.sleep(self._config.heartbeat_interval)
            if not self.is_connected:
                break
            try:
                response = self.call(ClientEvent.HEARTBEAT, {})
                robot = RobotInfo.model_validate(response)
                logger.debug("Heartbeat OK - status={}", robot.status.value)
            except AckTimeoutError:
                logger.warning("Heartbeat sem resposta da plataforma dentro do tempo limite")

    # -- low-level primitives, reused by ExecutionManager/QueueConsumer -----------------------

    def call(self, event: str, data: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Emit `event` and block for the server's acknowledgement (Socket.IO's `emitWithAck`)."""
        if not self.is_connected:
            raise NotConnectedError(f"Não é possível emitir '{event}': socket desconectado")
        try:
            return self._sio.call(event, data, namespace=NAMESPACE, timeout=timeout or self._config.ack_timeout)
        except socketio.exceptions.TimeoutError as exc:
            raise AckTimeoutError(f"Timeout aguardando resposta de '{event}'") from exc

    def emit(self, event: str, data: dict[str, Any]) -> None:
        """Fire-and-forget emit, for events the gateway doesn't acknowledge."""
        if not self.is_connected:
            raise NotConnectedError(f"Não é possível emitir '{event}': socket desconectado")
        self._sio.emit(event, data, namespace=NAMESPACE)

    def set_status(self, status: RobotInstanceStatus) -> RobotInfo:
        response = self.call(ClientEvent.STATUS, {"status": status.value})
        return RobotInfo.model_validate(response)

    def on_automation_start(self, handler: AutomationStartHandler) -> None:
        self._automation_start_handlers.append(handler)

    # -- introspection ------------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return bool(self._sio.connected)

    @property
    def connection_info(self) -> RobotConnection | None:
        return self._connection_info
