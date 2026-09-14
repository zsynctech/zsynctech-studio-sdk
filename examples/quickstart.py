"""Manual smoke test for the SDK against a real backend.

Connects a robot, opens an execution, reports one task, and finishes it - the same flow a
real robot script would follow. Run with:

    ZSYNCTECH_API_KEY=<your robot's api key> uv run python examples/quickstart.py

Set ZSYNCTECH_BASE_URL too if you're not pointing at a local dev backend on :5000.
"""

import os

from zsynctech_studio_sdk import RobotClient

API_KEY = os.environ["ZSYNCTECH_API_KEY"]
BASE_URL = os.environ.get("ZSYNCTECH_BASE_URL", "http://localhost:5000")


def main() -> None:
    client = RobotClient(api_key=API_KEY, base_url=BASE_URL, hostname="quickstart-example")

    with client:
        print("connected:", client.connected)
        print("instance_id:", client.instance_id)
        print("instance_code:", client.instance_code)

        execution_id = client.start_execution(total=1, observation="SDK quickstart example")
        print("execution_id:", execution_id)

        with client.start_task(external_id="item-1"):
            pass  # ... do the actual work here - auto-reports success on a clean exit

        result = client.finish_execution()
        print("finished:", result.execution_id, result.status)

    print("connected after disconnect:", client.connected)


if __name__ == "__main__":
    main()
