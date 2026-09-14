"""Enumerations shared by every model in the ``/robot`` protocol.

Mirrors the backend's own enums (``zsynctech-backend/src/modules/admin/tasks/enums/task-status.enum.ts``,
``robot-instance-status.enum.ts``) so wire values match exactly.
"""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Outcome a robot may report for a single task.

    Only these three values are accepted by the platform over the ``/robot`` namespace -
    ``PENDING``/``REJECTED`` exist on the backend's merged enum but belong exclusively to the
    queue-import pipeline and are never valid here.
    """

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    WARNING = "WARNING"


class RobotInstanceStatus(StrEnum):
    """Live state of a connected robot instance, as reported via the ``status`` event."""

    ONLINE = "ONLINE"
    BUSY = "BUSY"


class ExecutionFinishStatus(StrEnum):
    """Terminal status a robot may report when closing out an execution."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MachineOsPlatform(StrEnum):
    """Operating system family sent during the socket handshake, if known."""

    WINDOWS = "windows"
    LINUX = "linux"
    DARWIN = "darwin"
    OTHER = "other"
