"""Executions: one run of a robot, as the platform shows it.

`Execution` is the open run itself - observe it, report tasks on it, finish it. `ExecutionScope`
is what `robot.execution(...)` returns: the same thing as a decorator or a `with` block, opening
an execution on the way in and always closing it on the way out.

One execution can be open at a time per connection, mirroring what the gateway enforces
server-side (it tracks a single execution per socket).
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from .exceptions import NoActiveExecutionError
from .loggers import logger
from .models.enums import ExecutionFinishStatus, TaskStatus
from .models.execution import ExecutionFinishResult
from .models.task import TaskItem
from .protocol import ClientEvent

if TYPE_CHECKING:
    from .robot import Robot

P = ParamSpec("P")
R = TypeVar("R")

# An observation is short text on the platform; a traceback-sized exception message isn't.
_FAILURE_OBSERVATION_MAX = 500


class Execution:
    """An open execution. Reports tasks and observations until finished, then refuses more."""

    def __init__(self, robot: Robot, execution_id: str) -> None:
        self._robot = robot
        self.id = execution_id
        self.finished = False

    def observe(self, observation: str) -> None:
        """Replace the observation shown on the platform - e.g. to narrate progress
        ("processando 3/50"). As many times as needed while it runs."""
        self._require_open()
        self._robot._transport.call(
            ClientEvent.EXECUTION_OBSERVATION, {"executionId": self.id, "observation": observation}
        )
        logger.debug("Observação da execução {} atualizada: {}", self.id, observation)

    def report(
        self,
        *,
        status: TaskStatus,
        external_id: str | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        attempts: int = 1,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Report one task of the robot's own source (not the platform queue). The times are
        filled in with now when not given."""
        item = TaskItem(
            external_id=external_id,
            status=status,
            message=message,
            result=result,
            payload=payload,
            attempts=attempts,
            **({"started_at": started_at} if started_at else {}),
            **({"finished_at": finished_at} if finished_at else {}),
        )
        self.report_many([item])

    def report_many(self, items: list[TaskItem]) -> None:
        """Report several tasks in one go - cheaper than one `report()` each for big batches."""
        if not items:
            return
        self._require_open()
        payload = {"executionId": self.id, "tasks": [item.to_wire() for item in items]}
        self._robot._transport.emit(ClientEvent.EXECUTION_TASK, payload)
        logger.debug("{} task(s) reportada(s) na execução {}", len(items), self.id)

    def finish(self, *, observation: str | None = None) -> ExecutionFinishResult:
        """Close it as COMPLETED. `observation` replaces the one it was started with, e.g. to
        record what actually happened ("fila vazia, nada a processar")."""
        return self._close(ExecutionFinishStatus.COMPLETED, observation)

    def fail(self, *, observation: str | None = None) -> ExecutionFinishResult:
        """Close it as FAILED, saying why in `observation`."""
        return self._close(ExecutionFinishStatus.FAILED, observation)

    def _close(self, status: ExecutionFinishStatus, observation: str | None) -> ExecutionFinishResult:
        self._require_open()
        payload: dict[str, object] = {"executionId": self.id, "status": status.value}
        if observation is not None:
            payload["observation"] = observation
        response = self._robot._transport.call(ClientEvent.EXECUTION_FINISH, payload)
        result = ExecutionFinishResult.model_validate(response)
        self.finished = True
        self._robot._execution_closed(self)
        logger.info("Execução {} finalizada com status {}", self.id, status.value)
        return result

    def _require_open(self) -> None:
        if self.finished:
            raise NoActiveExecutionError(f"A execução {self.id} já foi finalizada")

    # A started execution can also close itself on the way out of a `with` block.
    def __enter__(self) -> Execution:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _close_on_exit(self, exc)


def _close_on_exit(execution: Execution, exc: BaseException | None) -> None:
    """COMPLETED on a clean exit, FAILED (saying why) on an exception - unless the code inside
    already finished it by hand."""
    if execution.finished:
        return
    if exc is None:
        execution.finish()
        return
    logger.opt(exception=exc).error("Execução {} interrompida por uma exceção - marcando como FAILED", execution.id)
    reason = f"{type(exc).__name__}: {exc}"
    execution.fail(observation=reason[:_FAILURE_OBSERVATION_MAX])


class ExecutionScope:
    """What `robot.execution(...)` returns: a decorator and a `with` block in one.

        @robot.execution(observation="Boletos do dia")
        def main(): ...

        with robot.execution(observation="Boletos do dia") as execution: ...

    As a decorator, every call of the function is an execution of its own.
    """

    def __init__(self, robot: Robot, *, observation: str | None, total: int | None) -> None:
        self._robot = robot
        self._observation = observation
        self._total = total
        self._execution: Execution | None = None

    def __enter__(self) -> Execution:
        self._execution = self._robot.start_execution(observation=self._observation, total=self._total)
        return self._execution

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        execution, self._execution = self._execution, None
        if execution is not None:
            _close_on_exit(execution, exc)

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def run(*args: P.args, **kwargs: P.kwargs) -> R:
            # A fresh scope per call: the same decorated function may run again later.
            with ExecutionScope(self._robot, observation=self._observation, total=self._total):
                return func(*args, **kwargs)

        return run
