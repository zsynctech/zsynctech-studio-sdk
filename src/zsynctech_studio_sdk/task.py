from zsynctech_studio_sdk.utils import get_utc_now
from zsynctech_studio_sdk.models import TaskModel
from zsynctech_studio_sdk.enums import TaskStatus
from zsynctech_studio_sdk import client
from uuid_extensions import uuid7
from typing import Optional


TASK_STATUS_COMPLETED = [
    TaskStatus.FAIL,
    TaskStatus.SUCCESS,
    TaskStatus.VALIDATION_ERROR,
]


class Task:
    def __init__(self, execution_id: str, code: Optional[str] = None, description: Optional[str] = None):
        self._current_task = TaskModel(
            executionId=execution_id,
            startDate=get_utc_now()
        )
        self._resource_path = "tasks"

        if code:
            self._current_task.code = code
        else:
            self._current_task.code = str(uuid7())

        if description:
            self._current_task.description = description
        else:
            self._current_task.description = "Descrição não informada"
        
    @property
    def task_id(self):
        return self._current_task.id
    
    def _update(
            self,
            status: Optional[TaskStatus] = None,
            observation: Optional[str] = None,
        ) -> dict:
        if status in TASK_STATUS_COMPLETED:
            self._current_task.endDate = get_utc_now()

        if status is not None:
            self._current_task.status = status
    
        if observation is not None:
            self._current_task.observation = observation

        client.post(
            endpoint=self._resource_path,
            json=self._current_task.model_dump()
        )

        return self._current_task.model_dump()

    def start(self, observation: Optional[str] = None) -> dict:
        """Updates the task status to running

        Args:
            observation (Optional[str], optional): Task observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current task
        """
        return self._update(TaskStatus.RUNNING, observation)

    def fail(self, observation: Optional[str] = None) -> dict:
        """Updates the task status to fail

        Args:
            observation (Optional[str], optional): Task observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current task
        """
        return self._update(TaskStatus.FAIL, observation=observation)

    def success(self, observation: Optional[str] = None) -> dict:
        """Updates the task status to success

        Args:
            observation (Optional[str], optional): Task observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current task
        """
        return self._update(TaskStatus.SUCCESS, observation=observation)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._current_task.status not in TASK_STATUS_COMPLETED:
            if exc_type is not None:
                self.fail(observation=str(exc_value))
            else:
                self.success()

        return False