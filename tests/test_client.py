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
from zsyncstudio.exceptions import AuthenticationError, ConflictError, NotFoundError
from zsyncstudio.exceptions import ConnectionError as ZSyncConnectionError
from zsyncstudio.models import Page, Task, TaskCompletion
from zsyncstudio.sync_api import Client, ExecutionRun, ExecutionStatus, SecretType, TaskStatus


@pytest.fixture
def client() -> Client:
    return Client(BASE_URL, API_TOKEN)


def test_client_exposes_instance_id_parsed_from_token(client: Client) -> None:
    assert client.instance_id == INSTANCE_ID


def test_client_rejects_malformed_token() -> None:
    with pytest.raises(ValueError, match="api_token inválido"):
        Client(BASE_URL, "not-a-valid-token")


@pytest.mark.respx(assert_all_called=False)
def test_client_appends_api_v1_prefix_by_default(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(200, json=make_execution())
    )

    Client(BASE_URL, API_TOKEN).get_execution(EXECUTION_ID)

    assert route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
def test_client_accepts_custom_api_version(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE_URL}/api/v2/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(200, json=make_execution())
    )

    Client(BASE_URL, API_TOKEN, api_version="v2").get_execution(EXECUTION_ID)

    assert route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
def test_sends_api_token_header(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(200, json=make_execution())
    )

    client.get_execution(EXECUTION_ID)

    assert route.calls.last.request.headers["X-API-Token"] == API_TOKEN


@pytest.mark.respx(assert_all_called=False)
def test_get_pending_execution_returns_execution(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        return_value=httpx.Response(200, json=make_execution(status="PENDING"))
    )

    execution = client.get_pending_execution(timeout=5)

    assert execution is not None
    assert execution.status is ExecutionStatus.PENDING
    assert route.calls.last.request.url.params["timeout"] == "5"


@pytest.mark.respx(assert_all_called=False)
def test_get_pending_execution_returns_none_when_no_work(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        return_value=httpx.Response(200, json=None)
    )

    assert client.get_pending_execution() is None


@pytest.mark.respx(assert_all_called=False)
def test_poll_pending_executions_blocks_until_execution_available(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.Response(200, json=None),
            httpx.Response(200, json=None),
            httpx.Response(200, json=make_execution(status="PENDING")),
        ]
    )

    execution = client.poll_pending_executions(timeout=1, retry_delay=0)

    assert isinstance(execution, ExecutionRun)
    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 3


@pytest.mark.respx(assert_all_called=False)
def test_start_execution_posts_instance_id_and_returns_execution_run(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/executions").mock(
        return_value=httpx.Response(201, json=make_execution())
    )

    execution = client.start_execution()

    assert route.calls.last.request.content == f'{{"instanceId":"{INSTANCE_ID}"}}'.encode()
    assert isinstance(execution, ExecutionRun)
    assert execution.id == EXECUTION_ID


@pytest.mark.respx(assert_all_called=False)
def test_schedule_execution_returns_execution_run_ready_to_start(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/schedule").mock(
        return_value=httpx.Response(201, json=make_execution(status="PENDING"))
    )
    claim_route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/claim").mock(
        return_value=httpx.Response(200, json=make_execution(status="RUNNING"))
    )

    execution = client.schedule_execution()
    execution.start()

    assert isinstance(execution, ExecutionRun)
    assert execution.id == EXECUTION_ID
    assert claim_route.calls.call_count == 1


@pytest.mark.respx(assert_all_called=False)
def test_claim_execution(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/claim").mock(
        return_value=httpx.Response(200, json=make_execution(status="RUNNING"))
    )

    execution = client.claim_execution(EXECUTION_ID)

    assert execution.status is ExecutionStatus.RUNNING


@pytest.mark.respx(assert_all_called=False)
def test_cancel_execution(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/cancel").mock(
        return_value=httpx.Response(200, json=make_execution(status="CANCELLED"))
    )

    execution = client.cancel_execution(EXECUTION_ID)

    assert execution.status is ExecutionStatus.CANCELLED


