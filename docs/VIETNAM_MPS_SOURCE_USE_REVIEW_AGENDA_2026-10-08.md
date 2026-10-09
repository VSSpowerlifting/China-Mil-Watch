# Vietnam MPS: current-source human review agenda for missing private synopses

## The gap

The official-source collector can correctly archive more articles than the Sunday AI writer has privately prepared, source-version-matched research notes for. As shown by the October 8 MPS run, this is a **real recurring editorial operations gap**, not a collector error. The existing Sunday readiness audit (#228, merged) measures missing, stale and machine-held material; the current-source Sunday feeder (#243) refuses to invent it.

The longer-term answer is **not** to feed original Vietnamese article bodies into a third-party model by default. The separate automated synopsis tool from #222 requires an actual, individual source-use decision permitting a bounded text excerpt; public access alone does not supply that permission.

This milestone provides a narrowly scoped, **metadata-only, unsigned** work queue that lets the research lead identify *which original publisher documents need attention*, without licensing or processing them automatically.

## What the new tool produces

Run the read-only script `scripts.prepare_vietnam_source_use_review_agenda` against the **current** `shadow/vietnam-mps-foreign-affairs` branch tip. It replays the original archive, captures, content-version digests and Git state via the existing audit, then matches the current-week machine-eligible sources against any exact-week source-specific research notes.

Each unresolved source row contains **only** its first-party publisher URL, original headline, publication date, immutable MPS content-version SHA, current shadow state commit and an explicit designation of *missing* or *stale* research notes. Machine-held/integrity-blocked articles are separately counted, not offered as safe candidates.

All human source-use decisions default to **not-authorized**. Model excerpt authorization, private model readiness, public citation approval, full-reporting-week coverage, publisher silence and email sending are explicitly **false**. This is NOT a valid `vietnam-private-model-source-use/1` authorization file: it lacks a reviewer, reviewed time, source-use rationale, affirmative decision and any permitted excerpt length. Neither the existing gated synopsis generator nor the Brief publication bridge can consume it as approval.

The October 8 MPS archive introduced source `mps-vi:1791366010`, covering the October 7 Vietnam–Australia security-cooperation meeting, after the first two October 5 source notes were prepared. As long as the third note from PR #245 is not on main, the check should identify it as missing; once the verified #245 notes merge, that gap should disappear. Both outcomes are valid, depending on exactly which current notebook and immutable source state are checked.

## How to run locally

For a separately cloned and provenance-verified shadow-state branch:

```sh
python -m scripts.prepare_vietnam_source_use_review_agenda \
  --state-repo /path/to/mps-shadow-clone \
  --state-commit <actual-current-40-hex-MPS-head> \
  --week-ending 2026-10-10 \
  --notes research/vietnam_briefs_candidates/editorial_notes_2026-10-10.json \
  --out /private/vietnam-unsigned-source-use-agenda-2026-10-10.json
```

Omit `--notes` if no weekly note file exists; do **not** use a fabricated empty notes file to hide a malformed or stale existing catalog. Outputs must be new and outside the checkout; overwrites and symlinks are refused. The command prints **counts only** to terminal logs, not article metadata or any private original text. The full metadata-only agenda stays under the operator-controlled private path.

The standalone read-only PR workflow verifies the actual MPS orphan-state Git tip and executes the script with the present weekly notes. It does not upload or email the agenda, issue a reviewer notification, call an LLM, schedule collection, or add artifacts to the public site. It reports only the number of unsigned review leads.

## What a human should decide next

The research editor can examine the official original and institutional source rights; where appropriate, they can independently prepare a short, personally verified English synopsis with its URL, exact current digest and careful caveats **without sending original body text to a model**. Alternatively, if there is a legitimate documented external model-processing basis, the separate #222 gate can consume a **new independently written** private per-source authorization for a strictly bounded excerpt. This agenda must never be relabeled as that permission.

Once a source-version-matched private note exists, the normal Sunday feeder and its strict October 10 source-count gate can admit the short, unapproved English research note into **one thematic AI draft**, while Dylan retains editing responsibility and Ben retains final Brief publication approval. Public use of the citation still requires the separate #225 original-source review bridge.

This tool does **not** activate the MPS desk in production, process full article bodies externally, generate a finished Brief, change GitHub scheduling or send a manuscript. Rights and editorial decisions stay outside the automatic pipeline.
