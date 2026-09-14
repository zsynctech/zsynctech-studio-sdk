from collections.abc import Callable
from typing import Any

import pytest
import socketio
from pytest_mock import MockerFixture

from zsynctech_studio_sdk.exceptions import (
    AuthenticationError,
    ConcurrencyLimitError,
    ExecutionError,
    SdkError,
)
from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.transport.socket_transport import SocketTransport

_CONNECT_PAYLOAD = {
    "id": "r1",
    "name": "Robo",
    "maxConcurrency": 1,
    "instanceId": "i1",
    "instanceCode": "R-1",
}


def _config() -> RobotClientConfig:
    return RobotClientConfig(api_key="key", base_url="https://studio.example.com")


def _make_transport(
    mocker: MockerFixture, on_start: Callable[[], None] | None = None
) -> tuple[SocketTransport, Any]:
    mock_client_class = mocker.patch("zsynctech_studio_sdk.transport.socket_transport.socketio.Client")
    mock_sio = mock_client_class.return_value
    mock_sio.connected = True
    transport = SocketTransport(_config(), on_start=on_start)
    return transport, mock_sio


def test_connect_returns_the_connect_result_on_success(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connect.side_effect = lambda *a, **k: transport._on_connected(_CONNECT_PAYLOAD)

    result = transport.connect(timeout=1.0)

    assert result.instance_id == "i1"
    transport.disconnect()


def test_connect_raises_concurrency_limit_error(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connect.side_effect = lambda *a, **k: transport._on_error(
        {"message": "Este robô já atingiu o número máximo de instâncias."}
    )

    with pytest.raises(ConcurrencyLimitError):
        transport.connect(timeout=1.0)


def test_connect_raises_authentication_error(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connect.side_effect = lambda *a, **k: transport._on_error({"message": "API key inválida"})

    with pytest.raises(AuthenticationError):
        transport.connect(timeout=1.0)


def test_connect_times_out_when_the_platform_never_replies(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    # connect() intentionally does nothing here - neither `connected` nor `error` ever fires.

    with pytest.raises(SdkError):
        transport.connect(timeout=0.05)
    mock_sio.disconnect.assert_called_once()


def test_disconnect_stops_the_heartbeat_and_closes_the_socket(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connect.side_effect = lambda *a, **k: transport._on_connected(_CONNECT_PAYLOAD)
    transport.connect(timeout=1.0)

    transport.disconnect()

    mock_sio.disconnect.assert_called_once()


def test_call_raises_execution_error_with_the_exception_events_message(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)

    def _raise_after_exception_event(*_args: Any, **_kwargs: Any) -> None:
        # Mirrors real timing: NestJS emits `exception` on the socket, then the failed call's
        # ack never arrives and the underlying client eventually times out - see
        # SocketTransport.call's docstring.
        transport._on_exception({"message": "executionId obrigatório"})
        raise socketio.exceptions.TimeoutError()

    mock_sio.call.side_effect = _raise_after_exception_event

    with pytest.raises(ExecutionError, match="executionId obrigatório"):
        transport.call("execution:finish", {})


def test_call_raises_a_generic_execution_error_on_bare_timeout(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.call.side_effect = socketio.exceptions.TimeoutError()

    with pytest.raises(ExecutionError, match="Timed out"):
        transport.call("execution:finish", {})


def test_on_start_callback_is_invoked_on_automation_start(mocker: MockerFixture) -> None:
    received: list[bool] = []
    transport, _mock_sio = _make_transport(mocker, on_start=lambda: received.append(True))

    transport._on_automation_start({"requestedAt": "now"})

    assert received == [True]


def test_wait_returns_immediately_once_already_disconnected(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connected = False
    sleep = mocker.patch("zsynctech_studio_sdk.transport.socket_transport.time.sleep")

    transport.wait()

    sleep.assert_not_called()


def test_wait_polls_until_the_connection_drops(mocker: MockerFixture) -> None:
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connected = True

    def _disconnect_after_first_sleep(_seconds: float) -> None:
        mock_sio.connected = False

    mocker.patch(
        "zsynctech_studio_sdk.transport.socket_transport.time.sleep",
        side_effect=_disconnect_after_first_sleep,
    )

    transport.wait()  # would hang forever if it didn't stop polling once disconnected

    assert mock_sio.connected is False


def test_wait_swallows_keyboard_interrupt_instead_of_hanging_on_join(mocker: MockerFixture) -> None:
    # Regression test: SocketTransport.wait() used to delegate to the underlying client's own
    # `wait()`, which blocks on a plain `Thread.join()` - known to swallow Ctrl+C on some
    # platforms (Windows in particular). Polling with time.sleep() instead must let
    # KeyboardInterrupt actually stop it.
    transport, mock_sio = _make_transport(mocker)
    mock_sio.connected = True
    mocker.patch(
        "zsynctech_studio_sdk.transport.socket_transport.time.sleep",
        side_effect=KeyboardInterrupt(),
    )

    transport.wait()  # must not raise
