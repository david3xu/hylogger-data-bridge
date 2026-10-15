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
  if [[ -f "$kit_dir/model-parts.txt" ]]; then
    mkdir -p "$kit_dir/downloads" "$temporary_model"
    release_url="$(cat "$kit_dir/release-url")"
    while read -r expected_hash part_name; do
      if [[ ! "$part_name" =~ ^model-part-[0-9]+$ ]]; then echo "Invalid model part."; exit 1; fi
      part_path="$kit_dir/downloads/$part_name"
      if [[ ! -f "$part_path" ]] || [[ "$(/usr/bin/shasum -a 256 "$part_path" | /usr/bin/awk '{print $1}')" != "$expected_hash" ]]; then
        /usr/bin/curl --fail --location --retry 3 "$release_url/$part_name" -o "$part_path.partial"
        if [[ "$(/usr/bin/shasum -a 256 "$part_path.partial" | /usr/bin/awk '{print $1}')" != "$expected_hash" ]]; then
          echo "Model download checksum mismatch."; exit 1
        fi
        mv "$part_path.partial" "$part_path"
      fi
    done < "$kit_dir/model-parts.txt"
    cat "$kit_dir"/downloads/model-part-* | /usr/bin/tar -xf - -C "$temporary_model"
    while read -r expected_hash relative_name model_url; do
      if [[ "$relative_name" != base/model.safetensors || "$model_url" != https://huggingface.co/mlx-community/Qwen3.5-4B-4bit/resolve/* ]]; then
        echo "Invalid upstream model file."; exit 1
      fi
      destination="$temporary_model/$relative_name"
      /usr/bin/curl --fail --location --retry 3 "$model_url" -o "$destination.partial"
      if [[ "$(/usr/bin/shasum -a 256 "$destination.partial" | /usr/bin/awk '{print $1}')" != "$expected_hash" ]]; then
        echo "Upstream model checksum mismatch."; exit 1
      fi
      mv "$destination.partial" "$destination"
    done < "$kit_dir/model-files.txt"
  else
    cp -R "$kit_dir/model" "$temporary_model"
  fi
  mv "$temporary_model" "$model_folder"
  trap - EXIT
fi
setup_options=()
# The public preview opens standalone books; host integration is explicitly opt-in.
if [[ "${HYLOGGER_INSTALL_HOST:-0}" != 1 || "${HYLOGGER_SKIP_HOST:-0}" == 1 ]]; then
  setup_options+=(--no-host)
fi
echo "Checking the installed local model before connecting it to your chat host."
"$runtime/bin/hylogger" check-model --model "$model_folder" --model-python "$runtime/bin/python"
"$runtime/bin/hylogger" setup --model "$model_folder" --model-python "$runtime/bin/python" "${setup_options[@]}"
echo "Installation finished. Open a real-data book with:"
printf '"%s/bin/hylogger" review --workspace /path/to/folder --package SWMB007s_chips --target 5 10 --reference 0 5\n' "$runtime"
echo "To discover packages first, omit --package, --target and --reference."
echo "After deciding in the book, use the same command with --case CASE_ID instead of --package."
echo "Host-workspace access and automatic return remain separate acceptance gates for this build."