@pytest.mark.respx(assert_all_called=False)
def test_update_observation_sends_patch(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.patch(f"{API_BASE_URL}/executions/{EXECUTION_ID}/observation").mock(
        return_value=httpx.Response(200, json=make_execution(observation="lote 3 de 10"))
    )

    execution = client.update_observation(EXECUTION_ID, "lote 3 de 10")

    assert execution.observation == "lote 3 de 10"
    assert execution.status is ExecutionStatus.RUNNING
    assert route.calls.last.request.content == b'{"observation":"lote 3 de 10"}'


@pytest.mark.respx(assert_all_called=False)
def test_set_total_tasks_sends_patch(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.patch(f"{API_BASE_URL}/executions/{EXECUTION_ID}/total-tasks").mock(
        return_value=httpx.Response(200, json=make_execution(totalTasks=1000))
    )

    execution = client.set_total_tasks(EXECUTION_ID, 1000)

    assert execution.total_tasks == 1000
    assert route.calls.last.request.content == b'{"totalTasks":1000}'


@pytest.mark.respx(assert_all_called=False)
def test_list_executions_returns_typed_page(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions").mock(
        return_value=httpx.Response(200, json=make_page(make_execution()))
    )

    page = client.list_executions(status=ExecutionStatus.RUNNING, page=1, page_size=20)

    assert isinstance(page, Page)
    assert page.total_items == 1
    assert page.data[0].id == EXECUTION_ID


@pytest.mark.respx(assert_all_called=False)
def test_list_executions_omits_none_filters_from_query(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions").mock(
        return_value=httpx.Response(200, json=make_page(make_execution()))
    )

    client.list_executions()

    sent_params = dict(route.calls.last.request.url.params)
    assert "status" not in sent_params
    assert "instanceId" not in sent_params
    assert sent_params["page"] == "1"


def test_finish_execution_rejects_non_terminal_status(client: Client) -> None:
    with pytest.raises(ValueError, match="status terminal"):
        client.finish_execution(EXECUTION_ID, status=ExecutionStatus.RUNNING)


@pytest.mark.respx(assert_all_called=False)
def test_finish_execution_maps_conflict_to_conflict_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/finish").mock(
        return_value=httpx.Response(
            409, json=make_error_body(409, "Esta execução já foi encerrada")
        )
    )

    with pytest.raises(ConflictError) as exc_info:
        client.finish_execution(EXECUTION_ID)

    assert exc_info.value.status_code == 409


@pytest.mark.respx(assert_all_called=False)
def test_get_execution_maps_404_to_not_found_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        return_value=httpx.Response(404, json=make_error_body(404, "Execução não encontrada"))
    )

    with pytest.raises(NotFoundError):
        client.get_execution(EXECUTION_ID)


@pytest.mark.respx(assert_all_called=False)
def test_complete_task_sends_terminal_status_payload(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/complete").mock(
        return_value=httpx.Response(201, json=make_task())
    )

    task = client.complete_task(EXECUTION_ID, "invoice-001", TaskStatus.SUCCESS)

    assert '"status":"SUCCESS"' in route.calls.last.request.content.decode()
    assert isinstance(task, Task)


@pytest.mark.respx(assert_all_called=False)
def test_batch_complete_tasks_returns_all_tasks(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    respx_mock.post(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/batch").mock(
        return_value=httpx.Response(201, json=[make_task(), make_task()])
    )
    tasks = [
        TaskCompletion(reference="a", status=TaskStatus.SUCCESS),
        TaskCompletion(reference="b", status=TaskStatus.ERROR),
    ]

    result = client.batch_complete_tasks(EXECUTION_ID, tasks)

    assert len(result) == 2


def test_batch_complete_tasks_rejects_empty_list(client: Client) -> None:
    with pytest.raises(ValueError, match="vazia"):
        client.batch_complete_tasks(EXECUTION_ID, [])


def test_batch_complete_tasks_rejects_more_than_500(client: Client) -> None:
    tasks = [TaskCompletion(reference="a", status=TaskStatus.SUCCESS) for _ in range(501)]

    with pytest.raises(ValueError, match="500"):
        client.batch_complete_tasks(EXECUTION_ID, tasks)


@pytest.mark.respx(assert_all_called=False)
def test_get_task_summary(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 3,
                "success": 2,
                "error": 1,
                "warning": 0,
                "skipped": 0,
                "avgDurationMs": 120.5,
                "totalDurationMs": 361.5,
                "fastestTask": {"reference": "a", "durationMs": 100.0},
                "slowestTask": {"reference": "b", "durationMs": 150.0},
            },
        )
    )

    summary = client.get_task_summary(EXECUTION_ID)

    assert summary.total == 3
    assert summary.fastest_task is not None
    assert summary.fastest_task.reference == "a"


@pytest.mark.respx(assert_all_called=False)
def test_list_tasks_returns_typed_page(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}/tasks").mock(
        return_value=httpx.Response(200, json=make_page(make_task()))
    )

    page = client.list_tasks(EXECUTION_ID, status=TaskStatus.SUCCESS, sort="desc")

    assert page.data[0].reference == "invoice-001"


@pytest.mark.respx(assert_all_called=False)
def test_transport_error_is_wrapped(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/executions/{EXECUTION_ID}").mock(
        side_effect=httpx.ConnectError("boom")
    )

    with pytest.raises(ZSyncConnectionError):
        client.get_execution(EXECUTION_ID)


def test_context_manager_closes_owned_http_client() -> None:
    client = Client(BASE_URL, API_TOKEN)

    with client:
        pass

    assert client._http.is_closed


