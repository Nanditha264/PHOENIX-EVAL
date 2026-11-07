"""Time and ISO 8601 formatting utilities."""

from datetime import datetime, timezone


def current_utc_timestamp() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def current_utc_iso() -> str:
    """Return the current UTC timestamp formatted as an ISO 8601 string."""
    return current_utc_timestamp().isoformat()


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
    dt = datetime.fromisoformat(timestamp_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
