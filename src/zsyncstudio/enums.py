"""Enums espelhando os status usados pela API do ZSync Tech Studio."""

from __future__ import annotations

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Status de uma execução de automação."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(StrEnum):
    """Status de uma task dentro de uma execução.

    Tasks só são reportadas já em seu estado final — não há PENDING/RUNNING
    intermediário: o robô processa o item e reporta o resultado numa única
    chamada (`complete_task` / `batch_complete_tasks`).
    """

    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


# Status terminais aceitos pela API em `finish_execution` / `complete_task`.
# Mantidos aqui (e não recalculados no cliente) porque espelham exatamente as
# constantes TERMINAL_STATUSES dos DTOs do backend.
TERMINAL_EXECUTION_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}
)

TERMINAL_TASK_STATUSES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.SUCCESS, TaskStatus.WARNING, TaskStatus.ERROR, TaskStatus.SKIPPED}
)
