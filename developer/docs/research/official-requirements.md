# Official hackathon requirements

Checked: 2026-10-14, Australia/Perth.
This is a preparation summary; the linked organiser sources govern. Recheck them before submission.

## Repository and submission

The [official repository README](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/blob/da1f60a044290ca6cb8599836163514defc043ee/README.md) tells teams to build in their own public repository and submit its URL. A fork of the coordination repository is not required. The current local project is independent, with no remote or submission yet.

- Submission deadline: **Thursday 15 October 2026, 11:59 pm AWST (UTC+8)**.
- In-person pitch: Friday 16 October 2026.
- Judging uses the latest commit on the default branch at the deadline; later pushes are not considered.
- Pitch slides: PDF preferred, maximum 25 MB; the submission form also allows PPTX or a link.
- AI tools are allowed; the submission requires a truthful AI-use declaration.

The [submission template](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/blob/da1f60a044290ca6cb8599836163514defc043ee/.github/ISSUE_TEMPLATE/submission.yml) requires team name, captain, members, one challenge theme, public repository URL, project summary, data used, AI-use declaration and pitch slides. It also requires confirmation of a public runnable README, no committed HyLogger/confidential data and agreement with the terms. Only the owner/team may make those confirmations.

The project README must identify the team, theme, actual problem/results, source packages/download locations, installation/run procedure and licence. Screenshots or a demo are strongly encouraged.

## Data and scientific checks

Never commit raw HyLogger packages or imagery. Ignore local data directories and identify actual source packages in the README. Small derived summaries/figures can be considered separately after checking their terms.

The [organiser FAQ](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/discussions/1) provides an interim data-package download, data dictionary location and the `hylogger_dataset_index` linkage table. It also reports NVCL 502 errors with rate-limit guidance pending: avoid bulk fetches.

The FAQ distinguishes raw measurements from corrected/interpreted TSG products, explains Final Mask, and warns that SWIR and TIR abundance estimates are not directly interchangeable. Treat statistical changes as review candidates; do not claim ore, grade or mineral certainty without appropriate validation.

## Participation and rights

The [terms and conditions](https://www.wa.gov.au/media/164933/download?inline=), sections 1 and 4, state:

- Eligibility is university students and early-career professionals with less than three years' professional experience, as specified in registration. Registration and team participation follow organiser instructions. The [event page](https://www.wa.gov.au/organisation/department-of-mines-petroleum-and-exploration/geological-survey-of-western-australia/gswa-hackathons) lists registration closing on 2 October. This repository does not establish eligibility, registration or an exception.
- Participants retain created IP unless otherwise agreed in writing; submission grants GSWA a non-exclusive, royalty-free licence for the listed non-commercial uses.
- The terms specify MIT sharing of event code and public availability of winners' codebases/pitch decks. Obtain contributor/owner confirmation before adding a project licence or publishing.
- Source datasets retain their respective licences; the terms identify GSWA data as CC BY 4.0. Third-party material must be credited and used with the necessary rights. Do not apply the future code licence to the source data or private briefs.

These are source summaries, not a claim that the user has accepted the terms.

## Selection criteria

The [official selection-criteria document](https://www.wa.gov.au/media/165378/download?inline=) gives: innovation/originality 20%, impact/relevance 20%, clarity/understanding 30%, team collaboration 10%, and X-factor 20%. Its impact questions include use of supplied data. Record coverage and omissions honestly; communicate the actual result and limitations in the team's own words.

## Local evidence

Dated originals are in `private/references/official/2026-10-14/`, excluded from Git. Hashes and retrieval sources are recorded in `private/reference-manifest.json`. Public clones must use the URLs above; no private document or Datacore service is a runtime dependency.
