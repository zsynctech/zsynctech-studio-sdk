"""Models for the connect handshake, both over Socket.IO and the REST fallback."""

from zsynctech_studio_sdk.models.base import CamelModel


class ConnectResult(CamelModel):
    """What the platform returns on a successful connect.

    Mirrors ``RobotConnectResponseDto`` (socket ``connected`` event and
    ``POST /v1/robot/connect``): the robot's own fields plus the newly created instance's
    identity. Extra fields the backend may add to the robot DTO over time are ignored rather
    than rejected, so the SDK doesn't break on additive backend changes.
    """

    id: str
    name: str
    max_concurrency: int
    instance_id: str
    instance_code: str
