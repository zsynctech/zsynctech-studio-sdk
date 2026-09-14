"""Client configuration model."""

from pydantic import BaseModel, Field, field_validator

from zsynctech_studio_sdk.models.enums import MachineOsPlatform
from zsynctech_studio_sdk.utils.system import default_hostname, default_platform

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 10.0
"""How often the SDK sends `heartbeat` on the caller's behalf.

Comfortably under the platform's fixed, non-configurable 30-second instance timeout
(`INSTANCE_HEARTBEAT_TIMEOUT_MS` in `robot-heartbeat-watchdog.service.ts`) - that server-side
constant is intentionally not exposed here for the caller to change.
"""


class RobotClientConfig(BaseModel):
    """Everything :class:`~zsynctech_studio_sdk.client.RobotClient` needs to connect.

    Attributes:
        api_key: The robot's API key, issued by the platform.
        base_url: Platform origin, e.g. ``https://studio.zsynctech.com.br``. No trailing slash.
        hostname: Reported at connect time. Defaults to the local machine's hostname.
        version: Optional free-form version string for the robot script itself.
        platform: Reported at connect time. Defaults to the local machine's OS family.
        heartbeat_interval_seconds: How often the SDK sends `heartbeat`. Override only for
            testing - the default already sits well inside the platform's fixed timeout.
    """

    api_key: str = Field(min_length=1)
    base_url: str
    hostname: str = Field(default_factory=default_hostname)
    version: str | None = None
    platform: MachineOsPlatform = Field(default_factory=default_platform)
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")
