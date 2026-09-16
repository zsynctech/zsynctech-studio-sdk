"""Robô que processa a própria fonte de dados, sem consumir a fila da plataforma.

Diferente de `simulate_robot.py` (que usa `client.queue.consume()` para pegar tasks já
importadas na plataforma), este robô é dono da sua própria lista de itens - por exemplo,
linhas lidas de uma planilha, resultados de uma consulta a outro sistema, um scraping, etc. -
e reporta cada resultado diretamente à execução via `execution:task` (`ExecutionManager.
report_tasks`), sem passar pela fila.

Uso:
    uv run python examples/own_tasks_robot.py <api-key>
    API_KEY=<api-key> uv run python examples/own_tasks_robot.py

Variáveis de ambiente opcionais:
    BACKEND_URL   default http://localhost:5000
    VERSION       default 1.0.0-own-tasks-py
    AUTO_START    "1" para iniciar a automação assim que conectar, sem esperar o botão
                  "Iniciar" da plataforma
"""

from __future__ import annotations

import os
import sys

from zsynctech_studio_sdk import RobotClient, TaskItem, TaskStatus
from zsynctech_studio_sdk.loggers import logger
from zsynctech_studio_sdk.utils import utc_now


def parse_api_key() -> str:
    for arg in sys.argv[1:]:
        if arg == "--api-key" and len(sys.argv) > sys.argv.index(arg) + 1:
            return sys.argv[sys.argv.index(arg) + 1]
        if arg.startswith("--api-key="):
            return arg.split("=", 1)[1]
        if not arg.startswith("--"):
            return arg
    return os.environ.get("API_KEY", "")


def fetch_own_items() -> list[dict[str, str]]:
    """Simula a fonte de dados própria do robô (planilha, API interna, banco, ...).

    Num robô real isso seria a leitura de um arquivo, uma query, uma chamada HTTP etc. - o
    SDK não precisa saber nada sobre a origem, só recebe o resultado já processado.
    """
    return [{"id": f"pedido-{i}", "valor": str(100 * i)} for i in range(1, 6)]


def process_item(item: dict[str, str]) -> dict[str, str]:
    """Trabalho real do robô para um item - aqui só simula um resultado."""
    logger.info("Processando {}...", item["id"])
    return {"confirmado": "true", "valor_processado": item["valor"]}


def run_automation(client: RobotClient) -> None:
    items = fetch_own_items()
    logger.info("[automação] {} item(ns) próprio(s) para processar", len(items))

    with client.execution.run(observation="Processamento de itens próprios"):
        for item in items:
            started_at = utc_now()
            try:
                resultado = process_item(item)
                task = TaskItem(
                    external_id=item["id"],
                    status=TaskStatus.SUCCESS,
                    message="Processado com sucesso",
                    payload=item,
                    result=resultado,
                    started_at=started_at,
                    finished_at=utc_now(),
                )
            except Exception as exc:
                logger.exception("Falha ao processar {}", item["id"])
                task = TaskItem(
                    external_id=item["id"],
                    status=TaskStatus.FAILURE,
                    message=str(exc),
                    payload=item,
                    started_at=started_at,
                    finished_at=utc_now(),
                )

            # Reporta um a um, assim que cada item termina - se o robô cair no meio da lista,
            # o que já foi processado fica registrado na plataforma em vez de perdido num
            # lote que nunca chegou a ser enviado.
            client.execution.report_tasks([task])
            logger.info("[task] {} -> {}", task.external_id, task.status.value)

        logger.info("[automação] {} item(ns) reportado(s)", len(items))


def main() -> None:
    api_key = parse_api_key()
    if not api_key:
        print("Passe a api key do robô por parâmetro: python own_tasks_robot.py <api-key>")
        print("(ou defina a variável de ambiente API_KEY)")
        raise SystemExit(1)

    client = RobotClient.from_api_key(
        api_key,
        backend_url=os.environ.get("BACKEND_URL", "http://localhost:5000"),
        version=os.environ.get("VERSION", "1.0.0-own-tasks-py"),
    )

    @client.on_automation_start
    def _on_automation_start() -> None:
        run_automation(client)

    with client:
        if os.environ.get("AUTO_START") == "1":
            run_automation(client)
        client.listen()


if __name__ == "__main__":
    main()
