"""
ZSyncTech Studio SDK
====================

Python SDK for building robots that integrate with the ZSyncTech Studio
automation platform via its REST API.

Quickstart::

    from zsynctech_studio_sdk import task, execution
    from zsynctech_studio_sdk.config import SDKConfig

    @task
    def fetch_data():
        ...

    @task(name="Process records")
    def process():
        ...

    @execution
    def run():
        fetch_data()
        process()

    if __name__ == "__main__":
        run.listener()                        # reads API_TOKEN, INSTANCE_ID from env
        # or:
        run.listener(config=SDKConfig(...))   # explicit config

Advanced usage::

    from zsynctech_studio_sdk.services import ExecutionService, TaskService
    from zsynctech_studio_sdk.http import HttpClient
    from zsynctech_studio_sdk.models import ExecutionStatus, TaskStatus

    with HttpClient("http://localhost:3000", "zst_token") as http:
        svc = ExecutionService(http)
        executions = svc.list(status=ExecutionStatus.RUNNING)
"""

from .config import SDKConfig
from .context import get_current_context
from .decorators import execution, task
from .models.execution import ExecutionStatus
from .models.task import TaskStatus

__all__ = [
    "task",
    "execution",
    "SDKConfig",
    "get_current_context",
    "ExecutionStatus",
    "TaskStatus"
]

