"""Data models and enums exchanged with the zsynctech-studio `/robot` gateway."""

from .base import SdkBaseModel
from .config import RobotClientConfig
from .credential import CredentialInfo, RevealedCredential
from .enums import (
    CredentialStatus,
    CredentialType,
    ExecutionFinishStatus,
    Platform,
    RobotAvailability,
    RobotInstanceStatus,
    RobotStatus,
    TaskStatus,
)
from .execution import ExecutionFinishResult, ExecutionStartResult
from .robot import RobotConnection, RobotInfo
from .task import ClaimedTask, TaskItem

__all__ = [
    "SdkBaseModel",
    "RobotClientConfig",
    "CredentialInfo",
    "RevealedCredential",
    "CredentialStatus",
    "CredentialType",
    "ExecutionFinishStatus",
    "Platform",
    "RobotAvailability",
    "RobotInstanceStatus",
    "RobotStatus",
    "TaskStatus",
    "ExecutionFinishResult",
    "ExecutionStartResult",
    "RobotConnection",
    "RobotInfo",
    "ClaimedTask",
    "TaskItem",
]
