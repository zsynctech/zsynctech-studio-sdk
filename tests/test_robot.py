"""Tests for the `Robot` API - a fake transport stands in for the socket, recording what would
be sent and answering the way the `/robot` gateway does."""

from __future__ import annotations

from typing import Any

import pytest

from zsynctech_studio_sdk import NoActiveExecutionError, Robot, RobotSDKError, Task, TaskStatus, TaskWarning
from zsynctech_studio_sdk.loggers import logger
from zsynctech_studio_sdk.models.robot import RobotConnection, RobotInfo

CONNECTION_INFO = RobotConnection.model_validate(
    {
        "id": "robot-1",
        "name": "Robô teste",
        "availability": "ACTIVE",
        "status": "ONLINE",
        "maxConcurrency": 1,
        "connectedInstanceCount": 1,
        "busyInstanceCount": 0,
        "instanceId": "instance-1",
        "instanceCode": "abc123",
    }
)


def queued(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"taskId": task_id, "externalId": f"ext-{task_id}", "attempts": 1, "payload": payload or {}}


class FakeTransport:
    """Records every call/emit and answers like the gateway: execution ids in sequence, the
    queued tasks one by one, then an empty queue."""

    def __init__(self, queue: list[dict[str, Any]] | None = None) -> None:
        self.queue = list(queue or [])
        self.connected = False
        self.stopping = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.waited = False
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.emits: list[tuple[str, dict[str, Any]]] = []
        self.handlers: list[Any] = []
        self._executions = 0

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def is_stopping(self) -> bool:
        return self.stopping

    def connect(self) -> RobotConnection:
        self.connect_calls += 1
        self.connected = True
        return CONNECTION_INFO

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def wait(self) -> None:
        self.waited = True

    def call(self, event: str, data: dict[str, Any], *, timeout: float | None = None) -> Any:
        self.calls.append((event, data))
        if event == "execution:start":
            self._executions += 1
            return {"executionId": f"exec-{self._executions}"}
        if event == "execution:finish":
            return {"executionId": data["executionId"], "status": data["status"]}
        if event == "queue:next":
            return self.queue.pop(0) if self.queue else None
        return {}

    def emit(self, event: str, data: dict[str, Any]) -> None:
        self.emits.append((event, data))

    def set_status(self, status: Any) -> RobotInfo:
        return RobotInfo.model_validate({**CONNECTION_INFO.model_dump(by_alias=True), "status": status.value})

    def on_automation_start(self, handler: Any) -> None:
        self.handlers.append(handler)

    def sent(self, event: str) -> list[dict[str, Any]]:
        return [data for name, data in self.calls + self.emits if name == event]


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def robot(transport: FakeTransport) -> Robot:
    return Robot("abc123", _transport=transport)


# -- connection --------------------------------------------------------------------------------


class TestConnection:
    def test_connects_only_when_something_needs_it(self, robot: Robot, transport: FakeTransport) -> None:
        assert transport.connect_calls == 0

        robot.start_execution()
        robot.current_execution.finish()  # type: ignore[union-attr]

        assert transport.connect_calls == 1

    def test_does_not_open_a_second_connection_while_one_is_up(self, robot: Robot, transport: FakeTransport) -> None:
        robot.start_execution().finish()
        robot.start_execution().finish()

        assert transport.connect_calls == 1

    def test_close_disconnects_once_and_is_safe_to_repeat(self, robot: Robot, transport: FakeTransport) -> None:
        robot.connect()
        robot.close()
        robot.close()

        assert transport.disconnect_calls == 1

    def test_close_without_ever_connecting_does_nothing(self, robot: Robot, transport: FakeTransport) -> None:
        robot.close()

        assert transport.disconnect_calls == 0

    def test_works_as_a_context_manager_for_whoever_prefers_it(self, robot: Robot, transport: FakeTransport) -> None:
        with robot as same:
            assert same is robot
            assert transport.connect_calls == 1

        assert transport.disconnect_calls == 1

    def test_from_env_reads_the_api_key_and_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZSYNC_API_KEY", "from-env")
        monkeypatch.setenv("ZSYNC_BACKEND_URL", "https://plataforma.exemplo")

        robot = Robot.from_env(_transport=FakeTransport())

        assert robot.config.api_key == "from-env"
        assert robot.config.backend_url == "https://plataforma.exemplo"

    def test_from_env_says_which_variable_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZSYNC_API_KEY", raising=False)

        with pytest.raises(RobotSDKError, match="ZSYNC_API_KEY"):
            Robot.from_env()


# -- executions --------------------------------------------------------------------------------


