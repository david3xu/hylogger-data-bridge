# Purpose: turn an actual bounded model prediction into validated advisory metadata.
import math
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from hylogger_bridge.advice.encode import encode
from hylogger_bridge.contracts.assess import check_advice
from hylogger_bridge.contracts.digest import digest

Predict = Callable[[str, dict[str, Any]], dict[str, Any]]


class ModelProvider:
    def __init__(self, predict: Predict, version: str, data_origin: str) -> None:
        if data_origin not in {"synthetic", "organiser"}:
            raise ValueError("unknown training-data origin")
        self.predict = predict
        self.version = version
        self.data_origin = data_origin

    def assess(self, request: dict[str, Any], at: str) -> dict[str, Any]:
        state, questions, mapping = encode(request)
        result = self.predict(state, questions)["follow_up"]
        scores = result["probabilities"]
        if set(scores) != set(mapping):
            raise ValueError("model output options do not match the offered candidates")
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
            for v in scores.values()
        ):
            raise ValueError("model returned invalid option probabilities")
        if not math.isclose(sum(scores.values()), 1, abs_tol=0.001):
            raise ValueError("model probabilities must sum to one")
        order = sorted(mapping, key=lambda k: (-scores[k], k))
        if result["answer"] not in mapping or scores[result["answer"]] != scores[order[0]]:
            raise ValueError("model answer does not match its highest option probability")
        advice = {
            "contract_version": 1,
            "id": f"assess-{uuid4()}",
            "page_id": request["page_id"],
            "state_revision": request["state_revision"],
            "model_version": self.version,
            "origin": "model",
            "status": "available",
            "request_hash": digest(request),
            "suggestions": [
                {
                    "candidate_id": mapping[key],
                    "rank": rank,
                    "rationale": "Ranked by the decision head; no explanation was generated.",
                    "evidence_ids": [],
                }
                for rank, key in enumerate(order, 1)
            ],
            "evidence_gaps": [],
            "uncertainty": None,
            "limitations": [
                f"Training data origin: {self.data_origin}; usefulness is unverified.",
                "Scores are not geological confidence; calibrated uncertainty is unverified.",
                "Advice does not authorise execution or supply geological judgement.",
            ],
            "created_at": at,
        }
        check_advice(request, advice)
        return advice
