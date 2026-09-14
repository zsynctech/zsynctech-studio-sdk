import pytest
from pydantic import ValidationError

from zsynctech_studio_sdk.models.enums import TaskStatus
from zsynctech_studio_sdk.models.execution import ExecutionFinishResult, ExecutionStartResult, Task


def test_task_accepts_a_valid_status() -> None:
    task = Task(status=TaskStatus.SUCCESS)
    assert task.status == TaskStatus.SUCCESS
    assert task.attempts == 1
    assert task.started_at
    assert task.finished_at


def test_task_rejects_an_invalid_status() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate({"status": "PENDING"})


def test_task_rejects_zero_attempts() -> None:
    with pytest.raises(ValidationError):
        Task(status=TaskStatus.FAILURE, attempts=0)


def test_task_serializes_to_camel_case_wire_shape() -> None:
    task = Task(status=TaskStatus.WARNING, external_id="task-1", started_at="a", finished_at="b")
    dumped = task.model_dump(by_alias=True)
    assert dumped["externalId"] == "task-1"
    assert dumped["startedAt"] == "a"
    assert dumped["finishedAt"] == "b"


def test_execution_start_result_parses_camel_case_ack() -> None:
    result = ExecutionStartResult.model_validate({"executionId": "exec-1"})
    assert result.execution_id == "exec-1"


def test_execution_finish_result_uppercases_status() -> None:
    result = ExecutionFinishResult.model_validate({"executionId": "exec-1", "status": "completed"})
    assert result.status == "COMPLETED"
