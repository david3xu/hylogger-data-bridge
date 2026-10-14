# Purpose: one clock for every stored timestamp, in the contract's RFC 3339 form.
from datetime import UTC, datetime


def now() -> str:
    return datetime.now(UTC).isoformat()
