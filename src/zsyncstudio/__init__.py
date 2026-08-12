"""SDK Python para robôs (RPA) integrarem com o ZSync Tech Studio.

Ao estilo do `playwright`, este pacote não expõe um cliente diretamente —
escolha a variante síncrona ou assíncrona:

```python
from zsyncstudio.sync_api import Client

client = Client("https://studio.exemplo.com", api_token)
# client.instance_id já vem do próprio token (zst_<instanceId>.<secret>)

pending = client.get_pending_execution()
if pending is not None:
    execution = client.run_execution(pending)
    execution.start()

    for invoice in invoices:
        task = execution.task(invoice.number)
        task.start()
        try:
            process(invoice)
        except Exception as exc:
            task.error(str(exc))
        else:
            task.finish()

    if execution.had_errors:
        execution.error("alguns itens falharam")
    else:
        execution.finish()
```

```python
from zsyncstudio.async_api import Client

client = Client(base_url, api_token)
...
```
"""

__version__ = "1.3.19"

__all__ = ["__version__", "main"]


def main() -> None:
    print(f"zsyncstudio {__version__}")
