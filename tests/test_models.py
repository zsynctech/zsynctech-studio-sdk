from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.factories import make_execution, make_page, make_task
from zsyncstudio.enums import ExecutionStatus, TaskStatus
from zsyncstudio.models import Execution, Page, Task, TaskCompletion, TaskSummary


def test_execution_from_api_parses_all_fields() -> None:
    execution = Execution.from_api(
        make_execution(status="COMPLETED", observation="ok", finishedAt="2026-07-30T12:05:00.000Z")
    )

    assert execution.status is ExecutionStatus.COMPLETED
    assert execution.observation == "ok"
    assert execution.started_at == datetime.fromisoformat("2026-07-30T12:00:00.000Z")
    assert execution.finished_at == datetime.fromisoformat("2026-07-30T12:05:00.000Z")
    assert execution.triggered_by is None


def test_task_from_api_parses_metadata() -> None:
    task = Task.from_api(make_task(metadata={"attempt": 1}, status="ERROR"))

    assert task.status is TaskStatus.ERROR
    assert task.metadata == {"attempt": 1}


def test_task_summary_from_api_handles_no_timed_tasks() -> None:
    summary = TaskSummary.from_api(
        {
            "total": 0,
            "success": 0,
            "error": 0,
            "warning": 0,
            "skipped": 0,
            "avgDurationMs": None,
            "totalDurationMs": 0,
            "fastestTask": None,
            "slowestTask": None,
        }
    )

    assert summary.fastest_task is None
    assert summary.slowest_task is None
    assert summary.avg_duration_ms is None


def test_page_from_api_builds_typed_items() -> None:
    page = Page.from_api(make_page(make_task()), Task)

    assert page.total_items == 1
    assert page.page_size == 20
    assert isinstance(page.data[0], Task)
    assert page.data[0].reference == "invoice-001"


def test_task_completion_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        TaskCompletion(reference="", status=TaskStatus.SUCCESS)


def test_task_completion_to_json_omits_unset_optional_fields() -> None:
    completion = TaskCompletion(reference="invoice-001", status=TaskStatus.SUCCESS)

    payload = completion.to_json()

    assert payload == {"reference": "invoice-001", "status": "SUCCESS"}


def test_task_completion_to_json_serializes_datetimes_as_isoformat() -> None:
    started = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)
    completion = TaskCompletion(
        reference="invoice-001",
        status=TaskStatus.WARNING,
        observation="parcial",
        metadata={"retries": 2},
        started_at=started,
        finished_at=started,
    )

    payload = completion.to_json()

    assert payload["startedAt"] == started.isoformat()
    assert payload["finishedAt"] == started.isoformat()
    assert payload["observation"] == "parcial"
    assert payload["metadata"] == {"retries": 2}
