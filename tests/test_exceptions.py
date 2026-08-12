from __future__ import annotations

import pytest

from tests.factories import make_error_body
from zsyncstudio.exceptions import (
    ApiError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    ValidationError,
    build_api_error,
)


@pytest.mark.parametrize(
    ("status_code", "expected_cls"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, ValidationError),
        (500, ServerError),
        (503, ServerError),
        (418, ApiError),
    ],
)
def test_build_api_error_maps_status_code_to_exception_type(
    status_code: int, expected_cls: type[ApiError]
) -> None:
    error = build_api_error(status_code, make_error_body(status_code, "deu ruim"))

    assert type(error) is expected_cls
    assert error.status_code == status_code
    assert error.message == "deu ruim"
    assert error.path == "/executions/x"


def test_build_api_error_joins_validation_message_list() -> None:
    error = build_api_error(400, make_error_body(400, ["reference é obrigatório", "order >= 0"]))

    assert error.errors == ["reference é obrigatório", "order >= 0"]
    assert error.message == "reference é obrigatório; order >= 0"


def test_build_api_error_handles_non_dict_body() -> None:
    error = build_api_error(500, "Internal Server Error")

    assert isinstance(error, ServerError)
    assert error.message == "Internal Server Error"
    assert error.errors is None
