from __future__ import annotations

import pytest

from tests.factories import API_TOKEN, INSTANCE_ID
from zsyncstudio._http import parse_instance_id, resolve_api_base_url


def test_resolve_api_base_url_appends_api_and_version() -> None:
    assert resolve_api_base_url("https://studio.exemplo.com", "v1") == (
        "https://studio.exemplo.com/api/v1"
    )


def test_resolve_api_base_url_strips_trailing_slash() -> None:
    assert resolve_api_base_url("https://studio.exemplo.com/", "v1") == (
        "https://studio.exemplo.com/api/v1"
    )


def test_resolve_api_base_url_accepts_custom_version() -> None:
    assert resolve_api_base_url("https://studio.exemplo.com", "v2") == (
        "https://studio.exemplo.com/api/v2"
    )


def test_parse_instance_id_extracts_uuid_from_token() -> None:
    assert parse_instance_id(API_TOKEN) == INSTANCE_ID


def test_parse_instance_id_rejects_missing_prefix() -> None:
    with pytest.raises(ValueError, match="zst_"):
        parse_instance_id(f"{INSTANCE_ID}.super-secret")


def test_parse_instance_id_rejects_missing_dot() -> None:
    with pytest.raises(ValueError, match="api_token inválido"):
        parse_instance_id(f"zst_{INSTANCE_ID}")


def test_parse_instance_id_rejects_empty_secret() -> None:
    with pytest.raises(ValueError, match="api_token inválido"):
        parse_instance_id(f"zst_{INSTANCE_ID}.")


def test_parse_instance_id_rejects_non_uuid_instance_id() -> None:
    with pytest.raises(ValueError, match="UUID"):
        parse_instance_id("zst_not-a-uuid.super-secret")
