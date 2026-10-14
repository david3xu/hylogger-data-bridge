# Project preparation

Updated: 2026-10-14
Status: local documentation repository prepared; implementation and event participation unverified.

## Purpose and scope

Working folder name: `hylogger-data-bridge`. The original briefs use HyLogger Data Bridge, HyLogger Review Bridge and HyLogger TrustLab. These are concept names; the public product and team name remain to be confirmed.

Start with one drill hole and one complete review workflow: load the package, inspect completeness and depth relationships, flag an interval using a transparent rule, show evidence, record review status and export. An AI explanation is optional until that deterministic workflow works. Keep any unreviewed geological conclusion explicitly unvalidated.

## Documents preserved

`private/briefs/` contains unchanged copies of:

- `HyLogger_Data_Bridge_Idea.md`
- `GSWA_HyLogger_Hackathon_Innovation_and_Datacore_Audit_Brief.docx`

The extra downloaded `(1).docx` has the same SHA-256 as the canonical brief, so a second copy was not imported. The originals in Downloads are untouched.

`private/references/official/2026-10-14/` contains the official repository README and submission templates pinned to commit `da1f60a044290ca6cb8599836163514defc043ee`, the event webpage, the terms PDF and the selection-criteria DOCX. These are local reference snapshots, not project code or inherited licences. `private/reference-manifest.json` records source locations and SHA-256.

The original briefs were read for content; they were not rewritten or certified for document layout.

## Source corrections

Use [the current official requirements](research/official-requirements.md) over the older brief. In particular, the submission is due Thursday night, not Friday. The interim dataset link and FAQ now provide information that the 3 October brief marked unknown. Its proposed Datacore states and interruption tests are not authorisation to change Datacore or stop shared services.

The selection criteria ask whether supplied data were incorporated. Keep an explicit inventory of used, unavailable and out-of-scope products. A one-hole MVP is our scope recommendation, not an organiser waiver of that criterion.

## Next actions

1. Confirm registration/eligibility, team and captain, public repository owner/name, and the MIT code-release decision. Local preparation does not confirm any of these.
2. Select one manageable hole and inspect its actual products, processing level, depth fields, masks, imagery and licence. Record the source inventory before writing parsers.
3. Agree on the smallest Python processing and interface design, dependency lock and tests. Do not add cloud services or couple the app to Datacore.
4. Build and test the one-hole workflow, obtain domain feedback if available, then write accurate run instructions and evidence. Without a reviewer, retain an unreviewed status.
5. Review the staged content before creating the eventual public GitHub repository. Complete the organiser's submission checklist and pitch before the recorded deadline.

## Verification boundary

Preparation checks cover copied-document hashes, local Git isolation, ignored private/data paths and local documentation links. No real-data parsing, application run, geological review, eligibility, public release or submission success is claimed.

On 14 October, all eight reference-file SHA-256 checks passed; both original briefs matched their Downloads sources byte-for-byte. Six project-facing Markdown documents had nine valid relative links. Six private/data/credential/output ignore probes passed, while `data/README.md` remained trackable. No private service addresses, credentials or user-home paths were found in the project-facing documents.
