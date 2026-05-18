"""
Execution context management.

Uses a ``ContextVar`` to propagate the current execution state to every
``@task``-decorated function invoked during a robot run.  Because the SDK
now communicates over synchronous HTTP (no event loop required), the context
holds direct references to the service layer instead of an asyncio loop.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.execution_service import ExecutionService
    from .services.task_service import TaskService


@dataclass
class ExecutionContext:
    """Holds all state needed to track a single execution run.

    An instance is created by the :class:`~zsynctech_studio_sdk.runner.RobotRunner`
    when a pending execution is claimed, stored in ``_execution_context_var``,
    and then made available to every ``@task``-decorated function called during
    that execution.

    Attributes:
        execution_id:       UUID of the active execution.
        execution_service:  Service for execution lifecycle operations.
        task_service:       Service for task register/update operations.
        instance_code:      Short code of the automation instance, or ``None`` if unavailable.
        automation_name:    Display name of the automation, or ``None`` if unavailable.
    """

    execution_id: str
    execution_service: ExecutionService
    task_service: TaskService
    instance_code: str | None = field(default=None)
    automation_name: str | None = field(default=None)
    _task_counter: int = field(default=0, init=False, repr=False)
    task_observation: str | None = field(default=None, init=False, repr=False)
    execution_observation: str | None = field(default=None, init=False, repr=False)

    def next_task_order(self) -> int:
        """Return the current task index and advance the internal counter.

        Returns:
            Zero-based order index for the next task to be registered.
        """
        order = self._task_counter
        self._task_counter += 1
        return order


@dataclass
class OfflineExecutionContext:
    """Lightweight execution context used in offline (no-platform) runs.

    Activated by :class:`~zsynctech_studio_sdk.decorators.ExecutionWrapper`
    when the execution function is called directly (not via ``listener``).
    Exposes the same user-facing attributes as :class:`ExecutionContext` so
    that robot code can unconditionally read and write ``execution_observation``
    and ``task_observation`` without guarding against ``None``.

    Attributes:
        instance_code:   Always ``None`` in offline mode.
        automation_name: Always ``None`` in offline mode.
    """

    execution_id: str = field(default="offline")
    instance_code: str | None = field(default=None)
    automation_name: str | None = field(default=None)
    _task_counter: int = field(default=0, init=False, repr=False)
    task_observation: str | None = field(default=None, init=False, repr=False)
    execution_observation: str | None = field(default=None, init=False, repr=False)

    def next_task_order(self) -> int:
        """Return the current task index and advance the internal counter."""
        order = self._task_counter
        self._task_counter += 1
        return order


# -- ContextVar ----------------------------------------------------------------

_AnyContext = ExecutionContext | OfflineExecutionContext | None

_execution_context_var: ContextVar[_AnyContext] = ContextVar(
    "zsynctech_execution_context", default=None
)


def get_current_context() -> ExecutionContext | OfflineExecutionContext | None:
    """Return the active execution context, or ``None`` outside an execution.

    Returns:
        :class:`ExecutionContext` during a live platform run,
        :class:`OfflineExecutionContext` during an offline run, or
        ``None`` when called outside any execution.
    """
    return _execution_context_var.get()


def _set_context(ctx: _AnyContext) -> Token[_AnyContext]:
    """Internal - set the current context and return a reset token.

    Args:
        ctx: The context to activate (or ``None`` to clear).

    Returns:
        A reset token to pass to :func:`_reset_context`.
    """
    return _execution_context_var.set(ctx)


def _reset_context(token: Token[_AnyContext]) -> None:
    """Internal - restore the context to the state before the matching set call.

    Args:
        token: The token returned by :func:`_set_context`.
    """
    _execution_context_var.reset(token)
