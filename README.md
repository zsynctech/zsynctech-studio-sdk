# zsynctech-sdk

SDK Python oficial para conectar robôs de RPA à plataforma **zsynctech-studio**: execuções,
fila de tasks, tasks de fonte própria e cofre de credenciais.

A base são chamadas simples; os decorators e blocos `with` são atalhos opcionais por cima
delas. Use o que encaixar no seu script - não há conexão para gerenciar: ela abre na primeira
chamada que precisa e fecha sozinha quando o processo termina.

## Uso rápido

```python
from zsynctech_studio_sdk import Robot

robot = Robot.from_env()  # lê ZSYNC_API_KEY e ZSYNC_BACKEND_URL

@robot.task
def processar(task):
    return consultar_portal(task.payload)   # retorno -> SUCCESS, exceção -> FAILURE

@robot.execution(observation="Boletos do dia")
def main():
    for task in robot.queue.tasks():
        processar(task)

main()
```

Também dá para criar com a chave direto: `Robot("<api-key>", backend_url="https://...")`.
Qualquer campo de `RobotClientConfig` pode ser passado (ex.: `heartbeat_interval=10`).

## Execuções

Uma execução é uma rodada do robô, como a plataforma mostra. `robot.execution` serve de
decorator e de bloco `with`: abre a execução na entrada, finaliza como `COMPLETED` na saída e
como `FAILED` se der exceção (com o motivo na observação, e a exceção segue adiante).

```python
@robot.execution                                  # sem parênteses
def main(): ...

@robot.execution(observation="Boletos do dia", total=150)
def main(): ...

with robot.execution(observation="Boletos do dia") as execution:
    ...
```

Com o decorator, cada chamada da função é uma execução nova.

Para controle total, abra e feche na mão:

```python
execution = robot.start_execution(observation="Boletagem VCOM")
execution.observe("Processando 3/50")             # atualiza a observação, quantas vezes quiser
execution.finish(observation="Fila vazia, nada a processar")
# ou: execution.fail(observation="Portal fora do ar")
```

`robot.current_execution` é a execução aberta no momento (ou `None`). Uma por vez - é o que a
plataforma aceita por conexão.

## Fila da plataforma

Use quando as tasks vêm de uma planilha importada na plataforma. Cada task reporta o próprio
resultado:

```python
for task in robot.queue.tasks():          # até a fila esvaziar (ou o robô estar encerrando)
    try:
        task.success(result=processar(task.payload))
    except PortalError as erro:
        task.failure(message=str(erro))

task = robot.queue.next()                 # uma por vez; None com a fila vazia
```

`Task` tem `id`, `external_id`, `attempts` e `payload`, e reporta com `.success()`,
`.warning()` ou `.failure()` - cada um aceita `message=` e `result=`. Um resultado só por task.

Uma task deixada sem resultado não é reportada por você: ela volta para a fila quando o lease
vence, e um aviso no log diz isso.

## `@robot.task`

Reporta o resultado pela forma como a função terminou:

| A função... | Resultado |
| --- | --- |
| retorna um `dict` | `SUCCESS`, com ele como `result` |
| retorna outro valor | `SUCCESS`, com `{"value": ...}` como `result` |
| levanta `TaskWarning("...", result=...)` | `WARNING` |
| levanta qualquer outra exceção | `FAILURE`, com a mensagem da exceção |

```python
from zsynctech_studio_sdk import TaskWarning

@robot.task
def processar(task):
    dados = consultar(task.payload)
    if dados.parcial:
        raise TaskWarning("Dado parcial retornado", result=dados.to_dict())
    return dados.to_dict()
```

Se a própria função já reportou (`task.warning(...)`), o atalho não reporta de novo. Erros são
reportados, logados e **não** seguem adiante, para o loop passar ao próximo item; use
`@robot.task(reraise=True)` para que sigam.

## Sem fila: fonte de dados própria

Use quando o robô lê de uma fonte própria (planilha local, API interna, scraping, banco...).
Os resultados vão direto para a execução:

```python
@robot.task(external_id=lambda linha: linha["id"])
def enviar(linha):
    return {"protocolo": enviar_para_portal(linha)}

@robot.execution(observation="Planilha local")
def main():
    for linha in ler_planilha():
        enviar(linha)
```

Ou sem atalho, com `execution.report(...)` - os horários são preenchidos sozinhos:

```python
with robot.execution(observation="Planilha local") as execution:
    for linha in ler_planilha():
        execution.report(external_id=linha["id"], status=TaskStatus.SUCCESS, result={...})
```

Para lotes grandes, `execution.report_many([TaskItem(...), ...])` manda tudo de uma vez.

## Botão "Iniciar" da plataforma

Só para robôs que rodam sob demanda. Registre o que rodar e deixe o processo escutando:

```python
@robot.on_start
@robot.execution(observation="Disparado pela plataforma")
def main(): ...

robot.serve()   # até Ctrl+C ou a conexão encerrar de vez
```

Quem roda por agendador próprio, cron ou à mão não precisa de `serve()`: chama `main()`.
Em loops longos, `robot.stopping` diz se o robô está encerrando - `queue.tasks()` já confere.

## Conexão

Abre sozinha na primeira chamada que precisa dela e fecha quando o processo termina. Para
controlar na mão: `robot.connect()`, `robot.close()` ou `with robot: ...`.

Uma queda de conexão no meio de uma execução faz a plataforma cancelar essa execução e devolver
as tasks pegas à fila; o SDK reconecta sozinho, mas a execução cancelada não volta.

## Credenciais

O cofre é acessado via REST, sem precisar de conexão:

