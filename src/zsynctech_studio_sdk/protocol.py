"""Wire protocol constants for the `/robot` Socket.IO gateway and its REST counterpart.

Centralizing every namespace, event name and REST path here means `connection.py`,
`execution.py`, `queue.py` and `credentials.py` never hardcode a literal string - a typo
becomes an import error instead of a silent mismatch with the backend
(`zsynctech-backend/src/modules/robot/`).
"""

from __future__ import annotations

NAMESPACE = "/robot"

# REST counterpart to the /robot namespace - used only by CredentialManager, which has no
# reason to hold a socket open just to read/rotate a secret. See robot-credential.controller.ts.
CREDENTIALS_PATH = "/robot/credentials"


class ServerEvent:
    """Events pushed by the platform to the robot."""

    CONNECTED = "connected"
    AUTOMATION_START = "automation:start"
    ERROR = "error"
    EXCEPTION = "exception"
    DISCONNECT = "disconnect"
    CONNECT_ERROR = "connect_error"


class ClientEvent:
    """Events emitted by the robot to the platform."""

    HEARTBEAT = "heartbeat"
    STATUS = "status"
    EXECUTION_START = "execution:start"
    EXECUTION_TASK = "execution:task"
    EXECUTION_FINISH = "execution:finish"
    QUEUE_NEXT = "queue:next"
    QUEUE_TASK_RESULT = "queue:task-result"
