# Philippines AFP — day-zero full-source editorial review queue

**Not a completed human review. Not production.** This is a read-only, commit-pinned review tool for the first successful AFP **scheduled shadow** run on October 7, 2026. It does not collect a single new page, decide whether a record is genuine, grant reuse permission, publish articles, promote the Philippines Desk, or modify the existing historical state.

## Measured Day-0 checkpoint

| Evidence | Immutable locator / measured value |
|---|---|
| State branch | shadow/ph-afp |
| Immutable state commit | `492001f34ba6176169b6acc96a237f05592a3395` |
| Exact state/shadow.db Git blob | `e42f8f0dde480a99452d89bcfc7ee84b5aa55f13` |
| Original Day-0 ledger blob | `ee84c63ac69009fc8c59f787772e40045367f30e` |
| Day-0 clock blob | `28ebaf7d201a6ad7d863dd8f85d65f602372b624` |
| Run ID | `37631681338-1` |
| Reported result | `ok` / health `ok` |
| Listing | 1,090 reconciled entries over 11 API pages; terminal `next: null` |
| Day-0 collection | 13 selected, 13 retrieved, 13 inserted, 13 with body text |
| Reported capture failures | Zero |
| Day zero UTC | 2026-10-07 13:51:44 UTC |
| Source qualification | Pending; this is only the first successful scheduled day |

The AFP operating policy requires **at least five representative human reviews** when a run inserts more than five new records. This packet proposes reviewing **all 13** Day-0 inserts, eliminating selection bias inside this first batch. It does not assert that any human has done so. Historical publication timestamps are publisher claims, not independently certified truth.

## Generate an unsigned packet

First make sure the **exact historical state commit** exists in your local Git object database. An operator may explicitly fetch `shadow/ph-afp` in the ordinary Git workflow, but the audit itself cannot fetch or silently substitute the advancing branch. It resolves three exact objects—Day-0 SQLite, original completed ledger, and original clock—checks their Git blob SHA-1 hashes and refuses changes or missing objects.

From the collector checkout:

    python3 scripts/prepare_ph_afp_day0_review.py packet \
      --state-repo /path/to/repository-with-ph-afp-history \
      > /tmp/ph-afp-day0-unsigned-review.json

This prints full **preserved extracted text** and original record metadata, not an editor's topic classification. It reads the committed SQLite database in a temporary immutable, query-only connection, validates its integrity, asserts that all 13 text-bearing records and 13 request captures match the Day-0 ledger and clock, verifies SHA-256 of each extracted text and raw API detail payload, matches identity/URLs/source fingerprints and refuses historical revisions in the frozen initial snapshot. The original capture bytes remain in the frozen Git database; the packet carries the capture digest and request URL as separate inspection pointers.

The packet starts with every decision set to **pending**, blank reviewer name, blank rationale and no attested original-capture reading. No preselected positive or negative judgments, no model assignments, no AI-generated editorial prose, no editorial signoff.

## Human reviewer checklist

For each of the 13 records, a genuine human checks the complete stored text **against the original archived API response**, not just a current webpage or a brief excerpt. The reviewer must independently assess:

1. AFP is actually the issuing institution, with correct source ID.
2. Original title is faithfully represented by stored title.
3. Publisher-stated date and timezone were stored accurately; flag mismatches.
4. Extracted body is complete and has no navigation furniture or invented text.
5. Reader-facing canonical URL is distinguished from the separately captured API request and final URL.
6. The capture and original-source provenance really match the supplied archive.

The human may set a completed record to `verified` only with six passing checks, a real name, `read_original_capture: true`, UTC review timestamp, and source-specific explanation. Use `hold` if any check fails; all six checks still must be recorded, with at least one false. Leave `pending` if review was not performed. Machine validation only checks the shape of a self-attested claim: it **does not authenticate people or certify that a human truly read the text**.

After editing a copy of the unsigned JSON:

    python3 scripts/prepare_ph_afp_day0_review.py validate \
      --state-repo /path/to/repository-with-ph-afp-history \
      --decisions /tmp/ph-afp-day0-decisions.json

An editor can require all thirteen rows to have completed decisions:

    python3 scripts/prepare_ph_afp_day0_review.py validate \
      --state-repo /path/to/repository-with-ph-afp-history \
      --decisions /tmp/ph-afp-day0-decisions.json --require-complete

Validation refuses changes to archived titles, bodies, IDs, canonical/requested URLs, publisher dates, original capture SHA-256, snapshot commit/ledger/clock or record order. Pending records cannot falsely carry reviewer identity or checks. Regardless of reviewer-entered decisions, this tool **always** reports no human identity authentication, no editorial approval, no production writes, and no desk qualification.

## Operational separation

- Do **not** overwrite, merge, publish to Pages, or write review decisions into `shadow/ph-afp`. The script writes **only to stdout**. Its temporary SQLite file is cleaned up automatically.
- AFP collection uses `ph_afp_shadow.yml` at **06:40 UTC daily**, with a fourteen-day normal lookback and cap 100. This reviewed Day-0 snapshot covers only the first scheduled successful run; it does not substitute for seven successful scheduled logical days, later review packets, identity/date-drift analysis or institutional scope assessment.
- The separately attributed Philippine NSC collector has healthy quiet-window observations but **zero stored bodies** in the last inspected state and cannot replace AFP source text. DND, PCG and other sources require their own compliant source-access decisions.
- The API's observed `X-Robots-Tag: noindex, nofollow` remains a documented indexing/reuse consideration. This packet does **not** settle rights/terms for republishing originals.
- PR #99 is an older unmerged NSC parser-safety proposal and separate from this AFP source-integrity review.
- Any Philippines production desk declaration, use of archived body text on a public page, taxonomy attachment or automated research writing still needs explicit governance and a completed maturity assessment.

## Offline tests

    python3 -m unittest tests.test_ph_afp_day0_review -v

These tests construct **only synthetic AFP-looking data**, a disposable SQLite archive, and a temporary Git repository. They verify the 13-record count and capture integrity, fail-closed clock/ledger/object changes, missing/wrong source identity, record immutability, reviewer attribution, check completeness, `hold` and `verified` conditions, no automatic approval, and refusal to substitute symbolic branches for exact Git commit IDs.

**Review boundary:** commit-bound unsigned Day-0 inspection only. A green machine test is not a completed human review, a reliable seven-day collector, or an authorized production desk.
