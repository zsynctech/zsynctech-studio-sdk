"""Execution lifecycle results: acknowledgements returned by `execution:start`/`execution:finish`."""

from __future__ import annotations

from .base import SdkBaseModel
from .enums import ExecutionFinishStatus


class ExecutionStartResult(SdkBaseModel):
    """Acknowledgement returned by `execution:start`."""

    execution_id: str


class ExecutionFinishResult(SdkBaseModel):
    """Acknowledgement returned by `execution:finish`."""

    execution_id: str
    status: ExecutionFinishStatus