def test_context_manager_does_not_close_injected_http_client() -> None:
    http_client = httpx.Client()
    client = Client(BASE_URL, API_TOKEN, http_client=http_client)

    with client:
        pass

    assert not http_client.is_closed
    http_client.close()


def test_close_is_registered_to_run_at_process_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    registered: list[object] = []
    monkeypatch.setattr("atexit.register", registered.append)

    client = Client(BASE_URL, API_TOKEN)

    assert registered == [client.close]


def test_manual_close_unregisters_the_atexit_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    unregistered: list[object] = []
    monkeypatch.setattr("atexit.unregister", unregistered.append)

    client = Client(BASE_URL, API_TOKEN)
    client.close()

    assert unregistered == [client.close]
    assert client._http.is_closed


@pytest.mark.respx(assert_all_called=False)
def test_poll_pending_executions_retries_after_connection_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(200, json=make_execution()),
        ]
    )

    execution = client.poll_pending_executions(timeout=1, retry_delay=0)

    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 2


@pytest.mark.respx(assert_all_called=False)
def test_poll_pending_executions_retries_after_server_error(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        side_effect=[
            httpx.Response(503, json=make_error_body(503, "Serviço indisponível")),
            httpx.Response(200, json=make_execution()),
        ]
    )

    execution = client.poll_pending_executions(timeout=1, retry_delay=0)

    assert execution.id == EXECUTION_ID
    assert route.calls.call_count == 2


@pytest.mark.respx(assert_all_called=False)
def test_poll_pending_executions_does_not_retry_non_server_api_errors(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/executions/pending/{INSTANCE_ID}").mock(
        return_value=httpx.Response(401, json=make_error_body(401, "Token inválido"))
    )

    with pytest.raises(AuthenticationError):
        client.poll_pending_executions(timeout=1, retry_delay=0)

    assert route.calls.call_count == 1


# ──────────────── Secrets ────────────────


@pytest.mark.respx(assert_all_called=False)
def test_get_secret_reveals_current_version(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret())
    )

    secret = client.get_secret(SECRET_ID)

    assert secret.secret_id == SECRET_ID
    assert secret.version_number == 1
    assert secret.type is SecretType.TEXT
    assert secret.value == "s3cr3t"
    assert route.calls.last.request.url.params.get("version") is None


@pytest.mark.respx(assert_all_called=False)
def test_get_secret_requests_specific_version(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret(versionNumber=3))
    )

    secret = client.get_secret(SECRET_ID, version=3)

    assert secret.version_number == 3
    assert route.calls.last.request.url.params["version"] == "3"


@pytest.mark.respx(assert_all_called=False)
def test_get_secret_parses_key_value_type(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(
            200,
            json=make_reveal_secret(type="KEY_VALUE", value={"user": "bot", "password": "hunter2"}),
        )
    )

    secret = client.get_secret(SECRET_ID)

    assert secret.type is SecretType.KEY_VALUE
    assert secret.value == {"user": "bot", "password": "hunter2"}


@pytest.mark.respx(assert_all_called=False)
def test_rotate_secret_sends_post_with_value(respx_mock: respx.MockRouter, client: Client) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/secrets/{SECRET_ID}/versions").mock(
        return_value=httpx.Response(200, json=make_secret_meta(currentVersion=2))
    )

    meta = client.rotate_secret(SECRET_ID, "new-value")

    assert meta.current_version == 2
    assert route.calls.last.request.content == b'{"value":"new-value"}'


@pytest.mark.respx(assert_all_called=False)
def test_rotate_secret_omits_expires_at_when_not_given(
    respx_mock: respx.MockRouter, client: Client
) -> None:
    route = respx_mock.post(f"{API_BASE_URL}/secrets/{SECRET_ID}/versions").mock(
        return_value=httpx.Response(200, json=make_secret_meta())
    )

    client.rotate_secret(SECRET_ID, "value")

    assert b"expiresAt" not in route.calls.last.request.content


@pytest.mark.respx(assert_all_called=False)
def test_secret_rotate_delegates_to_client(respx_mock: respx.MockRouter, client: Client) -> None:
    respx_mock.get(f"{API_BASE_URL}/secrets/{SECRET_ID}/reveal").mock(
        return_value=httpx.Response(200, json=make_reveal_secret())
    )
    rotate_route = respx_mock.post(f"{API_BASE_URL}/secrets/{SECRET_ID}/versions").mock(
        return_value=httpx.Response(200, json=make_secret_meta(currentVersion=2))
    )

    secret = client.get_secret(SECRET_ID)
    meta = secret.rotate("rotated-value")

    assert meta.current_version == 2
    assert rotate_route.calls.last.request.content == b'{"value":"rotated-value"}'
