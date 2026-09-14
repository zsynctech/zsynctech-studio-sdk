"""Shared base model for every wire-facing (non-config) model in this package.

The backend's DTOs are serialized as camelCase JSON (standard NestJS/class-transformer
convention), while idiomatic Python uses snake_case attributes. :class:`CamelModel` bridges
the two in one place instead of every model repeating its own ``alias_generator``.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for models that serialize to/from the platform's camelCase JSON wire format."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )
