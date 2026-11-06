"""Simula um robô de verdade usando o SDK: conecta, roda uma execução falsa e, com --wait, fica
conectado esperando o "Iniciar" da plataforma - uma execução a cada clique, até Ctrl+C.

Equivalente em Python do antigo simulate-robot-execution.js, agora sobre a API nova do SDK.

Uso:
    uv run python scripts/simulate_robot.py --api-key <api-key> [opções]

Exemplos:
    uv run python scripts/simulate_robot.py --api-key <api-key> --wait
    uv run python scripts/simulate_robot.py --api-key <api-key> --tasks 30 --delay 200
    uv run python scripts/simulate_robot.py --api-key <api-key> --mode queue --wait

Opções:
    --url URL              URL do backend (default: ZSYNC_BACKEND_URL ou http://localhost:5000)
    --api-key KEY          API key do robô (ou ZSYNC_API_KEY)
    --tasks N              tasks simuladas no modo "report" (default 10)
    --delay MS             tempo simulado por task, em ms (default 500)
    --mode report|queue    "report": inventa as tasks e reporta direto na execução (default)
                           "queue": consome a fila do robô na plataforma
    --queue-id ID          fila a consumir no modo "queue" (default: a do próprio robô)
    --observation TEXTO    observação da execução (default "Execução simulada")
    --final-status S       força o status final: COMPLETED ou FAILED (default: automático)
    --wait                 não inicia sozinho: espera o "Iniciar" da plataforma, uma execução
                           por clique, até Ctrl+C
    --verbose              mostra também os logs de depuração do SDK
"""

from __future__ import annotations

import argparse
import os
import random
import time
from dataclasses import dataclass

from zsynctech_studio_sdk import Robot, TaskStatus, get_logger
from zsynctech_studio_sdk.utils import utc_now

# Mesmo formato e cores dos logs do SDK, só com o nome "simulador" no lugar.
log = get_logger("simulador")


@dataclass(frozen=True)
class Outcome:
    status: TaskStatus
    weight: int
    messages: tuple[str, ...]


# Parecido com uma automação real: maioria sucesso, uma fatia de avisos (ex.: "sem oferta") e
# uma fatia menor de falhas (ex.: site fora do ar).
OUTCOMES = (
    Outcome(TaskStatus.SUCCESS, 80, ("Processado com sucesso", "Documento localizado", "OK")),
    Outcome(TaskStatus.WARNING, 12, ("Sem oferta disponivel", "Dado parcial retornado", "Requer revisao manual")),
    Outcome(TaskStatus.FAILURE, 8, ("Falha ao acessar o site", "Timeout na requisicao", "Credencial invalida")),
)


def pick_outcome() -> tuple[TaskStatus, str]:
    outcome = random.choices(OUTCOMES, weights=[o.weight for o in OUTCOMES])[0]
    return outcome.status, random.choice(outcome.messages)


def log_outcome(status: TaskStatus, line: str) -> None:
    """Cada resultado na cor do seu status: sucesso verde, aviso amarelo, falha vermelho."""
    if status is TaskStatus.SUCCESS:
        log.success(line)
    elif status is TaskStatus.WARNING:
        log.warning(line)
    else:
        log.error(line)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simula um robo executando uma automacao no zsynctech-studio")
    parser.add_argument("--url", default=os.environ.get("ZSYNC_BACKEND_URL", "http://localhost:5000"))
    parser.add_argument("--api-key", default=os.environ.get("ZSYNC_API_KEY"))
    parser.add_argument("--tasks", type=int, default=10)
    parser.add_argument("--delay", type=int, default=500, help="ms por task")
    parser.add_argument("--mode", choices=["report", "queue"], default="report")
    parser.add_argument("--queue-id")
    parser.add_argument("--observation", default="Execucao simulada")
    parser.add_argument("--final-status", choices=["COMPLETED", "FAILED"])
    parser.add_argument("--wait", action="store_true", help='espera o "Iniciar" da plataforma, ate Ctrl+C')
    parser.add_argument("--verbose", action="store_true", help="mostra tambem os logs de depuracao do SDK")
    args = parser.parse_args()
    if not args.api_key:
        parser.error("informe a API key do robo com --api-key ou ZSYNC_API_KEY")
    return args


def main() -> None:
    args = parse_args()
    robot = Robot(
        args.api_key,
        backend_url=args.url,
        hostname="simulador-local",
        version="2.0.0-simulador",
        log_level="DEBUG" if args.verbose else "INFO",
    )

    def run_once() -> None:
        execution = robot.start_execution(
            observation=args.observation, total=args.tasks if args.mode == "report" else None
        )
        counts = {TaskStatus.SUCCESS: 0, TaskStatus.WARNING: 0, TaskStatus.FAILURE: 0}
        try:
            if args.mode == "queue":
                for done, task in enumerate(robot.queue.tasks(args.queue_id), start=1):
                    time.sleep(args.delay / 1000)
                    status, message = pick_outcome()
                    report = {
                        TaskStatus.SUCCESS: task.success,
                        TaskStatus.WARNING: task.warning,
                        TaskStatus.FAILURE: task.failure,
                    }[status]
                    report(message=message, result={"simulado": True})
                    counts[status] += 1
                    log_outcome(status, f"[{done}] task {task.id}: {status.value} - {message}")
                log.info("{} task(s) da fila processada(s)", sum(counts.values()))
            else:
                for i in range(1, args.tasks + 1):
                    started_at = utc_now()
                    time.sleep(args.delay / 1000)
                    status, message = pick_outcome()
                    execution.report(
                        external_id=f"item-{i}",
                        status=status,
                        message=message,
                        payload={"index": i},
                        result={"processedAt": utc_now().isoformat()} if status is TaskStatus.SUCCESS else None,
                        started_at=started_at,
                        finished_at=utc_now(),
                    )
                    counts[status] += 1
                    log_outcome(status, f"[{i}/{args.tasks}] item-{i}: {status.value} - {message}")
        except Exception as error:
            log.error("Erro durante a execucao: {}", error)
            execution.fail(observation=f"Simulacao interrompida: {error}")
            raise

        success, warning, failure = counts.values()
        done = success + warning + failure
        final = args.final_status or ("FAILED" if done > 0 and failure == done else "COMPLETED")
        summary = f"Simulacao concluida: {success} sucesso, {warning} aviso, {failure} falha."
        log.info("Finalizando ({} sucesso, {} aviso, {} falha) como {}", success, warning, failure, final)
        if final == "FAILED":
            execution.fail(observation=summary)
        else:
            execution.finish(observation=summary)
        if args.wait:
            log.info('Aguardando a plataforma iniciar o robo (clique em "Iniciar" na tela de Robos)...')

    robot.connect()

    if args.wait:

        @robot.on_start
        def on_start() -> None:
            log.info("Chamada recebida da plataforma - iniciando execucao")
            run_once()

        log.info('Aguardando a plataforma iniciar o robo (clique em "Iniciar" na tela de Robos)...')
        robot.serve()  # cada clique roda uma execucao; so sai com Ctrl+C
    else:
        run_once()
        robot.close()


if __name__ == "__main__":
    main()
