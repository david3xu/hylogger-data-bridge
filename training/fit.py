# Purpose: train the selected LoRA/decision head and export its complete local model.
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from hylogger_bridge.advice.assets import sha, write
from hylogger_bridge.advice.encode import VERSION as INPUT_VERSION
from hylogger_bridge.advice.precision import prepare
from training.records import convert, load


def fingerprints(model: Any) -> dict[str, str]:
    """Check that both adapters and the head changed, rather than only fitting a new head."""
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        import mlx.core as mx
        import numpy as np
        from mlx.utils import tree_flatten

        values = tree_flatten(model.trainable_parameters())
        arrays = ((name, np.asarray(value.astype(mx.float32)).tobytes()) for name, value in values)
    else:
        arrays = (
            (name, value.detach().float().cpu().numpy().tobytes())
            for name, value in model.named_parameters()
            if value.requires_grad
        )
    digests = {"lora": hashlib.sha256(), "head": hashlib.sha256()}
    counts = dict.fromkeys(digests, 0)
    for name, raw in arrays:
        key = "lora" if "lora" in name.lower() else "head" if "head" in name.lower() else None
        if key is not None:
            digests[key].update(name.encode() + raw)
            counts[key] += 1
    if not all(counts.values()):
        raise ValueError(f"expected trainable LoRA and head parameters, got {counts}")
    return {key: digest.hexdigest() for key, digest in digests.items()}


def run(config: Path, records: Path, output: Path) -> None:
    settings = json.loads(config.read_text())
    if output.exists():
        raise ValueError("choose a new output directory; do not overwrite an earlier run")
    rows = load(records)
    if {r["origin"] for r in rows} != {settings["data_origin"]}:
        raise ValueError("record provenance differs from the experiment configuration")
    # Imported only inside the heavy experiment; ordinary checks need no training framework.
    from unsloth import DecisionTrainer, FastDecisionModel, is_bfloat16_supported

    TrainingArguments = importlib.import_module("transformers").TrainingArguments

    start = time.monotonic()
    model, tokenizer = FastDecisionModel.from_pretrained(
        model_name=settings["model"],
        revision=settings["revision"],
        max_seq_length=settings["max_seq_length"],
        load_in_4bit=True,
        random_state=settings["seed"],
    )
    precision = prepare(model)
    model = FastDecisionModel.get_peft_model(
        model,
        r=settings["lora_rank"],
        lora_alpha=settings["lora_rank"] * 2,
        lora_dropout=0,
        random_state=settings["seed"],
        use_gradient_checkpointing=False,
    )
    partitions = {}
    for split in ("train", "validation", "test"):
        selected = [convert(row) for row in rows if row["split"] == split]
        items, report = FastDecisionModel.build_dataset(selected, tokenizer, model)
        if report["skipped"] or report.get("truncated", 0) or len(items) != len(selected):
            raise ValueError(f"dataset encoding discarded information: {split}: {report}")
        partitions[split] = items
    before = fingerprints(model)
    baseline = FastDecisionModel.evaluate(model, tokenizer, partitions["validation"])
    baseline_test = FastDecisionModel.evaluate(model, tokenizer, partitions["test"])
    mac = platform.system() == "Darwin"
    trainer = DecisionTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=partitions["train"],
        eval_dataset=partitions["validation"],
        args=TrainingArguments(
            output_dir=str(output / "checkpoints"),
            max_steps=settings["max_steps"],
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=settings["learning_rate"],
            warmup_steps=0,
            bf16=not mac and is_bfloat16_supported(),
            fp16=False,
            logging_steps=1,
            save_strategy="no",
            eval_strategy="no",
            report_to="none",
            seed=settings["seed"],
            dataloader_num_workers=0,
        ),
    )
    trained = trainer.train()
    after = fingerprints(model)
    if any(before[key] == after[key] for key in before):
        raise ValueError("training did not change both LoRA and head parameters")
    FastDecisionModel.for_inference(model)
    metrics = FastDecisionModel.evaluate(model, tokenizer, partitions["test"])
    reference = []
    for row in [r for r in rows if r["split"] == "test"]:
        item = convert(row)
        answers = FastDecisionModel.predict(model, tokenizer, item["state"], item["questions"])
        reference.append({"request": row["request"], "answers": answers})
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output / "adapter"), tokenizer)
    # Preserve the trained adapters over the exact pinned base. Merging a quantized Qwen
    # checkpoint changed predictions in the measured Mac run; never promote that export.
    from huggingface_hub import snapshot_download

    base = Path(
        snapshot_download(settings["model"], revision=settings["revision"], local_files_only=True)
    )
    packaged = output / "model"
    shutil.copytree(base, packaged / "base", ignore=shutil.ignore_patterns(".cache"))
    shutil.copytree(output / "adapter", packaged / "adapter")
    dependencies = {
        dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
    }
    if mac:
        import mlx.core as mx

        peak_memory = int(mx.get_peak_memory())
    else:
        import torch

        peak_memory = int(torch.cuda.max_memory_allocated())
    report = {
        "version": f"qwen35-4b-{uuid4().hex[:12]}",
        "input_version": INPUT_VERSION,
        "precision": precision,
        "action_types": sorted(
            {c["action_type"] for r in rows for c in r["request"]["candidates"]}
        ),
        "config": settings,
        "data_origin": settings["data_origin"],
        "purpose": settings["purpose"],
        "records_sha256": sha(records),
        "label_origins": sorted({r["label_origin"] for r in rows}),
        "groups": {s: sorted({r["group"] for r in rows if r["split"] == s}) for s in partitions},
        "dependencies": dependencies,
        "before_validation": baseline,
        "before_test": baseline_test,
        "after_test": metrics,
        "parameter_fingerprints_before": before,
        "parameter_fingerprints_after": after,
        "train_metrics": trained.metrics,
        "elapsed_seconds": time.monotonic() - start,
        "host": platform.platform(),
        "source_files": {
            str(p): sha(p)
            for p in sorted(
                [*Path("training").glob("*.py"), *Path("src/hylogger_bridge/advice").glob("*.py")]
            )
        },
        "python": sys.version,
        "peak_accelerator_bytes": peak_memory,
        "reference": reference,
        "limitations": settings.get(
            "limitations",
            [
                "Portability experiment; synthetic teaching labels are not expert truth.",
                "No claim of geological usefulness or unseen-hole generalisation.",
            ],
        ),
    }
    write(packaged, report)
    (output / "run.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"Saved self-contained base/adapter model to {output}; local reload is still required.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/qwen.json"))
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.config, args.records, args.output)


if __name__ == "__main__":
    main()
