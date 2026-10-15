# Purpose: record which source, configuration and data produced and evaluated a model.
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

LAUNCH = "304ea542d672f6ce3d26c7f5759fb12a5081a1b5"
USED_AT_LAUNCH = (
    "training/fit.py",
    "training/records.py",
    "training/rubric.py",
    "training/real.py",
    "training/mac_real.json",
    "training/real.json",
    "src/hylogger_bridge/science/package.py",
    "src/hylogger_bridge/science/features.py",
    "src/hylogger_bridge/science/hole.py",
    "src/hylogger_bridge/science/request.py",
    "src/hylogger_bridge/advice/encode.py",
    "src/hylogger_bridge/advice/provider.py",
    "src/hylogger_bridge/advice/assets.py",
    "src/hylogger_bridge/advice/precision.py",
    "src/hylogger_bridge/advice/local.py",
)


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def blob(commit: str, path: str) -> str:
    return hashlib.sha256(git("show", f"{commit}:{path}")).hexdigest()


def build(run_json: Path, extra: list[Path]) -> dict[str, Any]:
    run = json.loads(run_json.read_text())
    head = git("rev-parse", "HEAD").decode().strip()
    return {
        "model_version": run["version"],
        "records_sha256": run["records_sha256"],
        "config": run["config"],
        "training_launch": {
            "commit": LAUNCH,
            "note": "hashes of the exact blobs committed at the launch commit. Since then "
            "fit.py, rubric.py, records.py and the config are unchanged; real.py changed only by "
            "formatting and one manifest text string; science/ changed (see the repair commit).",
            "blobs_sha256": {path: blob(LAUNCH, path) for path in USED_AT_LAUNCH},
        },
        "fit_recorded_source_hashes": {
            "note": "recorded by fit at the END of the run over the then-current tree; not "
            "proof of the code loaded at launch, and it omits science/",
            "files": run["source_files"],
        },
        "evaluation_and_runtime_revision": head,
        "dependencies": run["dependencies"],
        "python": run["python"],
        "host": run["host"],
        "parameter_fingerprints_before": run["parameter_fingerprints_before"],
        "parameter_fingerprints_after": run["parameter_fingerprints_after"],
        "artifacts_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in extra if p.exists()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("artifacts", type=Path, nargs="*")
    args = parser.parse_args()
    args.out.write_text(json.dumps(build(args.run, args.artifacts), indent=2) + "\n")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
