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
    SECRET_ID,
    make_error_body,
    make_execution,
    make_page,
    make_reveal_secret,
    make_secret_meta,
    make_task,
)
from zsyncstudio.async_api import (
    Client,
    ExecutionRun,
    ExecutionStatus,
    SecretNotActiveError,
    SecretStatus,
    SecretType,
    TaskStatus,
    ValidationError,
)
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


@pytest.mark.respx(assert_all_called=False)
async def test_set_total_tasks_sends_patch(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.patch(f"{API_BASE_URL}/executions/{EXECUTION_ID}/total-tasks").mock(
        return_value=httpx.Response(200, json=make_execution(totalTasks=1000))
    )

    execution = await client.set_total_tasks(EXECUTION_ID, 1000)

    assert execution.total_tasks == 1000
    assert route.calls.last.request.content == b'{"totalTasks":1000}'


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


# ──────────────── Secrets ────────────────


@pytest.mark.respx(assert_all_called=False)
async def test_get_secret_reveals_current_version(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret())
    )

    secret = await client.get_secret(SECRET_ID)

    assert secret.secret_id == SECRET_ID
    assert secret.version_number == 1
    assert secret.type is SecretType.TEXT
    assert secret.value == "s3cr3t"
    assert route.calls.last.request.url.params.get("version") is None


@pytest.mark.respx(assert_all_called=False)
async def test_get_secret_requests_specific_version(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret(versionNumber=3))
    )

    secret = await client.get_secret(SECRET_ID, version=3)

    assert secret.version_number == 3
    assert route.calls.last.request.url.params["version"] == "3"


@pytest.mark.respx(assert_all_called=False)
async def test_get_secret_raises_secret_not_active_error_when_expired(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(
            400,
            json={
                **make_error_body(400, "Credencial expirada", path=f"/secrets/{SECRET_ID}/reveal"),
                "secretStatus": "EXPIRED",
                "secretStatusReason": None,
            },
        )
    )

    with pytest.raises(SecretNotActiveError) as exc_info:
        await client.get_secret(SECRET_ID)

    error = exc_info.value
    assert error.status is SecretStatus.EXPIRED
    assert error.is_expired
    assert not error.is_blocked
    assert error.status_reason is None
    assert isinstance(error, ValidationError)


@pytest.mark.respx(assert_all_called=False)
async def test_rotate_secret_sends_post_with_value(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/secrets/{SECRET_ID}/versions").mock(
        return_value=httpx.Response(200, json=make_secret_meta(currentVersion=2))
    )

    meta = await client.rotate_secret(SECRET_ID, "new-value")

    assert meta.current_version == 2
    assert route.calls.last.request.content == b'{"value":"new-value"}'


@pytest.mark.respx(assert_all_called=False)
async def test_secret_rotate_delegates_to_client(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret())
    )
    rotate_route = respx_mock.post(f"{API_BASE_URL}/secrets/{SECRET_ID}/versions").mock(
        return_value=httpx.Response(200, json=make_secret_meta(currentVersion=2))
    )

    secret = await client.get_secret(SECRET_ID)
    meta = await secret.rotate("rotated-value")

    assert meta.current_version == 2
    assert rotate_route.calls.last.request.content == b'{"value":"rotated-value"}'


@pytest.mark.respx(assert_all_called=False)
async def test_get_secret_status_reports_blocked(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}").mock(
        return_value=httpx.Response(
            200, json=make_secret_meta(status="BLOCKED", statusReason="login rejeitado")
        )
    )

    meta = await client.get_secret_status(SECRET_ID)

    assert meta.status is SecretStatus.BLOCKED
    assert meta.is_blocked
    assert not meta.is_active


@pytest.mark.respx(assert_all_called=False)
async def test_block_secret_sends_patch_with_reason(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.patch(f"{API_BASE_URL}/secrets/{SECRET_ID}/status").mock(
        return_value=httpx.Response(200, json=make_secret_meta(status="BLOCKED"))
    )

    meta = await client.block_secret(SECRET_ID, "senha rejeitada pelo sistema alvo")

    assert meta.status is SecretStatus.BLOCKED
    assert route.calls.last.request.content == (
        b'{"status":"BLOCKED","reason":"senha rejeitada pelo sistema alvo"}'
    )


@pytest.mark.respx(assert_all_called=False)
async def test_expire_secret_sends_patch_with_reason(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.patch(f"{API_BASE_URL}/secrets/{SECRET_ID}/status").mock(
        return_value=httpx.Response(200, json=make_secret_meta(status="EXPIRED"))
    )

    meta = await client.expire_secret(SECRET_ID, "senha não é mais válida")

    assert meta.status is SecretStatus.EXPIRED


@pytest.mark.respx(assert_all_called=False)
async def test_secret_block_and_expire_delegate_to_client(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret())
    )
    block_route = respx_mock.patch(f"{API_BASE_URL}/secrets/{SECRET_ID}/status").mock(
        return_value=httpx.Response(200, json=make_secret_meta(status="BLOCKED"))
    )

    secret = await client.get_secret(SECRET_ID)
    meta = await secret.block("motivo")

    assert meta.status is SecretStatus.BLOCKED
    assert block_route.calls.last.request.content == b'{"status":"BLOCKED","reason":"motivo"}'


@pytest.mark.respx(assert_all_called=False)
async def test_set_secret_status_conflict_raises_conflict_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.patch(f"{API_BASE_URL}/secrets/{SECRET_ID}/status").mock(
        return_value=httpx.Response(409, json={"message": "já está em um estado restrito"})
    )

    with pytest.raises(ConflictError):
        await client.block_secret(SECRET_ID, "motivo")
