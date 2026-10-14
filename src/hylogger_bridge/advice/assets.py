# Purpose: record and verify a self-contained decision checkpoint and its file hashes.
import hashlib
import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REQUIRED = {
    "base/config.json",
    "base/tokenizer_config.json",
    "base/tokenizer.json",
    "adapter/adapter_config.json",
    "adapter/unsloth_decision_config.json",
    "adapter/joint_head.safetensors",
    "adapter/joint_head_config.json",
    "adapter/tokenizer_config.json",
    "adapter/tokenizer.json",
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
        n.endswith(".safetensors") and n.startswith("base/model") for n in names
    ):
        raise ValueError("base/adapter decision artifact is incomplete")
    value = {"schema_version": 2, **run, "files": names}
    (folder / "manifest.json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify(folder: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((folder / "manifest.json").read_text())
    if manifest["schema_version"] != 2 or manifest["files"] != files(folder):
        raise ValueError("artifact file hashes do not match its manifest")
    if not REQUIRED <= set(manifest["files"]):
        raise ValueError("required checkpoint files are missing")
    return manifest


@contextmanager
def adapter_view(folder: Path) -> Iterator[Path]:
    """Resolve the bundled base locally without modifying the hashed adapter metadata."""
    adapter, base = folder / "adapter", (folder / "base").resolve()
    with tempfile.TemporaryDirectory(prefix="hylogger-adapter-") as temporary:
        view = Path(temporary)
        edited = {"adapter_config.json", "unsloth_decision_config.json"}
        for item in adapter.iterdir():
            if item.name not in edited:
                (view / item.name).symlink_to(item.resolve())
        for name in edited:
            config = json.loads((adapter / name).read_text())
            key = "base_model_name_or_path" if name == "adapter_config.json" else "base_model"
            config[key] = str(base)
            (view / name).write_text(json.dumps(config))
        yield view
