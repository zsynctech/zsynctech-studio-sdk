"""Enums mirrored from the zsynctech-studio backend.

Every value here matches a TypeScript enum used by `RobotGateway` (see
`zsynctech-backend/src/modules/robot/robot.gateway.ts` and the enums it imports) so payloads
built by the SDK are always accepted as-is by the platform.
"""

from __future__ import annotations

from enum import StrEnum


class Platform(StrEnum):
    """Operating system reported during the handshake. Mirrors `MachineOsPlatform`."""

    WINDOWS = "windows"
    LINUX = "linux"
    DARWIN = "darwin"
    OTHER = "other"


class RobotInstanceStatus(StrEnum):
    """Status of a single connected instance. Mirrors `RobotInstanceStatus`.

    Sent by the robot itself over the `status` event; there is no OFFLINE value because a
    disconnected instance is deleted server-side rather than marked offline.
    """

    ONLINE = "ONLINE"
    BUSY = "BUSY"


class RobotStatus(StrEnum):
    """Aggregate status of a robot across all its connected instances. Mirrors `RobotStatus`.

    Read-only from the SDK's perspective: it's derived and returned by the server, never
    sent by the robot.
    """

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"


class RobotAvailability(StrEnum):
    """Whether the robot is currently allowed to run. Mirrors `RobotAvailability`.

    Read-only from the SDK's perspective, same as `RobotStatus`.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    SITE_DOWN = "SITE_DOWN"


class TaskStatus(StrEnum):
    """Outcome a robot may report for a task. Mirrors the reportable subset of `TaskStatus`.

    PENDING/REJECTED/PROCESSING exist on the backend's full `TaskStatus` enum too, but they
    belong exclusively to the queue-import pipeline - the gateway itself rejects them on
    `queue:task-result` / `execution:task`, so the SDK never exposes them here either.
    """

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    WARNING = "WARNING"


class ExecutionFinishStatus(StrEnum):
    """Terminal status a robot may report via `execution:finish`. Mirrors the subset of
    `ExecutionStatus` the gateway accepts from the robot (RUNNING/CANCELLED are server-only)."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CredentialType(StrEnum):
    """Shape of a credential's value. Mirrors `CredentialType`."""

    TEXT = "TEXT"
    KEY_VALUE = "KEY_VALUE"
    JSON = "JSON"


class CredentialStatus(StrEnum):
    """Lifecycle status of a credential. Mirrors `CredentialStatus`.

    ACTIVE/DELETED are read-only outcomes the platform itself controls; a robot can only ever
    report EXPIRED (see `CredentialManager.expire`/`set_status`), mirroring the
    `RobotCredentialStatusRequestDto` restriction on the backend. BLOCKED was retired as a
    settable status - it may still appear on old credentials revealed from the platform, but
    nothing can report it anymore, so it's not a member of this enum.
    """

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
