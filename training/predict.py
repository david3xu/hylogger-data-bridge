# Purpose: predict held-out rows with the untrained or the saved model, in one comparable format.
import argparse
import json
import os
import socket
from pathlib import Path
from typing import Any

from hylogger_bridge.advice.encode import encode
from training.evaluate import sha
from training.records import load


def rows_of(records: Path, split: str, rows: Path | None) -> list[dict[str, Any]]:
    """The frozen records of one split, or evaluation-only rows from a separate file."""
    if rows is not None:
        return [json.loads(line) for line in rows.read_text().splitlines() if line.strip()]
    return [row for row in load(records) if row["split"] == split]


def answer(row: dict[str, Any], predict: Any) -> dict[str, Any]:
    state, questions, mapping = encode(row["request"])
    result = predict(state, questions)["follow_up"]
    scores = {mapping[key]: value for key, value in result["probabilities"].items()}
    return {
        "id": row["id"],
        "gold": row["gold"],
        "pred": mapping[result["answer"]],
        "scores": scores,
    }


def untrained(
    config: Path, records: Path, run: Path, split: str, rows: Path | None
) -> dict[str, Any]:
    """The model as the training run began: same pinned base, seed and adapter/head setup."""
    from unsloth import FastDecisionModel

    from hylogger_bridge.advice.precision import prepare
    from training.fit import fingerprints

    settings = json.loads(config.read_text())
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name=settings["model"],
        revision=settings["revision"],
        max_seq_length=settings["max_seq_length"],
        load_in_4bit=True,
        random_state=settings["seed"],
    )
    prepare(model)
    model = FastDecisionModel.get_peft_model(
        model,
        r=settings["lora_rank"],
        lora_alpha=settings["lora_rank"] * 2,
        lora_dropout=0,
        random_state=settings["seed"],
        use_gradient_checkpointing=False,
    )
    start = fingerprints(model)
    recorded = json.loads(run.read_text())["parameter_fingerprints_before"]
    FastDecisionModel.for_inference(model)

    def predict(state: str, questions: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = FastDecisionModel.predict(model, tokenizer, state, questions)
        return result

    return {
        "model": "untrained",
        "same_start_as_training_run": start == recorded,
        "fingerprints": start,
        "recorded_fingerprints": recorded,
        "config_sha256": sha(config),
        "records_sha256": sha(records),
        "rows_sha256": sha(rows) if rows else None,
        "predictions": [answer(row, predict) for row in rows_of(records, split, rows)],
    }


def trained(folder: Path, records: Path, split: str, rows: Path | None) -> dict[str, Any]:
    """The saved base/adapter/head bundle, reloaded offline with network connections refused."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def no_network(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network access is disabled during the offline reload")

    socket.socket.connect = no_network  # type: ignore[method-assign]
    from hylogger_bridge.advice.assets import verify
    from hylogger_bridge.advice.local import LocalProvider

    manifest = verify(folder)
    provider = LocalProvider(folder)
    return {
        "model": provider.version,
        "manifest_records_sha256": manifest.get("records_sha256"),
        "records_sha256": sha(records),
        "rows_sha256": sha(rows) if rows else None,
        "offline": True,
        "predictions": [answer(row, provider.predict) for row in rows_of(records, split, rows)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("which", choices=["untrained", "trained"])
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("training/mac_real.json"))
    parser.add_argument("--run", type=Path, help="run.json of the training run (untrained only)")
    parser.add_argument("--model", type=Path, help="saved model folder (trained only)")
    parser.add_argument("--split", default="test")
    parser.add_argument("--rows", type=Path, help="evaluation-only rows instead of a split")
    args = parser.parse_args()
    if args.which == "untrained":
        value = untrained(args.config, args.records, args.run, args.split, args.rows)
    else:
        value = trained(args.model, args.records, args.split, args.rows)
    args.out.write_text(json.dumps(value, indent=2) + "\n")
    print(args.which, len(value["predictions"]), "rows ->", args.out)


if __name__ == "__main__":
    main()
