# HyLogger Evidence Review Plugin for Codex Desktop (Preview)

This plugin provides local Model Context Protocol (MCP) expert tools and skill instructions
for reviewing HyLogger drill-hole spectral data within Codex desktop.

## What this slice demonstrates

Expert chats normally → Codex selects our tools → real evidence book opens → expert decides IN THE BROWSER → expert returns to chat and says they decided → Codex verifies the committed decision through a tool → continues. This is EXPLICIT chat continuation, not automatic browser-to-agent continuation.

## Capabilities

The plugin exposes six expert tools over stdio MCP (worker tools are hidden in expert mode):
- `start_case`: Prepare or reuse an authoritative case for a real HyLogger package inside the authorised data directory (`--data-root`).
- `read_case`: Read a case's pages, readable evidence, decision choice, exact note, and whether a human decision is pending a worker.
- `continue_case`: Verify that a committed human decision is pending in the book; if not, ask the expert to decide in the browser; otherwise continue with the decision-directed calculation (e.g. interval comparison).
- `open_book`: Return the local HTTP URL to open the evidence book in the browser, reusing an active server process if already running.
- `find_packages`: Locate supported packages inside the authorised data folder.
- `list_cases`: List existing case investigations so conversations can reuse them.

No tool records, edits, or simulates a human decision. Decisions are committed exclusively by human experts in the browser.

## Official Packaging Guidance

Based on the official packaging documentation at https://developers.openai.com/plugins/build/plugins
(read October 15, 2026), the plugin follows the specifications described in:
- **"Install a local plugin manually"** (subsections: *"Example repo marketplace"* and *"Personal marketplace example"*)
- **"Bundled MCP servers and lifecycle hooks"** (portable `mcp.json` manifest)
- **"Path rules"** (keeping `plugin.json`, `mcp.json`, and `skills/` at plugin root)

## Prerequisites

Before loading the plugin in Codex desktop, run the repository [Real-data quickstart](../../README.md#real-data-quickstart) install block to prepare all runtime assets:

```sh
uv sync --locked
npm --prefix app ci && npm --prefix app run build
uv venv outputs/science-env --python 3.12
uv pip install --python outputs/science-env/bin/python -r training/science.txt
python3 -m training.fetch --only SWMB007s_chips.zip
```

This completes the required prerequisites:
1. **Base Python environment**: `uv sync --locked`.
2. **Built frontend assets**: `npm --prefix app ci && npm --prefix app run build` generates `app/dist/index.html`.
3. **Science virtual environment**: `outputs/science-env/bin/python` with pinned `pytsg` installed via `training/science.txt`.
4. **Authorised drill-hole dataset**: Public package `SWMB007s_chips` fetched into `data/raw/nvcl`.

## Local Installation in Codex Desktop

### Option A: Repo Marketplace (Official Method)

Following the official guidance section **"Install a local plugin manually"** (*"Example repo marketplace"*):

1. Keep the plugin directory at `$REPO_ROOT/plugins/hylogger`.
2. Add or update `$REPO_ROOT/.agents/plugins/marketplace.json`:
   ```json
   {
     "name": "local-repo",
     "plugins": [
       {
         "name": "hylogger",
         "source": {
           "source": "local",
           "path": "./plugins/hylogger"
         },
         "policy": {
           "installation": "AVAILABLE",
           "authentication": "ON_INSTALL"
         },
         "category": "Productivity"
       }
     ]
   }
   ```
3. Restart or reload Codex desktop and install the HyLogger plugin from the local marketplace.

### Option B: Local MCP Server Configuration

You can also point Codex desktop directly at the launcher via `.mcp.json` / `mcp.json` using the plugin-root-relative path:
```json
{
  "mcpServers": {
    "hylogger": {
      "command": "./bin/hylogger-mcp"
    }
  }
}
```

### Relocation / Setting HYLOGGER_HOME

The launcher script `plugins/hylogger/bin/hylogger-mcp` is working-directory independent:
- When run within the repository, it automatically resolves `$REPO_ROOT` from its own path (`../../..`).
- If the plugin folder is copied or moved outside the repository (for example, into `~/.codex/plugins/hylogger` as described under *"Personal marketplace example"*), set the `HYLOGGER_HOME` environment variable to the absolute path of the repository:
  ```sh
  export HYLOGGER_HOME="/absolute/path/to/hylogger-data-bridge"
  ```
  The launcher will use `$HYLOGGER_HOME` to locate `outputs/science-env`, `app/dist`, and `data/raw/nvcl`.

## Starting a New Conversation

1. Start a new conversation in Codex desktop with the HyLogger plugin active.
2. Enter the exact prompt:
   ```text
   Review hole SWMB007s: compare 5–10 m with 0–5 m and check data quality first.
   ```
3. **Expected workflow**:
   - Codex recognizes the intent and calls `start_case` with `package_id="SWMB007s_chips"`, `target=[5.0, 10.0]`, and `reference=[0.0, 5.0]`.
   - Codex calls `open_book` to obtain the local evidence book URL (e.g. `http://127.0.0.1:8766`).
   - Codex explains Page 1 evidence (Interval inventory, QA valid spot counts, TSG exclusions, advisory status of models) and provides the browser URL.
   - The expert opens the URL in their browser, reviews the evidence, selects a choice (`accept`, `modify`, or `reject`), enters their note, and clicks Commit.
   - The expert returns to Codex chat and states: *"I have committed my decision in the browser."*
   - Codex calls `read_case` to confirm `human_decision_pending: true`.
   - Codex calls `continue_case` to execute the continuation and reports Page 2 results.

## Verification Status

- Tool operation: verified by smoke test
- Host acceptance in Codex: UNVERIFIED
