"""loguru setup shared by every module in the SDK.

Every module logs through the same `logger` instance imported from here, so a robot script
gets one consistent, readable stream of `[timestamp] LEVEL - message` lines without having to
configure logging itself - though it's free to call `configure_logging()` again to redirect
to a file, change the level, or emit structured JSON.
"""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger as _logger

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>zsynctech-studio-sdk</cyan> - <level>{message}</level>"
)


def configure_logging(*, level: str = "INFO", sink: Any = None, serialize: bool = False) -> None:
    """(Re)configure the SDK's loguru sink.

    Called automatically by `RobotClient` on construction using `RobotClientConfig.log_level`.
    Call it again yourself - before constructing `RobotClient` - to log to a file, change the
    level, or switch to structured (`serialize=True`) output instead.
    """
    _logger.remove()
    _logger.add(
        sink or sys.stderr,
        level=level.upper(),
        format=_LOG_FORMAT,
        colorize=sink is None,
        serialize=serialize,
        backtrace=False,
        diagnose=False,
    )


logger = _logger
