"""`RobotClient`: the SDK's single entry point.

Composes `SocketConnection` + `ExecutionManager` + `QueueConsumer` behind one high-level API,
so a robot script only ever talks to this class:

    from zsynctech_studio_sdk import RobotClient, TaskStatus

    client = RobotClient.from_api_key("...", backend_url="https://minha-plataforma.com")

    @client.on_automation_start
    def handle_automation() -> None:
        with client.execution.run(observation="Processamento diário"):
            for task in client.queue.consume():
                with client.queue.processing(task) as outcome:
                    resultado = processar(task.payload)
                    outcome.success(result=resultado)

    with client:
        client.listen()
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from .connection import SocketConnection
from .credentials import CredentialManager
from .execution import ExecutionManager
from .loggers import configure_logging, logger
from .models.config import RobotClientConfig
from .models.enums import RobotInstanceStatus
from .models.robot import RobotConnection, RobotInfo
from .queue import QueueConsumer

AutomationStartHandler = Callable[[], None]


class RobotClient:
    """High-level client for a single robot instance's connection to the platform."""

    def __init__(self, config: RobotClientConfig) -> None:
        configure_logging(level=config.log_level)
        self._config = config
        self._connection = SocketConnection(config)
        self.execution = ExecutionManager(self._connection)
        self.queue = QueueConsumer(self._connection, self.execution)
        self.credentials = CredentialManager(config)

    @classmethod
    def from_api_key(cls, api_key: str, *, backend_url: str = "http://localhost:5000", **kwargs: object) -> RobotClient:
        """Convenience constructor: `RobotClient.from_api_key("...", backend_url="...")`.

        Any other `RobotClientConfig` field can be passed as a keyword argument (e.g.
        `heartbeat_interval=30`).
        """
        config = RobotClientConfig(api_key=api_key, backend_url=backend_url, **kwargs)
        return cls(config)

    def connect(self) -> RobotConnection:
        """Perform the handshake and block until the platform confirms the connection."""
        logger.info("Conectando em {} como '{}'...", self._config.backend_url, self._config.hostname)
        return self._connection.connect()

    def disconnect(self) -> None:
        self._connection.disconnect()

    def on_automation_start(self, handler: AutomationStartHandler) -> AutomationStartHandler:
        """Register `handler` to run (in a background thread) whenever the platform triggers
        this robot's "Iniciar" action. Usable as a decorator."""
        self._connection.on_automation_start(handler)
        return handler

    def set_status(self, status: RobotInstanceStatus) -> RobotInfo:
        """Manually report this instance's status (ONLINE/BUSY) to the platform."""
        return self._connection.set_status(status)

    def listen(self) -> None:
        """Block, waiting for the platform to trigger `automation:start`, until the connection
        closes or the user presses Ctrl+C.

        `automation:start` handlers keep firing on background threads while blocked here -
        this just keeps the main thread (and the process) alive to host them, the same role
        the bottom of `simulate-robot.js` plays.
        """
        logger.info("Aguardando eventos da plataforma (Ctrl+C para encerrar)...")
        try:
            self._connection.wait()
        except KeyboardInterrupt:
            logger.info("Encerrando por solicitação do usuário (Ctrl+C)...")
        finally:
            self.disconnect()

    @property
    def connection_info(self) -> RobotConnection | None:
        return self._connection.connection_info

    @property
    def is_connected(self) -> bool:
        return self._connection.is_connected

    def __enter__(self) -> RobotClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.disconnect()
