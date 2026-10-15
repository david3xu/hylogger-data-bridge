# Purpose: prepare redistributable preview assets without publishing scientific records.
import argparse
import json
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from hylogger_bridge.advice.assets import sha, verify
from scripts.build_product import build

PUBLIC_KEYS = {
    "schema_version",
    "version",
    "input_version",
    "precision",
    "action_types",
    "config",
    "data_origin",
    "purpose",
    "records_sha256",
    "label_origins",
    "groups",
    "dependencies",
    "before_validation",
    "before_test",
    "after_test",
    "parameter_fingerprints_before",
    "parameter_fingerprints_after",
    "train_metrics",
    "elapsed_seconds",
    "limitations",
    "files",
}


def public_manifest(model: Path) -> None:
    path = model / "manifest.json"
    value = json.loads(path.read_text())
    public = {k: v for k, v in value.items() if k in PUBLIC_KEYS}
    public["distribution"] = "Public preview; reference measurements and machine metadata omitted"
    path.write_text(json.dumps(public, indent=2, allow_nan=False) + "\n")
    verify(model)


def prepare(model: Path, python: Path, output: Path, tag: str) -> None:
    if output.exists():
        raise ValueError("Use a fresh output folder")
    output.mkdir(parents=True)
    kit = output / "hylogger-macos-arm64"
    build(model, python, kit)
    public_manifest(kit / "model")
    notices = kit / "notices"
    notices.mkdir()
    sources = {
        "QWEN-LICENSE": "https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/LICENSE",
        "UV-LICENSE-MIT": "https://raw.githubusercontent.com/astral-sh/uv/main/LICENSE-MIT",
        "UV-LICENSE-APACHE": "https://raw.githubusercontent.com/astral-sh/uv/main/LICENSE-APACHE",
    }
    for name, url in sources.items():
        with urllib.request.urlopen(url, timeout=30) as response:
            (notices / name).write_bytes(response.read())
    root = Path(__file__).resolve().parents[1]
    for name in ("react", "react-dom", "scheduler", "lucide-react"):
        license_path = root / "app/node_modules" / name / "LICENSE"
        if license_path.exists():
            shutil.copy2(license_path, notices / f"{name}-LICENSE")
    (notices / "MODEL.txt").write_text(
        "Qwen3.5-4B, Copyright 2026 Alibaba Cloud, Apache-2.0.\n"
        "Base: mlx-community/Qwen3.5-4B-4bit revision "
        "0e7ffd5c629ef7719d4cbc04069232580bfa9d9c.\n"
        "Modified by HyLogger Data Bridge: LoRA adapters and decision head fine-tuned on "
        "organiser-derived measurements; labels are teaching rules, not expert decisions.\n"
        "NVCL WA catalogue / Geological Survey of Western Australia, CC BY 4.0: "
        "https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026 and https://creativecommons.org/licenses/by/4.0/\n"
        "Training source and method attribution: developer/docs/training.md "
        "in the release source.\n"
        "Held-out predictions collapse to clarify (38.75%, majority baseline). "
        "No geological usefulness or expert validation is established.\n"
        "Original weights, tokenizer assets and attribution remain unchanged; only the runtime "
        "manifest omits source reference measurements and private machine metadata.\n"
        "uv: Copyright Astral Software Inc., MIT OR Apache-2.0; licenses included.\n"
        "Other Python dependencies are downloaded by their package managers with their licenses.\n"
    )
    archive = output / "model.tar"
    with tarfile.open(archive, "w") as stream:
        for path in sorted((kit / "model").rglob("*")):
            if path.is_file():
                stream.add(path, arcname=str(path.relative_to(kit / "model")), recursive=False)
    parts = []
    with archive.open("rb") as stream:
        number = 0
        while block := stream.read(512 * 1024 * 1024):
            part = output / f"model-part-{number:03d}"
            part.write_bytes(block)
            parts.append(part)
            number += 1
    archive.unlink()
    shutil.rmtree(kit / "model")
    (kit / "model-parts.txt").write_text("".join(f"{sha(p)}  {p.name}\n" for p in parts))
    release = f"https://github.com/david3xu/hylogger-data-bridge/releases/download/{tag}"
    (kit / "release-url").write_text(release + "\n")
    (kit / "INSTALL.txt").write_text(
        "HyLogger public preview — macOS Apple Silicon\n\n"
        "Double-click Install.command (or run bash Install.command). Internet is required.\n"
        "It downloads about 3 GB of model parts and installs managed Python and dependencies.\n"
        "No Node, Git, administrator access or source checkout is required.\n"
        "Run the printed hylogger review command with your local folder. Omit --package to list "
        "supported packages. Expert decisions are entered in the browser book.\n"
        "After deciding, run review --workspace FOLDER --case CASE_ID to continue explicitly.\n"
        "No HyLogger source data is included. Model advice is weak and experimental.\n"
        "Host-workspace chat, automatic return and ChatGPT support "
        "are NOT enabled in this preview.\n"
        "Host registration is opt-in with HYLOGGER_INSTALL_HOST=1; adapter remains unfinished.\n"
        "Unsigned / not notarized. Keep enough space for downloads, model, runtime and Python.\n"
    )
    (kit / "SHA256SUMS").unlink()
    names = [p for p in sorted(kit.rglob("*")) if p.is_file()]
    (kit / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(kit)}\n" for p in names))
    with zipfile.ZipFile(output / "hylogger-macos-arm64.zip", "w", zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(kit.rglob("*")):
            if path.is_file():
                stream.write(path, path.relative_to(output))
    wheel = next((kit / "wheels").glob("*.whl"))
    shutil.copy2(wheel, output / wheel.name)
    assets = [output / "hylogger-macos-arm64.zip", output / wheel.name, *parts]
    (output / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in assets))
    print(f"Preview assets prepared at {output}; nothing published by this script.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    prepare(args.model.resolve(), args.model_python.absolute(), args.output.resolve(), args.tag)


if __name__ == "__main__":
    main()
