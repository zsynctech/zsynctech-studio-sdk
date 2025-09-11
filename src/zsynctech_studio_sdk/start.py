from zsynctech_studio_sdk.utils import validate_id_format
from zsynctech_studio_sdk.models import Config
from zsynctech_studio_sdk import client
from typing import Callable, Optional
import pika
import json

EXCHANGE_NAME = "start"


class StartService:
    def __init__(self, rabbitmq_url: str, heartbeat: int = 5400):
        if client._instance_id is None:
            raise RuntimeError("Credentials not set. Call set_credentials() first.")
        self._instance_id = validate_id_format(client._instance_id)
        self._queue_name = f"robot_{self._instance_id}"
        self._connection = pika.BlockingConnection(
            parameters=pika.URLParameters(
                f"{rabbitmq_url}?heartbeat={heartbeat}"
            )
        )
        self._channel = self._connection.channel()

        self._channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type='direct',
            durable=True
        )
        self._channel.queue_declare(
            queue=self._queue_name,
            durable=True
        )
        self._channel.queue_bind(
            exchange=EXCHANGE_NAME,
            queue=self._queue_name,
            routing_key=f"instance.{self._instance_id}"
        )

    def get_start_config(self) -> Optional[Config]:
        """Checks if there are start events in the queue

        Returns:
            Optional[Config]: Returns the configuration json, 
            if the queue is empty it returns None
        """
        method_frame, _, body = self._channel.basic_get(
            queue=self._queue_name,
            auto_ack=True
        )
        if method_frame:
            try:
                message = json.loads(body)
            except json.JSONDecodeError:
                message = body.decode()
            return Config(**message)
        return None

    def start_listener(self, callback: Callable):
        """Starts a consumer to check for start events

        Args:
            callback (Callable): Function that will be 
            called when there is an event.
        """
        def _internal_callback(ch, method, properties, body):
            try:
                message = json.loads(body)
            except json.JSONDecodeError:
                message = body.decode()
            callback(Config(**message))

        self._channel.basic_consume(
            queue=self._queue_name,
            on_message_callback=_internal_callback,
            auto_ack=True
        )

        print(f"[StartService] Waiting for events in queue: {self._queue_name}...")

        try:
            self._channel.start_consuming()
        except KeyboardInterrupt:
            self.close()

    def close(self):
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            print("[StartService] Connection closed.")
