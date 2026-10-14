# Purpose: bundle an explicit source allowlist for Colab without data, weights or credentials.
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    names = [
        *root.glob("src/hylogger_bridge/advice/*.py"),
        *root.glob("src/hylogger_bridge/contracts/*.py"),
        *root.glob("training/*.py"),
        *root.glob("training/*.json"),
        root / "schemas/v1.json",
        root / "src/hylogger_bridge/__init__.py",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(names):
            archive.write(path, path.relative_to(root))
    print(f"Source bundle: {args.output}; {len(names)} allowlisted files, no datasets or weights.")


if __name__ == "__main__":
    main()
