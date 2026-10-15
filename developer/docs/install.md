# Install and use HyLogger

Updated: 2026-10-15

**[Download the Apple Silicon installer](https://github.com/david3xu/hylogger-data-bridge/releases/download/v0.1.4-preview.1/hylogger-macos-arm64.zip)** · [Release notes and checksums](https://github.com/david3xu/hylogger-data-bridge/releases/tag/v0.1.4-preview.1)

## Requirements

- macOS on an Apple Silicon Mac. This preview is not an Intel Mac, Windows or Linux installer.
- Codex desktop installed and signed in, for the conversational workflow.
- Internet during installation; about 3.2 GB of model downloads plus Python and dependencies.
- About 4.3 GiB for the installed model and runtime, with additional space for managed Python, caches and your data.

The preview is unsigned and not notarized. No source checkout, Git, Node, administrator access or model training is needed. The model runs locally after installation. Host conversation data handling still follows your Codex settings; local model inference is not a claim that all chat processing is offline.

## Install

Use the macOS account that will run Codex. Installation is per user: an admin account’s installation does not configure another account. Run without `sudo`; it is not needed to install this preview.

1. Download `hylogger-macos-arm64.zip` and extract it with Finder.
2. Open `Install.command` inside the extracted folder. Alternatively, open Terminal in that folder and run `bash Install.command`.
3. If macOS blocks `uv`, use the [security-prompt steps below](#macos-blocks-uv), then rerun the installer. Wait for model verification and **“Installation finished.”** The installer prints the installed command path.
4. Start a new local Codex conversation in your data workspace so the installed tools and skill can load.

Setup installs a managed Python runtime, scientific reader, prebuilt book interface, existing fine-tuned model and local Codex integration. It registers only HyLogger's plugin/marketplace and MCP server. An older local HyLogger marketplace is upgraded with rollback on setup failure; unrelated host configuration is preserved. No scientific-data folder is selected globally at installation.

For an isolated standalone install, run `HYLOGGER_SKIP_HOST=1 bash Install.command`. This skips host registration. ChatGPT/Work support is not certified by the Codex installation.

## macOS blocks uv

The downloaded preview includes `uv`, the helper that installs managed Python and dependencies. macOS may show **“uv Not Opened”** or **“Apple could not verify uv is free of malware.”** This is Gatekeeper blocking an unnotarized executable, not a folder-permission error. Passing the installer's checksum checks confirms file integrity; it does not establish Apple signing or a malware scan.

If you trust the release you downloaded and choose to authorise this executable:

1. Click **Done** on the warning.
2. Open **System Settings → Privacy & Security** and scroll down to the **Security** section near the bottom. `uv` is not an entry in the app-permissions list.
3. Find the recent message about blocked `uv`, select **Open Anyway**, and confirm the system prompt yourself.
4. Return to Terminal in the extracted installer folder and rerun:

   ```sh
   bash Install.command
   ```

If no blocked-`uv` entry appears, trigger a fresh attempt from that same folder:

```sh
./uv --version
```

Dismiss the warning with **Done**, reopen Privacy & Security, and check **Security** again. After allowing it, rerun `bash Install.command`.

This uses [Apple's per-app exception procedure](https://support.apple.com/en-ie/102445). Do not disable Gatekeeper globally, remove quarantine attributes recursively, or use `sudo` as a workaround. If your organisation manages the Mac and does not offer the exception, ask its administrator or stop installation.

## Prepare a data folder

Use an unpacked supported HyLogger TSG package, retaining its companion files and folder structure. Nested package folders are supported:

```text
my-project/
└── data/
    └── SWMB007s_chips/
        └── pkg/
            ├── …_tsg.tsg
            └── … companion package files
```

Open `my-project` as the conversation's workspace. The agent passes that authorised folder to the tools, which discover supported packages inside it. It does not search the whole computer. This is not a general importer for arbitrary CSVs, assay tables, images or ZIP archives.

No source dataset is bundled. The tested case is `SWMB007s_chips.zip` from the [WA NVCL catalogue](https://thredds.nci.org.au/thredds/catalog/rs07/WA/catalog.html). See [data handling](../../data/README.md) for attribution and the [source reproduction guide](develop.md#reproduce-the-real-data-case) for the bounded fetch command.

## First investigation

Ask:

> Review SWMB007s: check data quality and compare 5–10 m with 0–5 m.

The agent discovers the package, prepares real inventory and QA with separately labelled advice, and opens a local evidence book. If the hole or depth bounds are ambiguous, it asks for clarification.

Review the proposed comparison and decide **in the browser book**. Continue accepts the proposed next step; change needs explicit replacement intervals; set aside stops that candidate. Your choice and exact note are saved, the page locks and a successor opens.

A bound Codex conversation receives a notification for new committed work, verifies its exact decision and continuation, and calculates the matching next step. If a turn is active, the notification waits until it ends. The book reports queue status separately from work completion. If return is unavailable, say “I have committed my decision” in chat; the agent reads the stored record first. Never paste a note as a substitute for the saved decision.

The local model offers advice, not a geological decision. Its measured quality is weak; [training results](training.md#r1-real-data-pilot) disclose the collapse to `clarify`. No assays or resource estimates are produced.

## Open a book without chat

On a default installation, use the stable command below. If you use XDG directories, use the path printed by the installer instead.

```sh
"$HOME/.local/share/hylogger/hylogger" review --workspace /path/to/my-project
```

That lists supported packages. To prepare the example review:

```sh
"$HOME/.local/share/hylogger/hylogger" review \
  --workspace /path/to/my-project \
  --package data/SWMB007s_chips \
  --target 5 10 --reference 0 5
```

Use the exact package identifier returned by discovery. This standalone route is unbound and needs explicit follow-up after a browser decision. The installed `case read`, `case continue` and `case open` commands use the same registry as MCP; see the [expert case API](api.md#installed-expert-cases-and-return).

## Updates and storage

Download and run the newer release installer. Existing model assets are reused when the model version is unchanged; existing books are preserved. A stable launcher points to the selected installed runtime. Start a new local chat after updating if its tools have not refreshed.

Default locations:

| Contents | Location |
| --- | --- |
| Launcher | `~/.local/share/hylogger/hylogger` |
| Books and case records | `~/.local/share/hylogger/cases/` |
| Model, runtime and bundled plugin | `~/.local/share/hylogger/` |
| Runtime settings | `~/.config/hylogger/runtime.json` |

`XDG_DATA_HOME` and `XDG_CONFIG_HOME` override these roots. Scientific packages stay in your workspace. Setup does not move or delete them. Back up books and case records together; do not hand-edit their decision or delivery records.

## Book and conversation

Keep one book open beside the conversation. Review choices turn its pages live; the agent should not open another tab after each result. The optional **Review note** autosaves as you type in the current browser tab (including reload), with a visible warning if storage is unavailable. It is a draft until you choose an action: **Continue**, **Change the investigation**, or **Set aside** saves the decision, turns the page and notifies the agent. There is no second record button. Closing the tab or a different server URL does not guarantee draft recovery; committed notes remain in the local book. The note belongs to the saved decision. You do not need to copy it into chat. The current local host shows a labelled automatic book event when a decision wakes the agent; the note itself is retrieved from the book. Fully invisible wake-ups are not provided by this preview.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Codex tools do not appear | Open a new **local** chat after setup. The current chat may retain its previous tool list. The installed review skill also provides the agent a same-registry command fallback. |
| No package found | Check that the connected workspace contains the unpacked TSG package and companion files. Give the hole name; ask the agent to list supported packages. |
| “Decision committed; pending delivery” | Check chat-return status. If it says **Chat is not connected**, ask the same agent to bind the existing case using its verified current conversation UUID; the pending decision stays saved. An active turn must finish before a queued notification can run. Runtime 0.1.3 refuses silent unbound expert starts; explicit manual mode requires follow-up. |
| Model cannot load | Read the installer/runtime error and retry setup with the verified bundle. A model error is not replaced with fabricated fixture advice. |
| `uv: Permission denied` after extraction | Extract the original ZIP with Finder or macOS Archive Utility; some generic extraction libraries discard executable permissions. |
| macOS blocks `uv` / no Open Anyway entry | Follow [macOS blocks uv](#macos-blocks-uv): the message is under **Security**, not the app-permissions list. |

To inspect local installation settings and bundled resources:

```sh
"$HOME/.local/share/hylogger/hylogger" doctor
```

The [acceptance record](../../CLAUDE.md#verified-automatic-receiving-turn) states exactly what was tested. Fresh-chat first-class MCP selection, ChatGPT/Work, a new physical machine and expert geological validation remain separate checks. For source setup or debugging, use the [developer guide](develop.md).
