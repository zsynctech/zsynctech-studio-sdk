"""`Robot`: the SDK's entry point.

Plain calls at the base, shortcuts on top - use whichever fits the script:

    from zsynctech_studio_sdk import Robot

    robot = Robot.from_env()

    @robot.task
    def process(task):
        return consult_portal(task.payload)          # returned -> SUCCESS, raised -> FAILURE

    @robot.execution(observation="Boletos do dia")
    def main():
        for task in robot.queue.tasks():
            process(task)

    main()

There's no connection to manage: it opens on the first call that needs it and closes when the
process exits. `robot.serve()` is only for waiting on the platform's "Iniciar" button.
"""

from __future__ import annotations

import atexit
import functools
import os
import threading
from collections.abc import Callable
from types import TracebackType
from typing import Any, ParamSpec, TypeVar, overload

from .connection import AutomationStartHandler, SocketConnection, Transport
from .credentials import CredentialManager
from .exceptions import NoActiveExecutionError, RobotSDKError, TaskWarning
from .execution import Execution, ExecutionScope
from .loggers import configure_logging, logger
from .models.config import RobotClientConfig
from .models.enums import RobotInstanceStatus, TaskStatus
from .models.execution import ExecutionStartResult
from .models.robot import RobotInfo
from .protocol import ClientEvent
from .queue import Queue, Task
from .utils import utc_now

P = ParamSpec("P")
R = TypeVar("R")

API_KEY_ENV = "ZSYNC_API_KEY"
BACKEND_URL_ENV = "ZSYNC_BACKEND_URL"


