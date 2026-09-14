"""Models for the optional server-side queue: `queue:next` / `queue:task-result`."""

from typing import Any

from pydantic import Field

from zsynctech_studio_sdk.models.base import CamelModel
from zsynctech_studio_sdk.models.enums import TaskStatus


class ClaimedTask(CamelModel):
    """One task claimed via `queue:next`.

    ``task_id`` is ``None`` when the queue has nothing left to claim right now - not an error,
    an expected steady state the caller should poll around.
    """

    task_id: str | None = None
    external_id: str | None = None
    attempts: int = Field(default=1, ge=1)
    payload: dict[str, Any] | None = None

    @property
    def has_task(self) -> bool:
        """Whether this result actually carries a task to work on."""
        return self.task_id is not None


class TaskResultAck(CamelModel):
    """Ack payload from `queue:task-result`."""

    task_id: str
    status: TaskStatus
