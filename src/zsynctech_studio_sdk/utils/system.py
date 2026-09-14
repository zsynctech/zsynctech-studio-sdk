"""Local-machine defaults reusable wherever connection metadata is assembled."""

import platform as _platform
import socket

from zsynctech_studio_sdk.models.enums import MachineOsPlatform

_SYSTEM_TO_PLATFORM: dict[str, MachineOsPlatform] = {
    "Windows": MachineOsPlatform.WINDOWS,
    "Linux": MachineOsPlatform.LINUX,
    "Darwin": MachineOsPlatform.DARWIN,
}


def default_hostname() -> str:
    """Return this machine's hostname, used when ``RobotClientConfig.hostname`` is unset."""
    return socket.gethostname()


def default_platform() -> MachineOsPlatform:
    """Return this machine's OS family, used when ``RobotClientConfig.platform`` is unset.

    Falls back to ``MachineOsPlatform.OTHER`` for anything the backend's own
    ``MachineOsPlatform`` enum doesn't recognize, matching the gateway's own lenient
    ``sanitizePlatform`` - an unrecognized platform never blocks a connection.
    """
    return _SYSTEM_TO_PLATFORM.get(_platform.system(), MachineOsPlatform.OTHER)
