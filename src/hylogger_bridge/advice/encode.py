# Purpose: encode the same observed assessment request for training and inference.
import json
from typing import Any

from hylogger_bridge.contracts.check import validate

INSTRUCTIONS = "Which offered follow-up best serves the question and committed instruction?"


def encode(request: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, str]]:
    validate("AssessmentRequest", request)
    candidates = request["candidates"]
    ids = [item["id"] for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs must be unique")
    refs = [item["evidence_id"] for item in request["evidence"]]
    if len(refs) != len(set(refs)):
        raise ValueError("evidence IDs must be unique")
    observed = {
        "question": request["question"],
        "instruction": request["instruction"],
        "evidence": request["evidence"],
    }
    state = json.dumps(observed, sort_keys=True, ensure_ascii=False, allow_nan=False)
    mapping = {f"option_{i}": item["id"] for i, item in enumerate(candidates)}
    criteria = {
        key: json.dumps(
            {"action_type": item["action_type"], "arguments": item["arguments"]},
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        for key, item in zip(mapping, candidates, strict=True)
    }
    questions = {
        "follow_up": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria}
    }
    return state, questions, mapping
