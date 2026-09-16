"""Tests for `SocketConnection`'s event handlers - no real socket is opened."""

from __future__ import annotations

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
