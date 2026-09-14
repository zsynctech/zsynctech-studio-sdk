"""REST fallback transport for `/v1/robot`: connect, heartbeat, disconnect only.

Covers the subset of the protocol available without a persistent socket. It cannot receive
`automation:start` pushes and has no execution/queue endpoints - see
`robot-connection.controller.ts` for the exact (small) surface this mirrors. Prefer
:class:`~zsynctech_studio_sdk.transport.socket_transport.SocketTransport` unless the caller
specifically wants poll-only connect/heartbeat with no socket held open.
"""

from typing import Any

import httpx

from zsynctech_studio_sdk.exceptions import AuthenticationError, ConcurrencyLimitError, SdkError
from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.models.connection import ConnectResult

_CONCURRENCY_LIMIT_MARKER = "máximo de instâncias"


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    message = response.text
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        message = body["message"]

    if _CONCURRENCY_LIMIT_MARKER in message:
        raise ConcurrencyLimitError(message)
    if response.status_code in (401, 403, 404):
        raise AuthenticationError(message)
    raise SdkError(f"Request to {response.request.url} failed ({response.status_code}): {message}")


class RestTransport:
    """Thin `httpx`-based wrapper around the `/v1/robot` connect/heartbeat/disconnect endpoints."""

    def __init__(self, config: RobotClientConfig, http_client: httpx.Client | None = None) -> None:
        """Create a transport bound to ``config``.

        Args:
            config: Connection settings; only ``api_key`` and ``base_url`` are used here.
            http_client: Inject a pre-configured client (e.g. in tests). A new one is created
                against ``{base_url}/v1/robot`` otherwise.
        """
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(base_url=f"{config.base_url}/v1/robot", timeout=10.0)

    def connect(self) -> ConnectResult:
        """``POST /connect``. Note the REST endpoint accepts only ``apiKey`` - no
        hostname/version/platform metadata, unlike the socket handshake."""
        response = self._client.post("/connect", json={"apiKey": self._config.api_key})
        _raise_for_error(response)
        return ConnectResult.model_validate(response.json())

    def heartbeat(self, instance_id: str) -> dict[str, Any]:
        """``POST /heartbeat``. Returns the raw robot DTO - callers polling manually via REST
        are expected to call this on their own schedule, comfortably under 30 seconds."""
        response = self._client.post("/heartbeat", json={"instanceId": instance_id})
        _raise_for_error(response)
        body: dict[str, Any] = response.json()
        return body

    def disconnect(self, instance_id: str) -> dict[str, Any]:
        """``POST /disconnect``."""
        response = self._client.post("/disconnect", json={"instanceId": instance_id})
        _raise_for_error(response)
        body: dict[str, Any] = response.json()
        return body

    def close(self) -> None:
        """Close the underlying HTTP client, if this transport created it."""
        if self._owns_client:
            self._client.close()
