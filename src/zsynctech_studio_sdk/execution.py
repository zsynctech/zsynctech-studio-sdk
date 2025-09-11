from zsynctech_studio_sdk.models import ExecutionModel
from zsynctech_studio_sdk.enums import ExecutionStatus
from zsynctech_studio_sdk.utils import get_utc_now
from zsynctech_studio_sdk import client
from typing import Optional, Any

EXECUTION_STATUS_COMPLETED = [
    ExecutionStatus.ERROR,
    ExecutionStatus.FINISHED,
    ExecutionStatus.OUT_OF_OPERATING_HOURS,
    ExecutionStatus.INTERRUPTED,
]


class Execution:
    def __init__(self, execution_id: str):
        self._current_execution = ExecutionModel(
            id=execution_id
        )
        self._resource_path = "executions"

    @property
    def execution_id(self):
        return self._current_execution.id
    
    def _update(
            self,
            status: Optional[ExecutionStatus] = None,
            observation: Optional[str] = None,
            total_task_count: Optional[int] = None,
            current_task_count: Optional[int] = None,
        ) -> dict:

        if self._current_execution.status in EXECUTION_STATUS_COMPLETED:
            return self._current_execution.model_dump()

        if status in EXECUTION_STATUS_COMPLETED:
            self._current_execution.endDate = get_utc_now()

        if status is not None:
            self._current_execution.status = status
        
        if observation is not None:
            self._current_execution.observation = observation
        
        if total_task_count is not None:
            self._current_execution.totalTaskCount = total_task_count
    
        if current_task_count is not None:
            self._current_execution.currentTaskCount = current_task_count

        client.post(
            endpoint=self._resource_path,
            json=self._current_execution.model_dump()
        )

        return self._current_execution.model_dump()

    def set_total_task_count(self, total_task_count: int) -> dict[str, Any]:
        """Update the total number of tasks to be processed 

        Args:
            total_task_count (int): total number of tasks to be processed.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(total_task_count=total_task_count)

    def update_current_task_count(self, current_task_count: int) -> dict[str, Any]:
        """Update the number of tasks currently processed

        Args:
            current_task_count (int): Number of tasks processed.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(current_task_count=current_task_count)

    def update_observation(self, observation: str) -> dict[str, Any]:
        """Updates the execution observation text

        Args:
            observation (str): Execution observation text.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(observation=observation)

    def start(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to running

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.RUNNING, observation)

    def error(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to error

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.ERROR, observation=observation)

    def waiting(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to waiting

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.WAITING, observation=observation)

    def out_of_operating_hours(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to out_of_operating_hours

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.OUT_OF_OPERATING_HOURS, observation=observation)

    def finished(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to finished

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.FINISHED, observation=observation)

    def interrupted(self, observation: Optional[str] = None) -> dict:
        """Updates the execution status to finished

        Args:
            observation (Optional[str], optional): Execution observation text. Defaults to None.

        Returns:
            dict: Dictionary containing the information of the current execution
        """
        return self._update(ExecutionStatus.INTERRUPTED, observation=observation)
