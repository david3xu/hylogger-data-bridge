# HyLogger Data Bridge

An expert-in-the-loop investigation toolkit for reviewing an unfamiliar drill hole with HyLogger data. Scientific code calculates the evidence, a small local model offers advice, and the geologist records the review decision in an evidence book that keeps every page and note.

**Version one, honestly:** one real hole (SWMB007s) from the public NVCL WA catalogue. The tool checks data quality and compares two depth intervals using TSG-interpreted SWIR mineral groups, shows the evidence in a browser book, records your accept / modify / reject decision with your exact note, and continues the investigation according to that decision. It does not estimate resources, identify minerals from raw spectra, or use assays (none are linked in this case). The local model is weak (see [Limitations](#limitations)).

## Real-data quickstart

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

## What you can and cannot reproduce

| Route | Reproducible from a fresh clone | How |
| --- | --- | --- |
| Real scientific calculations (inventory, QA, interval comparison) | Yes | The quickstart above, from the public package |
| Advice on the first page without the model | Yes, labelled | Default: the book shows `origin: fixture` and says no trained model was consulted |
| Actual local model advice | Only with the model bundle | Add `--model outputs/model/real-r1/model --model-python <model environment python>` to `demo`. The bundle (Qwen3.5-4B base, LoRA adapters, decision head) is not published; [training](developer/docs/training.md#r1-real-data-pilot) documents how it was made |

No step needs a paid service or account. The model, when used, runs offline with network access blocked.

## Connecting an AI tool

For the local Codex preview, after the real-data installation above:

```sh
python3 scripts/setup_plugin.py --data-root data/raw/nvcl
codex plugin marketplace add .
codex plugin add hylogger@hylogger-local
```

Start a **new local Codex chat**, then ask: “Review hole SWMB007s: check quality and compare 5–10 m with 0–5 m.” The preview discovers packages inside the configured folder and opens a browser evidence book. After committing your decision in the book, return to chat and say you have decided. It verifies the stored decision before continuing. Setup stores runtime locations in your private user configuration; books default to your user data directory, outside the checkout. See the [plugin guide](plugins/hylogger/README.md).

This is explicit continuation, not automatic browser-to-agent wakeup. Default advice is visibly labelled as a fixture; real calculations still use your selected HyLogger package. ChatGPT Work and a one-command packaged end-user release remain unverified.

`uv run hylogger-mcp --db <book>` starts a stdio MCP adapter that exposes the book's worker operations: read the book, claim, acknowledge or fail a delivery, submit evidence or a result, request advice and read delivery attempts. See the [API](developer/docs/api.md).

The local preview exposes scientific preparation and decision-directed continuation through expert MCP tools. Actual normal-chat selection is a separate host acceptance check; a direct tool smoke does not prove it. No public plugin listing, ChatGPT Work compatibility or automatic browser-triggered continuation is claimed. The intended product is: install once, connect a supported folder, chat normally, watch the book, decide, continue.

### Codex plugin (preview)

A preview plugin package for Codex desktop is provided in `plugins/hylogger/`:
- **Demonstration:** Expert chats normally → Codex selects our tools → real evidence book opens → expert decides IN THE BROWSER → expert returns to chat and says they decided → Codex verifies the committed decision through a tool → continues. This is EXPLICIT chat continuation, not automatic browser-to-agent continuation.
- **Tools:** `start_case`, `read_case`, `continue_case`, `open_book`, `find_packages`, `list_cases`.
- **Status:** Tool operation is verified by smoke test; host acceptance in Codex desktop is UNVERIFIED. See [plugins/hylogger/README.md](plugins/hylogger/README.md) for local installation instructions.

## Limitations

- **Model.** Qwen3.5-4B fine-tuned on 960 real-measurement records whose labels are teaching rules, not expert decisions. On 240 held-out records it answers `clarify` every time: 38.75%, exactly the majority baseline (untrained 17.5%). Treat its advice as an experimental, disclosed negative result. Details: [R1 real-data pilot](developer/docs/training.md#r1-real-data-pilot).
- **Science.** Mineral groups are TSG's own SWIR interpretations of clean spots, not fresh identification from spectra. Only QA and interval comparison are implemented for the real case; no assay overlap is calculated or claimed.
- **Workflow.** The worker that continues after your decision is an explicit command, not an automatic chat agent. Modified intervals are passed by an operator; notes are never parsed.
- **Validation.** No expert geological validation has been recorded. Decisions made while testing are labelled `[TEST DECISION — not expert validation]`.

## Data

NVCL WA catalogue on NCI THREDDS, licensed CC BY 4.0 ([licence](https://thredds.nci.org.au/thredds/fileServer/rs07/license/license_CCBY4.txt), DOI 10.25914/ctaf-6c13). The demonstration uses the metre-chip package `SWMB007s_chips.zip`; `training.fetch` records its URL, retrieval time, size and SHA-256 in `data/raw/nvcl/retrieval.jsonl`. Packages are read with GSWA [pytsg](https://github.com/Geological-Survey-of-Western-Australia/pytsg) at a pinned commit (`training/science.txt`). Model training used 19 frozen packages (`training/real.json`). Raw packages, books, generated records and model weights stay outside Git ([data handling](data/README.md)).

## Synthetic demo and developer checks

```sh
uv run --locked --offline python -m hylogger_bridge.book_server
```

This serves a visibly synthetic example on `http://127.0.0.1:8766` for checking the book mechanics. `bash scripts/check.sh` runs formatting, lint, strict typing, the Python and frontend tests, the documentation link check and the wheel probe. The earlier synthetic action selector and Qwen experiment are described in [training](developer/docs/training.md#running-the-selected-experiment).

## Project guide

- [Design](developer/docs/design.md): expert authority, local model, book and package boundaries.
- [Model training](developer/docs/training.md): grounded examples, supervision, the real-data pilot and its result.
- [API](developer/docs/api.md): HTTP routes, worker lifecycle and MCP tools.
- [Submission readiness](developer/docs/submission.md): version-one gates and status.
- [Tasks](developer/docs/tasks.md) and [contributing and CI](developer/docs/github.md).
- [Development instructions](CLAUDE.md) and [data handling](data/README.md).

```text
app/                   React and TypeScript evidence book
src/hylogger_bridge/   Python runtime: book, science adapter, advice, HTTP/MCP adapters
training/              Real-data preparation, the real case commands, model training and evaluation
tests/                 Python checks
schemas/               Versioned shared contracts
scripts/               Developer validation
developer/docs/        Project documentation
data/                  Local source data; only README tracked
```

## Scope and rights

Data Adoption theme: **expert evidence review supporting resource evaluation**. Resource estimation, grade control, ore–waste classification, alteration mapping, geometallurgy and environmental assessment are outside this version. A flagged interval is a review candidate, not proof of ore, grade or mineralisation. See the [scope and value criteria](developer/docs/design.md#mvp-scope-resource-evaluation-evidence-review).

This is an independent project repository for the GSWA HyLogger Hackathon 2026; see the [organiser repository](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026) for event requirements. No project licence has been selected. Source datasets keep their own licences. AI assisted preparation and implementation; claims here describe only demonstrated capabilities.
