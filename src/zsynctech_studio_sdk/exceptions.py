"""Exception hierarchy raised by the SDK. Every exception the SDK raises is one of these,
so a caller only ever needs `except RobotSDKError` to catch everything the SDK can throw."""

from __future__ import annotations


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
    """The server did not acknowledge an event within the configured timeout."""


class NoActiveExecutionError(RobotSDKError):
    """An operation that requires an open execution (queue consumption, task reporting) was
    called without one having been started via `ExecutionManager.start()`."""


class CredentialRequestError(RobotSDKError):
    """A `CredentialManager` REST call failed - a non-2xx response, or the request never made
    it to the server at all (network error, timeout)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
