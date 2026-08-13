"""Exceções lançadas pelo SDK.

`ZSyncStudioError` é a base de tudo que o SDK lança deliberadamente. Erros de
transporte (timeout, DNS, conexão recusada) chegam como `ConnectionError`;
erros retornados pela API chegam como uma subclasse de `ApiError`, escolhida
a partir do `statusCode` HTTP devolvido pelo `AllExceptionsFilter` do backend.
"""

from __future__ import annotations

from typing import Any

from .enums import SecretStatus, SecretType


class ZSyncStudioError(Exception):
    """Classe base para todos os erros do SDK."""


class ConnectionError(ZSyncStudioError):
    """Falha de rede ao tentar alcançar o backend (timeout, DNS, recusa de conexão)."""


class ApiError(ZSyncStudioError):
    """Erro retornado pela API (HTTP 4xx/5xx) com o corpo já decodificado.

    Args:
        status_code: Código HTTP retornado.
        message: Mensagem legível, já normalizada para string (o backend às
            vezes retorna uma lista de mensagens de validação; nesse caso elas
            são unidas por "; ").
        path: Caminho da requisição, quando presente no corpo do erro.
        errors: Lista de mensagens de validação individuais, quando o corpo
            original trazia `message` como lista.
        body: Corpo bruto (já parseado como JSON) da resposta de erro.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        path: str | None = None,
        errors: list[str] | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message
        self.path = path
        self.errors = errors
        self.body = body


class ValidationError(ApiError):
    """HTTP 400/422 — payload rejeitado pelo `ValidationPipe` do backend."""


class SecretNotActiveError(ValidationError):
    """Reveal recusado porque a credencial não está `ACTIVE`.

    Carrega `status`/`status_reason`/`secret_type`/`current_version`
    extraídos do corpo do erro. `Client.get_secret()` captura esta exceção
    internamente e devolve um `Secret` com esses campos em vez de propagá-la —
    ela só chega até você se acessar a API mais diretamente.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        status: SecretStatus,
        status_reason: str | None,
        secret_type: SecretType | None = None,
        current_version: int | None = None,
        path: str | None = None,
        errors: list[str] | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(status_code, message, path=path, errors=errors, body=body)
        self.status = status
        self.status_reason = status_reason
        self.secret_type = secret_type
        self.current_version = current_version

    @property
    def is_blocked(self) -> bool:
        return self.status is SecretStatus.BLOCKED

    @property
    def is_expired(self) -> bool:
        return self.status is SecretStatus.EXPIRED


class AuthenticationError(ApiError):
    """HTTP 401 — token de API ausente, inválido ou expirado."""


class PermissionDeniedError(ApiError):
    """HTTP 403 — token válido, mas sem acesso ao recurso (ex.: instância de outro robô)."""


class NotFoundError(ApiError):
    """HTTP 404 — recurso inexistente (execução, task, instância)."""


class ConflictError(ApiError):
    """HTTP 409 — transição de estado inválida (ex.: finalizar execução já encerrada)."""


class ServerError(ApiError):
    """HTTP 5xx — erro interno do backend."""


class TaskWarning(ZSyncStudioError):
    """Levante dentro da função passada a `ExecutionRun.task()` para marcar a task
    como `WARNING` em vez de `ERROR`, sem interromper o processamento dos demais itens.
    """


class TaskSkipped(ZSyncStudioError):
    """Levante dentro da função passada a `ExecutionRun.task()` para marcar a task
    como `SKIPPED` em vez de `ERROR`, sem interromper o processamento dos demais itens.
    """


_STATUS_TO_EXCEPTION: dict[int, type[ApiError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
}


def build_api_error(status_code: int, body: Any) -> ApiError:
    """Constrói a exceção apropriada a partir do status HTTP e do corpo do erro.

    O corpo segue o formato do `AllExceptionsFilter` do backend:
    `{"statusCode": int, "message": str | list[str], "path": str, ...}`.
    """
    message: str
    errors: list[str] | None = None
    path: str | None = None

    if isinstance(body, dict):
        raw_message = body.get("message")
        path = body.get("path")
        if isinstance(raw_message, list):
            errors = [str(item) for item in raw_message]
            message = "; ".join(errors) if errors else "Erro desconhecido"
        elif raw_message is not None:
            message = str(raw_message)
        else:
            message = "Erro desconhecido"
    else:
        message = str(body) if body else f"HTTP {status_code}"

    if isinstance(body, dict) and "secretStatus" in body:
        raw_type = body.get("secretType")
        return SecretNotActiveError(
            status_code,
            message,
            status=SecretStatus(body["secretStatus"]),
            status_reason=body.get("secretStatusReason"),
            secret_type=SecretType(raw_type) if raw_type else None,
            current_version=body.get("secretCurrentVersion"),
            path=path,
            errors=errors,
            body=body,
        )

    exception_cls = _STATUS_TO_EXCEPTION.get(status_code)
    if exception_cls is None:
        exception_cls = ServerError if status_code >= 500 else ApiError

    return exception_cls(status_code, message, path=path, errors=errors, body=body)
