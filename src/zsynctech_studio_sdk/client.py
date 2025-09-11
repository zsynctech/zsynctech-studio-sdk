import httpx

_client = None
_secret_key = None
_instance_id = None
_server = None


def set_credentials(secret_key: str, instance_id: str, server: str):
    global _client, _secret_key, _server, _instance_id
    _secret_key = secret_key
    _instance_id = instance_id
    _server = str(server).rstrip("/")
    _client = httpx.Client(
        base_url=f"{_server}/automation-gateway/",
        headers={
            "Authorization": f"Bearer {_secret_key}::{_instance_id}"
        }
    )


def request(method: str, endpoint: str, **kwargs) -> httpx.Response:
    if _client is None:
        raise RuntimeError("Credentials not set. Call set_credentials() first.")
    response = _client.request(method, endpoint, **kwargs)
    response.raise_for_status()
    return response

def get(endpoint: str, params: dict = None) -> httpx.Response:
    return request("GET", endpoint, params=params)

def post(endpoint: str, json: dict = None) -> httpx.Response:
    return request("POST", endpoint, json=json)

def put(endpoint: str, json: dict = None) -> httpx.Response:
    return request("PUT", endpoint, json=json)

def delete(endpoint: str) -> httpx.Response:
    return request("DELETE", endpoint)