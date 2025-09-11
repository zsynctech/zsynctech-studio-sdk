from datetime import datetime, timezone
import re


def get_utc_now() -> str:
    """
    Get the current date and time in UTC format as an ISO string.

    Returns:
        str: Current UTC datetime in ISO format with 'Z' suffix (e.g., '2024-01-15T10:30:45.123Z')
    """
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def validate_id_format(v):
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', v):
        raise ValueError('ID deve ser um UUID válido')
    version = int(v[14], 16)
    if version != 7:
        raise ValueError('ID deve ser um UUID7 válido')
    return v