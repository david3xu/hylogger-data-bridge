# Purpose: hash a JSON value canonically so advice can name the exact request it answered.
import hashlib
import json


def digest(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
