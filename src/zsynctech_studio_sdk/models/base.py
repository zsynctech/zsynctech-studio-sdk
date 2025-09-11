from zsynctech_studio_sdk.enums.execution import ExecutionStatus
from pydantic import BaseModel, Field, field_validator
from zsynctech_studio_sdk.enums.step import StepStatus
from zsynctech_studio_sdk.enums.task import TaskStatus
from uuid_extensions.uuid7 import uuid7
from typing import Optional, Union
from datetime import datetime
import re


class BaseEntity(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid7()),
        min_length=1,
        description="ID único da execução"
    )
    observation: Optional[str] = None
    status: Optional[Union[ExecutionStatus, StepStatus, TaskStatus]] = None
    endDate: Optional[str] = None

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v):
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', v):
            raise ValueError('ID deve ser um UUID válido')
        version = int(v[14], 16)
        if version != 7:
            raise ValueError('ID deve ser um UUID7 válido')
        return v

    @field_validator('endDate')
    @classmethod
    def validate_end_date_format(cls, v):
        if v is None:
            return v
        pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$'
        if not re.match(pattern, v):
            raise ValueError('endDate deve estar no formato ISO 8601 com Z')
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('endDate deve ser uma data válida')
        return v

    class Config:
        extra = "forbid"
        validate_assignment = True