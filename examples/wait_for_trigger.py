"""Simulates a real robot: connects and idles, waiting for the platform to trigger it.

Run this, then in the Robôs UI open your robot -> aba Instâncias (you should see this
connection listed) and click "Iniciar automação" - `run_automation` below fires in response.

    ZSYNCTECH_API_KEY=<your robot's api key> uv run python examples/wait_for_trigger.py

Set ZSYNCTECH_BASE_URL too if you're not pointing at a local dev backend on :5000.
Stop with Ctrl+C.
"""

import os
from random import randint
from time import sleep

from zsynctech_studio_sdk import RobotClient

API_KEY = os.environ["ZSYNCTECH_API_KEY"]
BASE_URL = os.environ.get("ZSYNCTECH_BASE_URL", "http://localhost:5000")
TASK_COUNT = 15

client = RobotClient(api_key=API_KEY, base_url=BASE_URL, hostname="wait-for-trigger-example")


@client.on_start
def run_automation() -> None:
    print("automation:start received - running...")
    client.start_execution(total=TASK_COUNT, observation="Triggered from the platform")

    for i in range(TASK_COUNT):
        # Each item gets its own external_id - reusing one across tasks makes the platform
        # treat later reports as retries of the same task (see execution-task.consumer.ts),
        # collapsing the running success count instead of counting each one.
        try:
            with client.start_task(external_id=f"item-{i}"):
                sleep(randint(1, 4))  # ... do the actual work here ...
                raise RuntimeError("Ocorreu um erro inesperado")  # auto-reports error() on exit
        except RuntimeError:
            pass  # already reported via task.error() - just keep the loop going
    client.finish_execution()
    print("execution finished")


def main() -> None:
    with client:
        print("connected as instance", client.instance_code)
        print("waiting for automation:start - trigger it from the Robôs UI...")
        client.wait_forever()


if __name__ == "__main__":
    main()
