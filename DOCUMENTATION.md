# zsynctech-studio-sdk — Documentation

Python SDK for connecting RPA robots to the ZsyncTech Studio platform. It wraps the platform's
`/robot` Socket.IO protocol — connection handshake, automatic heartbeat, execution lifecycle,
and the optional server-side task queue — behind a single, friendly `RobotClient`.

- **Requires:** Python ≥ 3.13
- **Package:** `zsynctech_studio_sdk`
- **Dependencies:** `pydantic`, `python-socketio[client]`, `httpx`

## Table of contents

- [Install](#install)
- [Quick start](#quick-start)
- [Core concepts](#core-concepts)
- [Reporting tasks](#reporting-tasks)
- [Consuming the server-side queue](#consuming-the-server-side-queue)
- [Error handling](#error-handling)
- [API reference](#api-reference)
  - [`RobotClient`](#robotclient)
  - [`TaskHandle`](#taskhandle)
  - [`RobotClientConfig`](#robotclientconfig)
  - [Models](#models)
  - [Enums](#enums)
  - [Exceptions](#exceptions)
- [REST fallback](#rest-fallback)
- [Development](#development)

## Install

```bash
uv add zsynctech-studio-sdk
```

or with pip:

```bash
pip install zsynctech-studio-sdk
```

## Quick start

```python
from zsynctech_studio_sdk import ExecutionFinishStatus, RobotClient

client = RobotClient(api_key="...", base_url="https://studio.zsynctech.com.br")


@client.on_start
def run_automation() -> None:
    client.start_execution(total=100)
    try:
        with client.start_task(external_id="item-1"):
            ...  # do the actual work — auto-reports success on a clean exit
        client.finish_execution()
    except Exception:
        client.finish_execution(status=ExecutionFinishStatus.FAILED)
        raise


with client:
    client.wait_forever()
```

Run it, then trigger the robot from the Studio UI ("Iniciar automação") — `run_automation`
fires in response to the platform's `automation:start` push.

## Core concepts

**Connection.** `client.connect()` (or `with client:`) opens a Socket.IO connection to the
platform's `/robot` namespace, authenticating with the robot's API key. On success the platform
assigns this connection a unique **instance** — a robot (automation) can have several
connected instances at once, up to its configured `maxConcurrency`, each independently
receiving triggers.

**Heartbeat.** The platform enforces a fixed, non-configurable 30-second instance timeout. The
SDK sends a `heartbeat` automatically every 10 seconds in the background from `connect()`
until `disconnect()` — you never need to call it yourself.

**Instance identity.** Once connected, `client.instance_id` and `client.instance_code` expose
this connection's server-assigned identity (e.g. `SDK-TEST-ROBOT-4F2A9C`). The instance code
follows a readable `<SLUG-OF-ROBOT-NAME>-<RANDOM>` pattern and shows up in the platform's
"Instâncias" tab for the robot.

**Triggers.** When someone clicks "Iniciar automação" (or a schedule fires), the platform picks
one idle connected instance and pushes it an `automation:start` event. Register a handler for
this with `@client.on_start` (decorator) or `client.on_start(fn)`.

**Executions.** One "run" of the automation is an *execution*: `start_execution()` opens it,
any number of `start_task()` / `report_tasks()` calls report individual task outcomes against
it, and `finish_execution()` closes it out. Exactly one execution is open at a time per
`RobotClient` instance (tracked internally) — you may also pass an explicit `execution_id` to
any of these methods if you're managing more than one concurrently.

## Reporting tasks

The friendliest way to report a task's outcome is `start_task()`, which returns a
[`TaskHandle`](#taskhandle):

```python
task = client.start_task(external_id="row-42")
try:
    ...
    task.success()
except Exception as exc:
    task.error(message=str(exc))
```

Or use it as a context manager — it reports automatically on exit (success on a clean exit,
failure on an exception) unless the block already reported explicitly:

```python
with client.start_task(external_id="row-42") as task:
    ...
    task.warning(message="needs review")  # optional — overrides the default success
```

To report several tasks in one call (e.g. after processing a batch), build
[`Task`](#models) instances directly and call `report_tasks`:

```python
from zsynctech_studio_sdk import Task, TaskStatus

client.report_tasks([
    Task(status=TaskStatus.SUCCESS, external_id="item-1"),
    Task(status=TaskStatus.FAILURE, external_id="item-2", message="timeout"),
])
```

> **Give every task a distinct `external_id`.** The platform treats a repeated `external_id`
> within the same execution as a *retry* of that same task — it inserts a new row for each
> report, but only counts the **net** effect (the latest status) toward the running
> success/failure/warning totals. Reusing one `external_id` across genuinely different tasks
> will make the visible counts look wrong even though every row was recorded.

`report_tasks` is rate-limited server-side to 300 calls/second — batch multiple `Task`
instances into one call rather than calling it once per task in a tight loop.

## Consuming the server-side queue

For robots that pull work from a platform-managed queue instead of generating their own task
list:

```python
with client:
    client.start_execution()
    while (task := client.claim_next_task()).has_task:
        # ... process task.payload ...
        client.report_task_result(task.task_id, TaskStatus.SUCCESS)
    client.finish_execution()
```

`claim_next_task()` requires an execution already opened via `start_execution()`. An empty
queue is a normal outcome (`task.has_task` is `False`), not an error.

## Error handling

Every method that talks to the platform can raise a subclass of `SdkError`:

```python
from zsynctech_studio_sdk import AuthenticationError, ConcurrencyLimitError, SdkError

try:
    client.connect()
except ConcurrencyLimitError:
    print("This robot is already at its maxConcurrency limit.")
except AuthenticationError:
    print("Invalid API key or inactive robot.")
except SdkError as exc:
    print(f"Could not connect: {exc}")
```

See [Exceptions](#exceptions) for the full hierarchy and when each is raised.

## API reference

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

Create either from a ready `RobotClientConfig` or its raw fields (`api_key` + `base_url`
required; any other `RobotClientConfig` field — `hostname`, `version`, `platform`,
`heartbeat_interval_seconds` — can be passed as a keyword argument too).

| Method / property | Description |
| --- | --- |
| `connect(timeout=10.0) -> ConnectResult` | Opens the connection, blocking until the platform confirms or rejects it. Raises `AuthenticationError` or `ConcurrencyLimitError`. |
| `disconnect() -> None` | Stops the heartbeat loop and closes the connection. |
| `with client: ...` | Context manager — `connect()` on enter, `disconnect()` on exit. |
| `connected -> bool` | Whether the transport currently holds an open connection. |
| `instance_id -> str` | This connection's server-assigned instance id. Requires `connect()` first. |
| `instance_code -> str` | This connection's human-readable instance code. Requires `connect()` first. |
| `on_start(callback) -> callback` | Registers the callback invoked when the platform pushes `automation:start`. Usable as a decorator. |
| `set_status(status: RobotInstanceStatus) -> None` | Manually reports this instance's status. The SDK never does this automatically. |
| `start_execution(total=None, observation=None) -> str` | Opens a new execution, remembers its id, returns it. |
| `start_task(external_id=None, attempts=1) -> TaskHandle` | Opens a task against the current execution; returns a handle to report its outcome. See [Reporting tasks](#reporting-tasks). |
| `report_tasks(tasks: Sequence[Task], execution_id=None) -> None` | Reports a batch of task outcomes. |
| `finish_execution(status=ExecutionFinishStatus.COMPLETED, execution_id=None) -> ExecutionFinishResult` | Closes out the current (or given) execution. |
| `claim_next_task(queue_id=None) -> ClaimedTask` | Claims the next pending task from the server-side queue, if any. |
| `report_task_result(task_id, status, message=None, result=None) -> TaskResultAck` | Reports the outcome of a task previously handed out by `claim_next_task`. |
| `wait_forever() -> None` | Blocks the calling thread until the connection closes or Ctrl+C is pressed. Ctrl+C stops this cleanly, letting a `with` block's `disconnect()` run afterward. |

### `TaskHandle`

Returned by `RobotClient.start_task()`. Captures `started_at` at creation.

| Method | Description |
| --- | --- |
| `success(message=None, result=None) -> None` | Reports the task as `TaskStatus.SUCCESS`. |
| `warning(message=None, result=None) -> None` | Reports the task as `TaskStatus.WARNING`. |
| `error(message=None, result=None) -> None` | Reports the task as `TaskStatus.FAILURE`. |
| `with task: ...` | Context manager — reports `success()` on a clean exit or `error()` on an exception, unless already reported explicitly inside the block. Never suppresses the exception. |

Calling a second reporting method (or exiting a `with` block after reporting explicitly inside
it) is safe — only the first report is sent. Calling a reporting method twice *explicitly*
raises `RuntimeError`.

### `RobotClientConfig`

Pydantic model backing `RobotClient`'s configuration.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | `str` | — | Required. The robot's API key. |
| `base_url` | `str` | — | Required. Platform origin, e.g. `https://studio.zsynctech.com.br`. Trailing slash stripped automatically. |
| `hostname` | `str` | local hostname | Reported at connect time. |
| `version` | `str \| None` | `None` | Optional free-form version string for the robot script. |
| `platform` | `MachineOsPlatform` | local OS family | Reported at connect time. |
| `heartbeat_interval_seconds` | `float` | `10.0` | How often the SDK sends `heartbeat`. Override only for testing — the platform's own 30s timeout is fixed and not exposed here. |

### Models

All data models live under `zsynctech_studio_sdk.models` (also re-exported from the package
root).

- **`Task`** — one task outcome: `external_id`, `attempts` (≥1, default 1), `status`
  (`TaskStatus`), `message`, `payload` (dict), `result` (dict), `started_at`/`finished_at`
  (ISO-8601 strings, default "now").
- **`ConnectResult`** — returned by `connect()`: `id`, `name`, `max_concurrency`,
  `instance_id`, `instance_code`.
- **`ExecutionStartResult`** — `execution_id`.
- **`ExecutionFinishResult`** — `execution_id`, `status`.
- **`ClaimedTask`** — `task_id` (`None` if the queue is empty — check `.has_task`),
  `external_id`, `attempts`, `payload`.
- **`TaskResultAck`** — `task_id`, `status`.

### Enums

- **`TaskStatus`** — `SUCCESS`, `FAILURE`, `WARNING`.
- **`RobotInstanceStatus`** — `ONLINE`, `BUSY`.
- **`ExecutionFinishStatus`** — `COMPLETED`, `FAILED`.
- **`MachineOsPlatform`** — `WINDOWS`, `LINUX`, `DARWIN`, `OTHER`.

### Exceptions

All exceptions inherit from `SdkError`.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The API key is invalid, or the robot is inactive. |
| `ConcurrencyLimitError` | This robot already has `max_concurrency` instances connected. |
| `NotConnectedError` | An execution/queue/task method is called before `connect()`. |
| `ExecutionError` | The platform rejects an `execution:*`/`queue:*` call (bad payload, no open execution, etc.), or the underlying call times out with no server-side error to report. |

## REST fallback

`zsynctech_studio_sdk.transport.RestTransport` covers connect/heartbeat/disconnect only, over
plain HTTP (`POST {base_url}/v1/robot/{connect,heartbeat,disconnect}`) — for callers that
explicitly want poll-only connect/heartbeat without holding a socket open. It cannot receive
`automation:start` pushes and has no execution/queue endpoints, so prefer `RobotClient` (the
Socket.IO path) unless you have a specific reason not to hold a persistent connection.

## Development

```bash
uv sync
uv run pytest --cov=zsynctech_studio_sdk
uv run mypy --strict src
uv run ruff check src tests
uv run black --check src tests
```

Project layout:

```
src/zsynctech_studio_sdk/
  client.py              # RobotClient façade
  task_handle.py          # TaskHandle
  exceptions.py            # SdkError hierarchy
  models/                   # Pydantic models only
  transport/                 # Socket.IO + REST transports
  utils/                      # small reusable helpers (time, logging, system)
tests/                         # mirrors the package layout, no real network
examples/                       # runnable scripts against a real platform instance
```
