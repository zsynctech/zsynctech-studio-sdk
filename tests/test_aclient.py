from __future__ import annotations

import httpx
import pytest
import respx

from tests.factories import (
    API_BASE_URL,
    API_TOKEN,
    BASE_URL,
    EXECUTION_ID,
    INSTANCE_ID,
    make_error_body,
    make_execution,
    make_page,
    make_task,
)
from zsyncstudio.async_api import Client, ExecutionRun, ExecutionStatus, TaskStatus
from zsyncstudio.exceptions import AuthenticationError, ConflictError
from zsyncstudio.exceptions import ConnectionError as ZSyncConnectionError
from zsyncstudio.models import Page, TaskCompletion


@pytest.fixture
def client() -> Client:
    return Client(BASE_URL, API_TOKEN)


@pytest.mark.respx(assert_all_called=False)
async def test_sends_api_token_header(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(200, json=make_execution())
    )

    await client.get_execution(EXECUTION_ID)

    assert route.calls.last.request.headers["X-API-Token"] == API_TOKEN


@pytest.mark.respx(assert_all_called=False)
async def test_client_accepts_custom_api_version(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE_URL}/api/v2/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(200, json=make_execution())
    )

    await Client(BASE_URL, API_TOKEN, api_version="v2").get_execution(EXECUTION_ID)

    assert route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
async def test_get_pending_execution_returns_none_when_no_work(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        return_value=httpx.Response(200, json=None)
    )

    assert await client.get_pending_execution() is None


@pytest.mark.respx(assert_all_called=False)
async def test_poll_pending_executions_blocks_until_execution_available(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.Response(200, json=None),
            httpx.Response(200, json=None),
            httpx.Response(200, json=make_execution(status="PENDING")),
        ]
    )

    execution = await client.poll_pending_executions(timeout=1, retry_delay=0)

    assert isinstance(execution, ExecutionRun)
    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 3


@pytest.mark.respx(assert_all_called=False)
async def test_list_executions_returns_typed_page(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions").mock(
        return_value=httpx.Response(200, json=make_page(make_execution()))
    )

    page = await client.list_executions()

    assert isinstance(page, Page)
    assert page.data[0].id == EXECUTION_ID


@pytest.mark.respx(assert_all_called=False)
async def test_finish_execution_maps_conflict_to_conflict_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(
            409, json=make_error_body(409, "Esta execução já foi encerrada")
        )
    )

    with pytest.raises(ConflictError):
        await client.finish_execution(EXECUTION_ID)


async def test_context_manager_closes_owned_http_client() -> None:
    client = Client(BASE_URL, API_TOKEN)

    async with client:
        pass

    assert client._http.is_closed


async def test_context_manager_does_not_close_injected_http_client() -> None:
    http_client = httpx.AsyncClient()
    client = Client(BASE_URL, API_TOKEN, http_client=http_client)

    async with client:
        pass

    assert not http_client.is_closed
    await http_client.aclose()


@pytest.mark.respx(assert_all_called=False)
async def test_start_and_schedule_execution_return_execution_run(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions").mock(
        return_value=httpx.Response(201, json=make_execution(status="RUNNING"))
    )
    respx_mock.post(f"{API_BASE_URL}/executions/schedule").mock(
        return_value=httpx.Response(201, json=make_execution(status="PENDING"))
    )

    started = await client.start_execution()
    scheduled = await client.schedule_execution()

    assert isinstance(started, ExecutionRun)
    assert isinstance(scheduled, ExecutionRun)
    assert started.id == EXECUTION_ID
    assert scheduled.id == EXECUTION_ID


@pytest.mark.respx(assert_all_called=False)
async def test_claim_and_cancel_execution(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/claim").mock(
        return_value=httpx.Response(200, json=make_execution(status="RUNNING"))
    )
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/cancel").mock(
        return_value=httpx.Response(200, json=make_execution(status="CANCELLED"))
    )

    claimed = await client.claim_execution(EXECUTION_ID)
    cancelled = await client.cancel_execution(EXECUTION_ID)

    assert claimed.status is ExecutionStatus.RUNNING
    assert cancelled.status is ExecutionStatus.CANCELLED


@pytest.mark.respx(assert_all_called=False)
async def test_update_observation_sends_patch(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.patch(f"{API_BASE_URL}/executions/{EXECUTION_ID}/observation").mock(
        return_value=httpx.Response(200, json=make_execution(observation="lote 3 de 10"))
    )

    execution = await client.update_observation(EXECUTION_ID, "lote 3 de 10")

    assert execution.observation == "lote 3 de 10"
    assert route.calls.last.request.content == b'{"observation":"lote 3 de 10"}'


async def test_finish_execution_rejects_non_terminal_status(client: Client) -> None:
    with pytest.raises(ValueError, match="status terminal"):
        await client.finish_execution(EXECUTION_ID, status=ExecutionStatus.RUNNING)


@pytest.mark.respx(assert_all_called=False)
async def test_complete_task(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/complete").mock(
        return_value=httpx.Response(201, json=make_task(status="SUCCESS"))
    )

    completed = await client.complete_task(EXECUTION_ID, "invoice-001", TaskStatus.SUCCESS)

    assert completed.status is TaskStatus.SUCCESS


@pytest.mark.respx(assert_all_called=False)
async def test_batch_complete_tasks(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/batch").mock(
        return_value=httpx.Response(201, json=[make_task()])
    )

    result = await client.batch_complete_tasks(
        EXECUTION_ID, [TaskCompletion(reference="a", status=TaskStatus.SUCCESS)]
    )

    assert len(result) == 1


@pytest.mark.respx(assert_all_called=False)
async def test_get_task_summary_and_list_tasks(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 1,
                "success": 1,
                "error": 0,
                "warning": 0,
                "skipped": 0,
                "avgDurationMs": 10.0,
                "totalDurationMs": 10.0,
                "fastestTask": None,
                "slowestTask": None,
            },
        )
    )
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks").mock(
        return_value=httpx.Response(200, json=make_page(make_task()))
    )

    summary = await client.get_task_summary(EXECUTION_ID)
    page = await client.list_tasks(EXECUTION_ID)

    assert summary.total == 1
    assert page.data[0].reference == "invoice-001"


@pytest.mark.respx(assert_all_called=False)
async def test_transport_error_is_wrapped(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        side_effect=httpx.ConnectError("boom")
    )

    with pytest.raises(ZSyncConnectionError):
        await client.get_execution(EXECUTION_ID)


@pytest.mark.respx(assert_all_called=False)
async def test_poll_pending_executions_retries_after_connection_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, json=make_execution()),
        ]
    )

    execution = await client.poll_pending_executions(timeout=1, retry_delay=0)

    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 2


@pytest.mark.respx(assert_all_called=False)
async def test_poll_pending_executions_retries_after_server_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.Response(503, json=make_error_body(503, "Serviço indisponível")),
            httpx.Response(200, json=make_execution()),
        ]
    )

    execution = await client.poll_pending_executions(timeout=1, retry_delay=0)

    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 2


@pytest.mark.respx(assert_all_called=False)
async def test_poll_pending_executions_does_not_retry_non_server_api_errors(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        return_value=httpx.Response(401, json=make_error_body(401, "Token inválido"))
    )

    with pytest.raises(AuthenticationError):
        await client.poll_pending_executions(timeout=1, retry_delay=0)

    assert route.calls.call_count == 1

    assert route.calls.call_count == 1
