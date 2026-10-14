#!/usr/bin/env bash
# Purpose: run the prepared local demo model on one canonical assessment request.
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
model_python="${HYLOGGER_MODEL_PYTHON:-$root/cache/model-env/bin/python}"
model_dir="${HYLOGGER_MODEL_DIR:-$root/outputs/model/demo/model}"
request_file="${1:-$root/outputs/model/request.json}"
if [[ ! -x "$model_python" ]]; then
  echo "Model environment missing; follow developer/docs/training.md." >&2
  exit 1
fi
exec "$model_python" -I -m hylogger_bridge.advice.cli --model "$model_dir" --request "$request_file"
