# Purpose: hash a request on the server so advice can name the exact request it answered.
# The hash is issued by this server and opaque to clients; clients never recompute it.
import hashlib
import json

_EXACT = 2**53


def _plain(value: object) -> object:
    # JSON has one number type: 1 and 1.0 are the same value and must hash alike.
    if isinstance(value, float) and value.is_integer() and abs(value) < _EXACT:
        return int(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def digest(value: object) -> str:
    raw = json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
