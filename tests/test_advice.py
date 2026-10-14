# Purpose: exercise advisory safety, training leakage and exported-asset integrity boundaries.
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from hylogger_bridge.advice.assets import REQUIRED, adapter_view, verify, write
from hylogger_bridge.advice.encode import encode
from hylogger_bridge.advice.provider import ModelProvider
from hylogger_bridge.contracts.assess import check_advice
from training.records import convert, load
from training.smoke import records

AT = "2026-10-15T09:00:00+00:00"


def request() -> dict[str, Any]:
    row: dict[str, Any] = records()[0]["request"]
    return row


def predictor(state: str, questions: dict[str, Any]) -> dict[str, Any]:
    # Deliberately score the QA action by its description, independently of option position.
    weights = {
        key: 7 if json.loads(value)["action_type"] == "qa_check" else 1
        for key, value in questions["follow_up"]["criteria"].items()
    }
    return {
        "follow_up": {
            "answer": max(weights, key=lambda key: weights[key]),
            "probabilities": {key: value / sum(weights.values()) for key, value in weights.items()},
        }
    }


def test_advice_keeps_identity_when_candidates_are_reordered() -> None:
    provider = ModelProvider(predictor, "synthetic-test-model", "synthetic")
    for offered in (
        request(),
        {**request(), "candidates": list(reversed(request()["candidates"]))},
    ):
        advice = provider.assess(offered, AT)
        check_advice(offered, advice)
        assert advice["suggestions"][0]["candidate_id"] == "cand-qa_check"
        assert advice["origin"] == "model"
        assert "synthetic" in advice["limitations"][0]
        assert advice["uncertainty"] is None
        assert all(item["evidence_ids"] == [] for item in advice["suggestions"])
        assert all("score" not in item for item in advice["suggestions"])


@pytest.mark.parametrize("defect", ["unknown", "missing", "nan", "negative", "sum", "answer"])
def test_invalid_model_output_cannot_become_advice(defect: str) -> None:
    def broken(state: str, questions: dict[str, Any]) -> dict[str, Any]:
        result = predictor(state, questions)
        part = result["follow_up"]
        scores = part["probabilities"]
        if defect == "unknown":
            scores["foreign"] = 0
        elif defect == "missing":
            scores.pop(next(iter(scores)))
        elif defect == "nan":
            scores[next(iter(scores))] = float("nan")
        elif defect == "negative":
            scores[next(iter(scores))] = -1
        elif defect == "sum":
            scores.update(dict.fromkeys(scores, 0.5))
        else:
            part["answer"] = "unknown"
        return result

    with pytest.raises(ValueError):
        ModelProvider(broken, "test", "synthetic").assess(request(), AT)


def test_encoding_excludes_labels_and_preserves_unknown_features() -> None:
    row = deepcopy(records()[0])
    row["request"]["evidence"][0]["features"]["unobserved"] = None
    first = convert(row)
    row["gold"] = "cand-clarify"
    second = convert(row)
    assert first["state"] == second["state"]
    assert first["questions"] == second["questions"]
    assert first["gold"] != second["gold"]
    assert json.loads(first["state"])["evidence"][0]["features"]["unobserved"] is None


def test_ambiguous_candidate_ids_are_refused() -> None:
    offered = request()
    offered["candidates"].append(deepcopy(offered["candidates"][0]))
    with pytest.raises(ValueError, match="unique"):
        encode(offered)


def test_whole_source_group_must_stay_in_one_split(tmp_path: Path) -> None:
    rows = records()
    rows[-1]["group"] = rows[0]["group"]
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="leaks"):
        load(path)


def test_unresolved_labels_are_refused(tmp_path: Path) -> None:
    rows = records()
    rows[0]["label_origin"] = "unresolved"
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="unresolved"):
        load(path)


def test_checkpoint_tampering_is_detected(tmp_path: Path) -> None:
    # Fake bytes test manifest integrity only; no model loading or inference is claimed.
    for name in REQUIRED | {"base/model.safetensors"}:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"synthetic manifest test")
    write(tmp_path, {"data_origin": "synthetic"})
    verify(tmp_path)
    (tmp_path / "adapter/joint_head.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hashes"):
        verify(tmp_path)


def test_real_origin_cannot_be_claimed_without_source_provenance(tmp_path: Path) -> None:
    rows = records()
    rows[0]["origin"] = "organiser"
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="provenance"):
        load(path)


def test_adapter_base_resolution_survives_relocation_without_mutation(tmp_path: Path) -> None:
    bundle = tmp_path / "original"
    (bundle / "base").mkdir(parents=True)
    (bundle / "adapter").mkdir()
    for name in ("adapter_config.json", "unsloth_decision_config.json"):
        (bundle / "adapter" / name).write_text('{"base_model":"remote/original"}')
    original = (bundle / "adapter/unsloth_decision_config.json").read_bytes()
    bundle = bundle.rename(tmp_path / "relocated")
    with adapter_view(bundle) as view:
        saved = json.loads((view / "unsloth_decision_config.json").read_text())
        assert saved["base_model"] == str((bundle / "base").resolve())
    assert (bundle / "adapter/unsloth_decision_config.json").read_bytes() == original
    assert not view.exists()
