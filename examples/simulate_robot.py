"""Equivalente em Python do robô de simulação em `simulate-robot.js`.

Espera o comando "Iniciar" da plataforma (ou inicia de imediato com AUTO_START=1), abre uma
execução, consome a fila até esvaziar reportando um resultado aleatório por task, e finaliza a
execução.

Uso:
    uv run python examples/simulate_robot.py <api-key>
    API_KEY=<api-key> uv run python examples/simulate_robot.py

Variáveis de ambiente opcionais (mesmos nomes do simulador em Node.js):
    BACKEND_URL   default http://localhost:5000
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

from zsynctech_studio_sdk import CredentialRequestError, Robot, Task, TaskWarning
from zsynctech_studio_sdk.loggers import logger

# Só para demonstrar robot.credentials.reveal() - troque pelo id de uma credencial sua.
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


api_key = parse_api_key()
if not api_key:
    print("Passe a api key do robô por parâmetro: python simulate_robot.py <api-key>")
    print("(ou defina a variável de ambiente API_KEY)")
    raise SystemExit(1)

robot = Robot(
    api_key,
    backend_url=os.environ.get("BACKEND_URL", "http://localhost:5000"),
    version=os.environ.get("VERSION", "1.0.0-sim-py"),
)

FAIL_RATE = float(os.environ.get("FAIL_RATE", "0"))
WARN_RATE = float(os.environ.get("WARN_RATE", "0"))


@robot.task
def process(task: Task) -> dict[str, bool]:
    """Retorno vira SUCCESS, TaskWarning vira WARNING, qualquer outra exceção vira FAILURE."""
    roll = random.random()
    if roll < FAIL_RATE:
        raise RuntimeError("Falha simulada")
    if roll < FAIL_RATE + WARN_RATE:
        raise TaskWarning("Aviso simulado", result={"simulated": True})
    return {"simulated": True}


@robot.on_start
@robot.execution(observation="Simulação via simulate_robot.py")
def run_automation() -> None:
    processed = 0
    for task in robot.queue.tasks():
        process(task)
        processed += 1
    logger.info("[automação] fila esvaziada ({} task(s) processada(s))", processed)


def log_credential() -> None:
    """Demonstra robot.credentials.reveal() - REST puro, não precisa de conexão aberta."""
    try:
        credencial = robot.credentials.reveal(CREDENTIAL_ID)
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


if __name__ == "__main__":
    log_credential()
    if os.environ.get("AUTO_START") == "1":
        run_automation()
    robot.serve()
