# Development

Updated: 2026-10-15

For the installed product, use the [installation guide](install.md). This guide is for working from source and reproducing calculations. The installed preview includes the actual model; source-only reproduction uses visibly labelled fixture advice unless you supply a verified model bundle.

## Reproduce the real-data case

Requires macOS or Linux, Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 22, git and internet access for the one-off downloads (Python/npm packages, pytsg and the public HyLogger package from NCI THREDDS).

```sh
git clone https://github.com/david3xu/hylogger-data-bridge && cd hylogger-data-bridge
uv sync --locked
npm --prefix app ci && npm --prefix app run build

# Science environment (GSWA pytsg, pinned) and the real package
uv venv outputs/science-env --python 3.12
uv pip install --python outputs/science-env/bin/python -r training/science.txt -e .
uv run python -m training.fetch --only SWMB007s_chips.zip

# One step: a fresh book for SWMB007s, comparing 5-10 m (target) with 0-5 m (reference)
export PYTHONPATH=src:.
outputs/science-env/bin/python -m training.live demo --book outputs/live-book/real-swmb007s.sqlite3

# Serve the book
uv run python -m hylogger_bridge.book_server --db outputs/live-book/real-swmb007s.sqlite3
```

Open `http://127.0.0.1:8766`. The first page shows the hole, both intervals, data coverage and quality calculated from the package, the advice and where it came from, and the limits of the case. Choose **accept**, **modify** or **reject**, write a note and submit. The page locks with your exact note and a new working page opens. Then, in a second terminal:

```sh
export PYTHONPATH=src:.
outputs/science-env/bin/python -m training.live continue --book outputs/live-book/real-swmb007s.sqlite3
```

`continue` follows your decision: **accept** calculates the planned interval comparison; **reject** stops without calculating; **modify** calculates only the intervals you pass explicitly (`--target 10 15 --reference 5 10`, metres) and otherwise records that clarification is needed, so you can decide again. Your note is never parsed, changed or replaced. Reload the browser page to see the result.

`demo` refuses to reuse an existing book; give a new `--book` name for a fresh case. `--package`, `--package-id`, `--target` and `--reference` select another prepared package and intervals.

## Reproducibility

| Route | Reproducible from a fresh clone | How |
| --- | --- | --- |
| Real scientific calculations (inventory, QA, interval comparison) | Yes | The quickstart above, from the public package |
| Advice on the first page without the model | Yes, labelled | Default: the book shows `origin: fixture` and says no trained model was consulted |
| Actual local model advice | Only with the model bundle | Add `--model outputs/model/real-r1/model --model-python <model environment python>` to `demo`. The public preview distributes the bundle (Qwen3.5-4B base, LoRA adapters, decision head); [training](training.md#r1-real-data-pilot) documents how it was made |

No step needs a paid service or account. The model, when used, runs offline with network access blocked.

## Run checks

```sh
bash scripts/check.sh
```

This runs Python formatting, lint, strict typing and tests; frontend checks and production build; local documentation links; and an installed-wheel probe outside the checkout. Ordinary CI uses small fixtures and never downloads raw HyLogger data or trains the large model. See [contributing and CI](github.md).

For a visibly synthetic book without source data:

```sh
uv run --locked --offline python -m hylogger_bridge.book_server
```

## Source plugin setup

After preparing the science environment and real package above:

```sh
python3 scripts/setup_plugin.py --data-root data/raw/nvcl
codex plugin marketplace add .
codex plugin add hylogger@hylogger-local
```

This developer route requires its checkout and science environment to remain available. It differs from the release installer, which registers an installed runtime and uses the workspace supplied by each chat. See [plugin development and host behavior](../../plugins/hylogger/README.md).

## Repository layout

```text
app/                   React and TypeScript evidence book
src/hylogger_bridge/   Scientific tools, book, model inference and transports
training/              Data preparation, fine-tuning and evaluation
schemas/               Shared contracts
tests/                 Python checks
scripts/               Build, release and validation tools
developer/docs/        Maintained documentation
data/                  Ignored source data; only README tracked
```

Scientific calculations belong in reproducible code. Model output is advisory; expert decisions are recorded in the browser. Keep datasets, books, generated training records and weights out of Git. Read [project instructions](../../CLAUDE.md), [architecture](design.md), [API](api.md) and [data handling](../../data/README.md) before changing these boundaries. Exact acceptance evidence belongs in the [canonical record](../../CLAUDE.md#verified-automatic-receiving-turn).
