from enum import StrEnum


class TaskStatus(StrEnum):
    UNPROCESSED = 'UNPROCESSED'
    VALIDATION_ERROR = 'VALIDATION_ERROR'
    SUCCESS = 'SUCCESS'
    FAIL = 'FAIL'
    RUNNING = 'RUNNING'
