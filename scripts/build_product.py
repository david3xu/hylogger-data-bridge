# Purpose: build a private local demo installer containing the installed app, uv and trained bundle.
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

from hylogger_bridge.advice.assets import sha, verify


def requirements(python: Path) -> str:
    result = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.metadata as m,json; print(json.dumps(["
            "[d.metadata['Name'],d.version,d.read_text('direct_url.json')] "
            "for d in m.distributions()]))",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    pins = []
    for name, version, direct in json.loads(result.stdout):
        if name.lower().replace("_", "-") == "hylogger-data-bridge":
            continue
        if direct:
            source = json.loads(direct)
            url = source["url"]
            commit = source.get("vcs_info", {}).get("commit_id", "")
            if not url.startswith("https://github.com/unslothai/") or not re.fullmatch(
                r"[a-f0-9]{40}", commit
            ):
                raise ValueError(f"unsupported local/non-pinned model dependency: {name}")
            # HTTP source archives build without Git on the expert's computer.
            pins.append(f"{name} @ {url}/archive/{commit}.zip")
        else:
            pins.append(f"{name}=={version}")
    return "\n".join(sorted(pins, key=str.casefold)) + "\n"


def build(model: Path, model_python: Path, output: Path, archive: bool = False) -> Path:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise ValueError("the initial installer target is macOS Apple Silicon")
    if output.exists():
        raise ValueError("choose a fresh output folder; existing installers are preserved")
    manifest = verify(model)
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["npm", "--prefix", "app", "run", "build"], cwd=root, check=True)
    output.mkdir(parents=True)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(output / "wheels")], cwd=root, check=True
    )
    wheel = next((output / "wheels").glob("hylogger_data_bridge-*.whl"))
    build_id = hashlib.sha256(wheel.read_bytes()).hexdigest()[:16]
    (output / "build-id").write_text(build_id + "\n")
    (output / "runtime.txt").write_text(requirements(model_python))
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv is required on the build machine")
    shutil.copy2(uv, output / "uv")
    shutil.copy2(root / "packaging/Install.command", output / "Install.command")
    (output / "Install.command").chmod(0o755)
    shutil.copytree(model, output / "model")
    (output / "INSTALL.txt").write_text(
        "HyLogger private Apple Silicon demo kit\n\n"
        "Install and sign in to Codex desktop first. Internet is needed during installation.\n"
        "Double-click Install.command. Use the folder already connected to your chat host.\n"
        "The installer manages Python, scientific/model dependencies, the book and plugin.\n"
        "No source checkout, Node, training or administrator access is required.\n"
        "Keep enough disk space for the model, runtime and this installer.\n\n"
        f"Model: {manifest['version']}; trained on organiser measurements with teaching labels.\n"
        "Predictions collapse to clarify; usefulness is not established.\n"
        "No HyLogger source data is included. No expert validation is claimed.\n"
        "Automatic continuation and ChatGPT host acceptance are separate release gates.\n"
        "This local kit is not signed/notarized or a public release.\n"
    )
    names = [p for p in sorted(output.rglob("*")) if p.is_file()]
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha(p)}  {p.relative_to(output)}\n" for p in names)
    )
    if archive:
        shutil.make_archive(str(output), "zip", root_dir=output.parent, base_dir=output.name)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    folder = build(
        args.model.resolve(), args.model_python.absolute(), args.output.resolve(), args.archive
    )
    print(f"Private demo kit prepared: {folder}. Nothing was published.")


if __name__ == "__main__":
    main()
