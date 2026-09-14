from typing import Any

import pytest
from pytest_mock import MockerFixture

from zsynctech_studio_sdk.client import RobotClient
from zsynctech_studio_sdk.exceptions import ExecutionError, NotConnectedError
from zsynctech_studio_sdk.models.connection import ConnectResult
from zsynctech_studio_sdk.models.enums import ExecutionFinishStatus, RobotInstanceStatus, TaskStatus
from zsynctech_studio_sdk.models.execution import Task
from zsynctech_studio_sdk.transport.socket_transport import SocketTransport

_CONNECT_PAYLOAD = {
    "id": "r1",
    "name": "Robo",
    "maxConcurrency": 1,
    "instanceId": "i1",
    "instanceCode": "R-1",
}


def _client_with_fake_transport(mocker: MockerFixture) -> tuple[RobotClient, Any]:
    fake_transport = mocker.create_autospec(SocketTransport, instance=True)
    client = RobotClient(api_key="key", base_url="https://studio.example.com", transport=fake_transport)
    return client, fake_transport


def test_execution_methods_raise_not_connected_before_connect(mocker: MockerFixture) -> None:
    client, _transport = _client_with_fake_transport(mocker)

    with pytest.raises(NotConnectedError):
        client.start_execution()


def test_connect_stores_the_result_and_exposes_instance_identity(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()

    client.connect()

    assert client.instance_id == "i1"
    assert client.instance_code == "R-1"


def test_start_execution_sends_the_expected_payload_and_remembers_the_execution_id(
    mocker: MockerFixture,
) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    fake_transport.call.return_value = {"executionId": "exec-1"}
    client.connect()

    execution_id = client.start_execution(total=10, observation="obs")

    assert execution_id == "exec-1"
    fake_transport.call.assert_called_with("execution:start", {"total": 10, "observation": "obs"})


def test_report_tasks_uses_the_current_execution_id_when_none_is_given(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    fake_transport.call.return_value = {"executionId": "exec-1"}
    client.connect()
    client.start_execution()

    client.report_tasks([Task(status=TaskStatus.SUCCESS)])

    emitted_event, emitted_payload = fake_transport.emit.call_args[0]
    assert emitted_event == "execution:task"
    assert emitted_payload["executionId"] == "exec-1"
    assert len(emitted_payload["tasks"]) == 1


def test_report_tasks_without_an_open_execution_raises(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    client.connect()

    with pytest.raises(ExecutionError):
        client.report_tasks([Task(status=TaskStatus.SUCCESS)])


def test_finish_execution_clears_the_current_execution_id(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    fake_transport.call.side_effect = [
        {"executionId": "exec-1"},
        {"executionId": "exec-1", "status": "COMPLETED"},
    ]
    client.connect()
    client.start_execution()

    client.finish_execution(ExecutionFinishStatus.COMPLETED)

    with pytest.raises(ExecutionError):
        client.report_tasks([Task(status=TaskStatus.SUCCESS)])


def test_claim_next_task_returns_the_claimed_task(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    fake_transport.call.return_value = {"taskId": "task-1", "attempts": 1}
    client.connect()

    claimed = client.claim_next_task()

    assert claimed.has_task
    assert claimed.task_id == "task-1"


def test_start_task_returns_a_handle_that_reports_through_report_tasks(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    fake_transport.call.return_value = {"executionId": "exec-1"}
    client.connect()
    client.start_execution()

    task = client.start_task(external_id="row-1")
    task.success(message="done")

    emitted_event, emitted_payload = fake_transport.emit.call_args[0]
    assert emitted_event == "execution:task"
    assert emitted_payload["tasks"][0]["status"] == "SUCCESS"
    assert emitted_payload["tasks"][0]["externalId"] == "row-1"
    assert emitted_payload["tasks"][0]["message"] == "done"


def test_start_task_raises_not_connected_before_connect(mocker: MockerFixture) -> None:
    client, _transport = _client_with_fake_transport(mocker)

    with pytest.raises(NotConnectedError):
        client.start_task()


def test_set_status_forwards_to_the_transport(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()
    client.connect()

    client.set_status(RobotInstanceStatus.BUSY)

    fake_transport.call.assert_called_with("status", {"status": "BUSY"})


def test_context_manager_connects_and_disconnects(mocker: MockerFixture) -> None:
    client, fake_transport = _client_with_fake_transport(mocker)
    fake_transport.connect.return_value = _make_connect_result()

    with client:
        fake_transport.connect.assert_called_once()

    fake_transport.disconnect.assert_called_once()


def _make_connect_result() -> ConnectResult:
    return ConnectResult.model_validate(_CONNECT_PAYLOAD)
