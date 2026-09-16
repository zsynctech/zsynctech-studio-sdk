"""SDK Python para conectar robôs (RPA) à plataforma zsynctech-studio via `/robot` (Socket.IO).

Uso rápido:

    from zsynctech_studio_sdk import RobotClient, TaskStatus

    client = RobotClient.from_api_key("<sua-api-key>", backend_url="http://localhost:5000")

    @client.on_automation_start
    def handle_automation() -> None:
        with client.execution.run(observation="Minha automação"):
            for task in client.queue.consume():
                with client.queue.processing(task) as outcome:
                    outcome.success(result={"ok": True})

    with client:
        client.listen()

O cofre de credenciais é acessado à parte, via REST (não precisa de conexão aberta):

    credencial = client.credentials.reveal("<credential-id>")
    print(credencial.value)

Veja `examples/simulate_robot.py` para um exemplo completo.
"""

from .client import RobotClient
from .credentials import CredentialManager
from .exceptions import (
    AckTimeoutError,
    CredentialRequestError,
    NoActiveExecutionError,
    NotConnectedError,
    RobotConnectionError,
    RobotSDKError,
)
from .execution import ExecutionManager
from .models import (
    ClaimedTask,
    CredentialInfo,
    CredentialStatus,
    CredentialType,
    ExecutionFinishResult,
    ExecutionFinishStatus,
    ExecutionStartResult,
    Platform,
    RevealedCredential,
    RobotAvailability,
    RobotClientConfig,
    RobotConnection,
    RobotInfo,
    RobotInstanceStatus,
    RobotStatus,
    TaskItem,
    TaskStatus,
)
from .queue import QueueConsumer, TaskOutcome

__all__ = [
    "RobotClient",
    "RobotClientConfig",
    "ExecutionManager",
    "QueueConsumer",
    "TaskOutcome",
    "CredentialManager",
    "RobotSDKError",
    "RobotConnectionError",
    "NotConnectedError",
    "AckTimeoutError",
    "NoActiveExecutionError",
    "CredentialRequestError",
    "ClaimedTask",
    "TaskItem",
    "RobotInfo",
    "RobotConnection",
    "ExecutionStartResult",
    "ExecutionFinishResult",
    "CredentialInfo",
    "RevealedCredential",
    "Platform",
    "RobotStatus",
    "RobotAvailability",
    "RobotInstanceStatus",
    "TaskStatus",
    "ExecutionFinishStatus",
    "CredentialStatus",
    "CredentialType",
    "main",
]


def main() -> None:
    print("zsynctech-studio-sdk - use RobotClient para conectar um robô à plataforma zsynctech-studio.")
