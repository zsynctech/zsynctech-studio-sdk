"""Ergonomic per-task reporting handle, returned by :meth:`RobotClient.start_task`."""

from collections.abc import Callable
from types import TracebackType
from typing import Any

from zsynctech_studio_sdk.models.enums import TaskStatus
from zsynctech_studio_sdk.models.execution import Task
from zsynctech_studio_sdk.utils.time import utc_now_iso

ReportTaskFn = Callable[[Task], None]


class TaskHandle:
    """One in-progress task, opened by :meth:`RobotClient.start_task`.

    Captures ``started_at`` at creation. Call exactly one of :meth:`success`,
    :meth:`warning`, or :meth:`error` to report the outcome - each stamps
    ``finished_at`` and sends the task through the same path :meth:`RobotClient.report_tasks`
    uses, so callers don't have to build a :class:`~zsynctech_studio_sdk.models.execution.Task`
    by hand for the common one-task-at-a-time case::

        task = client.start_task(external_id="row-42")
        try:
            ...
            task.success()
        except Exception as exc:
            task.error(message=str(exc))

    Also usable as a context manager, which reports automatically on exit unless the block
    already reported explicitly::

        with client.start_task() as task:
            ...  # task.success() on a clean exit, task.error() if this raises
    """

    def __init__(self, report: ReportTaskFn, external_id: str | None = None, attempts: int = 1) -> None:
        self._report = report
        self._external_id = external_id
        self._attempts = attempts
        self._started_at = utc_now_iso()
        self._closed = False

    def success(self, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        """Report this task as :attr:`TaskStatus.SUCCESS`."""
        self._finish(TaskStatus.SUCCESS, message, result)

    def warning(self, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        """Report this task as :attr:`TaskStatus.WARNING`."""
        self._finish(TaskStatus.WARNING, message, result)

    def error(self, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        """Report this task as :attr:`TaskStatus.FAILURE`."""
        self._finish(TaskStatus.FAILURE, message, result)

    def __enter__(self) -> "TaskHandle":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        if self._closed:
            return  # already reported explicitly inside the block
        if exc_type is None:
            self.success()
        else:
            self.error(message=str(exc) if str(exc) else exc_type.__name__)
        # Implicit None return - never suppresses the exception.

    def _finish(self, status: TaskStatus, message: str | None, result: dict[str, Any] | None) -> None:
        if self._closed:
            raise RuntimeError("This task was already reported - call client.start_task() to start a new one")
        self._closed = True
        task = Task(
            external_id=self._external_id,
            attempts=self._attempts,
            status=status,
            message=message,
            result=result,
            started_at=self._started_at,
            finished_at=utc_now_iso(),
        )
        self._report(task)


__all__ = ["TaskHandle"]
