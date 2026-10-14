# Purpose: one clock for every stored timestamp, in the contract's RFC 3339 form.
from datetime import UTC, datetime, timedelta


def moment() -> datetime:
    return datetime.now(UTC)


def now() -> str:
    return moment().isoformat()


def stamp(at: datetime, plus_seconds: float = 0) -> str:
    return (at + timedelta(seconds=plus_seconds)).isoformat()


def parse(text: str) -> datetime:
    return datetime.fromisoformat(text)
