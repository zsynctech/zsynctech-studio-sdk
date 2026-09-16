"""Execution lifecycle: `execution:start` / `execution:task` / `execution:finish`.

One execution can be open at a time per connection, mirroring what the gateway itself
enforces server-side (it tracks a single `client.data.executionId` per socket).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from .connection import SocketConnection
from .exceptions import NoActiveExecutionError
from .loggers import logger
from .models.enums import ExecutionFinishStatus
from .models.execution import ExecutionFinishResult, ExecutionStartResult
from .models.task import TaskItem
from .protocol import ClientEvent


class ExecutionManager:
    """Starts, reports on, and finishes executions over a `SocketConnection`."""

    def __init__(self, connection: SocketConnection) -> None:
        self._connection = connection
        self._execution_id: str | None = None

    @property
    def execution_id(self) -> str | None:
        return self._execution_id

    @property
    def is_running(self) -> bool:
        return self._execution_id is not None

    def start(self, *, observation: str | None = None, total: int | None = None) -> str:
        """Open a new execution and return its id. Fails if one is already open."""
        if self.is_running:
            raise RuntimeError(
                f"Já existe uma execução em andamento ({self._execution_id}); finalize-a antes de iniciar outra"
            )

        payload: dict[str, object] = {}
        if observation is not None:
            payload["observation"] = observation
        if total is not None:
            payload["total"] = total

        response = self._connection.call(ClientEvent.EXECUTION_START, payload)
        result = ExecutionStartResult.model_validate(response)
        self._execution_id = result.execution_id
        logger.info("Execução iniciada: {}", self._execution_id)
        return self._execution_id

    def report_tasks(self, tasks: list[TaskItem]) -> None:
        """Report a batch of task outcomes directly (not via the queue), e.g. for robots that
        process their own input source instead of consuming a platform queue."""
        if not tasks:
            return
        self._require_execution()
        payload = {"executionId": self._execution_id, "tasks": [task.to_wire() for task in tasks]}
        self._connection.emit(ClientEvent.EXECUTION_TASK, payload)
        logger.debug("{} task(s) reportada(s) na execução {}", len(tasks), self._execution_id)

    def finish(
        self,
        status: ExecutionFinishStatus = ExecutionFinishStatus.COMPLETED,
        *,
        observation: str | None = None,
    ) -> ExecutionFinishResult:
        """Close the current execution with `status`.

        `observation` replaces the one set in `start()`, e.g. to record the actual outcome
        ("fila vazia, nada a processar") instead of a generic description picked before any
        work happened.
        """
        self._require_execution()
        payload: dict[str, object] = {"executionId": self._execution_id, "status": status.value}
        if observation is not None:
            payload["observation"] = observation
        response = self._connection.call(ClientEvent.EXECUTION_FINISH, payload)
        result = ExecutionFinishResult.model_validate(response)
        logger.info("Execução {} finalizada com status {}", result.execution_id, result.status.value)
        self._execution_id = None
        return result

    def update_observation(self, observation: str) -> None:
        """Update the current execution's observation without finishing it - use to narrate
        progress ("processando 3/50") as the execution goes along. Can be called as many
        times as needed."""
        self._require_execution()
        self._connection.call(
            ClientEvent.EXECUTION_OBSERVATION,
            {"executionId": self._execution_id, "observation": observation},
        )
        logger.debug("Observação da execução {} atualizada: {}", self._execution_id, observation)

    def _require_execution(self) -> None:
        if not self.is_running:
            raise NoActiveExecutionError("Nenhuma execução em andamento - chame start() primeiro")

    @contextmanager
    def run(self, *, observation: str | None = None, total: int | None = None) -> Generator[str]:
        """Start an execution, yield its id, and always finish it: COMPLETED on a clean exit,
        FAILED (and re-raised) if the body raises.

            with client.execution.run(observation="Fatura mensal") as execution_id:
                ...
        """
        execution_id = self.start(observation=observation, total=total)
        try:
            yield execution_id
        except Exception:
            logger.exception("Execução {} interrompida por uma exceção - marcando como FAILED", execution_id)
            self.finish(ExecutionFinishStatus.FAILED)
            raise
        else:
            self.finish(ExecutionFinishStatus.COMPLETED)
