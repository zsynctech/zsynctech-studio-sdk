"""Credential vault access: reveal, rotate, and report the status of a credential.

REST-only (no socket involved) - see `robot-credential.controller.ts`. Authenticated the same
way as every other robot-facing endpoint: the `apiKey` travels in the request body, not a
header, since there's no browser session for CSRF to protect.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import requests

from .exceptions import CredentialRequestError
from .loggers import logger
from .models.config import RobotClientConfig
from .models.credential import CredentialInfo, RevealedCredential
from .models.enums import CredentialStatus
from .protocol import CREDENTIALS_PATH
from .utils import ensure_iso

ReportableCredentialStatus = Literal[CredentialStatus.EXPIRED]


class CredentialManager:
    """Reads and rotates credentials from the platform's vault over its REST API."""

    def __init__(self, config: RobotClientConfig) -> None:
        self._config = config
        self._base_url = f"{config.backend_url}{config.api_prefix}{CREDENTIALS_PATH}"
        self._session = requests.Session()

    def reveal(self, credential_id: str) -> RevealedCredential:
        """Decrypt and return the current value of an active credential."""
        response = self._post(f"/{credential_id}/reveal", {})
        return RevealedCredential.model_validate(response)

    def rotate(self, credential_id: str, value: Any, *, expires_at: datetime | str | None = None) -> CredentialInfo:
        """Create a new version of a credential with `value`.

        `value`'s expected shape depends on the credential's existing type: a `str` for TEXT,
        a `dict[str, str]` for KEY_VALUE, or any JSON-compatible value for JSON.
        """
        payload: dict[str, Any] = {"value": value}
        if expires_at is not None:
            payload["expiresAt"] = ensure_iso(expires_at)
        response = self._post(f"/{credential_id}/versions", payload)
        return CredentialInfo.model_validate(response)

    def set_status(self, credential_id: str, status: ReportableCredentialStatus, reason: str) -> CredentialInfo:
        """Report that a credential should be marked EXPIRED, with a reason."""
        response = self._patch(f"/{credential_id}/status", {"status": status.value, "reason": reason})
        return CredentialInfo.model_validate(response)

    def expire(self, credential_id: str, reason: str) -> CredentialInfo:
        """Convenience for `set_status(credential_id, CredentialStatus.EXPIRED, reason)`."""
        return self.set_status(credential_id, CredentialStatus.EXPIRED, reason)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        body = {"apiKey": self._config.api_key, **payload}
        try:
            response = self._session.request(method, url, json=body, timeout=self._config.ack_timeout)
        except requests.RequestException as exc:
            raise CredentialRequestError(f"Falha ao chamar {url}: {exc}") from exc

        if not response.ok:
            raise CredentialRequestError(_extract_error_message(response), status_code=response.status_code)

        data: dict[str, Any] = response.json()
        logger.debug("{} {} -> {}", method, url, response.status_code)
        result: dict[str, Any] = data.get("payload", data)
        return result


def _extract_error_message(response: requests.Response) -> str:
    """Nest's `HttpExceptionFilter` returns `{ message: string | string[], ... }` on error."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text}"
    message = body.get("message", response.text)
    if isinstance(message, list):
        message = "; ".join(str(m) for m in message)
    return f"HTTP {response.status_code}: {message}"
