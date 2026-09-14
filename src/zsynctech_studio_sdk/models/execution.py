"""Models for the execution lifecycle: `execution:start` / `execution:task` / `execution:finish`."""

from typing import Any

from pydantic import Field, field_validator

from zsynctech_studio_sdk.models.base import CamelModel
from zsynctech_studio_sdk.models.enums import TaskStatus
from zsynctech_studio_sdk.utils.time import utc_now_iso


class Task(CamelModel):
    """One task outcome, as sent in `execution:task`'s ``tasks`` array.

    Mirrors the gateway's ``TaskItem`` (`robot.gateway.ts`). Only
    :class:`~zsynctech_studio_sdk.models.enums.TaskStatus` values are accepted - the server
    silently drops anything else, so the SDK validates client-side instead of letting a typo
    disappear without feedback.

    ``started_at``/``finished_at`` default to "now" so simple call sites don't need to track
    timestamps manually; pass them explicitly for tasks whose real duration matters.
    """

    external_id: str | None = None
    attempts: int = Field(default=1, ge=1)
    status: TaskStatus
    message: str | None = None
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    started_at: str = Field(default_factory=utc_now_iso)
    finished_at: str = Field(default_factory=utc_now_iso)


class ExecutionStartResult(CamelModel):
    """Ack payload from `execution:start`."""

    execution_id: str


class ExecutionFinishResult(CamelModel):
    """Ack payload from `execution:finish`."""

    execution_id: str
    status: str

    @field_validator("status")
    @classmethod
    def _uppercase(cls, value: str) -> str:
        return value.upper()
