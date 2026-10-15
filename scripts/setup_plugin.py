# Purpose: persist local preview runtime locations so cached plugins need no shell environment.
import argparse
import json
import os
from pathlib import Path


def configure(
    repo: Path,
    data: Path,
    cases: Path,
    config: Path,
    model: Path | None = None,
    model_python: Path | None = None,
    fixture: bool = False,
) -> Path:
    repo, data, cases = repo.resolve(), data.expanduser().resolve(), cases.expanduser().resolve()
    if not (repo / "outputs/science-env/bin/python").is_file():
        raise ValueError("prepare outputs/science-env using the README first")
    if not (repo / "app/dist/index.html").is_file():
        raise ValueError("build the book using npm --prefix app run build first")
    if not data.is_dir():
        raise ValueError("choose an existing authorised package folder with --data-root")
    config.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(config.read_text()) if config.exists() else {}
    value = {**previous, "repo": str(repo), "data_root": str(data), "cases": str(cases)}
    if model_python is not None and model is None:
        raise ValueError("--model-python requires --model")
    if fixture and model is not None:
        raise ValueError("choose --fixture or --model")
    if model is not None:
        model = model.expanduser().resolve()
        if not (model / "manifest.json").is_file():
            raise ValueError("--model must name a prepared, verified local bundle")
        if model_python is None:
            raise ValueError("provide the prepared model interpreter with --model-python")
        model_python = model_python.expanduser().absolute()
        if not model_python.is_file() or not os.access(model_python, os.X_OK):
            raise ValueError("--model-python must be an executable interpreter")
        value.update(model=str(model), model_python=str(model_python))
    elif fixture:
        value.pop("model", None)
        value.pop("model_python", None)
    temporary = config.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(config)
    return config


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=repo / "data/raw/nvcl")
    parser.add_argument("--cases", type=Path, default=Path.home() / ".local/share/hylogger/cases")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--model-python", type=Path)
    parser.add_argument(
        "--fixture", action="store_true", help="explicitly clear saved model selection"
    )
    args = parser.parse_args()
    config = configure(
        repo,
        args.data_root,
        args.cases,
        root / "hylogger/runtime.json",
        args.model,
        args.model_python,
        args.fixture,
    )
    print(f"Runtime configured: {config}")
    print("Next: codex plugin marketplace add . && codex plugin add hylogger@hylogger-local")
    print(
        "Start a new local Codex chat after installation. Existing books were not moved or deleted."
    )


if __name__ == "__main__":
    main()
