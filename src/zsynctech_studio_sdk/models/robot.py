"""Robot data returned by the platform. Mirrors `RobotResponseDto`."""

from __future__ import annotations

from datetime import datetime

from .base import SdkBaseModel
from .enums import RobotAvailability, RobotStatus


class RobotInfo(SdkBaseModel):
    """Snapshot of a robot's own data, as returned by `heartbeat` and `status`."""

    id: str
    name: str
    description: str | None = None
    availability: RobotAvailability
    status: RobotStatus
    max_concurrency: int
    connected_instance_count: int
    busy_instance_count: int
    manual_task_cost: float | None = None
    automated_task_cost: float | None = None
    manual_task_minutes: float | None = None
    operation_window_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RobotConnection(RobotInfo):
    """`RobotInfo` plus the instance identity handed out on a successful `connected` event.

    Only exists for the lifetime of this specific socket connection - a new `connect()` call
    (even for the same robot) gets a fresh `instance_id`/`instance_code`.
    """

    instance_id: str
    instance_code: str
