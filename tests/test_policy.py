# Purpose: verify local learning, portable scoring and enforced workflow boundaries.
import json
import subprocess
import sys
from pathlib import Path

import pytest
from sklearn.linear_model import LogisticRegression

from hylogger_bridge.policy import Policy
from hylogger_bridge.state import ACTIONS, State, encode
from hylogger_bridge.training import train


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("policy")
    dataset, artifact = root / "training.json", root / "model.json"
    subprocess.run(
        [sys.executable, "scripts/make_demo_training.py", "--out", str(dataset)],
        check=True,
    )
    train(dataset, artifact)
    return dataset, artifact


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({}, "DETECT_CHANGES"),
        ({"goal": "compare_intervals"}, "COMPARE_INTERVALS"),
        ({"goal": "assess_quality"}, "PRESENT_TO_EXPERT"),
        ({"changes_ready": True}, "GET_ASSAYS"),
        ({"changes_ready": True, "assays_status": "available"}, "CALCULATE_OVERLAP"),
        ({"changes_ready": True, "assays_status": "unavailable"}, "PRESENT_PARTIAL"),
        (
            {"changes_ready": True, "assays_status": "available", "overlap_ready": True},
            "PRESENT_TO_EXPERT",
        ),
        ({"goal": "compare_intervals", "comparison_ready": True}, "PRESENT_TO_EXPERT"),
    ],
)
def test_goal_and_evidence_change_learned_choice(
    trained: tuple[Path, Path],
    updates: dict[str, object],
    expected: str,
) -> None:
    state = State.from_dict(
        {
            "goal": "changes_with_assays",
            "data_loaded": True,
            "qa_status": "passed",
        }
        | updates
    )
    result = Policy.load(trained[1]).recommend(state)
    assert result["action"] == expected
    assert result["selection_basis"] == "learned_scores"
    assert result["validation_status"] == "synthetic_only"
    assert result["review_status"] == "unreviewed"


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({}, "LOAD_DATA"),
        ({"data_loaded": True}, "RUN_QA"),
        ({"data_loaded": True, "qa_status": "failed"}, "ASK_EXPERT"),
        ({"question_clear": False}, "ASK_EXPERT"),
        ({"cancelled": True}, "STOP"),
        ({"tool_failure": True}, "STOP"),
        ({"budget_remaining": 0}, "STOP"),
    ],
)
def test_adversarial_weights_cannot_bypass_prerequisites(
    trained: tuple[Path, Path],
    updates: dict[str, object],
    expected: str,
) -> None:
    original = Policy.load(trained[1])
    # Force every unsafe alternative to outrank the sole permitted action.
    weights = [[0.0] * len(original.weights[0]) for _ in ACTIONS]
    intercepts = [1000.0 if action != expected else -1000.0 for action in ACTIONS]
    policy = Policy(weights, intercepts, original.dataset_sha256, "test")
    result = policy.recommend(State.from_dict({"goal": "changes_with_assays"} | updates))
    assert result["action"] == expected
    assert result["selection_basis"] == "prerequisite_gate"


def test_completed_or_unavailable_actions_and_false_completion_are_masked(
    trained: tuple[Path, Path],
) -> None:
    policy = Policy.load(trained[1])
    state = State.from_dict(
        {
            "goal": "changes_with_assays",
            "data_loaded": True,
            "qa_status": "passed",
            "changes_ready": True,
            "comparison_ready": True,
            "assays_status": "unavailable",
        }
    )
    allowed = policy.recommend(state)["allowed_actions"]
    assert isinstance(allowed, list)
    assert set(allowed) == {
        "ASK_EXPERT",
        "PRESENT_PARTIAL",
    }


@pytest.mark.parametrize(
    "updates",
    [
        {"unexpected": True},
        {"data_loaded": 1},
        {"budget_remaining": True},
        {"budget_remaining": -1},
        {"goal": "invent_ore"},
        {"qa_status": "passed"},
        {"changes_ready": True},
        {"qa_status": "unknown"},
        {"assays_status": "maybe"},
        {"data_loaded": True, "qa_status": "passed", "overlap_ready": True},
    ],
)
def test_invalid_states_fail_closed(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        State.from_dict({"goal": "changes_with_assays"} | updates)


def test_export_matches_library_scores_and_retraining_is_deterministic(
    trained: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    dataset, path = trained
    records = json.loads(dataset.read_text())["records"]
    states = [State.from_dict(record["state"]) for record in records]
    reference = LogisticRegression(C=10.0, max_iter=2000, random_state=0)
    reference.fit([encode(state) for state in states], [r["action"] for r in records])
    reference_scores = reference.decision_function([encode(state) for state in states])
    policy = Policy.load(path)
    for state, scores in zip(states, reference_scores, strict=True):
        assert policy.scores(state) == pytest.approx(
            dict(zip(reference.classes_, scores, strict=True))
        )
    retrained = tmp_path / "model.json"
    train(dataset, retrained)
    assert path.read_bytes() == retrained.read_bytes()


@pytest.mark.parametrize(
    "mutation", ["nan", "oversized_integer", "dimensions", "features", "provenance"]
)
def test_corrupt_models_are_rejected(
    trained: tuple[Path, Path],
    tmp_path: Path,
    mutation: str,
) -> None:
    artifact = json.loads(trained[1].read_text())
    if mutation == "nan":
        artifact["weights"][0][0] = float("nan")
    elif mutation == "oversized_integer":
        artifact["weights"][0][0] = 10**1000
    elif mutation == "dimensions":
        artifact["intercepts"] = []
    elif mutation == "features":
        artifact["features"].reverse()
    else:
        artifact["training_origin"] = "expert_reviewed"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError):
        Policy.load(path)


def test_inference_works_with_only_standard_library(trained: tuple[Path, Path]) -> None:
    # -S omits site-packages; only the package's source directory is provided.
    source = str(Path("src").resolve())
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from hylogger_bridge.cli import main; "
        "sys.argv = ['hylogger-policy', 'recommend', '--model', sys.argv[2], "
        "'--state', 'examples/policy-state.json']; raise SystemExit(main())"
    )
    result = subprocess.run(
        [sys.executable, "-S", "-c", code, source, str(trained[1])],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["action"] == "GET_ASSAYS"


def test_cli_handles_stdin_and_invalid_input(trained: tuple[Path, Path]) -> None:
    command = ["hylogger-policy", "recommend", "--model", str(trained[1]), "--state", "-"]
    result = subprocess.run(
        command,
        input='{"goal":"assess_quality"}',
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["action"] == "LOAD_DATA"
    bad = subprocess.run(command, input="{", capture_output=True, text=True)
    assert bad.returncode == 2
    assert not bad.stdout and "Traceback" not in bad.stderr
    assert "error" in json.loads(bad.stderr)


def test_invalid_training_labels_are_rejected(trained: tuple[Path, Path], tmp_path: Path) -> None:
    dataset = json.loads(trained[0].read_text())
    dataset["records"][0]["action"] = "PRESENT_TO_EXPERT"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match="prerequisites"):
        train(path, tmp_path / "should-not-exist.json")
    assert not (tmp_path / "should-not-exist.json").exists()
