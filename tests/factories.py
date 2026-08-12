"""Fábricas de payloads JSON no formato exato retornado pela API do backend."""

from __future__ import annotations

from typing import Any

BASE_URL = "https://studio.test"
API_BASE_URL = f"{BASE_URL}/api/v1"
API_TOKEN = "zst_11111111-1111-1111-1111-111111111111.super-secret"
INSTANCE_ID = "11111111-1111-1111-1111-111111111111"
EXECUTION_ID = "22222222-2222-2222-2222-222222222222"
TASK_ID = "33333333-3333-3333-3333-333333333333"
SECRET_ID = "44444444-4444-4444-4444-444444444444"


def make_execution(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": EXECUTION_ID,
        "instanceId": INSTANCE_ID,
        "triggeredBy": None,
        "triggeredByApiToken": None,
        "triggeredBySchedule": None,
        "cancelledBy": None,
        "status": "RUNNING",
        "startedAt": "2026-07-30T12:00:00.000Z",
        "finishedAt": None,
        "observation": None,
        "totalTasks": None,
        "createdAt": "2026-07-30T12:00:00.000Z",
        "updatedAt": "2026-07-30T12:00:00.000Z",
    }
    data.update(overrides)
    return data


def make_task(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": TASK_ID,
        "executionId": EXECUTION_ID,
        "reference": "invoice-001",
        "status": "SUCCESS",
        "startedAt": "2026-07-30T12:00:00.000Z",
        "finishedAt": "2026-07-30T12:00:01.000Z",
        "observation": None,
        "metadata": None,
        "createdAt": "2026-07-30T12:00:00.000Z",
        "updatedAt": "2026-07-30T12:00:01.000Z",
    }
    data.update(overrides)
    return data


def make_secret_meta(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": SECRET_ID,
        "name": "api-credential",
        "type": "TEXT",
        "expiresAt": None,
        "expired": False,
        "currentVersion": 1,
        "status": "ACTIVE",
        "lockedAt": None,
        "createdAt": "2026-07-30T12:00:00.000Z",
        "updatedAt": "2026-07-30T12:00:00.000Z",
    }
    data.update(overrides)
    return data


def make_reveal_secret(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "secretId": SECRET_ID,
        "versionNumber": 1,
        "type": "TEXT",
        "value": "s3cr3t",
        "revealedAt": "2026-07-30T12:00:00.000Z",
    }
    data.update(overrides)
    return data


def make_page(item: dict[str, Any], *, total_items: int = 1) -> dict[str, Any]:
    return {
        "data": [item],
        "pagination": {
            "page": 1,
            "pageSize": 20,
            "totalItems": total_items,
            "totalPages": 1,
            "hasNextPage": False,
            "hasPreviousPage": False,
        },
    }


def make_error_body(
    status_code: int, message: str | list[str], *, path: str = "/executions/x"
) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "message": message,
        "timestamp": "2026-07-30T12:00:00.000Z",
        "path": path,
    }
