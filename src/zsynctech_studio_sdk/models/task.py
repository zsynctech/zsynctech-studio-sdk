"""Task-related data models: claimed queue items and reported outcomes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from ..utils import utc_now
from .base import SdkBaseModel
from .enums import TaskStatus


class ClaimedTask(SdkBaseModel):
    """A task handed out by `queue:next`, ready to be processed and reported on."""

    task_id: str
    external_id: str | None = None
    attempts: int = 1
    payload: dict[str, Any] | None = None


class TaskItem(SdkBaseModel):
    """One outcome reported through `execution:task` (direct, non-queue reporting).

    Unlike `ClaimedTask`, this is an outbound model built by the robot script itself - see
    `ExecutionManager.report_tasks`.
    """

    external_id: str | None = None
    attempts: int = 1
    status: TaskStatus
    message: str | None = None
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)
