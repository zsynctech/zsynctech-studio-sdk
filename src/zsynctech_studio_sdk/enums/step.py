from enum import StrEnum


class StepStatus(StrEnum):
    UNPROCESSED = 'UNPROCESSED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAIL = 'FAIL'
