from zsynctech_studio_sdk.models.config import RobotClientConfig


def test_defaults_hostname_and_platform_from_the_local_machine() -> None:
    config = RobotClientConfig(api_key="key", base_url="https://studio.example.com")
    assert config.hostname
    assert config.platform is not None


def test_strips_a_trailing_slash_from_base_url() -> None:
    config = RobotClientConfig(api_key="key", base_url="https://studio.example.com/")
    assert config.base_url == "https://studio.example.com"


def test_default_heartbeat_interval_is_well_under_the_server_timeout() -> None:
    config = RobotClientConfig(api_key="key", base_url="https://studio.example.com")
    assert config.heartbeat_interval_seconds < 30
