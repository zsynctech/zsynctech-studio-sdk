from __future__ import annotations

import httpx
import pytest
import respx

from tests.factories import (
    API_BASE_URL,
    API_TOKEN,
    BASE_URL,
    EXECUTION_ID,
    make_execution,
    make_task,
)
from zsyncstudio.exceptions import TaskSkipped, TaskWarning
from zsyncstudio.sync_api import Client, ExecutionStatus


@pytest.fixture
def client() -> Client:
    return Client(BASE_URL, API_TOKEN)


def _mock_complete(respx_mock: respx.MockRouter, *, task_status: str = "SUCCESS") -> respx.Route:
    return respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/complete").mock(
        return_value=httpx.Response(201, json=make_task(status=task_status))
    )


@pytest.mark.respx(assert_all_called=False)
def test_start_claims_the_execution(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/claim").mock(
        return_value=httpx.Response(200, json=make_execution(status="RUNNING"))
    )

    run = client.run_execution(EXECUTION_ID)
    execution = run.start()

    assert execution.status.value == "RUNNING"
    assert route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
def test_task_finish_reports_success(respx_mock: respx.MockRouter, client: Client) -> None:
    complete_route = _mock_complete(respx_mock)

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    task.start()
    task.finish()

    assert '"status":"SUCCESS"' in complete_route.calls.last.request.content.decode()


@pytest.mark.respx(assert_all_called=False)
def test_task_finish_without_start_still_reports(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    complete_route = _mock_complete(respx_mock)

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    task.finish()

    assert '"status":"SUCCESS"' in complete_route.calls.last.request.content.decode()


@pytest.mark.respx(assert_all_called=False)
def test_task_error_increments_had_errors(respx_mock: respx.MockRouter, client: Client) -> None:
    _mock_complete(respx_mock, task_status="ERROR")

    run = client.run_execution(EXECUTION_ID)
    assert run.had_errors is False

    task = run.task("invoice-001")
    task.start()
    try:
        raise RuntimeError("falha ao processar")
    except Exception as exc:
        task.error(str(exc))

    assert run.had_errors is True


@pytest.mark.respx(assert_all_called=False)
def test_task_error_reports_observation(respx_mock: respx.MockRouter, client: Client) -> None:
    complete_route = _mock_complete(respx_mock, task_status="ERROR")

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    try:
        raise RuntimeError("falha ao processar")
    except Exception as exc:
        task.error(str(exc))

    sent_body = complete_route.calls.last.request.content.decode()
    assert '"status":"ERROR"' in sent_body
    assert "falha ao processar" in sent_body


@pytest.mark.respx(assert_all_called=False)
def test_task_warning_reports_warning(respx_mock: respx.MockRouter, client: Client) -> None:
    complete_route = _mock_complete(respx_mock, task_status="WARNING")

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    try:
        raise TaskWarning("boleto vencido")
    except TaskWarning as warn:
        task.warning(str(warn))

    assert run.had_errors is False
    sent_body = complete_route.calls.last.request.content.decode()
    assert '"status":"WARNING"' in sent_body
    assert "boleto vencido" in sent_body


@pytest.mark.respx(assert_all_called=False)
def test_task_skipped_reports_skipped(respx_mock: respx.MockRouter, client: Client) -> None:
    complete_route = _mock_complete(respx_mock, task_status="SKIPPED")

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    try:
        raise TaskSkipped("já processada")
    except TaskSkipped as skip:
        task.skip(str(skip))

    assert '"status":"SKIPPED"' in complete_route.calls.last.request.content.decode()


@pytest.mark.respx(assert_all_called=False)
def test_run_execution_finish(respx_mock: respx.MockRouter, client: Client) -> None:
    finish_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(200, json=make_execution(status="COMPLETED"))
    )

    run = client.run_execution(EXECUTION_ID)
    run.finish("tudo certo")

    assert finish_route.calls.call_count == 1
    sent_body = finish_route.calls.last.request.content.decode()
    assert '"status":"COMPLETED"' in sent_body
    assert "tudo certo" in sent_body


@pytest.mark.respx(assert_all_called=False)
def test_run_execution_error(respx_mock: respx.MockRouter, client: Client) -> None:
    finish_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(200, json=make_execution(status="FAILED"))
    )

    run = client.run_execution(EXECUTION_ID)
    run.error("alguns itens falharam")

    sent_body = finish_route.calls.last.request.content.decode()
    assert '"status":"FAILED"' in sent_body
    assert "alguns itens falharam" in sent_body


@pytest.mark.respx(assert_all_called=False)
def test_run_execution_cancel(respx_mock: respx.MockRouter, client: Client) -> None:
    cancel_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/cancel").mock(
        return_value=httpx.Response(200, json=make_execution(status="CANCELLED"))
    )

    run = client.run_execution(EXECUTION_ID)
    run.cancel()

    assert cancel_route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
def test_run_execution_update_observation_does_not_finish(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    observation_route = respx_mock.patch(
        f"{API_BASE_URL}/executions/{EXECUTION_ID}/observation"
    ).mock(return_value=httpx.Response(200, json=make_execution(observation="lote 3 de 10")))
    finish_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(200, json=make_execution(status="COMPLETED"))
    )

    run = client.run_execution(EXECUTION_ID)
    execution = run.update_observation("lote 3 de 10")

    assert execution.observation == "lote 3 de 10"
    assert execution.status is ExecutionStatus.RUNNING
    assert observation_route.calls.call_count == 1
    assert finish_route.calls.call_count == 0
