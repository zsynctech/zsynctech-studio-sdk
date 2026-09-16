# zsynctech-studio-sdk

SDK Python para conectar robôs (RPA) à plataforma **zsynctech-studio** via Socket.IO
(namespace `/robot`) - handshake, heartbeat, ciclo de execução, consumo de fila e acesso ao
cofre de credenciais, com o mesmo protocolo que o robô real e o simulador em Node.js
(`simulate-robot.js`) usam.

## Instalação

Projeto gerenciado com [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Uso rápido

`client.on_automation_start` registra o que rodar quando a plataforma disparar o botão
"Iniciar" para esse robô. `client.listen()` mantém o processo vivo aguardando esse
evento (Ctrl+C encerra a conexão de forma limpa) - é o mesmo papel que o final de
`simulate-robot.js` cumpre.

Há duas formas de reportar trabalho, dependendo de onde a lista de tasks vem:

### Consumindo a fila da plataforma

Use quando as tasks vêm de uma planilha importada na plataforma - `client.queue.consume()`
entrega uma a uma até a fila esvaziar.

```python
from zsynctech_studio_sdk import RobotClient, TaskStatus

client = RobotClient.from_api_key(
    "<sua-api-key>",
    backend_url="http://localhost:5000",
)

@client.on_automation_start
def handle_automation() -> None:
    with client.execution.run(observation="Minha automação"):
        for task in client.queue.consume():
            with client.queue.processing(task) as outcome:
                resultado = processar(task.payload)
                outcome.success(result=resultado)

with client:
    client.listen()
```

### Sem fila: robô que processa a própria fonte de dados

Use quando o robô lê de uma fonte própria (planilha local, API interna, scraping, banco de
dados...) em vez de uma fila importada na plataforma - pule `client.queue` inteiramente e
reporte cada resultado direto com `client.execution.report_tasks(...)`.

```python
from zsynctech_studio_sdk import RobotClient, TaskItem, TaskStatus
from zsynctech_studio_sdk.utils import utc_now

client = RobotClient.from_api_key(
    "<sua-api-key>",
    backend_url="http://localhost:5000",
)

@client.on_automation_start
def handle_automation() -> None:
    itens = buscar_itens_a_processar()  # a fonte de dados é sua

    with client.execution.run(observation="Processamento de itens próprios"):
        for item in itens:
            started_at = utc_now()
            resultado = processar(item)

            client.execution.report_tasks([
                TaskItem(
                    external_id=item.id,
                    status=TaskStatus.SUCCESS,
                    result=resultado,
                    started_at=started_at,
                    finished_at=utc_now(),
                )
            ])

with client:
    client.listen()
```

Exemplos completos em [`examples/`](examples/):

- [`simulate_robot.py`](examples/simulate_robot.py) - equivalente ao simulador em Node.js,
  consumindo tasks de uma fila da plataforma (`client.queue.consume()`); também demonstra
  `client.credentials.reveal()` logo após conectar.
- [`own_tasks_robot.py`](examples/own_tasks_robot.py) - robô que processa a própria fonte de
  dados (planilha, API interna, etc.) e reporta os resultados direto na execução
  (`client.execution.report_tasks()`), sem usar fila.

## Credenciais

O cofre de credenciais é acessado via REST (`/robot/credentials`), sem precisar de uma conexão
`/robot` aberta - `client.credentials` funciona mesmo antes de `client.connect()`:

```python
credencial = client.credentials.reveal("<credential-id>")
print(credencial.value)  # str (TEXT), dict[str, str] (KEY_VALUE) ou JSON (JSON)

client.credentials.rotate("<credential-id>", "novo-valor")

client.credentials.block("<credential-id>", "Login rejeitado pelo site do fornecedor")
client.credentials.expire("<credential-id>", "Senha expirou no portal do fornecedor")
```

Veja `log_credential()` em [`examples/simulate_robot.py`](examples/simulate_robot.py) para um
exemplo em contexto (revela uma credencial e loga o valor assim que conecta).

## Arquitetura

| Módulo | Responsabilidade |
| --- | --- |
| `client.py` | `RobotClient` - fachada única que compõe as peças abaixo |
| `connection.py` | `SocketConnection` - handshake, heartbeat automático, reconexão, `call`/`emit` |
| `execution.py` | `ExecutionManager` - ciclo `execution:start` / `execution:task` / `execution:finish` |
| `queue.py` | `QueueConsumer` - `queue:next` / `queue:task-result`, iteração da fila |
| `credentials.py` | `CredentialManager` - `reveal`/`rotate`/`block`/`expire`, via REST |
| `protocol.py` | Constantes do protocolo (namespace, nomes de eventos, rotas REST) |
| `exceptions.py` | Hierarquia de exceções do SDK (`RobotSDKError` e subclasses) |
| `utils.py` | Funções utilitárias reutilizáveis (detecção de plataforma, hostname, timestamps) |
| `loggers.py` | Configuração do `loguru` compartilhada pelo SDK |
| `models/` | Modelos de dados e enums (Pydantic), espelhando os DTOs/enums do backend |

Cada classe tem uma única responsabilidade (SRP): a conexão bruta não sabe o que é uma
execução, a execução não sabe como a fila funciona, e o `RobotClient` só orquestra as três.
Novos comportamentos (ex.: outro jeito de processar tasks) se registram via
`on_automation_start`/`queue.processing`, sem precisar alterar essas classes.

## Modelos e enums (`models/`)

Todos os payloads trocados com a plataforma são validados com **Pydantic** e convertidos
entre `snake_case` (Python) e `camelCase` (protocolo) automaticamente via `SdkBaseModel`.
Os enums (`TaskStatus`, `RobotInstanceStatus`, `Platform`, ...) espelham exatamente os
enums TypeScript usados por `RobotGateway` no backend.

## Logs

O SDK usa [`loguru`](https://loguru.readthedocs.io/) e já vem configurado com um formato
legível por padrão. Para customizar (nível, arquivo de destino, JSON estruturado):

```python
from zsynctech_studio_sdk.loggers import configure_logging

configure_logging(level="DEBUG", sink="robot.log")
```

Chame antes de criar o `RobotClient`.

## Desenvolvimento

```bash
uv run pytest                          # testes
uv run ruff check src examples tests   # lint
uv run ruff format src examples tests  # formatação
uv run mypy src examples tests         # checagem de tipos (modo strict)
```

`ruff` e `mypy` só olham `src`/`examples`/`tests` (não o README) - a partir do ruff 0.12+ o
`ruff format` também reformata blocos de código Python dentro de Markdown, o que reescreveria
os exemplos deste arquivo com as convenções de um `.py` (2 linhas em branco antes de decorators
etc.) toda vez que rodasse. CI usa esse mesmo escopo (veja `.github/workflows/ci.yml`).
