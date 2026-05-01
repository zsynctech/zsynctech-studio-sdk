# ZSyncTech Studio SDK

SDK Python para construir robôs que se integram à plataforma de automação [ZSyncTech Studio](https://zsynctech.com).

## Requisitos

- Python ≥ 3.13
- Uma instância do ZSyncTech Studio em execução
- Um token de API de robô e o UUID da instância obtidos no painel da plataforma

## Instalação

```bash
pip install zsynctech-studio-sdk
```

Ou com [uv](https://docs.astral.sh/uv/):

```bash
uv add zsynctech-studio-sdk
```

## Início Rápido

Crie um arquivo `.env` com suas credenciais:

```env
API_TOKEN=zst_your_token_here
INSTANCE_ID=your-instance-uuid
BASE_URL=http://localhost:3000   # optional, defaults to http://localhost:3000
```

Defina seu robô:

```python
from zsynctech_studio_sdk import task, execution

@task
def fetch_data():
    # your logic here
    ...

@task(name="Process records")
def process():
    # your logic here
    ...

@execution
def run():
    fetch_data()
    process()

if __name__ == "__main__":
    run.listener()
```

Execute:

```bash
python robot.py
```

O robô se conectará à plataforma e começará a verificar execuções pendentes. Sempre que uma execução for disparada pelo painel (ou via API), a função `run` é chamada e cada etapa `@task` é rastreada em tempo real.

## Configuração

`SDKConfig` armazena todas as configurações de conexão. Pode ser construído a partir de variáveis de ambiente (padrão) ou explicitamente.

### Via variáveis de ambiente

| Variável      | Obrigatória | Padrão                   | Descrição                                      |
|---------------|-------------|--------------------------|------------------------------------------------|
| `API_TOKEN`   | sim         | —                        | Token de API do robô emitido pela plataforma   |
| `INSTANCE_ID` | sim         | —                        | UUID da instância de robô registrada           |
| `BASE_URL`    | não         | `http://localhost:3000`  | URL raiz da plataforma ZSyncTech               |

```python
from zsynctech_studio_sdk import SDKConfig

config = SDKConfig.from_env()
```

### Configuração explícita

```python
from zsynctech_studio_sdk import SDKConfig

config = SDKConfig(
    base_url="https://studio.mycompany.com",
    api_token="zst_abc123",
    instance_id="550e8400-e29b-41d4-a716-446655440000",
    poll_interval=10.0,  # seconds between polls, default is 5
)

run.listener(config=config)
```

O sufixo `/api/v1` é adicionado automaticamente caso não esteja presente em `base_url`.

## Decoradores

### `@task`

Marca uma função como uma etapa rastreada dentro de uma execução. Quando rodando dentro de um listener, a tarefa é registrada na plataforma e seu status é atualizado automaticamente.

```python
@task
def my_step():
    ...

# Custom display name shown in the platform UI
@task(name="Download report")
def download():
    ...
```

Fora de um listener (ex.: em testes unitários), funções `@task` se comportam como funções normais, sem interação com a plataforma.

### `@execution`

Marca uma função como o ponto de entrada do robô. Adiciona o método `.listener()` que inicia o loop de polling.

```python
@execution
def run():
    step_one()
    step_two()

# Start the robot (blocks until Ctrl+C)
run.listener()

# Pass explicit config
run.listener(config=SDKConfig(...))
```

Chamar a função decorada diretamente (sem `.listener()`) a executa em modo offline — útil para testes locais.

## Mapeadores de Status

Ambos os decoradores aceitam um `status_mapper` opcional que controla o que acontece quando exceções específicas são lançadas.

### Mapeador de status de tarefa

Mapeia tipos de exceção para valores de `TaskStatus`. Qualquer status diferente de `ERROR` suprime a exceção e permite que a execução continue.

```python
from zsynctech_studio_sdk import task, TaskStatus

class DataNotFound(Exception):
    pass

@task(
    name="Fetch records",
    status_mapper={DataNotFound: TaskStatus.WARNING},
)
def fetch_records():
    raise DataNotFound("No records today")
    # task finishes as WARNING, execution continues
```

### Mapeador de status de execução

Mapeia tipos de exceção para valores de `ExecutionStatus`. Mapear para `COMPLETED` suprime o erro e finaliza a execução normalmente.

```python
from zsynctech_studio_sdk import execution, ExecutionStatus

class MaintenanceError(Exception):
    pass

@execution(
    status_mapper={MaintenanceError: ExecutionStatus.COMPLETED},
)
def run():
    ...
    raise MaintenanceError("System in maintenance, skipping")
    # execution finishes as COMPLETED instead of FAILED
```

Valores disponíveis de `TaskStatus`: `PENDING`, `RUNNING`, `SUCCESS`, `WARNING`, `ERROR`, `SKIPPED`

Valores disponíveis de `ExecutionStatus`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`

## Uso Avançado

### Acessando o contexto atual

Dentro de uma função `@task` ou `@execution` é possível acessar o contexto de execução ativo:

```python
from zsynctech_studio_sdk import get_current_context

@task
def my_step():
    ctx = get_current_context()
    if ctx:
        print(f"Running inside execution {ctx.execution_id}")
```

### Definindo observações personalizadas

O contexto expõe dois campos para anexar mensagens de texto à task ou à execução, sem precisar lançar uma exceção.

**`ctx.task_observation`** — define a observação enviada ao finalizar a task atual (sucesso ou erro). Se não definido e ocorrer uma exceção, a mensagem da exceção é usada automaticamente. O valor é resetado a cada nova task.

```python
from zsynctech_studio_sdk import task, get_current_context

@task
def process_records():
    ctx = get_current_context()
    records = fetch()
    ctx.task_observation = f"Processed {len(records)} records"
```

**`ctx.execution_observation`** — define a observação enviada ao finalizar a execução inteira. Quando definido, sobrescreve a mensagem de exceção (caso haja).

```python
from zsynctech_studio_sdk import execution, task, get_current_context

@execution
def run():
    ctx = get_current_context()
    process_records()
    ctx.execution_observation = "All steps completed successfully"
```

## Hierarquia de Exceções

```
SDKError
├── ConfigurationError   — configuração inválida ou ausente
├── AuthenticationError  — token de API rejeitado pela plataforma (HTTP 401)
├── NotFoundError        — recurso solicitado não existe (HTTP 404)
├── ApiError             — resposta HTTP 4xx/5xx inesperada da plataforma
├── TaskError            — falha na operação de registro/atualização de tarefa
└── ExecutionError       — falha em operação do ciclo de vida de execução
```

```python
from zsynctech_studio_sdk import AuthenticationError, ApiError

try:
    run.listener()
except AuthenticationError:
    print("Invalid or expired API token.")
except ApiError as e:
    print(f"Platform error {e.status_code}: {e.detail}")
```
