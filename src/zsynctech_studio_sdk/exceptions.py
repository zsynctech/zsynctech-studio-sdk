"""Exception hierarchy raised by the SDK. Every exception the SDK raises is one of these,
so a caller only ever needs `except RobotSDKError` to catch everything the SDK can throw."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.enums import CredentialStatus


class RobotSDKError(Exception):
    """Base class for every exception raised by zsynctech-studio-sdk."""


class RobotConnectionError(RobotSDKError):
    """Connecting or the handshake itself failed.

    Covers an invalid/inactive API key, a robot at its `maxConcurrency` limit, or the
    server never confirming the connection (no `connected` event) within `ack_timeout`.
    """


class NotConnectedError(RobotSDKError):
    """An operation that requires an active connection was called before `connect()` or
    after `disconnect()`."""


class AckTimeoutError(RobotSDKError):
    """The server did not acknowledge an event, AND reported no error either, within the
    configured timeout. See `ServerRejectedError` for when the server DID respond, just not
    with success."""


class ServerRejectedError(RobotSDKError):
    """The gateway's own exception filter rejected the call - its `error` event arrived
    before the acknowledgement did, carrying the real reason (e.g. "Nenhuma execução em
    andamento..."). Without this, a NestJS WS exception filter never resolves the original
    call's acknowledgement on its own; the caller would otherwise just see a generic
    `AckTimeoutError` after waiting out the full `ack_timeout`, with the real reason only
    ever logged, never raised - see `SocketConnection._on_error`/`call`."""


class NoActiveExecutionError(RobotSDKError):
    """An operation that requires an open execution (queue consumption, task reporting) was
    called without one - see `@robot.execution` / `robot.start_execution()` - or on an execution
    that has already finished."""


class TaskAlreadyReportedError(RobotSDKError):
    """A task's outcome was reported a second time. Each task has exactly one outcome."""


class TaskWarning(Exception):  # noqa: N818 - raised by robot code to mean "done, with a remark", not a failure
    """Raise from a function decorated with `@robot.task` to report the task as WARNING: it got
    done, with a remark. `message` is the remark; `result`, whatever was produced anyway.

        @robot.task
        def process(task):
            if partial:
                raise TaskWarning("Dado parcial retornado", result={"protocolo": numero})

    Not a `RobotSDKError`: the SDK never raises it, robot code does.
    """

    def __init__(self, message: str, *, result: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.result = result


class CredentialRequestError(RobotSDKError):
    """A `CredentialManager` REST call failed - a non-2xx response, or the request never made
    it to the server at all (network error, timeout)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CredentialNotActiveError(CredentialRequestError):
    """The platform revealed a credential that is not ACTIVE (expired, for one): its value is not
    handed to the robot. Trying a login with it again is how a site ends up blocking the account -
    an admin has to update it in the vault first.

    A `CredentialRequestError`, so code that already handles that one keeps working.
    """

    def __init__(self, credential: str, status: CredentialStatus) -> None:
        super().__init__(
            f"A credencial '{credential}' está {status.value} na plataforma - atualize-a no cofre antes de o robô "
            "usá-la (nenhuma tentativa de login com ela)"
        )
        self.credential = credential
        self.status = status
