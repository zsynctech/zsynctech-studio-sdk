"""Small, reusable helpers with no dependency on the socket connection or the client facade.

Anything here is pure and side-effect free (besides reading the local machine's hostname), so
it's safe to import from any other module in the package - including the models - without
risking a circular import.
"""

from __future__ import annotations

import socket
import sys
from datetime import UTC, datetime

from .models.enums import Platform

_PLATFORM_BY_SYS_PLATFORM: dict[str, Platform] = {
    "win32": Platform.WINDOWS,
    "linux": Platform.LINUX,
    "darwin": Platform.DARWIN,
}


def detect_platform() -> Platform:
    """Infer the local `Platform` from `sys.platform`, defaulting to `Platform.OTHER`."""
    return _PLATFORM_BY_SYS_PLATFORM.get(sys.platform, Platform.OTHER)


def resolve_hostname(explicit: str | None = None) -> str:
    """Return `explicit` if given, otherwise the machine's own hostname."""
    return explicit or socket.gethostname()


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC `datetime`."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Current time as an ISO-8601 string in UTC - the format the gateway expects for
    `startedAt`/`finishedAt` on reported tasks."""
    return utc_now().isoformat()


def ensure_iso(value: datetime | str) -> str:
    """Normalize a timestamp to an ISO-8601 string, accepting either a `datetime` or a
    string that's already formatted."""
    return value.isoformat() if isinstance(value, datetime) else value
