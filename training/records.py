# Purpose: validate grounded teaching records and convert them without leaking labels.
import json
import re
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.encode import encode

SPLITS = {"train", "validation", "test"}


def load(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("training records are empty")
    groups: dict[str, str] = {}
    seen: set[str] = set()
    for row in rows:
        if row["id"] in seen:
            raise ValueError("record IDs repeat")
        seen.add(row["id"])
        split, group = row["split"], row["group"]
        if split not in SPLITS or not isinstance(group, str) or not group:
            raise ValueError("invalid split or source group")
        if group in groups and groups[group] != split:
            raise ValueError("source group leaks across splits")
        groups[group] = split
        if row["origin"] not in {"synthetic", "organiser"}:
            raise ValueError("unknown scientific-data origin")
        if row["origin"] == "organiser":
            source = row.get("provenance", {})
            required = {"source_url", "source_sha256", "tool_version", "method_version"}
            if not required <= set(source) or any(
                not isinstance(source[k], str) or not source[k].strip() for k in required
            ):
                raise ValueError("organiser records require source and processing provenance")
            if not re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"]):
                raise ValueError("organiser source hash must be SHA-256")
        if row["label_origin"] not in {"teaching_rule", "calculated_reference", "expert_reviewed"}:
            raise ValueError("unresolved labels cannot be used for training")
        _, _, mapping = encode(row["request"])
        if row["gold"] not in mapping.values():
            raise ValueError("gold must name an offered candidate")
    if {row["split"] for row in rows} != SPLITS:
        raise ValueError("train, validation and test groups are required")
    return rows


def convert(row: dict[str, Any]) -> dict[str, Any]:
    state, questions, mapping = encode(row["request"])
    key = next(key for key, value in mapping.items() if value == row["gold"])
    return {"state": state, "questions": questions, "gold": {"follow_up": key}}
