"""Pydantic models for the `/robot` protocol - the only place data shapes are defined."""

from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.models.connection import ConnectResult
from zsynctech_studio_sdk.models.enums import (
    ExecutionFinishStatus,
    MachineOsPlatform,
    RobotInstanceStatus,
    TaskStatus,
)
from zsynctech_studio_sdk.models.execution import (
    ExecutionFinishResult,
    ExecutionStartResult,
    Task,
)
from zsynctech_studio_sdk.models.queue import ClaimedTask, TaskResultAck

__all__ = [
    "ClaimedTask",
    "ConnectResult",
    "ExecutionFinishResult",
    "ExecutionFinishStatus",
    "ExecutionStartResult",
    "MachineOsPlatform",
    "RobotClientConfig",
    "RobotInstanceStatus",
    "Task",
    "TaskResultAck",
    "TaskStatus",
]
