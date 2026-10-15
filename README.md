# HyLogger Data Bridge

Review drill-hole evidence from a conversation, with the results in a live investigation book.

HyLogger Data Bridge helps geologists check data quality and compare depth intervals using local HyLogger/TSG packages. Scientific tools calculate the evidence, a local fine-tuned model offers advisory suggestions, and the expert records the next step in the book. Each decision preserves its evidence and exact note.

**[Download for macOS · Apple Silicon](https://github.com/david3xu/hylogger-data-bridge/releases/download/v0.1.2-preview.1/hylogger-macos-arm64.zip)** · [Release notes](https://github.com/david3xu/hylogger-data-bridge/releases/tag/v0.1.2-preview.1) · [Installation help](developer/docs/install.md)

## Install

Requires an Apple Silicon Mac and an installed, signed-in Codex desktop. The first installation needs internet and about 3.2 GB of model downloads. Model and runtime use about 4.3 GiB on disk, plus managed Python and caches. This is an unsigned preview.

1. **Download** the ZIP above and extract it with Finder.
2. **Install:** open `Install.command` in the extracted folder. To run it from Terminal instead, open Terminal in that folder and run:

   ```sh
   bash Install.command
   ```

3. **Start a new local Codex chat** in the folder containing your supported HyLogger data.

The installer sets up Python, scientific dependencies, the book, the existing model and Codex tools. You do not need Git, Node, a source checkout or a training run. No HyLogger source data is included. See [data preparation and troubleshooting](developer/docs/install.md).

## Use

Ask in chat:

> Review SWMB007s: check data quality and compare 5–10 m with 0–5 m.

Use your own hole identifier and depth intervals. The agent discovers supported packages in the connected workspace and opens the evidence book beside the conversation.

1. **Review** the data coverage, QA, comparison plan and separately labelled model advice.
2. **Decide in the book:** continue, change the investigation, or set the candidate aside. Add your note and record the decision.
3. **Continue in chat:** the bound Codex conversation receives the saved decision and updates the next page. Earlier pages stay locked.

If a chat turn is already running, its notification waits until that turn finishes. If automatic return is unavailable, tell the agent you have committed your decision; it reads the saved record before acting.

## What this preview does

- Reads supported local TSG packages with GSWA's [pytsg](https://github.com/Geological-Survey-of-Western-Australia/pytsg).
- Checks interval coverage and valid-spot counts, then compares TSG-interpreted SWIR mineral groups.
- Keeps evidence, model advice and human choices separate, with persistent pages and provenance.
- Supports expert evidence review for **resource evaluation**, demonstrated on the real SWMB007s metre-chip package.

It does not estimate resources, calculate assay overlap or identify minerals from raw spectra. The fine-tuned Qwen3.5-4B model is experimental: it predicted `clarify` for every held-out case, matching the majority baseline (38.75%). Its advice is not geological judgement or permission to act. See [training and evaluation](developer/docs/training.md#r1-real-data-pilot).

The installed Codex fallback completed the automatic browser → chat → book cycle. Fresh-chat first-class MCP selection, ChatGPT/Work compatibility, physical fresh-machine installation and expert geological validation remain unverified. [Validation record](CLAUDE.md#verified-automatic-receiving-turn).

## Data and provenance

The demonstration uses `SWMB007s_chips.zip` from the WA NVCL catalogue on NCI THREDDS (DOI 10.25914/ctaf-6c13), licensed [CC BY 4.0](https://thredds.nci.org.au/thredds/fileServer/rs07/license/license_CCBY4.txt). Model preparation used 19 frozen packages, documented in the [training guide](developer/docs/training.md). Raw packages, images, books and generated training records are excluded from this repository and installer. [Data sources and handling](data/README.md).

## Documentation

| I want to… | Guide |
| --- | --- |
| Install, prepare data or troubleshoot | [Installation](developer/docs/install.md) |
| Run from source or reproduce the demo | [Development](developer/docs/develop.md) |
| Understand the scientific and expert-review boundaries | [Design](developer/docs/design.md) |
| Inspect model training and evaluation | [Training](developer/docs/training.md) |
| Integrate tools or work on the Codex plugin | [API](developer/docs/api.md) · [Plugin](plugins/hylogger/README.md) |
| Contribute or inspect validation | [Contributing](developer/docs/github.md) · [Acceptance](CLAUDE.md#verified-automatic-receiving-turn) |

Independent project for the [GSWA HyLogger Hackathon 2026](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026), Data Adoption theme. No project source-code licence has been selected; source datasets and bundled dependencies retain their own licences. AI assisted development and preparation.
