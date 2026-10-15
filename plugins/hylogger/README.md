# HyLogger local Codex preview

Install once, open a local chat in a supported data workspace, and ask for drill-hole evidence review. The installed tools read local TSG packages, calculate QA and compare intervals. The expert decides in the browser book; the agent verifies the stored decision before continuing. Model advice is experimental and weak.

## Installed product

Use the [public preview installer](https://github.com/david3xu/hylogger-data-bridge/releases). It provides managed Python, prebuilt UI, the scientific runtime and the existing fine-tuned model. No source checkout, Node or fixed data folder is required. Setup registers only HyLogger's local marketplace/plugin and its installed MCP server. An older local HyLogger marketplace is replaced with rollback on failure. Existing books, model assets and unrelated host settings are preserved.

Open a new local Codex conversation after installation if tools have not refreshed. Verify the plugin with `codex plugin list --marketplace hylogger-local --json` and the server with `codex mcp list --json`. An already-running chat can use the installed case command through the skill; the expert does not need to type it. This unsigned Apple Silicon preview requires internet during installation; ChatGPT/Work and physical fresh-machine acceptance remain separate.

## Expert workflow

Ask: “Review SWMB007s: check quality and compare 5–10 m with 0–5 m.” The agent obtains the trusted workspace and its actual conversation ID, discovers supported packages there, and asks for missing or ambiguous bounds. No data is bundled or searched outside that authorised workspace.

1. `start_case` prepares inventory, QA and separately labelled advice; `open_book` returns the local book URL.
2. The expert reviews evidence and commits accept, modify or reject with the exact note in the browser.
3. A lightweight watcher queues a notification to the bound Codex conversation. The book distinguishes notification receipt from completed scientific work.
4. The agent calls `read_case`, matches page/decision/continuation IDs, then calls `continue_case`. The successor contains the result; history stays locked. Duplicate or delayed notifications cannot execute later work accidentally.

An unbound case or unavailable return channel uses explicit chat follow-up. Browser SSE updates the display; it never invokes an LLM. Notes are expert context, not executable agent instructions. Test decisions are labelled and are not geological validation.

## Tools and model boundary

Six expert MCP tools: `find_packages`, `list_cases`, `start_case`, `read_case`, `open_book`, `continue_case`. Worker operations are separate. No expert tool records a human decision. Installed CLI and MCP share a durable registry and saved original workspace; read/continue/open work across entry points.

The installed model loads offline in a bounded child process. Missing or invalid requested assets fail visibly without fixture substitution. Default developer fixture mode is labelled. The actual model predicts `clarify` for every held-out record (38.75%, majority baseline); it is not useful geological advice. See [training](../../developer/docs/training.md). Scientific results describe TSG-interpreted SWIR groups, not mineral abundance, assays or resource estimates.

## Developer route and evidence

Follow the [developer quickstart](../../README.md#real-data-quickstart), then run:

```sh
python3 scripts/setup_plugin.py --data-root data/raw/nvcl
codex plugin marketplace add .
codex plugin add hylogger@hylogger-local
```

This older route requires its checkout and science environment to remain available. `--model` and `--model-python` select an existing bundle; `--fixture` explicitly selects labelled technical fixtures. Production installation uses the bundled installed runtime instead.

The [canonical acceptance record](../../CLAUDE.md#verified-automatic-receiving-turn) separates unit checks, real-data installed tests and actual host-return acceptance. Automatic receiving-side continuation passed through the installed agent fallback on the tested Codex host. Installed MCP discovery/read also passed; first-class MCP selection in a fresh conversation remains unverified. Queue receipt alone is insufficient. Manifest and marketplace formats follow [official OpenAI packaging guidance](https://developers.openai.com/plugins/build/plugins), checked 15 October 2026. Portable Agent Plugins 1.0.0 manifests retain a compatibility overlay. GitHub prerelease distribution is separate from a public plugin-directory listing.
