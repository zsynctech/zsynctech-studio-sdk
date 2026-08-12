"""Modelos de dados trocados com a API do ZSync Tech Studio.

Os modelos de saída (`Execution`, `Task`, `TaskSummary`, `Page`) são
`dataclass`s imutáveis construídas a partir do JSON da API via `from_api`.
Os modelos de entrada (`TaskCompletion`) validam localmente as mesmas regras
do `class-validator` do backend, para falhar rápido antes de gastar uma
requisição HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .enums import TERMINAL_TASK_STATUSES, ExecutionStatus, SecretStatus, SecretType, TaskStatus


def _parse_datetime(value: str | None) -> datetime | None:
    """Converte um timestamp ISO 8601 da API (ou `None`) em `datetime`."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _require_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True, slots=True)
class Execution:
    """Uma execução de uma instância de automação."""

    id: str
    instance_id: str
    status: ExecutionStatus
    triggered_by: str | None
    triggered_by_api_token: str | None
    triggered_by_schedule: str | None
    cancelled_by: str | None
    started_at: datetime | None
    finished_at: datetime | None
    observation: str | None
    total_tasks: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Execution:
        return cls(
            id=data["id"],
            instance_id=data["instanceId"],
            status=ExecutionStatus(data["status"]),
            triggered_by=data.get("triggeredBy"),
            triggered_by_api_token=data.get("triggeredByApiToken"),
            triggered_by_schedule=data.get("triggeredBySchedule"),
            cancelled_by=data.get("cancelledBy"),
            started_at=_parse_datetime(data.get("startedAt")),
            finished_at=_parse_datetime(data.get("finishedAt")),
            observation=data.get("observation"),
            total_tasks=data.get("totalTasks"),
            created_at=_require_datetime(data["createdAt"]),
            updated_at=_require_datetime(data["updatedAt"]),
        )


@dataclass(frozen=True, slots=True)
class Task:
    """Uma task (item processado) dentro de uma execução."""

    id: str
    execution_id: str
    reference: str
    status: TaskStatus
    started_at: datetime | None
    finished_at: datetime | None
    observation: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Task:
        return cls(
            id=data["id"],
            execution_id=data["executionId"],
            reference=data["reference"],
            status=TaskStatus(data["status"]),
            started_at=_parse_datetime(data.get("startedAt")),
            finished_at=_parse_datetime(data.get("finishedAt")),
            observation=data.get("observation"),
            metadata=data.get("metadata"),
            created_at=_require_datetime(data["createdAt"]),
            updated_at=_require_datetime(data["updatedAt"]),
        )


@dataclass(frozen=True, slots=True)
class TaskTiming:
    """Referência e duração de uma task, usada em `TaskSummary`."""

    reference: str
    duration_ms: float

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> TaskTiming:
        return cls(reference=data["reference"], duration_ms=data["durationMs"])


@dataclass(frozen=True, slots=True)
class TaskSummary:
    """Estatísticas agregadas das tasks de uma execução."""

    total: int
    total_tasks: int | None
    success: int
    error: int
    warning: int
    skipped: int
    avg_duration_ms: float | None
    total_duration_ms: float
    fastest_task: TaskTiming | None
    slowest_task: TaskTiming | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> TaskSummary:
        fastest = data.get("fastestTask")
        slowest = data.get("slowestTask")
        return cls(
            total=data["total"],
            total_tasks=data.get("totalTasks"),
            success=data["success"],
            error=data["error"],
            warning=data["warning"],
            skipped=data["skipped"],
            avg_duration_ms=data.get("avgDurationMs"),
            total_duration_ms=data["totalDurationMs"],
            fastest_task=TaskTiming.from_api(fastest) if fastest else None,
            slowest_task=TaskTiming.from_api(slowest) if slowest else None,
        )


@dataclass(frozen=True, slots=True)
class SecretMeta:
    """Metadados de uma credencial (secret) — nunca inclui o valor.

    Retornado por `Client.rotate_secret()`. Para ler o valor, use
    `Client.get_secret()`, que devolve um `Secret`.
    """

    id: str
    name: str
    type: SecretType
    expires_at: datetime | None
    expired: bool
    current_version: int
    status: SecretStatus
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> SecretMeta:
        return cls(
            id=data["id"],
            name=data["name"],
            type=SecretType(data["type"]),
            expires_at=_parse_datetime(data.get("expiresAt")),
            expired=data["expired"],
            current_version=data["currentVersion"],
            status=SecretStatus(data["status"]),
            locked_at=_parse_datetime(data.get("lockedAt")),
            created_at=_require_datetime(data["createdAt"]),
            updated_at=_require_datetime(data["updatedAt"]),
        )


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Página de resultados, no formato `{data, pagination}` da API."""

    data: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool

    @classmethod
    def from_api(cls, data: dict[str, Any], item_cls: type[T]) -> Page[T]:
        pagination = data["pagination"]
        from_api = getattr(item_cls, "from_api")  # noqa: B009 - protocolo comum a Execution/Task
        return cls(
            data=[from_api(item) for item in data["data"]],
            page=pagination["page"],
            page_size=pagination["pageSize"],
            total_items=pagination["totalItems"],
            total_pages=pagination["totalPages"],
            has_next_page=pagination["hasNextPage"],
            has_previous_page=pagination["hasPreviousPage"],
        )


@dataclass(frozen=True, slots=True)
class TaskCompletion:
    """Uma task já finalizada, pronta para `batch_complete_tasks`.

    Espelha `CompleteTaskDto` do backend: `status` precisa ser um dos status
    terminais (`SUCCESS`, `WARNING`, `ERROR`, `SKIPPED`).
    """

    reference: str
    status: TaskStatus
    observation: str | None = None
    metadata: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not (1 <= len(self.reference) <= 255):
            raise ValueError("reference deve ter entre 1 e 255 caracteres")
        if self.status not in TERMINAL_TASK_STATUSES:
            raise ValueError(
                f"status deve ser um status terminal {sorted(TERMINAL_TASK_STATUSES)}, "
                f"recebido: {self.status}"
            )

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reference": self.reference,
            "status": self.status.value,
        }
        if self.observation is not None:
            payload["observation"] = self.observation
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        if self.started_at is not None:
            payload["startedAt"] = self.started_at.isoformat()
        if self.finished_at is not None:
            payload["finishedAt"] = self.finished_at.isoformat()
        return payload
