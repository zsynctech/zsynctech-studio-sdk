from zsynctech_studio_sdk.models.base import BaseEntity
from zsynctech_studio_sdk.enums.step import StepStatus
from pydantic import field_validator
from datetime import datetime
from typing import Optional
import re


class StepModel(BaseEntity):
    status: StepStatus = StepStatus.UNPROCESSED
    taskId: Optional[str] = None
    stepCode: Optional[str] = None
    startDate: Optional[str] = None
    automationOnClientId: str

    @field_validator('startDate')
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
