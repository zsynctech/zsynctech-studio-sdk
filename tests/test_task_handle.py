import pytest

from zsynctech_studio_sdk.models.enums import TaskStatus
from zsynctech_studio_sdk.models.execution import Task
from zsynctech_studio_sdk.task_handle import TaskHandle


def _handle() -> tuple[TaskHandle, list[Task]]:
    reported: list[Task] = []
    handle = TaskHandle(report=reported.append, external_id="row-1", attempts=2)
    return handle, reported


def test_success_reports_a_success_task_with_the_given_external_id_and_attempts() -> None:
    handle, reported = _handle()

    handle.success(message="ok")

    assert len(reported) == 1
    task = reported[0]
    assert task.status == TaskStatus.SUCCESS
    assert task.external_id == "row-1"
    assert task.attempts == 2
    assert task.message == "ok"
    assert task.started_at
    assert task.finished_at


def test_warning_reports_a_warning_task() -> None:
    handle, reported = _handle()

    handle.warning(message="careful")

    assert reported[0].status == TaskStatus.WARNING
    assert reported[0].message == "careful"


def test_error_reports_a_failure_task() -> None:
    handle, reported = _handle()

    handle.error(message="boom", result={"code": 500})

    assert reported[0].status == TaskStatus.FAILURE
    assert reported[0].message == "boom"
    assert reported[0].result == {"code": 500}


def test_reporting_twice_raises() -> None:
    handle, _reported = _handle()
    handle.success()

    with pytest.raises(RuntimeError):
        handle.error(message="too late")


def test_context_manager_reports_success_on_clean_exit() -> None:
    handle, reported = _handle()

    with handle:
        pass

    assert len(reported) == 1
    assert reported[0].status == TaskStatus.SUCCESS


def test_context_manager_reports_error_on_exception_and_does_not_suppress_it() -> None:
    handle, reported = _handle()

    with pytest.raises(ValueError, match="kaboom"), handle:
        raise ValueError("kaboom")

    assert len(reported) == 1
    assert reported[0].status == TaskStatus.FAILURE
    assert reported[0].message == "kaboom"


def test_context_manager_does_not_double_report_when_closed_explicitly_inside_the_block() -> None:
    handle, reported = _handle()

    with handle as task:
        task.success(message="done early")

    assert len(reported) == 1
    assert reported[0].message == "done early"
