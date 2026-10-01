"""Tests for `SocketConnection`'s event handlers - no real socket is opened."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from zsynctech_studio_sdk.connection import SocketConnection
from zsynctech_studio_sdk.exceptions import AckTimeoutError, NotConnectedError, ServerRejectedError
from zsynctech_studio_sdk.models import RobotClientConfig
from zsynctech_studio_sdk.models.robot import RobotConnection

CONFIG = RobotClientConfig(api_key="abc123", backend_url="http://localhost:5000")


def _connection_info() -> RobotConnection:
    return RobotConnection.model_validate(
        {
            "id": "robot-1",
            "name": "Robô teste",
            "availability": "ACTIVE",
            "status": "ONLINE",
            "maxConcurrency": 1,
            "connectedInstanceCount": 1,
            "busyInstanceCount": 0,
            "instanceId": "instance-1",
            "instanceCode": "abc123",
        }
    )


def test_on_error_before_handshake_completes_sets_handshake_error() -> None:
    connection = SocketConnection(CONFIG)

    connection._on_error({"message": "API key inválida ou robô inativo"})

    assert connection._handshake_error == "API key inválida ou robô inativo"
    assert connection._connected_event.is_set()


def test_on_error_while_already_connected_does_not_touch_handshake_state() -> None:
    connection = SocketConnection(CONFIG)
    connection._connection_info = _connection_info()

    connection._on_error({"message": "API key regenerada - reconecte com a nova chave."})

    assert connection._handshake_error is None
    assert not connection._connected_event.is_set()


def test_on_disconnect_does_not_stop_wait() -> None:
    """A transient drop must NOT unblock wait() - python-socketio is expected to keep retrying
    in the background (e.g. through an API restart) until it either reconnects or gives up."""
    connection = SocketConnection(CONFIG)

    connection._on_disconnect()

    assert not connection._stopped_event.is_set()


def test_on_disconnect_final_stops_wait() -> None:
    """Only the internal '__disconnect_final' signal - a server-sent disconnect, a finite
    reconnection_attempts being exhausted, or an explicit disconnect() - should unblock wait()."""
    connection = SocketConnection(CONFIG)

    connection._on_disconnect_final()

    assert connection._stopped_event.is_set()


def test_wait_returns_once_stopped_event_is_set() -> None:
    connection = SocketConnection(CONFIG)
    thread = threading.Thread(target=connection.wait, kwargs={"poll_interval": 0.01})
    thread.start()
    time.sleep(0.05)
    assert thread.is_alive(), "wait() should still be blocked while the connection is alive"

    connection._on_disconnect_final()
    thread.join(timeout=1)

    assert not thread.is_alive(), "wait() should return once reconnection has definitively ended"


def test_call_returns_result_from_ack_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = SocketConnection(CONFIG)
    connection._sio.connected = True

    def fake_emit(event: str, data: Any, namespace: str | None = None, callback: Any = None) -> None:
        callback({"executionId": "exec-1"})

    monkeypatch.setattr(connection._sio, "emit", fake_emit)

    assert connection.call("execution:start", {}) == {"executionId": "exec-1"}
    assert connection._pending_calls == []  # cleaned up, not left dangling


def test_call_raises_not_connected_error_without_emitting(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = SocketConnection(CONFIG)
    connection._sio.connected = False
    emitted = []
    monkeypatch.setattr(connection._sio, "emit", lambda *args, **kwargs: emitted.append(args))

    with pytest.raises(NotConnectedError):
        connection.call("execution:start", {})
    assert emitted == []


def test_call_raises_ack_timeout_error_when_nothing_ever_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = SocketConnection(CONFIG)
    connection._sio.connected = True
    monkeypatch.setattr(connection._sio, "emit", lambda *args, **kwargs: None)  # never acks, never errors

    with pytest.raises(AckTimeoutError):
        connection.call("execution:start", {}, timeout=0.05)
    assert connection._pending_calls == []


def test_call_raises_server_rejected_error_with_the_real_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirrors what actually happens when the gateway's handler throws: NestJS's WS exception
    filter never calls the acknowledgement back - it only ever emits a separate 'error' event
    (see StudioGateway/WsExceptionFilter) - handled here by _on_error. Before this fix, call()
    had no way to notice that and would just run out the clock into a generic AckTimeoutError,
    discarding the real reason (which _on_error only ever logged)."""
    connection = SocketConnection(CONFIG)
    connection._sio.connected = True
    connection._connection_info = _connection_info()  # "already connected" branch in _on_error

    def fake_emit(event: str, data: Any, namespace: str | None = None, callback: Any = None) -> None:
        connection._on_error({"message": "Nenhuma execução em andamento - chame execution:start primeiro"})

    monkeypatch.setattr(connection._sio, "emit", fake_emit)

    with pytest.raises(ServerRejectedError, match="Nenhuma execução em andamento"):
        connection.call("execution:finish", {}, timeout=1)
    assert connection._pending_calls == []


def test_on_error_wakes_every_call_currently_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    """There's no per-call correlation id on the wire, so a server-level 'error' (e.g. the api
    key was just regenerated) wakes up ALL pending calls, not just one - see _on_error."""
    connection = SocketConnection(CONFIG)
    connection._sio.connected = True
    connection._connection_info = _connection_info()
    monkeypatch.setattr(connection._sio, "emit", lambda *args, **kwargs: None)  # neither call ever acks on its own

    results: dict[str, BaseException] = {}

    def run(label: str) -> None:
        try:
            connection.call(label, {}, timeout=2)
        except BaseException as error:  # noqa: BLE001 - captured across threads, re-asserted below
            results[label] = error

    threads = [threading.Thread(target=run, args=(label,)) for label in ("a", "b")]
    for thread in threads:
        thread.start()
    time.sleep(0.05)  # let both calls register as pending before the error fires

    connection._on_error({"message": "API key regenerada - reconecte com a nova chave."})
    for thread in threads:
        thread.join(timeout=1)

    assert set(results) == {"a", "b"}
    assert all(isinstance(error, ServerRejectedError) for error in results.values())


def test_is_stopping_reflects_stopped_event() -> None:
    connection = SocketConnection(CONFIG)

    assert not connection.is_stopping
    connection._on_disconnect_final()
    assert connection.is_stopping


def test_on_connected_restarts_heartbeat_and_unblocks_connected_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """_on_connected must (re)start the heartbeat loop every time it fires - including after an
    automatic reconnection - not just on the very first connect()."""
    connection = SocketConnection(CONFIG)
    started_tasks = []
    monkeypatch.setattr(connection._sio, "start_background_task", lambda target: started_tasks.append(target))

    connection._on_connected(_connection_info().model_dump(by_alias=True))
    connection._on_connected(_connection_info().model_dump(by_alias=True))

    assert started_tasks == [connection._heartbeat_loop, connection._heartbeat_loop]
    assert connection._connected_event.is_set()