class Robot:
    """One robot instance on the platform: its executions, its queue and its credentials."""

    def __init__(self, api_key: str, *, backend_url: str = "http://localhost:5000", **config: Any) -> None:
        """`api_key` comes from the platform. Any other `RobotClientConfig` field can be passed
        too (e.g. `heartbeat_interval=10`)."""
        transport: Transport | None = config.pop("_transport", None)  # tests stand a fake in for the socket
        self.config = RobotClientConfig(api_key=api_key, backend_url=backend_url, **config)
        configure_logging(level=self.config.log_level)
        self._transport: Transport = transport or SocketConnection(self.config)
        self._connect_lock = threading.Lock()
        self._connected_once = False
        self._current: Execution | None = None
        self.queue = Queue(self)
        self.credentials = CredentialManager(self.config)

    @classmethod
    def from_env(cls, **config: Any) -> Robot:
        """Build it from `ZSYNC_API_KEY` and `ZSYNC_BACKEND_URL` (optional) - keeps the key out
        of the script."""
        api_key = os.environ.get(API_KEY_ENV)
        if not api_key:
            raise RobotSDKError(f"Defina a variável de ambiente {API_KEY_ENV} com a API key do robô")
        if BACKEND_URL_ENV in os.environ:
            config.setdefault("backend_url", os.environ[BACKEND_URL_ENV])
        return cls(api_key, **config)

    # -- connection ------------------------------------------------------------------------------

    def connect(self) -> None:
        """Open the connection now instead of on the first call that needs it."""
        self._ensure_connected()

    def close(self) -> None:
        """Close the connection, if one was opened. Safe to call more than once - and called by
        itself when the process exits."""
        with self._connect_lock:
            if not self._connected_once:
                return
            self._connected_once = False
        self._transport.disconnect()

    def _ensure_connected(self) -> None:
        # Only the first time: a connection that drops later is the transport's to bring back
        # (it reconnects by itself), not a reason to open a second one.
        with self._connect_lock:
            if self._connected_once:
                return
            logger.info("Conectando em {} como '{}'...", self.config.backend_url, self.config.hostname)
            self._transport.connect()
            self._connected_once = True
        atexit.register(self.close)

    @property
    def stopping(self) -> bool:
        """True once the connection is closed for good (Ctrl+C, `close()`, reconnection giving
        up). A long loop should check it between items - `queue.tasks()` already does."""
        return self._transport.is_stopping

    def set_status(self, status: RobotInstanceStatus) -> RobotInfo:
        """Report this instance as ONLINE or BUSY by hand."""
        self._ensure_connected()
        return self._transport.set_status(status)

    def __enter__(self) -> Robot:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- executions ------------------------------------------------------------------------------

    @property
    def current_execution(self) -> Execution | None:
        """The execution open right now, if any."""
        return self._current

    def start_execution(self, *, observation: str | None = None, total: int | None = None) -> Execution:
        """Open an execution by hand - `finish()` or `fail()` it when done. `total`, if known,
        lets the platform show the progress."""
        if self._current is not None:
            raise RobotSDKError(f"Já existe uma execução em andamento ({self._current.id}); finalize-a antes")
        self._ensure_connected()
        payload: dict[str, object] = {}
        if observation is not None:
            payload["observation"] = observation
        if total is not None:
            payload["total"] = total
        response = self._transport.call(ClientEvent.EXECUTION_START, payload)
        self._current = Execution(self, ExecutionStartResult.model_validate(response).execution_id)
        logger.info("Execução iniciada: {}", self._current.id)
        return self._current

    def _execution_closed(self, execution: Execution) -> None:
        if self._current is execution:
            self._current = None

    @overload
    def execution(self, func: Callable[P, R], /) -> Callable[P, R]: ...

    @overload
    def execution(self, /, *, observation: str | None = None, total: int | None = None) -> ExecutionScope: ...

    def execution(
        self,
        func: Callable[P, R] | None = None,
        /,
        *,
        observation: str | None = None,
        total: int | None = None,
    ) -> Callable[P, R] | ExecutionScope:
        """An execution around a function or a block - COMPLETED when it ends, FAILED (and the
        error let through) when it raises:

            @robot.execution
            def main(): ...

            @robot.execution(observation="Boletos do dia")
            def main(): ...

            with robot.execution(observation="Boletos do dia") as execution: ...
        """
        scope = ExecutionScope(self, observation=observation, total=total)
        return scope(func) if func is not None else scope

    # -- tasks -----------------------------------------------------------------------------------

    @overload
    def task(self, func: Callable[..., Any], /) -> Callable[..., Any]: ...

    @overload
    def task(
        self, /, *, external_id: Callable[[Any], str | None] | None = None, reraise: bool = False
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    def task(
        self,
        func: Callable[..., Any] | None = None,
        /,
        *,
        external_id: Callable[[Any], str | None] | None = None,
        reraise: bool = False,
    ) -> Callable[..., Any]:
        """Reports the outcome of the function it decorates, from how it ended: returned ->
        SUCCESS (the value as the result), `TaskWarning` -> WARNING, any other error -> FAILURE.

        Called with a queue `Task`, the outcome goes to that task - unless the function already
        reported one. Called with anything else (an item of the robot's own source), it's
        reported on the current execution, `external_id` saying how to name it:

            @robot.task(external_id=lambda row: row["id"])
            def send(row): ...

        Errors are reported, logged and not let through, so a loop moves on to the next item;
        `reraise=True` lets them through after reporting.
        """

        def decorate(target: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(target)
            def run(item: Any, *args: Any, **kwargs: Any) -> Any:
                outcome = _Outcome(self, item, external_id)
                try:
                    value = target(item, *args, **kwargs)
                except TaskWarning as warning:
                    outcome.report(TaskStatus.WARNING, message=warning.message, result=warning.result)
                    if reraise:
                        raise
                    return None
                except Exception as error:
                    logger.opt(exception=error).error("Task {} falhou", outcome.name)
                    outcome.report(TaskStatus.FAILURE, message=str(error))
                    if reraise:
                        raise
                    return None
                outcome.report(TaskStatus.SUCCESS, result=_as_result(value))
                return value

            return run

        return decorate(func) if func is not None else decorate

    # -- the platform's "Iniciar" button ---------------------------------------------------------

    def on_start(self, handler: AutomationStartHandler) -> AutomationStartHandler:
        """Run `handler` (on its own thread) whenever the platform's "Iniciar" is pressed for
        this robot. Usable as a decorator; only reached while `serve()` is running."""
        self._transport.on_automation_start(handler)
        return handler

    def serve(self) -> None:
        """Wait for the platform's "Iniciar" (see `on_start`) until Ctrl+C or the connection
        closes for good. Only for a robot that runs on demand - a script that runs on its own
        schedule doesn't need it."""
        self._ensure_connected()
        logger.info("Aguardando a plataforma (Ctrl+C para encerrar)...")
        try:
            self._transport.wait()
        except KeyboardInterrupt:
            logger.info("Encerrando por solicitação do usuário (Ctrl+C)...")
        finally:
            self.close()


class _Outcome:
    """Where `@robot.task` reports to: the queue task itself, or the current execution for an
    item of the robot's own source."""

    def __init__(self, robot: Robot, item: Any, external_id: Callable[[Any], str | None] | None) -> None:
        self._robot = robot
        self._item = item
        self._started_at = utc_now()
        self.name = item.id if isinstance(item, Task) else (external_id(item) if external_id else None)

    def report(self, status: TaskStatus, *, message: str | None = None, result: dict[str, Any] | None = None) -> None:
        if isinstance(self._item, Task):
            if not self._item.reported:  # the function may have reported it already
                self._item._report(status, message, result)
            return
        execution = self._robot.current_execution
        if execution is None:
            raise NoActiveExecutionError(
                "Nenhuma execução em andamento - chame a função de @robot.task dentro de @robot.execution"
            )
        execution.report(
            status=status,
            external_id=self.name,
            message=message,
            result=result,
            started_at=self._started_at,
            finished_at=utc_now(),
        )


def _as_result(value: Any) -> dict[str, Any] | None:
    """A task's result is an object; anything else returned is kept under `value`."""
    if value is None or isinstance(value, dict):
        return value
    return {"value": value}
