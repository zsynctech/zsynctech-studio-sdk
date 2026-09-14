# zsynctech-studio-sdk — Documentação

SDK Python para conectar robôs RPA à plataforma ZsyncTech Studio. Ele encapsula o protocolo
Socket.IO `/robot` da plataforma — handshake de conexão, heartbeat automático, ciclo de vida
de execução, e a fila opcional de tasks do servidor — atrás de um único `RobotClient` amigável.

- **Requer:** Python ≥ 3.13
- **Pacote:** `zsynctech_studio_sdk`
- **Dependências:** `pydantic`, `python-socketio[client]`, `httpx`

## Sumário

- [Instalação](#instalação)
- [Início rápido](#início-rápido)
- [Conceitos principais](#conceitos-principais)
- [Reportando tasks](#reportando-tasks)
- [Consumindo a fila do servidor](#consumindo-a-fila-do-servidor)
- [Tratamento de erros](#tratamento-de-erros)
- [Referência da API](#referência-da-api)
  - [`RobotClient`](#robotclient)
  - [`TaskHandle`](#taskhandle)
  - [`RobotClientConfig`](#robotclientconfig)
  - [Modelos](#modelos)
  - [Enums](#enums)
  - [Exceções](#exceções)
- [Fallback REST](#fallback-rest)
- [Desenvolvimento](#desenvolvimento)

## Instalação

```bash
uv add zsynctech-studio-sdk
```

ou com pip:

```bash
pip install zsynctech-studio-sdk
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
            ...  # faça o trabalho de verdade aqui — reporta sucesso automaticamente ao sair sem erro
        client.finish_execution()
    except Exception:
        client.finish_execution(status=ExecutionFinishStatus.FAILED)
        raise


with client:
    client.wait_forever()
```

Rode o script e depois dispare o robô pela UI do Studio ("Iniciar automação") -
`run_automation` é chamado em resposta ao evento `automation:start` enviado pela plataforma.

## Conceitos principais

**Conexão.** `client.connect()` (ou `with client:`) abre uma conexão Socket.IO no namespace
`/robot` da plataforma, autenticando com a API key do robô. Se der certo, a plataforma associa
essa conexão a uma **instância** — um robô (automação) pode ter várias instâncias conectadas
ao mesmo tempo, até o limite configurado em `maxConcurrency`, cada uma recebendo disparos de
forma independente.

**Heartbeat.** A plataforma impõe um timeout de instância fixo de 30 segundos, não
configurável. O SDK envia um `heartbeat` automaticamente a cada 10 segundos em segundo plano,
de `connect()` até `disconnect()` - você nunca precisa chamar isso manualmente.

**Identidade da instância.** Uma vez conectado, `client.instance_id` e `client.instance_code`
expõem a identidade dessa conexão, atribuída pelo servidor (ex: `SDK-TEST-ROBOT-4F2A9C`). O
código da instância segue o padrão legível `<SLUG-DO-NOME-DO-ROBO>-<ALEATORIO>` e aparece na
aba "Instâncias" do robô na plataforma.

**Disparos (triggers).** Quando alguém clica em "Iniciar automação" (ou um agendamento
dispara), a plataforma escolhe uma instância conectada ociosa e envia um evento
`automation:start` para ela. Registre um handler para isso com `@client.on_start` (decorator)
ou `client.on_start(fn)`.

**Execuções.** Uma "rodada" da automação é uma *execução*: `start_execution()` abre uma,
qualquer quantidade de chamadas a `start_task()` / `report_tasks()` reporta os resultados de
tasks individuais contra ela, e `finish_execution()` a encerra. Exatamente uma execução fica
aberta por vez por instância de `RobotClient` (controlado internamente) - você também pode
passar um `execution_id` explícito para qualquer um desses métodos se estiver gerenciando mais
de uma execução simultaneamente.

## Reportando tasks

A forma mais amigável de reportar o resultado de uma task é `start_task()`, que retorna um
[`TaskHandle`](#taskhandle):

```python
task = client.start_task(external_id="row-42")
try:
    ...
    task.success()
except Exception as exc:
    task.error(message=str(exc))
```

Ou use como context manager - ele reporta automaticamente ao sair do bloco (sucesso se sair
sem erro, falha se uma exceção estourar) a menos que o bloco já tenha reportado explicitamente:

```python
with client.start_task(external_id="row-42") as task:
    ...
    task.warning(message="precisa de revisão")  # opcional — sobrescreve o sucesso padrão
```

Para reportar várias tasks em uma única chamada (ex: depois de processar um lote), monte
instâncias de [`Task`](#modelos) diretamente e chame `report_tasks`:

```python
from zsynctech_studio_sdk import Task, TaskStatus

client.report_tasks([
    Task(status=TaskStatus.SUCCESS, external_id="item-1"),
    Task(status=TaskStatus.FAILURE, external_id="item-2", message="timeout"),
])
```

> **Dê um `external_id` distinto para cada task.** A plataforma trata um `external_id`
> repetido dentro da mesma execução como uma *nova tentativa* daquela mesma task - ela insere
> uma linha nova para cada report, mas só conta o efeito **líquido** (o status mais recente)
> nos totais de sucesso/falha/aviso. Reaproveitar um `external_id` entre tasks genuinamente
> diferentes vai fazer os totais aparecerem errados mesmo que cada linha tenha sido registrada.

`report_tasks` é limitado no servidor a 300 chamadas/segundo - agrupe várias instâncias de
`Task` em uma única chamada em vez de chamar uma vez por task num loop apertado.

## Consumindo a fila do servidor

Para robôs que consomem trabalho de uma fila gerenciada pela plataforma em vez de gerar sua
própria lista de tasks:

```python
with client:
    client.start_execution()
    while (task := client.claim_next_task()).has_task:
        # ... processe task.payload ...
        client.report_task_result(task.task_id, TaskStatus.SUCCESS)
    client.finish_execution()
```

`claim_next_task()` exige uma execução já aberta via `start_execution()`. Uma fila vazia é um
resultado normal (`task.has_task` é `False`), não um erro.

## Tratamento de erros

Todo método que fala com a plataforma pode levantar uma subclasse de `SdkError`:

```python
from zsynctech_studio_sdk import AuthenticationError, ConcurrencyLimitError, SdkError

try:
    client.connect()
except ConcurrencyLimitError:
    print("Esse robô já atingiu o limite de maxConcurrency.")
except AuthenticationError:
    print("API key inválida ou robô inativo.")
except SdkError as exc:
    print(f"Não foi possível conectar: {exc}")
```

Veja [Exceções](#exceções) para a hierarquia completa e quando cada uma é levantada.

## Referência da API

### `RobotClient`

```python
RobotClient(
    config: RobotClientConfig | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    **config_kwargs,
)
```

Crie a partir de um `RobotClientConfig` já pronto ou de seus campos brutos (`api_key` +
`base_url` obrigatórios; qualquer outro campo de `RobotClientConfig` - `hostname`, `version`,
`platform`, `heartbeat_interval_seconds` - pode ser passado como argumento nomeado também).

| Método / propriedade | Descrição |
| --- | --- |
| `connect(timeout=10.0) -> ConnectResult` | Abre a conexão, bloqueando até a plataforma confirmar ou rejeitar. Levanta `AuthenticationError` ou `ConcurrencyLimitError`. |
| `disconnect() -> None` | Para o loop de heartbeat e fecha a conexão. |
| `with client: ...` | Context manager - `connect()` ao entrar, `disconnect()` ao sair. |
| `connected -> bool` | Se o transporte atualmente mantém uma conexão aberta. |
| `instance_id -> str` | O id de instância atribuído pelo servidor para esta conexão. Exige `connect()` antes. |
| `instance_code -> str` | O código legível da instância para esta conexão. Exige `connect()` antes. |
| `on_start(callback) -> callback` | Registra o callback chamado quando a plataforma envia `automation:start`. Pode ser usado como decorator. |
| `set_status(status: RobotInstanceStatus) -> None` | Reporta manualmente o status desta instância. O SDK nunca faz isso automaticamente. |
| `start_execution(total=None, observation=None) -> str` | Abre uma nova execução, guarda seu id, retorna o id. |
| `start_task(external_id=None, attempts=1) -> TaskHandle` | Abre uma task contra a execução atual; retorna um handle para reportar seu resultado. Veja [Reportando tasks](#reportando-tasks). |
| `report_tasks(tasks: Sequence[Task], execution_id=None) -> None` | Reporta um lote de resultados de tasks. |
| `finish_execution(status=ExecutionFinishStatus.COMPLETED, execution_id=None) -> ExecutionFinishResult` | Encerra a execução atual (ou a indicada). |
| `claim_next_task(queue_id=None) -> ClaimedTask` | Reivindica a próxima task pendente da fila do servidor, se houver. |
| `report_task_result(task_id, status, message=None, result=None) -> TaskResultAck` | Reporta o resultado de uma task entregue anteriormente por `claim_next_task`. |
| `wait_forever() -> None` | Bloqueia a thread chamadora até a conexão fechar ou Ctrl+C ser pressionado. Ctrl+C interrompe isso de forma limpa, deixando o `disconnect()` de um bloco `with` rodar em seguida. |

### `TaskHandle`

Retornado por `RobotClient.start_task()`. Captura `started_at` no momento da criação.

| Método | Descrição |
| --- | --- |
| `success(message=None, result=None) -> None` | Reporta a task como `TaskStatus.SUCCESS`. |
| `warning(message=None, result=None) -> None` | Reporta a task como `TaskStatus.WARNING`. |
| `error(message=None, result=None) -> None` | Reporta a task como `TaskStatus.FAILURE`. |
| `with task: ...` | Context manager - reporta `success()` ao sair sem erro ou `error()` se uma exceção estourar, a menos que já tenha reportado explicitamente dentro do bloco. Nunca suprime a exceção. |

Chamar um segundo método de report (ou sair de um bloco `with` depois de já ter reportado
explicitamente dentro dele) é seguro - só o primeiro report é enviado. Chamar um método de
report duas vezes *explicitamente* levanta `RuntimeError`.

### `RobotClientConfig`

Modelo Pydantic por trás da configuração do `RobotClient`.

| Campo | Tipo | Padrão | Observações |
| --- | --- | --- | --- |
| `api_key` | `str` | — | Obrigatório. A API key do robô. |
| `base_url` | `str` | — | Obrigatório. Origem da plataforma, ex: `https://studio.zsynctech.com.br`. A barra final é removida automaticamente. |
| `hostname` | `str` | hostname local | Reportado no momento da conexão. |
| `version` | `str \| None` | `None` | String de versão livre, opcional, para o script do robô. |
| `platform` | `MachineOsPlatform` | família do SO local | Reportado no momento da conexão. |
| `heartbeat_interval_seconds` | `float` | `10.0` | Com que frequência o SDK envia `heartbeat`. Altere só para testes - o timeout de 30s da própria plataforma é fixo e não é exposto aqui. |

### Modelos

Todos os modelos de dados ficam em `zsynctech_studio_sdk.models` (também reexportados na raiz
do pacote).

- **`Task`** — o resultado de uma task: `external_id`, `attempts` (≥1, padrão 1), `status`
  (`TaskStatus`), `message`, `payload` (dict), `result` (dict), `started_at`/`finished_at`
  (strings ISO-8601, padrão "agora").
- **`ConnectResult`** — retornado por `connect()`: `id`, `name`, `max_concurrency`,
  `instance_id`, `instance_code`.
- **`ExecutionStartResult`** — `execution_id`.
- **`ExecutionFinishResult`** — `execution_id`, `status`.
- **`ClaimedTask`** — `task_id` (`None` se a fila estiver vazia - confira `.has_task`),
  `external_id`, `attempts`, `payload`.
- **`TaskResultAck`** — `task_id`, `status`.

### Enums

- **`TaskStatus`** — `SUCCESS`, `FAILURE`, `WARNING`.
- **`RobotInstanceStatus`** — `ONLINE`, `BUSY`.
- **`ExecutionFinishStatus`** — `COMPLETED`, `FAILED`.
- **`MachineOsPlatform`** — `WINDOWS`, `LINUX`, `DARWIN`, `OTHER`.

### Exceções

Todas as exceções herdam de `SdkError`.

| Exceção | Quando é levantada |
| --- | --- |
| `AuthenticationError` | A API key é inválida, ou o robô está inativo. |
| `ConcurrencyLimitError` | Esse robô já tem `max_concurrency` instâncias conectadas. |
| `NotConnectedError` | Um método de execução/fila/task é chamado antes de `connect()`. |
| `ExecutionError` | A plataforma rejeita uma chamada `execution:*`/`queue:*` (payload inválido, nenhuma execução aberta, etc.), ou a chamada expira sem um erro do servidor para reportar. |

## Fallback REST

`zsynctech_studio_sdk.transport.RestTransport` cobre apenas connect/heartbeat/disconnect, via
HTTP puro (`POST {base_url}/v1/robot/{connect,heartbeat,disconnect}`) - para quem quer
explicitamente connect/heartbeat via polling, sem manter um socket aberto. Ele não recebe
disparos `automation:start` e não tem endpoints de execução/fila, então prefira o `RobotClient`
(via Socket.IO) a menos que você tenha um motivo específico para não manter uma conexão
persistente.

## Desenvolvimento

```bash
uv sync
uv run pytest --cov=zsynctech_studio_sdk
uv run mypy --strict src
uv run ruff check src tests
uv run black --check src tests
```

Estrutura do projeto:

```
src/zsynctech_studio_sdk/
  client.py              # a façade RobotClient
  task_handle.py          # TaskHandle
  exceptions.py             # hierarquia de SdkError
  models/                    # somente modelos Pydantic
  transport/                  # transportes Socket.IO + REST
  utils/                        # pequenos helpers reutilizáveis (time, logging, system)
tests/                           # espelha a estrutura do pacote, sem rede real
examples/                         # scripts executáveis contra uma plataforma real
```