```python
credencial = robot.credentials.reveal_by_key("financeiro/senha-sap")
print(credencial.value)  # str (TEXT), dict[str, str] (KEY_VALUE) ou JSON (JSON)

robot.credentials.rotate_by_key("financeiro/senha-sap", "novo-valor")
robot.credentials.expire_by_key("financeiro/senha-sap", "Login rejeitado pelo site do fornecedor")
```

Prefira `key` a `id`: `id` é regenerado se o banco da plataforma for restaurado/migrado; `key`
é definida pelo admin e não muda. As versões por `id` também existem (`reveal`, `rotate`,
`expire`).

## Migrando da 1.x

| 1.x | 2.0 |
| --- | --- |
| `RobotClient.from_api_key(key, backend_url=...)` | `Robot(key, backend_url=...)` ou `Robot.from_env()` |
| `with client:` + `client.listen()` | Nada (conexão automática); `robot.serve()` só para o botão "Iniciar" |
| `@client.on_automation_start` | `@robot.on_start` |
| `with client.execution.run(...)` | `@robot.execution(...)` ou `with robot.execution(...)` |
| `client.execution.start()` / `.finish(status)` | `robot.start_execution()` / `execution.finish()` / `execution.fail()` |
| `client.execution.update_observation(...)` | `execution.observe(...)` |
| `client.execution.report_tasks([TaskItem(...)])` | `execution.report(...)` / `execution.report_many([...])` |
| `client.queue.consume()` | `robot.queue.tasks()` |
| `client.queue.claim_next()` | `robot.queue.next()` |
| `with client.queue.processing(task) as outcome: outcome.success()` | `task.success()` ou `@robot.task` |
| `client.is_stopping` | `robot.stopping` |

O protocolo com a plataforma é o mesmo: só a API do SDK mudou.

## Simulador de robô

`scripts/simulate_robot.py` se comporta como um robô de verdade, para ver a plataforma
funcionando sem um robô real (equivalente ao antigo `simulate-robot-execution.js`):

```bash
uv run python scripts/simulate_robot.py --api-key <api-key> --wait
```

Com `--wait`, conecta e fica esperando o "Iniciar" da plataforma: a cada clique roda uma
execução simulada e volta a esperar, até Ctrl+C. Sem `--wait`, roda uma execução e sai.

- `--tasks N` / `--delay MS`: quantas tasks simular e quanto cada uma demora (default 10 / 500ms).
- `--mode queue`: consome a fila do robô na plataforma em vez de inventar as tasks
  (`--queue-id` para uma fila específica).
- `--observation TEXTO` e `--final-status COMPLETED|FAILED` para controlar a execução.

Os resultados seguem a distribuição de uma automação real: 80% sucesso, 12% aviso, 8% falha.

## Exemplos

- [`simulate_robot.py`](examples/simulate_robot.py) - consome a fila da plataforma com
  `@robot.task`, espera o botão "Iniciar" e mostra `robot.credentials`.
- [`own_tasks_robot.py`](examples/own_tasks_robot.py) - processa a própria fonte de dados e
  reporta os resultados direto na execução.

## Arquitetura

| Módulo | Responsabilidade |
| --- | --- |
| `robot.py` | `Robot` - ponto de entrada: conexão automática, execuções, `@robot.task`, `serve()` |
| `execution.py` | `Execution` e `ExecutionScope` (decorator/`with` de `robot.execution`) |
| `queue.py` | `Queue` e `Task` - pegar tasks da fila e reportar o resultado de cada uma |
| `connection.py` | `Transport` (o que o `Robot` precisa do canal) e `SocketConnection`, a implementação atual |
| `credentials.py` | `CredentialManager` - `reveal`/`rotate`/`expire`, por `id` ou `key`, via REST |
| `protocol.py` | Constantes do protocolo (namespace, nomes de eventos, rotas REST) |
| `exceptions.py` | Hierarquia de exceções do SDK (`RobotSDKError` e subclasses) e `TaskWarning` |
| `utils.py` | Funções utilitárias (detecção de plataforma, hostname, timestamps) |
| `loggers.py` | Configuração do `loguru` compartilhada pelo SDK |
| `models/` | Modelos de dados e enums (Pydantic), espelhando os DTOs/enums do backend |

Nada acima de `connection.py` sabe que o canal é um socket: só conversa com `Transport`. Trocar
o transporte (por HTTP, por exemplo) não muda a API nem o código de quem usa o SDK.

## Modelos e enums (`models/`)

Todos os payloads trocados com a plataforma são validados com **Pydantic** e convertidos entre
`snake_case` (Python) e `camelCase` (protocolo) automaticamente via `SdkBaseModel`. Os enums
(`TaskStatus`, `RobotInstanceStatus`, `Platform`, ...) espelham os enums TypeScript do backend.

## Logs

O SDK usa [`loguru`](https://loguru.readthedocs.io/) e já vem configurado com um formato
legível por padrão. Para customizar (nível, arquivo de destino, JSON estruturado):

```python
from zsynctech_studio_sdk.loggers import configure_logging

configure_logging(level="DEBUG", sink="robot.log")
```

Chame antes de criar o `Robot`.

Para o script do robô logar no mesmo formato, com as mesmas cores e o mesmo nível, use
`get_logger` com o nome que deve aparecer na linha:

```python
from zsynctech_studio_sdk import get_logger

log = get_logger("boletos")
log.success("Boleto {} baixado", numero)   # ... | SUCCESS  | boletos - Boleto 123 baixado
log.warning("Sem oferta para {}", cpf)
```

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
