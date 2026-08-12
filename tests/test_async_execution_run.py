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
from zsyncstudio.async_api import Client, ExecutionStatus
from zsyncstudio.exceptions import TaskSkipped, TaskWarning


@pytest.fixture
def client() -> Client:
    return Client(BASE_URL, API_TOKEN)


def _mock_complete(respx_mock: respx.MockRouter, *, task_status: str = "SUCCESS") -> respx.Route:
    return respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/complete").mock(
        return_value=httpx.Response(201, json=make_task(status=task_status))
    )


@pytest.mark.respx(assert_all_called=False)
async def test_start_claims_the_execution(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/claim").mock(
        return_value=httpx.Response(200, json=make_execution(status="RUNNING"))
    )

    run = client.run_execution(EXECUTION_ID)
    execution = await run.start()

    assert execution.status.value == "RUNNING"
    assert route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_task_finish_reports_success(respx_mock: respx.MockRouter, client: Client) -> None:
    complete_route = _mock_complete(respx_mock)

    run = client.run_execution(EXECUTION_ID)
    task = run.task("invoice-001")
    task.start()
    await task.finish()

    assert '"status":"SUCCESS"' in complete_route.calls.last.request.content.decode()


@pytest.mark.respx(assert_all_called=False)
async def test_task_error_increments_had_errors(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    _mock_complete(respx_mock, task_status="ERROR")

    run = client.run_execution(EXECUTION_ID)
    assert run.had_errors is False

    task = run.task("invoice-001")
    try:
        raise RuntimeError("falha")
    except Exception as exc:
        await task.error(str(exc))

    assert run.had_errors is True


@pytest.mark.respx(assert_all_called=False)
async def test_task_warning_and_skipped(respx_mock: respx.MockRouter, client: Client) -> None:
    warning_route = respx_mock.post(
        f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/complete"
    ).mock(
        side_effect=[
            httpx.Response(201, json=make_task(status="WARNING")),
            httpx.Response(201, json=make_task(status="SKIPPED")),
        ]
    )

    run = client.run_execution(EXECUTION_ID)

    task_a = run.task("a")
    try:
        raise TaskWarning("boleto vencido")
    except TaskWarning as warn:
        await task_a.warning(str(warn))

    task_b = run.task("b")
    try:
        raise TaskSkipped("já processada")
    except TaskSkipped as skip:
        await task_b.skip(str(skip))

    assert run.had_errors is False
    bodies = [call.request.content.decode() for call in warning_route.calls]
    assert '"status":"WARNING"' in bodies[0]
    assert '"status":"SKIPPED"' in bodies[1]


@pytest.mark.respx(assert_all_called=False)
async def test_run_execution_finish_error_and_cancel(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    finish_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(200, json=make_execution(status="COMPLETED"))
    )

    run = client.run_execution(EXECUTION_ID)
    await run.finish("tudo certo")

    assert finish_route.calls.call_count == 1
    assert '"status":"COMPLETED"' in finish_route.calls.last.request.content.decode()

    run_with_error = client.run_execution(EXECUTION_ID)
    await run_with_error.error("alguns itens falharam")

    sent_body = finish_route.calls.last.request.content.decode()
    assert '"status":"FAILED"' in sent_body
    assert "alguns itens falharam" in sent_body

    cancel_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/cancel").mock(
        return_value=httpx.Response(200, json=make_execution(status="CANCELLED"))
    )

    run2 = client.run_execution(EXECUTION_ID)
    await run2.cancel()

    assert cancel_route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_run_execution_update_observation_does_not_finish(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    observation_route = respx_mock.patch(
        f"{API_BASE_URL}/executions/{EXECUTION_ID}/observation"
    ).mock(return_value=httpx.Response(200, json=make_execution(observation="lote 3 de 10")))
    finish_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(200, json=make_execution(status="COMPLETED"))
    )

    run = client.run_execution(EXECUTION_ID)
    execution = await run.update_observation("lote 3 de 10")

    assert execution.observation == "lote 3 de 10"
    assert execution.status is ExecutionStatus.RUNNING
    assert observation_route.calls.call_count == 1
    assert finish_route.calls.call_count == 0
