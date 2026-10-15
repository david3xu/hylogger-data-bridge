---
name: hylogger-review
description: Expert evidence review and workflow continuation for HyLogger TSG drill-hole spectral data.
---

# HyLogger Evidence Review

Use this skill whenever an expert asks to review, inspect, or compare HyLogger or TSG drill-hole spectral intervals.

## What this workflow demonstrates
Expert chats normally → Codex selects our tools → real evidence book opens → expert decides IN THE BROWSER → expert returns to chat and says they decided → Codex verifies the committed decision through a tool → continues. This is EXPLICIT chat continuation, not automatic browser-to-agent continuation.

## Instructions

### 1. Discovery and Case Reuse
1. Always start by calling `list_cases` to check whether a case for the requested hole and intervals already exists. If a matching case is found, reuse its `case_id`.
2. If the expert names a drill hole but no package:
   - Call `find_packages` with the hole name.
   - If no package or multiple packages are found, ask the expert to clarify. Never search outside the authorised data folder (`--data-root`).
3. If target or reference depth intervals are missing, ask the expert before calling tools.

### 2. Case Initialization & Evidence Review
1. Call `start_case` with `package_id`, `target` [top, bottom], and `reference` [top, bottom].
2. Call `open_book` with the `case_id` to get the local URL for the evidence book.
3. Explain the initial evidence (Page 1) in plain words:
   - Summarise the interval inventory and data quality (QA) numbers, explicitly mentioning valid spot counts (n/N) and exclusions.
   - State the scientific limits clearly: TSG interpretations only; no assay or assay-overlap results are used or claimed.
   - Note that model advice is experimental, advisory only, and is never a decision or authorisation.
4. Direct the expert to the browser:
   - Provide the evidence book URL returned by `open_book`.
   - Ask the expert to review the evidence in the browser book, make their decision (accept, modify, or reject), enter their note, and tell you in chat once they have committed it.

### 3. Verification & Continuation
1. When the expert returns to chat and says they have decided:
   - Call `read_case` to verify that a committed human decision is pending for a worker (`human_decision_pending: true`).
   - If no decision has been committed, ask the expert to make and submit their choice in the browser book first.
2. Once the committed decision is confirmed:
   - Call `continue_case` with `case_id` (and operator bounds if the expert chose `modify` with specific intervals).
   - Explain the successor page (Page 2) readable evidence and outcome in plain words.

## Strict Boundaries
- NEVER record, edit, or simulate a decision. Only human experts decide in the browser.
- NEVER present advisory suggestions as permissions or geological conclusions.
- NEVER claim assay, chemical, or resource results.