class TestExecution:
    def test_decorator_without_parentheses_starts_and_completes(self, robot: Robot, transport: FakeTransport) -> None:
        @robot.execution
        def main() -> str:
            assert robot.current_execution is not None
            return "feito"

        assert main() == "feito"
        assert transport.sent("execution:start") == [{}]
        assert transport.sent("execution:finish") == [{"executionId": "exec-1", "status": "COMPLETED"}]
        assert robot.current_execution is None

    def test_decorator_with_observation_and_total(self, robot: Robot, transport: FakeTransport) -> None:
        @robot.execution(observation="Boletos do dia", total=10)
        def main() -> None:
            pass

        main()

        assert transport.sent("execution:start") == [{"observation": "Boletos do dia", "total": 10}]

    def test_decorator_fails_the_execution_and_lets_the_error_through(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        @robot.execution
        def main() -> None:
            raise ValueError("portal fora do ar")

        with pytest.raises(ValueError, match="portal fora do ar"):
            main()

        [finish] = transport.sent("execution:finish")
        assert finish["status"] == "FAILED"
        assert "portal fora do ar" in finish["observation"]
        assert robot.current_execution is None

    def test_each_call_of_a_decorated_function_is_its_own_execution(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        @robot.execution
        def main() -> None:
            pass

        main()
        main()

        assert [f["executionId"] for f in transport.sent("execution:finish")] == ["exec-1", "exec-2"]

    def test_works_as_a_with_block(self, robot: Robot, transport: FakeTransport) -> None:
        with robot.execution(observation="Bloco") as execution:
            assert execution.id == "exec-1"
            assert robot.current_execution is execution

        assert transport.sent("execution:finish") == [{"executionId": "exec-1", "status": "COMPLETED"}]

    def test_an_execution_finished_by_hand_inside_is_not_finished_again(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        with robot.execution() as execution:
            execution.finish(observation="Nada a processar")

        assert transport.sent("execution:finish") == [
            {"executionId": "exec-1", "status": "COMPLETED", "observation": "Nada a processar"}
        ]

    def test_started_by_hand(self, robot: Robot, transport: FakeTransport) -> None:
        execution = robot.start_execution(observation="Manual")
        execution.observe("processando 3/50")
        execution.fail(observation="Deu ruim")

        assert transport.sent("execution:observation") == [{"executionId": "exec-1", "observation": "processando 3/50"}]
        assert transport.sent("execution:finish") == [
            {"executionId": "exec-1", "status": "FAILED", "observation": "Deu ruim"}
        ]

    def test_one_execution_at_a_time(self, robot: Robot) -> None:
        robot.start_execution()

        with pytest.raises(RobotSDKError, match="Já existe uma execução"):
            robot.start_execution()

    def test_a_finished_execution_refuses_more_work(self, robot: Robot) -> None:
        execution = robot.start_execution()
        execution.finish()

        with pytest.raises(NoActiveExecutionError):
            execution.observe("tarde demais")

    def test_reports_its_own_tasks_with_the_times_filled_in(self, robot: Robot, transport: FakeTransport) -> None:
        execution = robot.start_execution()
        execution.report(external_id="linha-1", status=TaskStatus.SUCCESS, result={"ok": True})

        [sent] = transport.sent("execution:task")
        [item] = sent["tasks"]
        assert sent["executionId"] == "exec-1"
        assert item["externalId"] == "linha-1"
        assert item["status"] == "SUCCESS"
        assert item["result"] == {"ok": True}
        assert item["startedAt"] and item["finishedAt"]


# -- queue -------------------------------------------------------------------------------------


class TestQueue:
    def test_hands_out_each_task_until_the_queue_is_empty(self) -> None:
        transport = FakeTransport(queue=[queued("t1", {"n": 1}), queued("t2", {"n": 2})])
        robot = Robot("abc123", _transport=transport)

        with robot.execution():
            seen = []
            for task in robot.queue.tasks():
                seen.append(task.payload)
                task.success(result={"n": task.payload["n"] * 10})

        assert seen == [{"n": 1}, {"n": 2}]
        assert transport.sent("queue:task-result") == [
            {"taskId": "t1", "status": "SUCCESS", "result": {"n": 10}},
            {"taskId": "t2", "status": "SUCCESS", "result": {"n": 20}},
        ]

    def test_next_returns_none_on_an_empty_queue(self, robot: Robot) -> None:
        with robot.execution():
            assert robot.queue.next() is None

    def test_needs_an_execution_and_says_how_to_open_one(self, robot: Robot) -> None:
        with pytest.raises(NoActiveExecutionError, match="@robot.execution"):
            robot.queue.next()

    def test_a_task_reports_one_outcome_only(self) -> None:
        transport = FakeTransport(queue=[queued("t1")])
        robot = Robot("abc123", _transport=transport)

        with robot.execution():
            task = robot.queue.next()
            assert task is not None
            task.warning(message="Dado parcial")
            with pytest.raises(RobotSDKError, match="já foi reportada"):
                task.success()

        assert transport.sent("queue:task-result") == [{"taskId": "t1", "status": "WARNING", "message": "Dado parcial"}]

    def test_warns_about_a_task_left_without_an_outcome(self, monkeypatch: pytest.MonkeyPatch) -> None:
        warnings: list[str] = []
        monkeypatch.setattr(logger, "warning", lambda message, *args: warnings.append(message.format(*args)))
        transport = FakeTransport(queue=[queued("t1"), queued("t2")])
        robot = Robot("abc123", _transport=transport)

        with robot.execution():
            for task in robot.queue.tasks():
                if task.id == "t2":
                    task.success()

        assert len(warnings) == 1
        assert "t1" in warnings[0]
        assert transport.sent("queue:task-result") == [{"taskId": "t2", "status": "SUCCESS"}]

    @pytest.mark.parametrize(
        ("answer", "reason"),
        [
            ({"taskId": None, "paused": True}, "pausada"),
            ({"taskId": None, "outsideWindow": True}, "janela de operação"),
            (None, "esvaziada"),
        ],
    )
    def test_ends_saying_why_there_is_no_more_work(
        self, monkeypatch: pytest.MonkeyPatch, answer: dict[str, Any] | None, reason: str
    ) -> None:
        """A paused queue or a closed window ends the loop just like an empty queue - the
        execution winds down and the rest waits - but the log says which it was."""
        infos: list[str] = []
        monkeypatch.setattr(logger, "info", lambda message, *args: infos.append(message.format(*args)))
        transport = FakeTransport(queue=[queued("t1"), *([answer] if answer else [])])
        robot = Robot("abc123", _transport=transport)

        handed = []
        with robot.execution():
            for task in robot.queue.tasks():
                task.success()
                handed.append(task.id)

        assert handed == ["t1"]
        assert any(reason in line for line in infos), infos

    def test_stops_handing_out_tasks_once_the_robot_is_stopping(self) -> None:
        transport = FakeTransport(queue=[queued("t1"), queued("t2")])
        robot = Robot("abc123", _transport=transport)

        with robot.execution():
            for task in robot.queue.tasks():
                task.success()
                transport.stopping = True

        assert [r["taskId"] for r in transport.sent("queue:task-result")] == ["t1"]


# -- @robot.task -------------------------------------------------------------------------------


class TestTaskDecorator:
    @pytest.fixture
    def transport(self) -> FakeTransport:
        return FakeTransport(queue=[queued("t1"), queued("t2"), queued("t3"), queued("t4")])

    def test_turns_a_return_into_success_and_an_error_into_failure(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        @robot.task
        def process(task: Task) -> Any:
            if task.id == "t1":
                return {"protocolo": "123"}
            if task.id == "t2":
                raise RuntimeError("CPF inválido")
            if task.id == "t3":
                raise TaskWarning("Dado parcial", result={"parcial": True})
            return "texto"

        with robot.execution():
            for task in robot.queue.tasks():
                process(task)

        assert transport.sent("queue:task-result") == [
            {"taskId": "t1", "status": "SUCCESS", "result": {"protocolo": "123"}},
            {"taskId": "t2", "status": "FAILURE", "message": "CPF inválido"},
            {"taskId": "t3", "status": "WARNING", "message": "Dado parcial", "result": {"parcial": True}},
            {"taskId": "t4", "status": "SUCCESS", "result": {"value": "texto"}},
        ]

    def test_does_not_report_again_what_the_function_already_reported(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        @robot.task
        def process(task: Task) -> None:
            task.warning(message="Revisar")

        with robot.execution():
            task = robot.queue.next()
            assert task is not None
            process(task)

        assert transport.sent("queue:task-result") == [{"taskId": "t1", "status": "WARNING", "message": "Revisar"}]

    def test_can_let_the_error_through_when_asked(self, robot: Robot, transport: FakeTransport) -> None:
        @robot.task(reraise=True)
        def process(task: Task) -> None:
            raise RuntimeError("pare tudo")

        with robot.execution():
            task = robot.queue.next()
            assert task is not None
            with pytest.raises(RuntimeError, match="pare tudo"):
                process(task)

        assert transport.sent("queue:task-result") == [{"taskId": "t1", "status": "FAILURE", "message": "pare tudo"}]

    def test_reports_items_of_its_own_source_on_the_execution(self, robot: Robot, transport: FakeTransport) -> None:
        @robot.task(external_id=lambda row: row["id"])
        def process(row: dict[str, Any]) -> dict[str, Any]:
            if row["id"] == "b":
                raise RuntimeError("linha inválida")
            return {"enviado": row["id"]}

        with robot.execution():
            for row in [{"id": "a"}, {"id": "b"}]:
                process(row)

        items = [item for sent in transport.sent("execution:task") for item in sent["tasks"]]
        assert [(i["externalId"], i["status"], i.get("result"), i.get("message")) for i in items] == [
            ("a", "SUCCESS", {"enviado": "a"}, None),
            ("b", "FAILURE", None, "linha inválida"),
        ]
        assert all(i["startedAt"] and i["finishedAt"] for i in items)


# -- service mode ------------------------------------------------------------------------------


class TestServe:
    def test_on_start_registers_the_handler_for_the_platform_button(
        self, robot: Robot, transport: FakeTransport
    ) -> None:
        @robot.on_start
        def main() -> None:
            pass

        assert transport.handlers == [main]

    def test_serve_connects_waits_and_closes(self, robot: Robot, transport: FakeTransport) -> None:
        robot.serve()

        assert (transport.connect_calls, transport.waited, transport.disconnect_calls) == (1, True, 1)

    def test_stopping_follows_the_connection(self, robot: Robot, transport: FakeTransport) -> None:
        assert robot.stopping is False
        transport.stopping = True
        assert robot.stopping is True
