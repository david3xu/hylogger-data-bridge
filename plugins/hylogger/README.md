# HyLogger Evidence Review Plugin for Codex Desktop (Preview)

This plugin provides local Model Context Protocol (MCP) expert tools and skill instructions for reviewing HyLogger drill-hole spectral data within Codex desktop.

## What this slice demonstrates

Expert chats normally → Codex selects our tools → real evidence book opens → expert decides IN THE BROWSER → expert returns to chat and says they decided → Codex verifies the committed decision through a tool → continues. This is EXPLICIT chat continuation, not automatic browser-to-agent continuation.

## Capabilities

The plugin exposes six expert tools over stdio MCP:
- `start_case`: Prepare or reuse an authoritative case for a real HyLogger package inside the authorised data directory (`--data-root`).
- `read_case`: Read a case's pages, readable evidence, decision choice, exact note, and whether a human decision is pending a worker.
- `continue_case`: Verify that a committed human decision is pending in the book; if not, ask the expert to decide in the browser; otherwise continue with the decision-directed calculation (e.g. interval comparison).
- `open_book`: Return the local HTTP URL to open the evidence book in the browser, reusing an active server process if already running.
- `find_packages`: Locate supported packages inside the authorised data folder.
- `list_cases`: List existing case investigations so conversations can reuse them.

No tool records, edits, or simulates a human decision. Decisions are committed exclusively by human experts in the browser.

## Local Installation in Codex Desktop

1. **Prepare the local environment**:
   ```sh
   uv sync --locked
   npm --prefix app run build
   ```
2. **Configure the plugin in Codex Desktop**:
   Point Codex desktop to load the plugin from `plugins/hylogger/`, or add the local MCP server configuration from `plugins/hylogger/.mcp.json`:
   ```json
   {
     "mcpServers": {
       "hylogger": {
         "command": "outputs/science-env/bin/python",
         "args": [
           "-m",
           "hylogger_bridge.mcp.server",
           "--cases",
           "outputs/cases",
           "--data-root",
           "data/raw/nvcl"
         ],
         "env": {
           "PYTHONPATH": "src:."
         }
       }
     }
   }
   ```
3. **Verify data access**:
   Ensure the authorised data directory (`data/raw/nvcl`) contains supported TSG packages.

## Verification Status

- Tool operation: verified by smoke test
- Host acceptance in Codex (ordinary prompt → tool selection → book → browser decision → chat follow-up → correct successor): UNVERIFIED
