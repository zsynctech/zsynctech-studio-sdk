"""Helpers HTTP compartilhados entre o cliente síncrono e o assíncrono.

Mantidos separados dos clientes porque não dependem de `httpx.Client` nem de
`httpx.AsyncClient` especificamente — apenas de `httpx.Response`, que as duas
variantes produzem da mesma forma.
"""

from __future__ import annotations

import re
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from .exceptions import build_api_error

try:
    _SDK_VERSION = version("zsynctech-studio-sdk")
except PackageNotFoundError:
    _SDK_VERSION = "0.0.0"

_TOKEN_PREFIX = "zst_"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def build_headers(api_token: str) -> dict[str, str]:
    """Monta os headers padrão, incluindo o token de instância `zst_...`.

    Usa `X-API-Token` (recomendado pelo `ApiTokenGuard` do backend) em vez de
    `Authorization: Bearer`, que fica reservado para sessões de usuário.
    """
    return {
        "X-API-Token": api_token,
        "Accept": "application/json",
        "User-Agent": f"zsynctech-studio-sdk/{_SDK_VERSION}",
    }


def resolve_api_base_url(base_url: str, api_version: str) -> str:
    """Monta a base_url final incluindo o prefixo `/api/<api_version>` do backend.

    O backend usa versionamento de URI (`app.enableVersioning({ type:
    VersioningType.URI })`) — todas as rotas vivem sob `/api/v<N>/...`, não
    sob a raiz. `base_url` recebido do usuário é só o host (ex.:
    `https://studio.exemplo.com`); o prefixo é acrescentado aqui para que ele
    não precise saber desse detalhe de implementação do backend.
    """
    return f"{base_url.rstrip('/')}/api/{api_version}"


def parse_instance_id(api_token: str) -> str:
    """Extrai o `instanceId` embutido no token (`zst_<instanceId>.<secret>`).

    O id da instância viaja dentro do próprio token — espelha a validação de
    `InstanceTokensService.validateToken` do backend, para falhar rápido (sem
    round-trip HTTP) se o token estiver malformado.
    """
    if not api_token.startswith(_TOKEN_PREFIX):
        raise ValueError("api_token inválido: deve começar com 'zst_'")

    instance_id, sep, secret = api_token[len(_TOKEN_PREFIX) :].partition(".")
    if not sep or not secret:
        raise ValueError("api_token inválido: formato esperado zst_<instanceId>.<secret>")
    if not _UUID_RE.match(instance_id):
        raise ValueError("api_token inválido: instanceId não é um UUID válido")

    return instance_id


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Remove chaves com valor `None` e serializa `Enum`s para o valor de API."""
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        cleaned[key] = value.value if isinstance(value, Enum) else value
    return cleaned


def raise_for_status(response: httpx.Response) -> None:
    """Levanta a subclasse de `ApiError` correspondente ao status HTTP, se houver erro."""
    if response.is_success:
        return

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    raise build_api_error(response.status_code, body)


def parse_json_or_none(response: httpx.Response) -> Any:
    """Decodifica o corpo JSON, tratando `204 No Content` / corpo vazio como `None`."""
    if response.status_code == httpx.codes.NO_CONTENT or not response.content:
        return None
    return response.json()
