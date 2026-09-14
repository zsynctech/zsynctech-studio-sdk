"""Consistent logger construction reusable across every SDK module."""

import logging

_BASE_LOGGER_NAME = "zsynctech_studio_sdk"


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under the SDK's base logger.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A standard library logger. The SDK never configures handlers or levels itself -
        that is the host application's responsibility - it only ensures every module logs
        under the same ``zsynctech_studio_sdk`` hierarchy so callers can filter/configure it
        as a single unit (e.g. ``logging.getLogger("zsynctech_studio_sdk").setLevel(...)``).
    """
    if name == _BASE_LOGGER_NAME or name.startswith(f"{_BASE_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_BASE_LOGGER_NAME}.{name}")
