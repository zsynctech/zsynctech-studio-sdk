from zsynctech_studio_sdk.utils import get_utc_now
from zsynctech_studio_sdk.models import StepModel
from zsynctech_studio_sdk.enums import StepStatus
from zsynctech_studio_sdk import client
from typing import Optional


STEP_STATUS_COMPLETED = [
    StepStatus.FAIL,
    StepStatus.SUCCESS,
]


class Step(StepModel):
    def __init__(self, task_id: str, code: str, observation: Optional[str] = None):
        self._current_step = StepModel(
            stepCode=code,
            taskId=task_id,
            startDate=get_utc_now(),
            observation=observation,
            automationOnClientId=client._instance_id
        )
        self._resource_path = "taskSteps"

    def _update(
            self,
            status: Optional[StepStatus] = None,
            observation: Optional[str] = None,
        ) -> dict:
        if status in STEP_STATUS_COMPLETED:
            self._current_step.endDate = get_utc_now()

        if observation is not None:
            self._current_step.observation = observation
        
        if status is not None:
            self._current_step.status = status

        client.post(
            endpoint=f"{self._resource_path}",
            json=self._current_step.model_dump()
        )

        return self._current_step.model_dump()
    
    def _start(self, observation: Optional[str] = None) -> dict:
        """Updates the step status to running

        Args:
            observation (Optional[str], optional): Step observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current step
        """
        return self._update(status=StepStatus.RUNNING, observation=observation)

    def fail(self, observation: Optional[str] = None) -> dict:
        """Updates the step status to fail

        Args:
            observation (Optional[str], optional): Step observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current step
        """
        return self._update(status=StepStatus.FAIL, observation=observation)

    def success(self, observation: Optional[str] = None) -> dict:
        """Updates the step status to success

        Args:
            observation (Optional[str], optional): Step observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current step
        """
        return self._update(status=StepStatus.SUCCESS, observation=observation)

    def __enter__(self):
        self._start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._current_step.status not in STEP_STATUS_COMPLETED:
            if exc_type is not None:
                self.fail(observation=str(exc_value))
            else:
                self.success()

        return False