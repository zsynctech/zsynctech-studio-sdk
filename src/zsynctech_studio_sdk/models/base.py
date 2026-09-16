"""Base pydantic model shared by every data model in the SDK."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class SdkBaseModel(BaseModel):
    """Base class for all SDK data models.

    The `/robot` gateway speaks camelCase (it's a NestJS/TypeScript backend); the SDK's
    Python API stays snake_case. `populate_by_name` lets a model be built from either
    style, and `to_wire()` is the single place that turns an outbound model back into the
    camelCase dict the gateway expects, so no other module has to know about aliasing.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    def to_wire(self) -> dict[str, Any]:
        """Serialize to the camelCase, JSON-ready dict sent over the socket."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")
