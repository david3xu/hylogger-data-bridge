#!/bin/bash
# Purpose: install the private Apple Silicon demo kit without Python, Node or a source checkout.
set -euo pipefail
kit_dir="$(cd "$(dirname "$0")" && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "This installer supports Apple Silicon Macs."
  exit 1
fi
cd "$kit_dir"
/usr/bin/shasum -a 256 -c SHA256SUMS
install_id="$(cat build-id)"
if [[ ! "$install_id" =~ ^[a-zA-Z0-9_-]+$ ]]; then echo "Invalid installer identifier."; exit 1; fi
install_home="${XDG_DATA_HOME:-$HOME/.local/share}/hylogger"
export UV_PYTHON_INSTALL_DIR="$install_home/python"
export UV_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hylogger/uv"
runtime="$install_home/runtimes/$install_id"
mkdir -p "$install_home/runtimes" "$install_home/models"
"$kit_dir/uv" python install --no-bin 3.12
if [[ ! -f "$runtime/bin/python" ]]; then
  "$kit_dir/uv" venv --managed-python --python 3.12 "$runtime"
fi
"$kit_dir/uv" pip install --python "$runtime/bin/python" -r "$kit_dir/runtime.txt" "$kit_dir"/wheels/hylogger_data_bridge-*.whl
model_folder="$install_home/models/$install_id"
if [[ ! -d "$model_folder" ]]; then
  temporary_model="$model_folder.installing-$$"
  trap 'rm -rf "$temporary_model"' EXIT
  cp -R "$kit_dir/model" "$temporary_model"
  mv "$temporary_model" "$model_folder"
  trap - EXIT
fi
setup_options=()
if [[ "${HYLOGGER_SKIP_HOST:-0}" == 1 ]]; then setup_options+=(--no-host); fi
echo "Checking the installed local model before connecting it to your chat host."
"$runtime/bin/hylogger" check-model --model "$model_folder" --model-python "$runtime/bin/python"
"$runtime/bin/hylogger" setup --model "$model_folder" --model-python "$runtime/bin/python" "${setup_options[@]}"
echo "Installation finished. Use the folder connected to your chat."
echo "Host-workspace access and automatic return remain separate acceptance gates for this build."
