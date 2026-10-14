# Purpose: train a local supervised selector and export portable numeric JSON.
import hashlib
import json
import warnings
from pathlib import Path

from hylogger_bridge.state import ACTIONS, FEATURES, State, encode


def train(dataset: Path, output: Path) -> dict[str, object]:
    # sklearn is needed only for training, never for inference.
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression

    raw = dataset.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"origin", "description", "records"}:
        raise ValueError("training dataset requires origin, description and records")
    if value["origin"] != "synthetic" or not isinstance(value["description"], str):
        raise ValueError("this mechanics prototype accepts only declared synthetic data")
    if not isinstance(value["records"], list) or not value["records"]:
        raise ValueError("training records must be a nonempty list")
    features: list[list[float]] = []
    targets: list[str] = []
    for record in value["records"]:
        if not isinstance(record, dict) or set(record) != {"state", "action"}:
            raise ValueError("each training record requires state and action")
        state = State.from_dict(record["state"])
        action = record["action"]
        if action not in state.allowed_actions():
            raise ValueError("training action violates prerequisites")
        features.append(encode(state))
        targets.append(action)
    if set(targets) != set(ACTIONS):
        raise ValueError("training data must cover every supported action")
    model = LogisticRegression(C=10.0, max_iter=2000, random_state=0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        model.fit(features, targets)
    indices = [list(model.classes_).index(action) for action in ACTIONS]
    artifact: dict[str, object] = {
        "schema_version": 1,
        "algorithm": "multiclass_logistic_regression",
        "features": list(FEATURES),
        "actions": list(ACTIONS),
        "weights": model.coef_[indices].tolist(),
        "intercepts": model.intercept_[indices].tolist(),
        "training_origin": "synthetic",
        "validation_status": "synthetic_only",
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "training_rows": len(targets),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return artifact
