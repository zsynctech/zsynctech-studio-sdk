"""Tests for `SocketConnection`'s event handlers - no real socket is opened."""

from __future__ import annotations

import threading
import time

import pytest

from zsynctech_studio_sdk.connection import SocketConnection
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
