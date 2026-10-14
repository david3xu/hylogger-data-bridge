#!/usr/bin/env bash
# Purpose: run the local policy prototype's format, lint, type and behaviour checks.
set -euo pipefail
export UV_CACHE_DIR="${UV_CACHE_DIR:-cache/uv}"
uv run --locked --offline ruff format --check src scripts tests training
uv run --locked --offline ruff check src scripts tests training
uv run --locked --offline mypy
uv run --locked --offline mypy --follow-imports=silent --ignore-missing-imports training
uv run --locked --offline python -m pytest
uv run --locked --offline python scripts/check_docs.py
uv run --locked --offline python scripts/check_wheel.py
npm --prefix app run check
