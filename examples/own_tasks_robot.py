"""Robô que processa a própria fonte de dados, sem consumir a fila da plataforma.

Diferente de `simulate_robot.py` (que pega as tasks já importadas na plataforma com
`robot.queue.tasks()`), este robô é dono da sua própria lista de itens - linhas de uma
planilha, o resultado de uma consulta a outro sistema, um scraping, etc. - e reporta cada
resultado direto na execução, sem passar pela fila.

Uso:
    uv run python examples/own_tasks_robot.py <api-key>
    API_KEY=<api-key> uv run python examples/own_tasks_robot.py

Variáveis de ambiente opcionais:
    BACKEND_URL   default http://localhost:5000
    VERSION       default 1.0.0-own-tasks-py
    SERVE         "1" para esperar o botão "Iniciar" da plataforma em vez de rodar uma vez e sair
"""

from __future__ import annotations

import os
import sys

from zsynctech_studio_sdk import Robot
from zsynctech_studio_sdk.loggers import logger


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
    print("Passe a api key do robô por parâmetro: python own_tasks_robot.py <api-key>")
    print("(ou defina a variável de ambiente API_KEY)")
    raise SystemExit(1)

robot = Robot(
    api_key,
    backend_url=os.environ.get("BACKEND_URL", "http://localhost:5000"),
    version=os.environ.get("VERSION", "1.0.0-own-tasks-py"),
)


def fetch_own_items() -> list[dict[str, str]]:
    """Simula a fonte de dados própria do robô (planilha, API interna, banco, ...).

    Num robô real isso seria a leitura de um arquivo, uma query, uma chamada HTTP etc. - o SDK
    não precisa saber nada sobre a origem, só recebe o resultado já processado.
    """
    return [{"id": f"pedido-{i}", "valor": str(100 * i)} for i in range(1, 6)]


# Cada chamada vira uma task da execução, com o id do item como identificador: retorno vira
# SUCCESS, exceção vira FAILURE. Reporta assim que cada item termina - se o robô cair no meio da
# lista, o que já foi processado fica registrado na plataforma.
@robot.task(external_id=lambda item: item["id"])
def process_item(item: dict[str, str]) -> dict[str, str]:
    logger.info("Processando {}...", item["id"])
    return {"confirmado": "true", "valor_processado": item["valor"]}


@robot.execution(observation="Processamento de itens próprios")
def run_automation() -> None:
    items = fetch_own_items()
    logger.info("[automação] {} item(ns) próprio(s) para processar", len(items))
    for item in items:
        process_item(item)


if __name__ == "__main__":
    if os.environ.get("SERVE") == "1":
        robot.on_start(run_automation)
        robot.serve()
    else:
        run_automation()
