"""Pure model/serialization tests - no socket connection involved."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from zsynctech_studio_sdk.models import ClaimedTask, RobotClientConfig, TaskItem, TaskStatus


def test_config_defaults_are_filled_in() -> None:
    config = RobotClientConfig(api_key="abc123")

    assert config.backend_url == "http://localhost:5000"
    assert config.hostname
    assert config.heartbeat_interval == 15.0
    assert config.ack_timeout == 8.0


def test_config_strips_trailing_slash_from_backend_url() -> None:
    config = RobotClientConfig(api_key="abc123", backend_url="http://localhost:5000/")

    assert config.backend_url == "http://localhost:5000"


def test_config_rejects_blank_api_key() -> None:
    with pytest.raises(ValidationError):
        RobotClientConfig(api_key="   ")


def test_claimed_task_parses_camel_case_payload() -> None:
    payload = {"taskId": "task-1", "externalId": "row-42", "attempts": 2, "payload": {"foo": "bar"}}

    task = ClaimedTask.model_validate(payload)

    assert task.task_id == "task-1"
    assert task.external_id == "row-42"
    assert task.attempts == 2
    assert task.payload == {"foo": "bar"}


def test_task_item_serializes_to_camel_case_wire_payload() -> None:
    item = TaskItem(
        external_id="row-1",
        status=TaskStatus.SUCCESS,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:05+00:00",
    )

    wire = item.to_wire()

    assert wire["externalId"] == "row-1"
    assert wire["status"] == "SUCCESS"
    assert "startedAt" in wire and "finishedAt" in wire
    assert "external_id" not in wire
