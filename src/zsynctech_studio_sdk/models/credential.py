"""Credential data returned by the platform's credential vault. Mirrors `CredentialResponseDto`
and `RevealCredentialValueResponseDto`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import SdkBaseModel
from .enums import CredentialStatus, CredentialType


class CredentialInfo(SdkBaseModel):
    """Metadata about a credential - never includes the decrypted value itself.

    Returned by `CredentialManager.rotate()` and `set_status()`; use `reveal()` to get the
    actual secret.
    """

    id: str
    name: str
    folder_id: str
    type: CredentialType
    expires_at: datetime | None = None
    current_version: int
    current_version_created_at: datetime
    status: CredentialStatus
    status_reason: str | None = None
    status_changed_at: datetime | None = None
    status_changed_by_label: str | None = None
    created_by_label: str | None = None
    created_at: datetime
    updated_at: datetime


class RevealedCredential(SdkBaseModel):
    """The decrypted value of a credential, as returned by `CredentialManager.reveal()`.

    `value`'s shape depends on `type`: a `str` for TEXT, a `dict[str, str]` for KEY_VALUE, or
    any JSON-compatible value for JSON. `status` is the credential's at the time of the reveal -
    always ACTIVE in what `reveal()` returns (see `CredentialNotActiveError`); `None` from a
    platform that doesn't say it.
    """

    credential_id: str
    version_number: int
    type: CredentialType
    value: Any
    status: CredentialStatus | None = None
    revealed_at: datetime
