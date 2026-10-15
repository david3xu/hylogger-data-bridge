# HyLogger Data Bridge

An expert-in-the-loop investigation toolkit for reviewing unfamiliar drill holes. AI coordinates the investigation, scientific tools calculate evidence, and geologists supply geological judgement.

**Current prototype:** a live investigation book and a small trained action selector using synthetic examples. A separate fine-tuned Qwen3.5-4B demonstration supplies a verified offline local assessment interface; measured evidence is in the training guide. Explicit worker tools (HTTP routes and a stdio MCP adapter) can claim a committed decision's delivery, acknowledge it and submit evidence or a result; they are explicit calls, not an automatic bridge. Real HyLogger analysis and automatic decision delivery back to chat remain unfinished. The staged book runner does not consult the selector.

## Run the demo

Requires Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 22 for development.

```sh
uv sync --locked
npm --prefix app ci
npm --prefix app run build
uv run --locked --offline python -m hylogger_bridge.book_server
```

Open `http://127.0.0.1:8766` beside your chat. Start the synthetic example, watch evidence arrive, then submit a choice and note. That page locks and a linked working page opens. Browse history or return to the latest page. SQLite preserves the book under ignored `outputs/live-book/`; keepalives do not invoke AI.

Advice is labelled fixture advice unless a launcher is given `--model <folder>` (the local fine-tuned bundle, in the prepared model environment; see [project instructions](CLAUDE.md#commands)). Worker tools: `uv run hylogger-mcp --db outputs/live-book/demo.sqlite3` and `uv run hylogger-walkthrough` (a synthetic tool-driven walkthrough).

## Try the baseline selector

```sh
uv run --locked python scripts/make_demo_training.py --out outputs/decision-policy/training.json
uv run --locked hylogger-policy train --data outputs/decision-policy/training.json --out outputs/decision-policy/model.json
uv run --locked hylogger-policy recommend --model outputs/decision-policy/model.json --state examples/policy-state.json
```

Training and inference run locally. This synthetic classifier checks workflow mechanics; it is not a fine-tuned geological decision model or a validated resource-evaluation method.

## Qwen decision-model experiment

The selected model is Qwen3.5-4B with LoRA and a decision head. Developer preparation, bounded training, complete checkpoint export and local assessment commands are in the [training guide](developer/docs/training.md#running-the-selected-experiment). Training software uses a separate environment; ordinary validation does not download weights or run large training. Generated records and model artifacts stay outside Git.

The local provider returns ranked candidate follow-ups through the shared assessment contract. The agent/human chooses what to do; scientific tools and backend prerequisites validate execution. Synthetic teaching records establish mechanics only, not geological usefulness.

## Project guide

- [Design](developer/docs/design.md): expert authority, local model, book and package boundaries.
- [Model training](developer/docs/training.md): grounded examples, supervision, selected experiment, operating commands, supervision and evaluation.
- [Real-data pilot](developer/docs/training.md#r1-real-data-pilot): real HyLogger evidence, a human-reviewed live case, and the disclosed model limits.
- [API](developer/docs/api.md): implemented demo routes, worker lifecycle routes and MCP tools, and the event contract.
- [Tasks](developer/docs/tasks.md): frontend/backend branches and acceptance gates.
- [Contributing and CI](developer/docs/github.md): branches, checks and publication rules.
- [Development instructions](CLAUDE.md) and [data handling](data/README.md).

```text
app/                   React and TypeScript frontend
src/hylogger_bridge/   Python runtime and synthetic baseline
examples/              Small synthetic inputs
tests/                 Python checks
scripts/               Developer validation and fixture generation
training/              Developer-only Qwen training and portability checks
developer/docs/        Essential project documentation
data/                  Local source data; only README tracked
```

Run `bash scripts/check.sh` after installing dependencies. Private notes, raw data, generated models, books and build outputs are ignored. Markdown uses an explicit public allowlist.

## Scope and rights

The selected Data Adoption focus is **expert evidence review supporting resource evaluation**. The first real demonstration targets one hole, a bounded spectral-change/assay-overlap investigation and an auditable expert review cycle. Full resource estimation, grade control, ore–waste classification, alteration mapping, geometallurgy and environmental assessment are outside the MVP. See the [scope and value criteria](developer/docs/design.md#mvp-scope-resource-evaluation-evidence-review).

A flagged interval is a review candidate, not proof of ore, grade or mineralisation. Scientific review remains unreviewed until a real expert assessment is recorded.

This is an independent project repository for the GSWA HyLogger Hackathon 2026; repository creation does not submit an entry or establish eligibility. Team details and a real demonstration hole remain to be selected. Refer to the [organiser repository](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026) for event requirements.

No project licence has been selected. Source datasets retain their own licences. AI assisted preparation and implementation; final claims must describe demonstrated capabilities accurately.
