"""Equivalente em Python do robô de simulação em `simulate-robot.js`.

Conecta em `/robot` com a mesma api key, espera o comando "Iniciar" da plataforma (ou inicia
de imediato com AUTO_START=1), abre uma execução, consome a fila até esvaziar reportando um
resultado aleatório por task, e finaliza a execução.

Uso:
    uv run python examples/simulate_robot.py <api-key>
    API_KEY=<api-key> uv run python examples/simulate_robot.py

Variáveis de ambiente opcionais (mesmos nomes do simulador em Node.js):
    BACKEND_URL   default http://localhost:5000
    HOSTNAME      default hostname da máquina
    VERSION       default 1.0.0-sim-py
    AUTO_START    "1" para iniciar a automação assim que conectar, sem esperar o botão
                  "Iniciar" da plataforma
    FAIL_RATE     0 a 1, chance de uma task simulada dar FAILURE (default 0)
    WARN_RATE     0 a 1, chance de uma task simulada dar WARNING (default 0)
"""

from __future__ import annotations

import os
import random
import sys

from zsynctech_studio_sdk import CredentialRequestError, RobotClient, TaskStatus
from zsynctech_studio_sdk.loggers import logger

# Só para demonstrar client.credentials.reveal() - troque pelo id de uma credencial sua.
CREDENTIAL_ID = "01a0a778-987d-7157-879a-c9fdfae040fa"


def parse_api_key() -> str:
    for arg in sys.argv[1:]:
        if arg == "--api-key" and len(sys.argv) > sys.argv.index(arg) + 1:
            return sys.argv[sys.argv.index(arg) + 1]
        if arg.startswith("--api-key="):
            return arg.split("=", 1)[1]
        if not arg.startswith("--"):
            return arg
    return os.environ.get("API_KEY", "")


def pick_outcome(fail_rate: float, warn_rate: float) -> tuple[TaskStatus, str]:
    roll = random.random()
    if roll < fail_rate:
        return TaskStatus.FAILURE, "Falha simulada"
    if roll < fail_rate + warn_rate:
        return TaskStatus.WARNING, "Aviso simulado"
    return TaskStatus.SUCCESS, "Processado com sucesso"


def log_credential(client: RobotClient) -> None:
    """Demonstra client.credentials.reveal() - REST puro, não precisa da conexão /robot aberta,
    então isso funcionaria mesmo antes de `client.connect()`."""
    try:
        credencial = client.credentials.reveal(CREDENTIAL_ID)
    except CredentialRequestError:
        logger.exception("[credencial] falha ao revelar {}", CREDENTIAL_ID)
        return
    logger.info(
        "[credencial] {} (versão {}, tipo {}) = {}",
        CREDENTIAL_ID,
        credencial.version_number,
        credencial.type.value,
        credencial.value,
    )


def run_automation(client: RobotClient) -> None:
    fail_rate = float(os.environ.get("FAIL_RATE", "0"))
    warn_rate = float(os.environ.get("WARN_RATE", "0"))

    logger.info("[automação] iniciando execução...")
    with client.execution.run(observation="Simulação via simulate_robot.py"):
        processed = 0
        for task in client.queue.consume():
            with client.queue.processing(task) as outcome:
                status, message = pick_outcome(fail_rate, warn_rate)
                if status is TaskStatus.FAILURE:
                    outcome.failure(message=message, result={"simulated": True})
                elif status is TaskStatus.WARNING:
                    outcome.warning(message=message, result={"simulated": True})
                else:
                    outcome.success(message=message, result={"simulated": True})
            logger.info("[task] {} -> {}", task.task_id, status.value)
            processed += 1
        logger.info("[automação] fila esvaziada ({} task(s) processada(s))", processed)


def main() -> None:
    api_key = parse_api_key()
    if not api_key:
        print("Passe a api key do robô por parâmetro: python simulate_robot.py <api-key>")
        print("(ou defina a variável de ambiente API_KEY)")
        raise SystemExit(1)

    # extra: dict[str, str] = {}
    # if os.environ.get("HOSTNAME"):
    #     extra["hostname"] = os.environ["HOSTNAME"]

    client = RobotClient.from_api_key(
        api_key,
        backend_url=os.environ.get("BACKEND_URL", "http://localhost:5000"),
        version=os.environ.get("VERSION", "1.0.0-sim-py"),
        # **extra,
    )

    @client.on_automation_start
    def _on_automation_start() -> None:
        run_automation(client)

    with client:
        log_credential(client)
        if os.environ.get("AUTO_START") == "1":
            run_automation(client)
        client.listen()


if __name__ == "__main__":
    main()
