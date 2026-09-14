import httpx
import pytest

from zsynctech_studio_sdk.exceptions import AuthenticationError, ConcurrencyLimitError
from zsynctech_studio_sdk.models.config import RobotClientConfig
from zsynctech_studio_sdk.transport.rest_transport import RestTransport


def _client_for(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, base_url="https://studio.example.com/v1/robot")


def _config() -> RobotClientConfig:
    return RobotClientConfig(api_key="key-123", base_url="https://studio.example.com")


def test_connect_posts_only_the_api_key_and_parses_the_response() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "robot-1",
                "name": "Robô",
                "maxConcurrency": 1,
                "instanceId": "i1",
                "instanceCode": "R-1",
            },
        )

    transport = RestTransport(_config(), http_client=_client_for(httpx.MockTransport(handler)))
    result = transport.connect()

    assert result.instance_id == "i1"
    assert seen_requests[0].url.path == "/v1/robot/connect"
    body = seen_requests[0].content
    assert b"apiKey" in body
    assert b"key-123" in body


def test_heartbeat_and_disconnect_post_the_instance_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"instanceId" in request.content
        return httpx.Response(200, json={"id": "robot-1"})

    transport = RestTransport(_config(), http_client=_client_for(httpx.MockTransport(handler)))
    assert transport.heartbeat("instance-1")["id"] == "robot-1"
    assert transport.disconnect("instance-1")["id"] == "robot-1"


def test_connect_raises_concurrency_limit_error_on_matching_message() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"message": "Este robô já atingiu o número máximo de instâncias."})

    transport = RestTransport(_config(), http_client=_client_for(httpx.MockTransport(handler)))
    with pytest.raises(ConcurrencyLimitError):
        transport.connect()


def test_connect_raises_authentication_error_on_401() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "API key inválida ou robô inativo"})

    transport = RestTransport(_config(), http_client=_client_for(httpx.MockTransport(handler)))
    with pytest.raises(AuthenticationError):
        transport.connect()
