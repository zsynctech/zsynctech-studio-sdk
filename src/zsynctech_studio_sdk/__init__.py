"""ZsyncTech Studio SDK - connects RPA robots to the platform's `/robot` protocol."""

from zsynctech_studio_sdk.client import RobotClient
from zsynctech_studio_sdk.exceptions import (
    AuthenticationError,
    ConcurrencyLimitError,
    ExecutionError,
    NotConnectedError,
    SdkError,
)
from zsynctech_studio_sdk.models import (
    ClaimedTask,
    ConnectResult,
    ExecutionFinishResult,
    ExecutionFinishStatus,
    ExecutionStartResult,
    MachineOsPlatform,
    RobotClientConfig,
    RobotInstanceStatus,
    Task,
    TaskResultAck,
    TaskStatus,
)
from zsynctech_studio_sdk.task_handle import TaskHandle

__all__ = [
    "AuthenticationError",
    "ClaimedTask",
    "ConcurrencyLimitError",
    "ConnectResult",
    "ExecutionError",
    "ExecutionFinishResult",
    "ExecutionFinishStatus",
    "ExecutionStartResult",
    "MachineOsPlatform",
    "NotConnectedError",
    "RobotClient",
    "RobotClientConfig",
    "RobotInstanceStatus",
    "SdkError",
    "Task",
    "TaskHandle",
    "TaskResultAck",
    "TaskStatus",
    "main",
]


def main() -> None:
    """CLI smoke-test entry point (`zsynctech-studio-sdk` console script)."""
    print("zsynctech-studio-sdk installed successfully - import zsynctech_studio_sdk.RobotClient to begin.")
