# Purpose: build the wheel and prove its schema loads from an install outside the checkout.
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MEMBER = "hylogger_bridge/contracts/v1.json"
PROBE = (
    "import sys\n"
    "from hylogger_bridge.advice.provider import ModelProvider\n"
    "assert callable(ModelProvider.assess)\n"
    "import hylogger_bridge.contracts.load as load\n"
    "assert load.__file__.startswith(sys.argv[1]), load.__file__\n"
    "assert load.schema()['title'].startswith('HyLogger')\n"
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(work / "dist")], cwd=root, check=True
        )
        wheel = next((work / "dist").glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            if archive.read(MEMBER) != (root / "schemas" / "v1.json").read_bytes():
                raise SystemExit("The wheel lacks schemas/v1.json or carries a different copy")
        env = work / "venv"
        subprocess.run(["uv", "venv", "--python", sys.executable, str(env)], check=True)
        python = str(env / "bin" / "python")
        subprocess.run(["uv", "pip", "install", "--python", python, str(wheel)], check=True)
        # -I ignores the working directory and environment, so only the installed copy can load.
        subprocess.run([python, "-I", "-c", PROBE, str(env)], cwd=work, check=True)
    print("Wheel carries the schema and loads outside the checkout")


if __name__ == "__main__":
    main()
