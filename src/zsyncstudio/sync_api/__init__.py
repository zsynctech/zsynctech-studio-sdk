"""API síncrona: `from zsyncstudio.sync_api import Client`."""

from ..enums import (
    TERMINAL_EXECUTION_STATUSES,
    TERMINAL_TASK_STATUSES,
    ExecutionStatus,
    SecretStatus,
    SecretType,
    TaskStatus,
)
from ..exceptions import (
    ApiError,
    AuthenticationError,
    ConflictError,
    ConnectionError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    TaskSkipped,
    TaskWarning,
    ValidationError,
    ZSyncStudioError,
)
from ..models import Execution, Page, SecretMeta, Task, TaskCompletion, TaskSummary, TaskTiming
from ._client import Client, ExecutionRun, Secret

__all__ = [
    "Client",
    "ExecutionRun",
    "ExecutionStatus",
    "TaskStatus",
    "SecretType",
    "SecretStatus",
    "TERMINAL_EXECUTION_STATUSES",
    "TERMINAL_TASK_STATUSES",
    "ApiError",
    "AuthenticationError",
    "ConflictError",
    "ConnectionError",
    "NotFoundError",
    "PermissionDeniedError",
    "ServerError",
    "TaskSkipped",
    "TaskWarning",
    "ValidationError",
    "ZSyncStudioError",
    "Execution",
    "Page",
    "Secret",
    "SecretMeta",
    "Task",
    "TaskCompletion",
    "TaskSummary",
    "TaskTiming",
]
