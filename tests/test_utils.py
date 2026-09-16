"""Tests for the reusable helpers in `zsynctech_studio_sdk.utils`."""

from __future__ import annotations

from datetime import UTC, datetime

from zsynctech_studio_sdk.models.enums import Platform
from zsynctech_studio_sdk.utils import detect_platform, ensure_iso, resolve_hostname, utc_now_iso


def test_detect_platform_returns_a_known_platform_enum_member() -> None:
    assert detect_platform() in set(Platform)


def test_resolve_hostname_prefers_explicit_value() -> None:
    assert resolve_hostname("my-machine") == "my-machine"


def test_resolve_hostname_falls_back_to_local_hostname() -> None:
    assert resolve_hostname(None) != ""


def test_utc_now_iso_is_timezone_aware() -> None:
    assert utc_now_iso().endswith("+00:00")


def test_ensure_iso_passes_through_strings_and_normalizes_datetimes() -> None:
    dt = datetime(2026, 1, 1, tzinfo=UTC)

    assert ensure_iso("2026-01-01T00:00:00+00:00") == "2026-01-01T00:00:00+00:00"
    assert ensure_iso(dt) == dt.isoformat()
