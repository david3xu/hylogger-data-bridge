# Purpose: execute the training bundle on a named Colab runtime without implicit file syncing.
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    folder = Path("/content/hylogger-model")
    with ZipFile("/content/source.zip") as bundle:
        # Accept the explicit source bundle only; never extract arbitrary absolute/parent paths.
        for item in bundle.infolist():
            if Path(item.filename).is_absolute() or ".." in Path(item.filename).parts:
                raise ValueError("unsafe source bundle path")
        bundle.extractall(folder)
    os.chdir(folder)
    sys.path[:0] = [str(folder), str(folder / "src")]
    from training.fit import run

    run(folder / "training/qwen.json", Path("/content/records.jsonl"), Path("/content/model-run"))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "training.check",
            "/content/model-run/merged",
            "--output",
            "/content/model-run/reload.json",
        ],
        check=True,
        env={**os.environ, "PYTHONPATH": str(folder / "src")},
    )
    import shutil

    shutil.make_archive("/content/model-run", "zip", "/content/model-run")
    print("Download /content/model-run.zip and the runtime log before releasing this runtime.")


if __name__ == "__main__":
    main()
