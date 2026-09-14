"""Exception hierarchy mirroring the platform's real `/robot` failure modes."""


class SdkError(Exception):
    """Base class for every exception raised by this SDK."""


class AuthenticationError(SdkError):
    """Raised when the platform rejects the API key (invalid or inactive robot)."""


class ConcurrencyLimitError(SdkError):
    """Raised when this robot already has ``max_concurrency`` instances connected."""


class NotConnectedError(SdkError):
    """Raised when an execution/queue method is called before :meth:`RobotClient.connect`."""


class ExecutionError(SdkError):
    """Raised when the platform rejects an `execution:*`/`queue:*` call (e.g. bad payload)."""
