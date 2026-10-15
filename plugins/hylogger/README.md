# HyLogger local Codex preview

Install once into the local host, select a supported package folder, then ask ordinary geological review questions. The preview runs real QA and TSG-interpreted SWIR interval comparison. Decisions remain in the evidence book; the chat reads their committed record before continuing.

## Prepare and install

Requires Python 3.12, uv, Node.js 22, git and the Codex CLI supplied with your desktop setup. From this checkout, follow the [real-data quickstart](../../README.md#real-data-quickstart). It prepares `outputs/science-env`, builds `app/dist` and obtains the official SWMB007s package. Installing the project into that science environment with `-e .` removes the runtime import-path setup requirement.

Then run:

```sh
python3 scripts/setup_plugin.py --data-root data/raw/nvcl
codex plugin marketplace add .
codex plugin add hylogger@hylogger-local
```

The setup command saves repository and authorised data locations under your user configuration (`~/.config/hylogger/runtime.json`, or `XDG_CONFIG_HOME`). Default books live under `~/.local/share/hylogger/cases`; existing books are never moved or deleted. Select another folder using `--data-root` or a different book registry using `--cases`. Select a parent folder containing unpacked package folders, each optionally with a `pkg/` subfolder; this version does not ingest arbitrary archives or assay files.

The installed plugin is a host-managed cached copy. Its launcher resolves the saved runtime without depending on a terminal's current directory or exported variables. Keep the configured checkout and science environment available. Re-run setup after moving the checkout. This is a developer preview, not a self-contained end-user installer.

If the desktop does not expose the plugin immediately, restart the app and start a new **local Codex** conversation. Verify installation with `codex plugin list --marketplace hylogger-local --json`. Shell invocation of an MCP server alone does not install the skill.

## Expert workflow

Ask normally: “Review hole SWMB007s: compare 5–10 m with 0–5 m and check quality first.” The skill checks existing cases, discovers the requested package inside the selected folder, and asks for missing or ambiguous information.

1. The tools prepare real inventory and QA, then return evidence with source, state and origin plus separately labelled advice.
2. Open the returned book URL and review the evidence. A ready page offers accept, modify and reject for the proposed next step.
3. Commit the decision and exact note **in the browser**. Return to chat and say: “I have committed my decision.”
4. The tools verify that the decision exists. Accept performs the planned comparison; reject stops; modify needs explicit validated replacement intervals or produces a clarification step. The old page stays locked.

This is **explicit chat continuation**. Browser SSE is live display transport and never wakes an LLM. No tool records a human decision or geological approval. Test activity is not expert validation.

## Tools and provenance

Six expert tools: `find_packages`, `list_cases`, `start_case`, `read_case`, `open_book`, `continue_case`. Existing worker operations are not exposed in expert mode. Invalid inputs or failed starts return errors rather than fabricated evidence.

Default advice is `origin: fixture`, with an explicit statement that no trained model ran. A requested `--model` uses the existing verified local provider and fails if its bundle/runtime cannot load; it never silently falls back. The trained model's collapsed predictions are disclosed separately in the [training guide](../../developer/docs/training.md). TSG group interpretations are not mineral abundance, fresh mineral identification, assays or resource estimates.

If you already have a prepared model bundle and its working model environment, select them once:

```sh
python3 scripts/setup_plugin.py --data-root data/raw/nvcl \
  --model /absolute/path/to/model \
  --model-python /absolute/path/to/model-env/bin/python
```

The science service keeps reading packages in its science environment. A persistent child process loads the actual checkpoint in the selected model environment, offline, and returns validated advice. Loading or inference failure is an error, never a fixture substitution. Keep this interpreter path intact, including its environment symlink. Startup announces the loaded model version on stderr. Use `python3 scripts/setup_plugin.py --fixture` to explicitly return to fixture advice; `HYLOGGER_FIXTURE=1` temporarily selects fixtures for technical smoke checks. No weights are included in the plugin or downloaded by it.

## Verification and scope

The production-boundary regressions cover fractional/exact case identity, failed-start recovery, authorised-folder containment, book identity, competing starts, and preservation of existing books. `python3 scripts/smoke_test.py` uses a disposable registry, real package reading and fixture advice. It does not simulate an expert decision.

Actual normal-chat selection and the owner-driven browser round trip must be recorded separately. This version claims neither ChatGPT Work support nor automatic continuation. Remote/cloud access, tunnel distribution, publication and bundled weights are outside this preview.

Manifest and marketplace formats follow the [official OpenAI packaging guidance](https://developers.openai.com/plugins/build/plugins), checked 15 October 2026. The portable `plugin.json` and `mcp.json` use Agent Plugins 1.0.0; the compatibility overlay preserves the same identity/version. Local host installation is separate from public directory submission.
