# zsyncstudio

SDK Python para robôs (RPA) se conectarem ao ZSync Tech Studio: buscar
execuções pendentes, reportar o progresso de cada etapa (task) e finalizar a
execução — usando o token de API gerado para a instância do robô.

Disponível em duas versões com a mesma interface: `zsyncstudio.sync_api`
(síncrona) e `zsyncstudio.async_api` (assíncrona, com `async`/`await`).

## Requisitos

- Python ≥ 3.13
- Uma instância do ZSync Tech Studio em execução
- Token de API do robô, gerado no dashboard da plataforma (formato
  `zst_<instanceId>.<secret>`)

## Instalação

```bash
uv add zsynctech-studio-sdk
```

ou

```bash
pip install zsynctech-studio-sdk
```

> O pacote se chama `zsynctech-studio-sdk` no PyPI, mas o módulo Python é
> `zsyncstudio` — é ele que você importa nos exemplos abaixo.

## Guia rápido

```python
from zsyncstudio.sync_api import Client, ExecutionRun

client = Client("https://studio.exemplo.com", api_token)


def run(execution: ExecutionRun) -> None:
    execution.start()  # reivindica a execução: PENDING → RUNNING

    for invoice in invoices:
        task = execution.task(invoice.number)
        try:
            charge(invoice)
        except Exception as exc:
            task.error(str(exc))
        else:
            task.finish()

    execution.error("alguns itens falharam") if execution.had_errors else execution.finish()


if __name__ == "__main__":
    while execution := client.poll_pending_executions():
        run(execution)
```

O robô fica esperando em `poll_pending_executions()` até a plataforma disparar
uma execução (pelo dashboard ou pela API). Cada `task(...)` representa um item
processado; chame `finish()`, `warning()`, `error()` ou `skip()` para reportar
o resultado. No fim, `finish()` marca a execução como concluída e `error()`
como falha.

Para reportar progresso no meio de uma execução longa, sem finalizá-la:

```python
execution.update_observation("processando lote 3 de 10")
```

### Robôs que decidem sozinhos quando rodar

Se o robô não depende da plataforma para saber quando executar (por exemplo,
dispara pelo agendador do próprio sistema operacional), use
`client.start_execution()` em vez de `poll_pending_executions()` — a execução
já nasce em andamento, então pule o `execution.start()` e vá direto para as
tasks.

## Uso assíncrono

```python
from zsyncstudio.async_api import Client, ExecutionRun

client = Client(base_url, api_token)


async def run(execution: ExecutionRun) -> None:
    await execution.start()

    for invoice in invoices:
        task = execution.task(invoice.number)
        try:
            await charge(invoice)
        except Exception as exc:
            await task.error(str(exc))
        else:
            await task.finish()


async def main() -> None:
    while execution := await client.poll_pending_executions():
        await run(execution)
```

## Tratamento de erros

Problemas de comunicação com a plataforma chegam como exceções que você pode
capturar:

```python
from zsyncstudio.sync_api import AuthenticationError, ApiError

try:
    client.poll_pending_executions()
except AuthenticationError:
    print("Token inválido ou expirado.")
except ApiError as exc:
    print(f"Erro da plataforma ({exc.status_code}): {exc.message}")
```

As principais exceções: `AuthenticationError` (token inválido), `NotFoundError`
(execução/instância inexistente), `ConflictError` (ex.: tentar finalizar uma
execução já encerrada) e `ConnectionError` (falha de rede). Todas herdam de
`ApiError` ou `ZSyncStudioError` e podem ser importadas de
`zsyncstudio.sync_api` / `zsyncstudio.async_api`.

Dentro de uma task, você também pode levantar `TaskWarning` ou `TaskSkipped`
para marcar o item como aviso ou pulado em vez de erro, sem interromper o
processamento dos demais itens.

## Metadados do projeto

- **Autor:** Rodrigo Zavan
- **Proprietário:** ZSync Tech LTDA
- **Requisito de Python:** ≥ 3.13

## Desenvolvimento

```bash
uv sync
uv run pytest
uv run mypy --strict src
uv run ruff check src tests
uv run black src tests
```
