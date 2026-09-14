"""Public façade: :class:`RobotClient`, the SDK's single entry point.

Composes :class:`~zsynctech_studio_sdk.transport.socket_transport.SocketTransport` for the
connection lifecycle and protocol calls; carries no wire-format or Socket.IO details itself.
"""

from collections.abc import Callable, Sequence
from typing import Any

from zsynctech_studio_sdk.exceptions import ExecutionError, NotConnectedError
from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.models.connection import ConnectResult
from zsynctech_studio_sdk.models.enums import ExecutionFinishStatus, RobotInstanceStatus, TaskStatus
from zsynctech_studio_sdk.models.execution import ExecutionFinishResult, ExecutionStartResult, Task
from zsynctech_studio_sdk.models.queue import ClaimedTask, TaskResultAck
from zsynctech_studio_sdk.task_handle import TaskHandle
from zsynctech_studio_sdk.transport.socket_transport import SocketTransport
from zsynctech_studio_sdk.utils.logging import get_logger

OnStartCallback = Callable[[], None]

logger = get_logger(__name__)


class RobotClient:
    """Connects one robot instance to the platform and speaks the full `/robot` protocol.

    Typical usage::

        client = RobotClient(api_key="...", base_url="https://studio.zsynctech.com.br")

        @client.on_start
        def run_automation() -> None:
            client.start_execution(total=100)
            ...
            client.finish_execution()

        with client:
            client.wait_forever()  # or your own event loop / sleep loop

    The heartbeat required to stay within the platform's fixed 30-second instance timeout is
    sent automatically in the background from :meth:`connect` until :meth:`disconnect` -
    callers never need to call it themselves.
    """

    def __init__(
        self,
        config: RobotClientConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: SocketTransport | None = None,
        **config_kwargs: Any,
    ) -> None:
        """Create a client, either from a ready :class:`RobotClientConfig` or its raw fields.

        Args:
            config: A pre-built config. When given, ``api_key``/``base_url``/``config_kwargs``
                are ignored.
            api_key: The robot's API key. Required when ``config`` is omitted.
            base_url: Platform origin, e.g. ``https://studio.zsynctech.com.br``. Required when
                ``config`` is omitted.
            transport: Inject a pre-built transport - intended for tests, which use this to
                supply a fake instead of a real `SocketTransport` that would open a socket.
            **config_kwargs: Any other :class:`RobotClientConfig` field (``hostname``,
                ``version``, ``platform``, ``heartbeat_interval_seconds``).
        """
        if config is None:
            if not api_key or not base_url:
                raise ValueError("Provide either `config` or both `api_key` and `base_url`")
            config = RobotClientConfig(api_key=api_key, base_url=base_url, **config_kwargs)
        self._config = config
        self._on_start_callback: OnStartCallback | None = None
        self._transport = transport or SocketTransport(config, on_start=self._dispatch_start)
        self._connect_result: ConnectResult | None = None
        self._current_execution_id: str | None = None

    def on_start(self, callback: OnStartCallback) -> OnStartCallback:
        """Register the callback invoked when the platform pushes `automation:start`.

        Usable as a decorator (see class docstring) or called directly:
        ``client.on_start(my_function)``.
        """
        self._on_start_callback = callback
        return callback

    def _dispatch_start(self) -> None:
        if self._on_start_callback is None:
            logger.warning("Received automation:start but no on_start callback is registered")
            return
        self._on_start_callback()

    def connect(self, timeout: float = 10.0) -> ConnectResult:
        """Open the connection, blocking until the platform confirms or rejects it.

        Raises:
            AuthenticationError: Invalid API key or inactive robot.
            ConcurrencyLimitError: `max_concurrency` instances are already connected.
        """
        self._connect_result = self._transport.connect(timeout=timeout)
        return self._connect_result

    def disconnect(self) -> None:
        """Stop the heartbeat loop and close the connection."""
        self._transport.disconnect()
        self._connect_result = None
        self._current_execution_id = None

    def __enter__(self) -> "RobotClient":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.disconnect()

    @property
    def connected(self) -> bool:
        """Whether the transport currently holds an open connection."""
        return self._transport.connected

    @property
    def instance_id(self) -> str:
        """This connection's server-assigned instance id. Requires :meth:`connect` first."""
        return self._require_connect_result().instance_id

    @property
    def instance_code(self) -> str:
        """This connection's human-readable instance code. Requires :meth:`connect` first."""
        return self._require_connect_result().instance_code

    def _require_connect_result(self) -> ConnectResult:
        if self._connect_result is None:
            raise NotConnectedError("Call connect() before using the robot protocol")
        return self._connect_result

    def set_status(self, status: RobotInstanceStatus) -> None:
        """Manually report this instance's status. The SDK does not do this automatically."""
        self._require_connect_result()
        self._transport.call("status", {"status": status.value})

    def start_execution(self, total: int | None = None, observation: str | None = None) -> str:
        """Open a new execution and remember its id for subsequent calls.

        Returns:
            The new execution's id.
        """
        self._require_connect_result()
        payload: dict[str, Any] = {}
        if total is not None:
            payload["total"] = total
        if observation is not None:
            payload["observation"] = observation
        ack = self._transport.call("execution:start", payload)
        result = ExecutionStartResult.model_validate(ack)
        self._current_execution_id = result.execution_id
        return result.execution_id

    def report_tasks(self, tasks: Sequence[Task], execution_id: str | None = None) -> None:
        """Report a batch of task outcomes for the current (or given) execution.

        Rate-limited server-side to 300 calls/second - batch several :class:`Task`
        instances per call rather than calling this once per task.
        """
        self._require_connect_result()
        resolved_execution_id = self._resolve_execution_id(execution_id)
        payload = {
            "executionId": resolved_execution_id,
            "tasks": [task.model_dump(by_alias=True) for task in tasks],
        }
        self._transport.emit("execution:task", payload)

    def start_task(self, external_id: str | None = None, attempts: int = 1) -> TaskHandle:
        """Open a task tracked against the current execution, returning a handle to report it.

        A friendlier alternative to building a :class:`~zsynctech_studio_sdk.models.execution.Task`
        and calling :meth:`report_tasks` yourself for the common one-task-at-a-time case::

            task = client.start_task(external_id="row-42")
            try:
                ...
                task.success()
            except Exception as exc:
                task.error(message=str(exc))

        Reporting a batch of several tasks at once (e.g. after processing a chunk) still calls
        for :meth:`report_tasks` directly - this returns one handle per task.
        """
        self._require_connect_result()
        return TaskHandle(
            report=lambda task: self.report_tasks([task]), external_id=external_id, attempts=attempts
        )

    def finish_execution(
        self,
        status: ExecutionFinishStatus = ExecutionFinishStatus.COMPLETED,
        execution_id: str | None = None,
    ) -> ExecutionFinishResult:
        """Close out the current (or given) execution."""
        self._require_connect_result()
        resolved_execution_id = self._resolve_execution_id(execution_id)
        ack = self._transport.call(
            "execution:finish", {"executionId": resolved_execution_id, "status": status.value}
        )
        result = ExecutionFinishResult.model_validate(ack)
        if resolved_execution_id == self._current_execution_id:
            self._current_execution_id = None
        return result

    def claim_next_task(self, queue_id: str | None = None) -> ClaimedTask:
        """Claim the next pending task from the server-side queue, if any.

        Requires an execution already opened via :meth:`start_execution`. Check
        :attr:`ClaimedTask.has_task` on the result - an empty queue is a normal outcome, not
        an error.
        """
        self._require_connect_result()
        payload = {"queueId": queue_id} if queue_id else {}
        ack = self._transport.call("queue:next", payload)
        return ClaimedTask.model_validate(ack)

    def report_task_result(
        self,
        task_id: str,
        status: TaskStatus,
        message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> TaskResultAck:
        """Report the outcome of a task previously handed out by :meth:`claim_next_task`."""
        self._require_connect_result()
        payload: dict[str, Any] = {"taskId": task_id, "status": status.value}
        if message is not None:
            payload["message"] = message
        if result is not None:
            payload["result"] = result
        ack = self._transport.call("queue:task-result", payload)
        return TaskResultAck.model_validate(ack)

    def wait_forever(self) -> None:
        """Block the calling thread until the connection closes or Ctrl+C is pressed.

        Convenient for a simple robot script whose only job is to wait for
        `automation:start` pushes inside a ``with`` block - see the class docstring.
        Ctrl+C stops this cleanly (unlike blocking directly on the underlying Socket.IO
        client), letting the ``with`` block's `disconnect()` run afterward.
        """
        self._transport.wait()

    def _resolve_execution_id(self, execution_id: str | None) -> str:
        resolved = execution_id or self._current_execution_id
        if resolved is None:
            raise ExecutionError("No open execution - call start_execution() first or pass execution_id")
        return resolved


__all__ = ["OnStartCallback", "RobotClient", "TaskHandle"]
