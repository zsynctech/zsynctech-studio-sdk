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
        try:
            run(execution)
        except Exception as exc:
            execution.error(str(exc))
```

O robô fica esperando em `poll_pending_executions()` até a plataforma disparar
uma execução (pelo dashboard ou pela API). Cada `task(...)` representa um item
processado; chame `finish()`, `warning()`, `error()` ou `skip()` para reportar
o resultado. No fim, `finish()` marca a execução como concluída e `error()`
como falha.

**Sempre** envolva `run(execution)` num `try/except` no loop principal, sem
relançar a exceção — se ela escapar do `while`, o robô inteiro para e não
volta a escutar por novas execuções. `poll_pending_executions()` já tolera
sozinho falhas transitórias de rede (`ConnectionError`) e erros 5xx da API
(retenta em vez de propagar); o `try/except` do loop é para erros da sua
própria lógica de processamento (`execution.start()` falhando porque a
execução já foi reivindicada por outro processo, por exemplo).

Para reportar progresso no meio de uma execução longa, sem finalizá-la:

```python
execution.update_observation("processando lote 3 de 10")
```

Se você sabe de antemão quantos itens serão processados, informe logo após
`start()` para o dashboard acompanhar o progresso real (ex.: "45/1000") em
vez de reportado/reportado:

```python
execution.set_total_tasks(1000)
```

Pode ser chamado mais de uma vez. Se você não informar, o total acompanha o
que já foi processado (1/1, 2/2, ...); se processar mais itens do que
declarou, o total passa a acompanhar o que já foi processado em vez de
ultrapassar 100%.

### Robôs que decidem sozinhos quando rodar

Se o robô não depende da plataforma para saber quando executar (por exemplo,
dispara pelo agendador do próprio sistema operacional), use
`client.start_execution()` em vez de `poll_pending_executions()` — a execução
já nasce em andamento, então pule o `execution.start()` e vá direto para as
tasks.

## Credenciais (secrets)

Se o robô precisa de uma senha ou token guardado no cofre de credenciais da
plataforma, revele o valor pelo id da credencial:

```python
secret = client.get_secret(secret_id)
password = secret.value  # str, dict[str, str] ou dado JSON — depende do tipo da credencial
```

Uma credencial tem status `ACTIVE`, `EXPIRED` ou `BLOCKED` (além de
`DELETED`, que já não aparece para o robô). `get_secret()` **não lança** por
causa do status — se a credencial não estiver `ACTIVE`, `secret.value` vem
`None` e `secret.is_blocked`/`secret.is_expired` já vêm preenchidos, sem
precisar de uma segunda chamada:

```python
secret = client.get_secret(secret_id)
if secret.is_blocked or secret.is_expired:
    ...  # avise alguém, ou pule esta credencial
else:
    password = secret.value
```

Depois de trocar a senha no sistema de destino, registre o novo valor (isso
cria uma nova versão, nunca sobrescreve a atual, e reativa a credencial se
ela estava `EXPIRED`/`BLOCKED`):

```python
secret.rotate("nova-senha")
```

O próprio robô também pode sinalizar um problema (ex.: login rejeitado pelo
sistema alvo) sem esperar a expiração automática:

```python
secret.block("senha rejeitada pelo sistema X")   # ou secret.expire("...")
```

A única forma de tirar uma credencial de `EXPIRED`/`BLOCKED` é criar uma nova
versão com `rotate()` — não existe um "desbloquear" manual. `get_secret()`
ainda falha com `NotFoundError` se a credencial (ou a versão) não existir.
Criar, excluir e ver o histórico completo (versões e eventos de status) só
estão disponíveis para administradores pelo painel.

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
        try:
            await run(execution)
        except Exception as exc:
            await execution.error(str(exc))
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
