from zsynctech_studio_sdk.models.connection import ConnectResult


def test_parses_camel_case_response_into_snake_case_fields() -> None:
    result = ConnectResult.model_validate(
        {
            "id": "robot-1",
            "name": "Robô Teste",
            "maxConcurrency": 5,
            "instanceId": "instance-1",
            "instanceCode": "ROBO-TESTE-4F2A9C",
            "status": "ONLINE",  # extra field the SDK doesn't model - must be ignored, not rejected
        }
    )
    assert result.id == "robot-1"
    assert result.max_concurrency == 5
    assert result.instance_id == "instance-1"
    assert result.instance_code == "ROBO-TESTE-4F2A9C"
