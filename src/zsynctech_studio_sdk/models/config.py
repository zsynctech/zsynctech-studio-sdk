from typing import Optional, List
from pydantic import BaseModel
from enum import StrEnum


class InputOutputTypes(StrEnum):
    FTP = 'FTP'
    API = 'API'
    FILA = 'FILA'


class Credential(BaseModel):
    key: str
    value: str
    encrypted: bool


class Config(BaseModel):
    instanceId: str
    executionId: str
    automationName: Optional[str] = "System"
    clientId: Optional[str] = None
    userId: Optional[str] = "System"
    outputPath: Optional[str] = None
    inputPath: Optional[str] = None
    inputMetaData: Optional[dict] = None
    inputType: Optional[InputOutputTypes] = InputOutputTypes.FTP
    outputType: Optional[InputOutputTypes] = InputOutputTypes.FTP
    outputMetaData: Optional[dict] = None
    keepAlive: Optional[bool] = False
    keepAliveInterval: Optional[int] = 30
    credentials: Optional[List[Credential]] = None
