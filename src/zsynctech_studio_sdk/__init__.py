"""SDK Python para conectar robôs (RPA) à plataforma zsynctech-studio.

Uso rápido:

    from zsynctech_studio_sdk import Robot

    robot = Robot.from_env()  # ZSYNC_API_KEY e ZSYNC_BACKEND_URL

    @robot.task
    def processar(task):
        return consultar_portal(task.payload)   # retorno -> SUCCESS, exceção -> FAILURE

    @robot.execution(observation="Boletos do dia")
    def main():
        for task in robot.queue.tasks():
            processar(task)

    main()

Não há conexão para gerenciar: ela abre na primeira chamada que precisa e fecha quando o
processo termina. Veja `examples/` para exemplos completos.
"""

from .credentials import CredentialManager
from .exceptions import (
    AckTimeoutError,
    CredentialRequestError,
    NoActiveExecutionError,
    NotConnectedError,
    RobotConnectionError,
    RobotSDKError,
    ServerRejectedError,
    TaskAlreadyReportedError,
    TaskWarning,
)
from .execution import Execution, ExecutionScope
from .loggers import configure_logging, get_logger
from .models import (
    CredentialInfo,
    CredentialStatus,
    CredentialType,
    ExecutionFinishResult,
    ExecutionFinishStatus,
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
from .queue import Queue, Task
from .robot import Robot

__all__ = [
    "Robot",
    "get_logger",
    "configure_logging",
    "RobotClientConfig",
    "Execution",
    "ExecutionScope",
    "Queue",
    "Task",
    "TaskItem",
    "CredentialManager",
    "RobotSDKError",
    "RobotConnectionError",
    "NotConnectedError",
    "AckTimeoutError",
    "ServerRejectedError",
    "NoActiveExecutionError",
    "TaskAlreadyReportedError",
    "TaskWarning",
    "CredentialRequestError",
    "RobotInfo",
    "RobotConnection",
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
    print("zsynctech-studio-sdk - use Robot para conectar um robô à plataforma zsynctech-studio.")
