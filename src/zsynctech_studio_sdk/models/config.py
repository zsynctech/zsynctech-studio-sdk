"""Configuration model for `RobotClient`."""

from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator

from ..utils import detect_platform, resolve_hostname
from .base import SdkBaseModel
from .enums import Platform


class RobotClientConfig(SdkBaseModel):
    """Everything `RobotClient` needs to open and maintain a `/robot` connection.

    Only `api_key` is required - every other field has a sensible default, matching what
    `simulate-robot.js` falls back to (own hostname, `os.platform()`, a 15s heartbeat).
    """

    model_config = ConfigDict(frozen=True)

    api_key: str = Field(..., min_length=1, description="Robot API key, generated on the platform")
    backend_url: str = Field(default="http://localhost:5000", description="Base URL of the zsynctech-studio backend")
    api_prefix: str = Field(default="/api/v1", description="REST prefix in front of the backend's HTTP routes")
    hostname: str = Field(default_factory=resolve_hostname, description="Reported machine hostname")
    version: str = Field(default="1.0.0", description="Robot/script version reported during the handshake")
    platform: Platform = Field(default_factory=detect_platform, description="Reported OS platform")
    heartbeat_interval: float = Field(default=15.0, gt=0, description="Seconds between automatic heartbeats")
    ack_timeout: float = Field(default=8.0, gt=0, description="Seconds to wait for a server acknowledgement")
    reconnection: bool = Field(default=True, description="Whether to auto-reconnect on connection loss")
    reconnection_attempts: int = Field(default=0, ge=0, description="Max reconnection attempts (0 = unlimited)")
    reconnection_delay: float = Field(default=1.0, gt=0, description="Seconds between reconnection attempts")
    log_level: str = Field(default="INFO", description="loguru level used by the SDK's default sink")

    @field_validator("api_key")
    @classmethod
    def _api_key_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("api_key não pode ser vazia")
        return stripped

    @field_validator("backend_url", "api_prefix")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")
