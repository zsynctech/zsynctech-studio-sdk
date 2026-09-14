# zsynctech-studio-sdk

Python SDK for connecting RPA robots to the ZsyncTech Studio platform. Wraps the `/robot`
Socket.IO protocol (connection handshake, automatic heartbeat, execution lifecycle, and the
optional server-side task queue) behind a single `RobotClient`.

## Install

```bash
uv add zsynctech-studio-sdk
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
            ...  # do the actual work - auto-reports success on a clean exit
        client.finish_execution()
    except Exception:
        client.finish_execution(status=ExecutionFinishStatus.FAILED)
        raise


with client:
    client.wait_forever()
```

The client authenticates on `connect()`, keeps a background heartbeat running for as long as
the connection is open, and invokes the `on_start` callback whenever the platform (or a
schedule) triggers this instance's automation.

## Reporting tasks

`start_task()` returns a handle for one task - call `.success()`/`.warning()`/`.error()` to
report its outcome, instead of building a `Task` model by hand:

```python
task = client.start_task(external_id="row-42")
try:
    ...
    task.success()
except Exception as exc:
    task.error(message=str(exc))
```

Or as a context manager, which reports automatically (success on a clean exit, error on an
exception) unless the block already reported explicitly:

```python
with client.start_task(external_id="row-42") as task:
    ...
    task.warning(message="needs review")  # optional - overrides the default success
```

To report several tasks in one call (e.g. after processing a batch), build
`Task` instances directly and use `report_tasks([...])`:

```python
from zsynctech_studio_sdk import Task, TaskStatus

client.report_tasks([
    Task(status=TaskStatus.SUCCESS, external_id="item-1"),
    Task(status=TaskStatus.FAILURE, external_id="item-2", message="timeout"),
])
```

## Consuming the server-side queue

```python
with client:
    client.start_execution()
    while (task := client.claim_next_task()).has_task:
        # ... process task.payload ...
        client.report_task_result(task.task_id, TaskStatus.SUCCESS)
    client.finish_execution()
```

## Development

```bash
uv sync
uv run pytest --cov=zsynctech_studio_sdk
uv run mypy --strict src
uv run ruff check src tests
uv run black --check src tests
```
