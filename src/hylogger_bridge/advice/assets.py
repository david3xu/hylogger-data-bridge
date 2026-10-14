# Purpose: record and verify a self-contained decision checkpoint and its file hashes.
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED = {
    "config.json",
    "unsloth_decision_config.json",
    "joint_head.safetensors",
    "joint_head_config.json",
    "tokenizer_config.json",
    "tokenizer.json",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def files(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): sha(p)
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.name != "manifest.json" and ".cache" not in p.parts
    }


def write(folder: Path, run: dict[str, Any]) -> None:
    names = files(folder)
    if not REQUIRED <= set(names) or not any(
        n.endswith(".safetensors") and n.startswith("model") for n in names
    ):
        raise ValueError("merged decision artifact is incomplete")
    value = {"schema_version": 1, **run, "files": names}
    (folder / "manifest.json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify(folder: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((folder / "manifest.json").read_text())
    if manifest["schema_version"] != 1 or manifest["files"] != files(folder):
        raise ValueError("artifact file hashes do not match its manifest")
    if not REQUIRED <= set(manifest["files"]):
        raise ValueError("required checkpoint files are missing")
    return manifest
