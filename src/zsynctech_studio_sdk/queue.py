"""Queue consumption: `queue:next` / `queue:task-result`.

Requires an execution already open through `ExecutionManager` - same rule the gateway's own
`queue:next` handler enforces (it reads the execution id off the socket).
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any

from .connection import SocketConnection
from .exceptions import NoActiveExecutionError
from .execution import ExecutionManager
from .loggers import logger
from .models.enums import TaskStatus
from .models.task import ClaimedTask
from .protocol import ClientEvent


class QueueConsumer:
    """Claims tasks from a robot's queue and reports their outcomes back."""

    def __init__(self, connection: SocketConnection, execution: ExecutionManager) -> None:
        self._connection = connection
        self._execution = execution

    def claim_next(self, queue_id: str | None = None) -> ClaimedTask | None:
        """Claim the next pending task, or `None` if the queue is empty.

        `queue_id` picks a specific queue; omitted, the platform uses the robot's oldest one.
        """
        if not self._execution.is_running:
            raise NoActiveExecutionError("Nenhuma execução em andamento - inicie uma execução antes de consumir a fila")

        payload = {"queueId": queue_id} if queue_id else {}
        response = self._connection.call(ClientEvent.QUEUE_NEXT, payload)
        if not response or not response.get("taskId"):
            return None
        return ClaimedTask.model_validate(response)

    def report_result(
        self,
        task: ClaimedTask | str,
        status: TaskStatus,
        *,
        message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Report the outcome of a task previously handed out by `claim_next`/`consume`."""
        task_id = task.task_id if isinstance(task, ClaimedTask) else task
        payload: dict[str, Any] = {"taskId": task_id, "status": status.value}
        if message is not None:
            payload["message"] = message
        if result is not None:
            payload["result"] = result
        self._connection.call(ClientEvent.QUEUE_TASK_RESULT, payload)
        logger.debug("Task {} reportada como {}", task_id, status.value)

    def consume(self, queue_id: str | None = None) -> Iterator[ClaimedTask]:
        """Yield each pending task until the queue is empty.

        for task in client.queue.consume():
            ...
        """
        while True:
            task = self.claim_next(queue_id)
            if task is None:
                logger.info("Fila esvaziada")
                return
            logger.info("Task {} recebida (tentativa {})", task.task_id, task.attempts)
            yield task

    @contextmanager
    def processing(self, task: ClaimedTask) -> Generator[TaskOutcome]:
        """Yield a `TaskOutcome` to report SUCCESS/WARNING/FAILURE for `task`.

        If the body raises and nothing was explicitly reported yet, reports FAILURE with the
        exception message before re-raising. If it exits cleanly without reporting, reports
        SUCCESS - so the common case only needs the body to do its work:

            for task in client.queue.consume():
                with client.queue.processing(task):
                    do_the_work(task.payload)
        """
        outcome = TaskOutcome(self, task)
        try:
            yield outcome
        except Exception as exc:
            if not outcome.reported:
                outcome.failure(message=str(exc))
            raise
        else:
            if not outcome.reported:
                outcome.success()


class TaskOutcome:
    """Reports at most one outcome for the `ClaimedTask` it was created for."""

    def __init__(self, consumer: QueueConsumer, task: ClaimedTask) -> None:
        self._consumer = consumer
        self._task = task
        self.reported = False

    def success(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        self._report(TaskStatus.SUCCESS, message, result)

    def warning(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        self._report(TaskStatus.WARNING, message, result)

    def failure(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        self._report(TaskStatus.FAILURE, message, result)

    def _report(self, status: TaskStatus, message: str | None, result: dict[str, Any] | None) -> None:
        self._consumer.report_result(self._task, status, message=message, result=result)
        self.reported = True
