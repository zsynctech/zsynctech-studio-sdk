"""Timestamp helpers reusable across models and transports."""

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    Every timestamp field in the ``/robot`` protocol (``Task.started_at``,
    ``Task.finished_at``) is validated server-side via ``Date.parse`` - an ISO-8601 string
    with a UTC offset is always accepted.
    """
    return datetime.now(UTC).isoformat()
