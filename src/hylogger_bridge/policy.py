# Purpose: load and score a validated numeric action-selector artifact without ML dependencies.
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from hylogger_bridge.state import ACTIONS, FEATURES, State, encode


@dataclass(frozen=True)
class Policy:
    weights: list[list[float]]
    intercepts: list[float]
    dataset_sha256: str
    model_id: str

    @classmethod
    def load(cls, path: Path) -> "Policy":
        raw = path.read_bytes()
        value = json.loads(raw)
        required = {
            "schema_version",
            "algorithm",
            "features",
            "actions",
            "weights",
            "intercepts",
            "training_origin",
            "validation_status",
            "dataset_sha256",
            "training_rows",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError("invalid policy artifact fields")
        if (
            type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["algorithm"] != "multiclass_logistic_regression"
            or value["features"] != list(FEATURES)
            or value["actions"] != list(ACTIONS)
            or value["training_origin"] != "synthetic"
            or value["validation_status"] != "synthetic_only"
            or type(value["training_rows"]) is not int
            or value["training_rows"] <= 0
        ):
            raise ValueError("unsupported policy schema or provenance")
        digest = value["dataset_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError("invalid dataset hash")
        weights = value["weights"]
        intercepts = value["intercepts"]
        if not isinstance(weights, list) or len(weights) != len(ACTIONS):
            raise ValueError("invalid coefficient matrix")
        if not isinstance(intercepts, list) or len(intercepts) != len(ACTIONS):
            raise ValueError("invalid intercept vector")
        for row in [*weights, intercepts]:
            if not isinstance(row, list) or len(row) != (
                len(ACTIONS) if row is intercepts else len(FEATURES)
            ):
                raise ValueError("invalid coefficient dimensions")
            try:
                valid_numbers = all(type(v) in (int, float) and math.isfinite(v) for v in row)
            except OverflowError:
                valid_numbers = False
            if not valid_numbers:
                raise ValueError("coefficients must be finite numbers")
        return cls(
            cast(list[list[float]], weights),
            cast(list[float], intercepts),
            digest,
            hashlib.sha256(raw).hexdigest(),
        )

    def scores(self, state: State) -> dict[str, float]:
        values = encode(state)
        result = {
            action: bias + sum(w * x for w, x in zip(row, values, strict=True))
            for action, row, bias in zip(ACTIONS, self.weights, self.intercepts, strict=True)
        }
        if any(not math.isfinite(score) for score in result.values()):
            raise ValueError("model scoring overflow")
        return result

    def recommend(self, state: State) -> dict[str, object]:
        allowed = state.allowed_actions()
        scores = self.scores(state)
        return {
            "action": max(allowed, key=lambda action: scores[action]),
            "allowed_actions": list(allowed),
            "model_scores": {action: scores[action] for action in allowed},
            "selection_basis": "prerequisite_gate" if len(allowed) == 1 else "learned_scores",
            "model_id": self.model_id,
            "dataset_sha256": self.dataset_sha256,
            "training_origin": "synthetic",
            "validation_status": "synthetic_only",
            "review_status": "unreviewed",
        }
