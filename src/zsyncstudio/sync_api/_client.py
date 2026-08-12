"""Cliente síncrono para a API do ZSync Tech Studio."""

from __future__ import annotations

import atexit
import time
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

import httpx

from .._http import (
    build_headers,
    clean_params,
    parse_instance_id,
    parse_json_or_none,
    raise_for_status,
    resolve_api_base_url,
)
from ..enums import TERMINAL_EXECUTION_STATUSES, ExecutionStatus, SecretType, TaskStatus
from ..exceptions import ConnectionError as ZSyncConnectionError
from ..exceptions import ServerError
from ..models import Execution, Page, SecretMeta, Task, TaskCompletion, TaskSummary


class Client:
    """Cliente HTTP síncrono autenticado com um token de instância (`zst_...`).

    Cobre o fluxo de robô descrito na API: disparar/agendar execuções, fazer
    polling por trabalho pendente, reivindicar (`claim`) uma execução e
    reportar tasks até finalizá-la. Um token de instância só enxerga a
    instância a que pertence — chamadas para outra instância retornam
    `PermissionDeniedError`.

    O `instanceId` viaja embutido no próprio token (`zst_<instanceId>.<secret>`)
    e fica disponível em `client.instance_id` — os métodos que precisam dele
    (`start_execution`, `schedule_execution`, `get_pending_execution`) não
    pedem para você passá-lo de novo.

    Não é preciso fechar a conexão HTTP manualmente: `close()` é registrada
    para rodar automaticamente na saída do processo (via `atexit`). Só chame
    `close()` você mesmo (ou use `with`) se quiser liberar a conexão antes
    disso — por exemplo, um processo de longa duração que cria vários
    `Client`s ao longo do tempo.

    ```python
    from zsyncstudio.sync_api import Client

    client = Client("https://studio.exemplo.com", api_token)
    execution = client.get_pending_execution()
    ```

    `base_url` é só o host — o prefixo `/api/v1` (versionamento de URI do
    backend) é acrescentado automaticamente. Se o backend mudar de versão,
    passe `api_version="v2"` em vez de embutir o prefixo você mesmo em
    `base_url`.
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        api_version: str = "v1",
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.instance_id = parse_instance_id(api_token)
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=resolve_api_base_url(base_url, api_version),
            headers=build_headers(api_token),
            timeout=timeout,
        )
        atexit.register(self.close)

    def close(self) -> None:
        """Fecha a conexão HTTP subjacente, se ela pertencer a este cliente.

        Chamado automaticamente na saída do processo — só precisa ser
        chamado manualmente para liberar a conexão antes disso.
        """
        atexit.unregister(self.close)
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._http.request(
                method,
                path,
                params=clean_params(params) if params else None,
                json=json,
            )
        except httpx.TransportError as exc:
            raise ZSyncConnectionError(f"Falha ao conectar em {path}: {exc}") from exc

        raise_for_status(response)
        return parse_json_or_none(response)

    # ──────────────── Execuções ────────────────

    def start_execution(self) -> ExecutionRun:
        """Inicia uma execução imediatamente (status `RUNNING`) para a instância do token,
        e já retorna o `ExecutionRun` pronto pra usar.

        Como a execução já nasce `RUNNING`, não é preciso chamar
        `execution.start()` depois — vá direto para `execution.task(...)`.
        Use para automações autônomas, que decidem sozinhas quando rodar, em
        vez de esperar `poll_pending_executions()`.
        """
        data = self._request("POST", "/executions", json={"instanceId": self.instance_id})
        return self.run_execution(Execution.from_api(data))

    def schedule_execution(self) -> ExecutionRun:
        """Cria uma execução pendente (status `PENDING`) para a instância do token,
        e já retorna o `ExecutionRun` pronto pra usar.

        Como a execução nasce `PENDING`, ainda é preciso chamar
        `execution.start()` antes de reportar tasks (mesmo contrato de
        `poll_pending_executions()`).
        """
        data = self._request("POST", "/executions/schedule", json={"instanceId": self.instance_id})
        return self.run_execution(Execution.from_api(data))

    def get_pending_execution(self, *, timeout: int = 20) -> Execution | None:
        """Faz long-polling por uma execução pendente da instância do token.

        Espelha `GET /executions/pending/:instanceId`: o backend segura a
        conexão por até `timeout` segundos (limitado a 30 no servidor) e
        retorna assim que houver uma execução `PENDING`, ou `None` se o prazo
        expirar sem trabalho disponível.
        """
        data = self._request(
            "GET", f"/executions/pending/{self.instance_id}", params={"timeout": timeout}
        )
        return Execution.from_api(data) if data else None

    def poll_pending_executions(
        self, *, timeout: int = 20, retry_delay: float = 5.0
    ) -> ExecutionRun:
        """Fica bloqueado até aparecer uma execução pendente, e a retorna já
        envolvida em `ExecutionRun` — pronta pra usar.

        Repete o long-polling indefinidamente (cada rodada sem trabalho já
        leva `timeout` segundos, o servidor segura a conexão). Se a conexão
        cair (`ConnectionError`) ou a API responder com erro de servidor
        (`ServerError`, HTTP 5xx), espera `retry_delay` segundos e tenta de
        novo, em vez de propagar — outros erros da API (401, 403, 404, 409,
        validação) propagam direto, já que repeti-los não resolveria nada.

        ```python
        while execution := client.poll_pending_executions():
            try:
                run(execution)
            except Exception as exc:
                execution.error(str(exc))
                raise
            else:
                execution.error("...") if execution.had_errors else execution.finish()
        ```
        """
        while True:
            try:
                pending = self.get_pending_execution(timeout=timeout)
            except (ZSyncConnectionError, ServerError):
                time.sleep(retry_delay)
                continue
            if pending is not None:
                return self.run_execution(pending)

    def claim_execution(self, execution_id: str) -> Execution:
        """Reivindica uma execução pendente, movendo-a de `PENDING` para `RUNNING`."""
        data = self._request("POST", f"/executions/{execution_id}/claim")
        return Execution.from_api(data)

    def get_execution(self, execution_id: str) -> Execution:
        """Busca uma execução pelo id."""
        data = self._request("GET", f"/executions/{execution_id}")
        return Execution.from_api(data)

    def list_executions(
        self,
        *,
        automation_id: str | None = None,
        status: ExecutionStatus | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Execution]:
        """Lista execuções com filtros e paginação.

        Um token de instância só enxerga suas próprias execuções — o backend
        sempre filtra pela instância do token, então não há parâmetro
        `instance_id` aqui.
        """
        data = self._request(
            "GET",
            "/executions",
            params={
                "automationId": automation_id,
                "status": status,
                "fromDate": from_date,
                "toDate": to_date,
                "search": search,
                "page": page,
                "pageSize": page_size,
            },
        )
        return Page.from_api(data, Execution)

    def finish_execution(
        self,
        execution_id: str,
        *,
        observation: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> Execution:
        """Finaliza uma execução em andamento.

        Se `status` não for informado, o backend decide automaticamente:
        `FAILED` quando há `observation`, `COMPLETED` caso contrário.
        """
        if status is not None and status not in TERMINAL_EXECUTION_STATUSES:
            raise ValueError(
                f"status deve ser um status terminal {sorted(TERMINAL_EXECUTION_STATUSES)}, "
                f"recebido: {status}"
            )
        payload: dict[str, Any] = {}
        if observation is not None:
            payload["observation"] = observation
        if status is not None:
            payload["status"] = status.value
        data = self._request("POST", f"/executions/{execution_id}/finish", json=payload)
        return Execution.from_api(data)

    def cancel_execution(self, execution_id: str) -> Execution:
        """Cancela uma execução `PENDING` ou `RUNNING`."""
        data = self._request("POST", f"/executions/{execution_id}/cancel")
        return Execution.from_api(data)

    def update_observation(self, execution_id: str, observation: str) -> Execution:
        """Atualiza a observação de uma execução `RUNNING`, sem finalizá-la.

        Útil para reportar progresso (ex.: "processando lote 3 de 10")
        enquanto o robô ainda trabalha.
        """
        data = self._request(
            "PATCH", f"/executions/{execution_id}/observation", json={"observation": observation}
        )
        return Execution.from_api(data)

    def set_total_tasks(self, execution_id: str, total_tasks: int) -> Execution:
        """Declara quantas tasks a execução `RUNNING` deve processar no total.

        Faz o progresso exibido no dashboard acompanhar esse valor (ex.:
        "45/1000") em vez de sempre mostrar reportado/reportado. Pode ser
        chamado mais de uma vez; se o robô processar mais tasks do que
        declarou, o total exibido acompanha o que já foi processado em vez
        de passar de 100%.
        """
        data = self._request(
            "PATCH",
            f"/executions/{execution_id}/total-tasks",
            json={"totalTasks": total_tasks},
        )
        return Execution.from_api(data)

    # ──────────────── Tasks ────────────────

    def complete_task(
        self,
        execution_id: str,
        reference: str,
        status: TaskStatus,
        *,
        observation: str | None = None,
        metadata: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Task:
        """Registra uma task já em seu estado final, em uma única chamada.

        `status` precisa ser terminal (`SUCCESS`, `WARNING`, `ERROR` ou
        `SKIPPED`) — não há registro em duas etapas, o item já chega
        processado.
        """
        completion = TaskCompletion(
            reference=reference,
            status=status,
            observation=observation,
            metadata=metadata,
            started_at=started_at,
            finished_at=finished_at,
        )
        data = self._request(
            "POST",
            f"/executions/{execution_id}/tasks/complete",
            json=completion.to_json(),
        )
        return Task.from_api(data)

    def batch_complete_tasks(self, execution_id: str, tasks: list[TaskCompletion]) -> list[Task]:
        """Registra e finaliza de 1 a 500 tasks em uma única chamada."""
        if not tasks:
            raise ValueError("tasks não pode ser uma lista vazia")
        if len(tasks) > 500:
            raise ValueError("no máximo 500 tasks por chamada")
        data = self._request(
            "POST",
            f"/executions/{execution_id}/tasks/batch",
            json={"tasks": [task.to_json() for task in tasks]},
        )
        return [Task.from_api(item) for item in data]

    def get_task_summary(self, execution_id: str) -> TaskSummary:
        """Retorna contagens por status e métricas de tempo das tasks de uma execução."""
        data = self._request("GET", f"/executions/{execution_id}/tasks/summary")
        return TaskSummary.from_api(data)

    def list_tasks(
        self,
        execution_id: str,
        *,
        status: TaskStatus | None = None,
        search: str | None = None,
        sort: str = "asc",
        page: int = 1,
        page_size: int = 100,
    ) -> Page[Task]:
        """Lista as tasks de uma execução, em ordem de chegada."""
        data = self._request(
            "GET",
            f"/executions/{execution_id}/tasks",
            params={
                "status": status,
                "search": search,
                "sort": sort,
                "page": page,
                "pageSize": page_size,
            },
        )
        return Page.from_api(data, Task)

    # ──────────────── Camada ergonômica ────────────────

    def run_execution(self, execution: Execution | str) -> ExecutionRun:
        """Envolve uma execução (`PENDING` ou `RUNNING`) num objeto imperativo.

        Sem gerenciador de contexto: chame `start()` para reivindicar uma
        execução ainda `PENDING`, `task(reference)` para abrir cada item, e
        `finish()`/`error()`/`cancel()` — um método por status terminal, igual
        a `TaskRun` — para encerrar a execução quando terminar.

        ```python
        pending = client.get_pending_execution()
        if pending is not None:
            execution = client.run_execution(pending)
            execution.start()

            for invoice in invoices:
                task = execution.task(invoice.number)
                task.start()
                try:
                    process(invoice)
                except TaskWarning as warn:
                    task.warning(str(warn))
                except TaskSkipped as skip:
                    task.skip(str(skip))
                except Exception as exc:
                    task.error(str(exc))
                else:
                    task.finish()

            if execution.had_errors:
                execution.error("alguns itens falharam")
            else:
                execution.finish()
        ```
        """
        execution_id = execution if isinstance(execution, str) else execution.id
        return ExecutionRun(self, execution_id)

    # ──────────────── Secrets ────────────────

    def get_secret(self, secret_id: str, *, version: int | None = None) -> Secret:
        """Revela (descriptografa) o valor de uma credencial.

        Sem `version`, revela a versão atual. Falha com `ValidationError` se a
        credencial estiver expirada (rotacione com `secret.rotate(...)` antes
        de revelar) ou com `NotFoundError` se ela (ou a versão) não existir.

        ```python
        secret = client.get_secret(secret_id)
        password = secret.value  # str, dict[str, str] ou dado JSON — depende do tipo da credencial
        ```
        """
        data = self._request("GET", f"/secrets/{secret_id}/reveal", params={"version": version})
        return Secret(
            self,
            secret_id=data["secretId"],
            version_number=data["versionNumber"],
            type=SecretType(data["type"]),
            value=data["value"],
            revealed_at=datetime.fromisoformat(data["revealedAt"]),
        )

    def rotate_secret(
        self, secret_id: str, value: Any, *, expires_at: datetime | None = None
    ) -> SecretMeta:
        """Cria uma nova versão de uma credencial com o valor informado.

        Nunca sobrescreve a versão atual — sempre cria a próxima. `value`
        precisa respeitar o tipo da credencial (texto, par chave-valor ou
        JSON). Falha com `ConflictError` se a credencial estiver bloqueada.
        """
        payload: dict[str, Any] = {"value": value}
        if expires_at is not None:
            payload["expiresAt"] = expires_at.isoformat()
        data = self._request("POST", f"/secrets/{secret_id}/versions", json=payload)
        return SecretMeta.from_api(data)


class ExecutionRun:
    """Execução aberta por `Client.run_execution`, controlada de forma imperativa."""

    def __init__(self, client: Client, execution_id: str) -> None:
        self._client = client
        self._execution_id = execution_id
        self._error_count = 0

    @property
    def id(self) -> str:
        return self._execution_id

    @property
    def had_errors(self) -> bool:
        """`True` se alguma task finalizada até agora tiver status `ERROR`."""
        return self._error_count > 0

    def start(self) -> Execution:
        """Reivindica a execução, movendo-a de `PENDING` para `RUNNING`.

        Chame só quando a execução ainda estiver `PENDING` (ex.: veio de
        `get_pending_execution`). Se já estiver `RUNNING` (ex.:
        `start_execution` imediato), pule esta chamada e vá direto para
        `task()`.
        """
        return self._client.claim_execution(self._execution_id)

    def task(self, reference: str) -> TaskRun:
        """Abre uma task local para `reference`.

        Nada é enviado à API até você chamar `task.finish()` (`SUCCESS`),
        `task.warning(...)`, `task.error(...)` ou `task.skip(...)`. Chame
        `task.start()` antes de processar o item para que o `startedAt`
        reportado reflita o início real do processamento.
        """
        return TaskRun(self, reference)

    def finish(self, observation: str | None = None) -> Execution:
        """Finaliza a execução como `COMPLETED`."""
        return self._client.finish_execution(
            self._execution_id, observation=observation, status=ExecutionStatus.COMPLETED
        )

    def error(self, observation: str | None = None) -> Execution:
        """Finaliza a execução como `FAILED`."""
        return self._client.finish_execution(
            self._execution_id, observation=observation, status=ExecutionStatus.FAILED
        )

    def cancel(self) -> Execution:
        """Cancela a execução (`CANCELLED`)."""
        return self._client.cancel_execution(self._execution_id)

    def update_observation(self, observation: str) -> Execution:
        """Atualiza a observação da execução sem finalizá-la (segue `RUNNING`).

        Útil para reportar progresso (ex.: "processando lote 3 de 10")
        enquanto o loop de tasks ainda está rodando.
        """
        return self._client.update_observation(self._execution_id, observation)

    def set_total_tasks(self, total_tasks: int) -> Execution:
        """Declara quantas tasks a execução deve processar no total.

        Faz o progresso exibido no dashboard acompanhar esse valor (ex.:
        "45/1000") em vez de sempre mostrar reportado/reportado. Pode ser
        chamado mais de uma vez; se o robô processar mais tasks do que
        declarou, o total exibido acompanha o que já foi processado em vez
        de passar de 100%.
        """
        return self._client.set_total_tasks(self._execution_id, total_tasks)


class TaskRun:
    """Task aberta por `ExecutionRun.task()` — local até um dos métodos de
    finalização (`finish`/`warning`/`error`/`skip`) reportá-la à API.
    """

    def __init__(self, run: ExecutionRun, reference: str) -> None:
        self._run = run
        self.reference = reference
        self._started_at: datetime | None = None

    def start(self) -> None:
        """Marca localmente o horário de início do processamento (sem chamada à API)."""
        self._started_at = datetime.now(UTC)

    def finish(
        self, observation: str | None = None, *, metadata: dict[str, Any] | None = None
    ) -> Task:
        """Reporta a task como `SUCCESS`."""
        return self._complete(TaskStatus.SUCCESS, observation, metadata)

    def warning(
        self, observation: str | None = None, *, metadata: dict[str, Any] | None = None
    ) -> Task:
        """Reporta a task como `WARNING`."""
        return self._complete(TaskStatus.WARNING, observation, metadata)

    def error(
        self, observation: str | None = None, *, metadata: dict[str, Any] | None = None
    ) -> Task:
        """Reporta a task como `ERROR`."""
        return self._complete(TaskStatus.ERROR, observation, metadata)

    def skip(
        self, observation: str | None = None, *, metadata: dict[str, Any] | None = None
    ) -> Task:
        """Reporta a task como `SKIPPED`."""
        return self._complete(TaskStatus.SKIPPED, observation, metadata)

    def _complete(
        self, status: TaskStatus, observation: str | None, metadata: dict[str, Any] | None
    ) -> Task:
        """Chama `complete_task`; `startedAt` usa o horário marcado por `start()`,
        se ele foi chamado, caso contrário o próprio horário desta chamada.
        """
        finished_at = datetime.now(UTC)
        started_at = self._started_at or finished_at
        if status is TaskStatus.ERROR:
            self._run._error_count += 1
        return self._run._client.complete_task(
            self._run.id,
            self.reference,
            status,
            observation=observation,
            metadata=metadata,
            started_at=started_at,
            finished_at=finished_at,
        )


class Secret:
    """Credencial revelada por `Client.get_secret()` — o valor já vem descriptografado.

    `value` é `str` para credenciais do tipo `TEXT`, `dict[str, str]` para
    `KEY_VALUE`, ou o dado JSON decodificado para `JSON`.
    """

    def __init__(
        self,
        client: Client,
        *,
        secret_id: str,
        version_number: int,
        type: SecretType,
        value: Any,
        revealed_at: datetime,
    ) -> None:
        self._client = client
        self.secret_id = secret_id
        self.version_number = version_number
        self.type = type
        self.value = value
        self.revealed_at = revealed_at

    def rotate(self, value: Any, *, expires_at: datetime | None = None) -> SecretMeta:
        """Cria uma nova versão desta credencial com o valor informado.

        Equivalente a `client.rotate_secret(secret.secret_id, value, ...)`.
        Esta instância de `Secret` continua representando a versão que você
        revelou — chame `client.get_secret(...)` de novo se precisar do valor
        recém-rotacionado.
        """
        return self._client.rotate_secret(self.secret_id, value, expires_at=expires_at)
