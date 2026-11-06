"""The robot's queue on the platform: tasks handed out one at a time, each reporting its own
outcome.

    for task in robot.queue.tasks():
        task.success(result=process(task.payload))

Needs an open execution - the gateway ties every claimed task to the execution working on it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .exceptions import NoActiveExecutionError, TaskAlreadyReportedError
from .loggers import logger
from .models.enums import TaskStatus
from .models.task import ClaimedTask
from .protocol import ClientEvent

if TYPE_CHECKING:
    from .robot import Robot


class Task:
    """One task handed out by the queue. Reports exactly one outcome: `success`, `warning` or
    `failure`."""

    def __init__(self, robot: Robot, claimed: ClaimedTask) -> None:
        self._robot = robot
        self.id = claimed.task_id
        self.external_id = claimed.external_id
        self.attempts = claimed.attempts
        self.payload: dict[str, Any] = claimed.payload or {}
        self.status: TaskStatus | None = None

    @property
    def reported(self) -> bool:
        return self.status is not None

    def success(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        self._report(TaskStatus.SUCCESS, message, result)

    def warning(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        """Done, with a remark - e.g. only part of the data came back."""
        self._report(TaskStatus.WARNING, message, result)

    def failure(self, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        self._report(TaskStatus.FAILURE, message, result)

    def _report(self, status: TaskStatus, message: str | None, result: dict[str, Any] | None) -> None:
        if self.status is not None:
            raise TaskAlreadyReportedError(f"A task {self.id} já foi reportada como {self.status.value}")
        payload: dict[str, Any] = {"taskId": self.id, "status": status.value}
        if message is not None:
            payload["message"] = message
        if result is not None:
            payload["result"] = result
        self._robot._transport.call(ClientEvent.QUEUE_TASK_RESULT, payload)
        self.status = status
        logger.debug("Task {} reportada como {}", self.id, status.value)

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, external_id={self.external_id!r}, attempts={self.attempts})"


class Queue:
    """Hands out the robot's queued tasks."""

    def __init__(self, robot: Robot) -> None:
        self._robot = robot
        # Why the last `next()` came back empty - see `_stop_reason`.
        self.stop_reason: str | None = None

    def next(self, queue_id: str | None = None) -> Task | None:
        """The next pending task, or `None` once the queue is empty. `queue_id` picks a specific
        queue; omitted, the platform uses the robot's own."""
        if self._robot.current_execution is None:
            raise NoActiveExecutionError(
                "Nenhuma execução em andamento - abra uma com @robot.execution ou robot.start_execution() "
                "antes de consumir a fila"
            )
        response = self._robot._transport.call(ClientEvent.QUEUE_NEXT, {"queueId": queue_id} if queue_id else {})
        if not response or not response.get("taskId"):
            # No task can mean the queue is empty, paused, or the robot's operation window has
            # closed - in the last two, what's left waits there for later.
            self.stop_reason = _stop_reason(response)
            return None
        task = Task(self._robot, ClaimedTask.model_validate(response))
        logger.info("Task {} recebida (tentativa {})", task.id, task.attempts)
        return task

    def tasks(self, queue_id: str | None = None) -> Iterator[Task]:
        """Each pending task, until the queue is empty or the robot is stopping.

        A task left without an outcome is not reported for you - it goes back to the queue once
        its lease runs out, and a warning says so.
        """
        task: Task | None = None
        try:
            while not self._robot.stopping:
                task = self.next(queue_id)
                if task is None:
                    logger.info(self.stop_reason or "Fila esvaziada")
                    return
                yield task
                _warn_if_unreported(task)
                task = None
        finally:
            # Left the loop early (break, an exception) with a task still in hand.
            if task is not None:
                _warn_if_unreported(task)


def _stop_reason(response: dict[str, Any] | None) -> str | None:
    if response and response.get("paused"):
        return "Fila pausada na plataforma - as tasks restantes ficam para depois"
    if response and response.get("outsideWindow"):
        return "Robô fora da janela de operação - as tasks restantes ficam para a próxima janela"
    return None


def _warn_if_unreported(task: Task) -> None:
    if not task.reported:
        logger.warning(
            "A task {} ficou sem resultado (success/warning/failure) e volta para a fila quando o lease vencer",
            task.id,
        )
