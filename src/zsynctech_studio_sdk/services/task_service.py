"""
Task service - wraps all ``/executions/{id}/tasks`` REST endpoints.

Each method corresponds to one platform endpoint and returns a typed model.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..http.client import HttpClient
from ..models.enums import TaskStatus
from ..models.task import CompleteTaskRequest, RegisterTaskRequest, Task, TaskSummary, UpdateTaskRequest

logger = logging.getLogger(__name__)


class TaskService:
    """High-level service for task lifecycle operations within an execution.

    Provides methods for registering, updating, and querying tasks via the
    ZSyncTech platform REST API.

    Args:
        http: Pre-configured :class:`~zsynctech_studio_sdk.http.HttpClient`.

    Example::

        service = TaskService(http_client)
        task = service.register("execution-uuid", "Fetch data", order=0)
        service.update("execution-uuid", task.id, TaskStatus.SUCCESS)
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # -- Robot-facing methods --------------------------------------------------

    def register(
        self,
        execution_id: str,
        name: str,
        order: int | None = None,
    ) -> Task:
        """Register a new task within a running execution.

        Calls ``POST /executions/{id}/tasks``.

        Args:
            execution_id: UUID of the parent execution.
            name:         Human-readable label for the task step (1–255 chars).
            order:        Zero-based sequence index. If omitted, the platform
                          assigns the next available position.

        Returns:
            The newly created :class:`~zsynctech_studio_sdk.models.Task` with
            ``status == TaskStatus.PENDING``.

        Raises:
            NotFoundError: If the execution does not exist.
            ApiError:      On unexpected platform errors.
        """
        request = RegisterTaskRequest(name=name, order=order)
        body = request.model_dump(exclude_none=True)
        data = self._http.post(f"/executions/{execution_id}/tasks", body)
        logger.debug("Task '%s' registered in execution %s.", name, execution_id)
        return Task.model_validate(data)

    def update(
        self,
        execution_id: str,
        task_id: str,
        status: TaskStatus | None = None,
        observation: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Update the status and/or result of a task.

        Calls ``PUT /executions/{id}/tasks/{taskId}``.

        Args:
            execution_id: UUID of the parent execution.
            task_id:      UUID of the task to update.
            status:       New lifecycle status.
            observation:  Free-text note, typically an error message.
            metadata:     Arbitrary JSON data (stack trace, output, etc.).

        Returns:
            The updated :class:`~zsynctech_studio_sdk.models.Task`.

        Raises:
            NotFoundError: If the execution or task does not exist.
            ApiError:      On unexpected platform errors.
        """
        request = UpdateTaskRequest(
            status=status,
            observation=observation,
            metadata=metadata,
        )
        body = request.model_dump(exclude_none=True)
        data = self._http.put(f"/executions/{execution_id}/tasks/{task_id}", body or None)
        logger.debug(
            "Task %s updated to status %s in execution %s.",
            task_id,
            status,
            execution_id,
        )
        return Task.model_validate(data)

    def complete(
        self,
        execution_id: str,
        name: str,
        status: TaskStatus,
        order: int | None = None,
        observation: str | None = None,
        metadata: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Task:
        """Register and complete a task in a single HTTP round-trip.

        Replaces the three-call flow (register → mark RUNNING → mark terminal)
        with one ``POST /executions/{id}/tasks/complete`` request. Only accepts
        terminal statuses: SUCCESS, WARNING, ERROR or SKIPPED.

        Args:
            execution_id: UUID of the parent execution.
            name:         Human-readable label for the task step (1–255 chars).
            status:       Terminal status (SUCCESS, WARNING, ERROR, SKIPPED).
            order:        Zero-based sequence index. If omitted, the platform
                          assigns the next available position.
            observation:  Optional free-text note (error message, summary, etc.).
            metadata:     Arbitrary JSON data (stack trace, output, etc.).

        Returns:
            The created :class:`~zsynctech_studio_sdk.models.Task`.

        Raises:
            NotFoundError: If the execution does not exist.
            ApiError:      On unexpected platform errors (e.g. 409 if the
                           execution was cancelled before this call).
        """
        request = CompleteTaskRequest(
            name=name,
            status=status,
            order=order,
            observation=observation,
            metadata=metadata,
            started_at=started_at,
            finished_at=finished_at,
        )
        # by_alias=True → started_at/finished_at serialized as startedAt/finishedAt
        # mode='json'   → datetime objects serialized as ISO 8601 strings
        body = request.model_dump(exclude_none=True, by_alias=True, mode='json')
        data = self._http.post(f"/executions/{execution_id}/tasks/complete", body)
        logger.debug("Task '%s' completed (%s) in execution %s.", name, status, execution_id)
        return Task.model_validate(data)

    def batch_complete(
        self,
        execution_id: str,
        tasks: list[CompleteTaskRequest],
    ) -> list[Task]:
        """Register and complete multiple tasks in a single HTTP round-trip.

        Calls ``POST /executions/{id}/tasks/batch``. Accepts 1–500 tasks.
        Useful when an automation accumulates results before reporting them.

        Args:
            execution_id: UUID of the parent execution.
            tasks:        List of :class:`~zsynctech_studio_sdk.models.CompleteTaskRequest`
                          objects describing each task.

        Returns:
            List of created :class:`~zsynctech_studio_sdk.models.Task` objects.

        Raises:
            NotFoundError: If the execution does not exist.
            ApiError:      On unexpected platform errors.
        """
        body = {"tasks": [t.model_dump(exclude_none=True) for t in tasks]}
        data = self._http.post(f"/executions/{execution_id}/tasks/batch", body)
        items: list[Any] = data if isinstance(data, list) else data.get("data", data)
        logger.debug("Batch of %d task(s) completed in execution %s.", len(tasks), execution_id)
        return [Task.model_validate(item) for item in items]

    # -- Query methods ---------------------------------------------------------

    def list(
        self,
        execution_id: str,
        status: TaskStatus | None = None,
        sort: str = "asc",
        page: int = 1,
        page_size: int = 100,
    ) -> list[Task]:
        """List all tasks for an execution, ordered by sequence.

        Calls ``GET /executions/{id}/tasks``.

        Args:
            execution_id: UUID of the parent execution.
            status:       Filter by task status.
            sort:         Sort order - ``"asc"`` (default) or ``"desc"``.
            page:         Page number (1-indexed). Defaults to 1.
            page_size:    Items per page (1–500). Defaults to 100.

        Returns:
            List of :class:`~zsynctech_studio_sdk.models.Task` objects.

        Raises:
            NotFoundError: If the execution does not exist.
            ApiError:      On unexpected platform errors.
        """
        params: dict[str, Any] = {
            "sort": sort,
            "page": page,
            "pageSize": page_size,
        }
        if status is not None:
            params["status"] = str(status)

        data = self._http.get(f"/executions/{execution_id}/tasks", params=params)

        # The endpoint returns a paginated envelope; extract the ``data`` list.
        items: list[Any] = data.get("data", data) if isinstance(data, dict) else data
        return [Task.model_validate(item) for item in items]

    def get_summary(self, execution_id: str) -> TaskSummary:
        """Return task count statistics for an execution.

        Calls ``GET /executions/{id}/tasks/summary``.

        Args:
            execution_id: UUID of the parent execution.

        Returns:
            A :class:`~zsynctech_studio_sdk.models.TaskSummary` with counts
            broken down by status.

        Raises:
            NotFoundError: If the execution does not exist.
            ApiError:      On unexpected platform errors.
        """
        data = self._http.get(f"/executions/{execution_id}/tasks/summary")
        return TaskSummary.model_validate(data)
