# zsynctech-studio-sdk

SDK Python para conectar robôs RPA à plataforma ZsyncTech Studio. Encapsula o protocolo
Socket.IO `/robot` (handshake de conexão, heartbeat automático, ciclo de vida de execução e a
fila opcional de tasks do servidor) atrás de um único `RobotClient`.

## Instalação

```bash
uv add zsynctech-studio-sdk
```

## Início rápido

```python
from zsynctech_studio_sdk import ExecutionFinishStatus, RobotClient

client = RobotClient(api_key="...", base_url="https://studio.zsynctech.com.br")


@client.on_start
def run_automation() -> None:
    client.start_execution(total=100)
    try:
        with client.start_task(external_id="item-1"):
            ...  # faça o trabalho de verdade aqui - reporta sucesso automaticamente ao sair sem erro
        client.finish_execution()
    except Exception:
        client.finish_execution(status=ExecutionFinishStatus.FAILED)
        raise


with client:
    client.wait_forever()
```

O client autentica em `connect()`, mantém um heartbeat em segundo plano enquanto a conexão
estiver aberta, e chama o callback `on_start` sempre que a plataforma (ou um agendamento)
disparar a automação dessa instância.

## Reportando tasks

`start_task()` retorna um handle para uma task - chame `.success()`/`.warning()`/`.error()`
para reportar o resultado, em vez de montar um modelo `Task` na mão:

```python
task = client.start_task(external_id="row-42")
try:
    ...
    task.success()
except Exception as exc:
    task.error(message=str(exc))
```

Ou use como context manager, que reporta automaticamente (sucesso ao sair sem erro, erro se
uma exceção estourar) a menos que o bloco já tenha reportado explicitamente:

```python
with client.start_task(external_id="row-42") as task:
    ...
    task.warning(message="precisa de revisão")  # opcional - sobrescreve o sucesso padrão
```

Para reportar várias tasks em uma única chamada (ex: depois de processar um lote), monte
instâncias de `Task` diretamente e use `report_tasks([...])`:

```python
from zsynctech_studio_sdk import Task, TaskStatus

client.report_tasks([
    Task(status=TaskStatus.SUCCESS, external_id="item-1"),
    Task(status=TaskStatus.FAILURE, external_id="item-2", message="timeout"),
])
```

## Consumindo a fila do servidor

```python
with client:
    client.start_execution()
    while (task := client.claim_next_task()).has_task:
        # ... processe task.payload ...
        client.report_task_result(task.task_id, TaskStatus.SUCCESS)
    client.finish_execution()
```

## Desenvolvimento

```bash
uv sync
uv run pytest --cov=zsynctech_studio_sdk
uv run mypy --strict src
uv run ruff check src tests
uv run black --check src tests
```

Veja [DOCUMENTATION.md](DOCUMENTATION.md) para a referência completa da API.
