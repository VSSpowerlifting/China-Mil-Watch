# AFP per-run source-integrity review — original API capture handoff

**Scope:** Administrative original-source verification for *new insertions from any completed scheduled AFP shadow run*. This extends the merged PR #178 Day-0 queue to subsequent dates. It is not a source collector, a classifier, human signoff, an authorization to republish originals, or evidence of seven-day reliability.

## First live Day-1 intake to review

The October 8, 2026 AFP shadow state was committed as `c668790ce3be88b08b3300b945bad58589b3a5b1` on `shadow/ph-afp`. Its scheduled run `37788547061-1` reported `ok`, `health: ok`, and exactly five new original-text records (13 previously preserved records were revisited as duplicates; no revisions), for 18 stored full-text records total. The full eleven-page AFP API listing reconciled 1,095 items with terminal pagination, with zero reported access, retrieval, parsing and identity failures.

The next actual human review must cover **all five** new records, not a cherry-picked five from a larger batch:

| Source ID | Source-stated publication date | Official AFP title |
|---|---|---|
| `afp:1404` | 2026-10-08 | AFP Chief of Staff Visits NOLCOM, Commends Personnel for Exemplary Performance |
| `afp:1403` | 2026-10-07 | AFP Leadership Calls for Efficient, Modernized Pension Services Under New PGMC Chief |
| `afp:1402` | 2026-10-07 | Chief of Staff Pushes for Sustained Military Presence, Enhanced Western Defense |
| `afp:1401` | 2026-10-07 | AFP Chief of Staff Visits Wounded Soldiers, Reaffirms Commitment to Personnel and Security Efforts |
| `afp:1399` | 2026-10-06 | AFP Welcomes New Thai Defense Attaché, Honors Predecessor |

The source dates are the AFP publisher's assertions, not independently certified dates. These five are **distinct source records**, not necessarily five separate strategic events or five topic decisions. The three-day date span reflects the scheduled collector's lookback and must not be represented as one day's news publication.

## Use the preserved original instead of current live content

First explicitly fetch `shadow/ph-afp` through ordinary Git operations into a local checkout and record the **literal 40-character commit SHA**. The script itself has no networking, no branch-following fallback and no permission to bypass access controls.

From the collector repo root, with the *named historical state commit* present in the indicated checkout:

    python3 scripts/prepare_ph_afp_run_review.py packet \
      --state-repo /path/to/repository-with-ph-afp-state-history \
      --state-commit c668790ce3be88b08b3300b945bad58589b3a5b1 \
      --run-id 37788547061-1 > /tmp/ph-afp-oct08-unsigned-review.json

Unlike the Day-0 packet, this version includes BOTH the entire extracted preserved `text_original` and `original_api_response_utf8`: exact raw JSON capture text from the original first-party AFP backend, containing the preserved `intro_html` and `body_html`. This lets a reviewer check extraction completeness, missing paragraphs, overlapping introductions, site furniture and title/date identity against the actual archived source without revisiting a mutable public page.

**Access handling:** The packet includes full preserved original-source bytes as UTF-8 text. Keep it in an access-controlled editorial workspace for specifically authorized reviewers; do not email or publish it indiscriminately, mirror it onto the public site, or treat its availability as granting reuse rights. The API's observed `X-Robots-Tag: noindex, nofollow` remains a separate indexing/reuse issue requiring owner review.

Generation verifies a complete healthy scheduled run and fails closed on inconsistent commit, ledger, state hash, collector identity, missing first-seen records, altered extracted text SHA-256, changed original response SHA-256, wrong first-party source IDs/slugs/titles/timestamps, malformed original JSON, and missing matched original captures. It reads SQLite only as a temporary immutable query-only copy and prints JSON to stdout.

All reviewer decisions start **pending**, with no prefilled name, approval, machine-guessed topics, or fabricated full-source attestation.

## Return and validate human decisions

An actual human reviewer must independently inspect the complete original API response for each record and fill in the six decision checks defined by PR #178: issuing institution/source ID, title fidelity, publisher timestamp and timezone, full extracted body fidelity/site furniture, distinct canonical vs API URLs, and capture provenance.

The reviewer may mark `verified` only when all six checks pass and real reviewer identification, truthful `read_original_capture: true`, UTC timestamp, and a source-specific rationale are supplied. Mark `hold` when a check genuinely fails; leave `pending` if unreviewed. Do not treat the original API payload's own factual allegations as independent corroboration of military events.

    python3 scripts/prepare_ph_afp_run_review.py validate \
      --state-repo /path/to/repository-with-ph-afp-state-history \
      --state-commit c668790ce3be88b08b3300b945bad58589b3a5b1 \
      --run-id 37788547061-1 \
      --decisions /tmp/ph-afp-oct08-decisions.json --require-complete

Validation reconstructs the packet from the same exact historical Git objects, rejects changes to captured original JSON/body/title/publisher dates/source ID/capture hashes/run ID/commit, and reuses PR #178's per-record human-review gates. The machine cannot authenticate the purported person or their claimed reading and never sets editorial approval, qualification or production write flags.

For later runs, use the new state SHA and actual run ID in the same command rather than duplicating per-day source-review scripts. A correctly completed scheduled quiet run may contain **zero** new records and accordingly create an empty review packet; that does not count as an excuse to skip an actual nonzero batch.

## Non-goals

Do not write this review file to `shadow/ph-afp`, production `pla_watch.db`, `desks/`, `output/` or the public archive. Do not classify a record from its title or infer that the AFP, the Philippine Coast Guard, and the National Security Council are interchangeable source issuers. The still-separate seven-day reliability audit in #183 will need CI and GitHub Actions provenance review; completing this intake neither certifies seven days nor qualifies the Philippines Desk.

## Tests

    python3 -m unittest tests.test_ph_afp_run_review -v

Sixteen synthetic-only tests exercise raw payload fidelity, preserved source IDs and date parity, per-record unsigned state, exact Git commit pinning, failure/non-scheduled runs, missing captures, falsified original bytes, reviewer attribution and refusal to write approvals. Synthetic identities are test fixtures, not human reviewers. Full exact-head CI and preservation checks are required before merge.
