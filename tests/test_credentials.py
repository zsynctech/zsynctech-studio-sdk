"""Tests for `CredentialManager` - HTTP is mocked, no network involved."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zsynctech_studio_sdk.credentials import CredentialManager
from zsynctech_studio_sdk.exceptions import CredentialRequestError
from zsynctech_studio_sdk.models import CredentialInfo, CredentialStatus, RevealedCredential, RobotClientConfig

CONFIG = RobotClientConfig(api_key="abc123", backend_url="http://localhost:5000")

CREDENTIAL_INFO_PAYLOAD = {
    "payload": {
        "id": "cred-1",
        "name": "Portal do fornecedor",
        "folderId": "folder-1",
        "type": "TEXT",
        "expiresAt": None,
        "currentVersion": 2,
        "currentVersionCreatedAt": "2026-01-01T00:00:00+00:00",
        "status": "ACTIVE",
        "statusReason": None,
        "statusChangedAt": None,
        "statusChangedByLabel": None,
        "createdByLabel": "admin@zsynctech.com.br",
        "createdAt": "2026-01-01T00:00:00+00:00",
        "updatedAt": "2026-01-01T00:00:00+00:00",
    }
}


def _mock_response(json_body: dict[str, Any], *, ok: bool = True, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.json.return_value = json_body
    response.text = str(json_body)
    return response


def test_reveal_builds_the_expected_url_and_body() -> None:
    manager = CredentialManager(CONFIG)
    reveal_payload = {
        "payload": {
            "credentialId": "cred-1",
            "versionNumber": 2,
            "type": "TEXT",
            "value": "s3cr3t",
            "revealedAt": "2026-01-01T00:00:00+00:00",
        }
    }

    with patch.object(manager._session, "request", return_value=_mock_response(reveal_payload)) as mock_request:
        result = manager.reveal("cred-1")

    mock_request.assert_called_once()
    called_method, called_url = mock_request.call_args.args
    assert called_method == "POST"
    assert called_url == "http://localhost:5000/api/v1/robot/credentials/cred-1/reveal"
    assert mock_request.call_args.kwargs["json"] == {"apiKey": "abc123"}
    assert isinstance(result, RevealedCredential)
    assert result.value == "s3cr3t"


def test_rotate_sends_value_and_optional_expires_at() -> None:
    manager = CredentialManager(CONFIG)
    mock_response = _mock_response(CREDENTIAL_INFO_PAYLOAD)

    with patch.object(manager._session, "request", return_value=mock_response) as mock_request:
        result = manager.rotate("cred-1", "novo-valor", expires_at="2027-01-01T00:00:00+00:00")

    body = mock_request.call_args.kwargs["json"]
    assert body == {"apiKey": "abc123", "value": "novo-valor", "expiresAt": "2027-01-01T00:00:00+00:00"}
    assert isinstance(result, CredentialInfo)
    assert result.current_version == 2


def test_block_sets_status_blocked_with_reason() -> None:
    manager = CredentialManager(CONFIG)
    mock_response = _mock_response(CREDENTIAL_INFO_PAYLOAD)

    with patch.object(manager._session, "request", return_value=mock_response) as mock_request:
        manager.block("cred-1", "Login rejeitado pelo site do fornecedor")

    called_method, called_url = mock_request.call_args.args
    assert called_method == "PATCH"
    assert called_url.endswith("/cred-1/status")
    assert mock_request.call_args.kwargs["json"] == {
        "apiKey": "abc123",
        "status": CredentialStatus.BLOCKED.value,
        "reason": "Login rejeitado pelo site do fornecedor",
    }


def test_non_ok_response_raises_credential_request_error_with_status_code() -> None:
    manager = CredentialManager(CONFIG)
    error_response = _mock_response({"message": "API key inválida"}, ok=False, status_code=401)

    with (
        patch.object(manager._session, "request", return_value=error_response),
        pytest.raises(CredentialRequestError) as exc_info,
    ):
        manager.reveal("cred-1")

    assert exc_info.value.status_code == 401
    assert "API key inválida" in str(exc_info.value)
