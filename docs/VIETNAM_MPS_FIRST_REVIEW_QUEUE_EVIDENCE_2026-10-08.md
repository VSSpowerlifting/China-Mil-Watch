# Vietnam MPS — first real-state review queue verification (2026-10-08 UTC)

This is **mechanical candidate evidence**, not human editorial review, rights
authorization, production admission, or a completed Day 7/14/30 checkpoint.

## Exact execution receipt

Disposable GitHub Actions proof:
[run 37713500055](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37713500055),
job 113104592077, on immutable proof head
`993021c53fc6b8289eaf011100e2b89ca2c8340c`
(PR #132, closed without merge after the result was reviewed).

The source state was freshly cloned from the exact
`shadow/vietnam-mps-foreign-affairs` branch with read-only public Git
access. Its pinned current commit is:

`46f6a0e59e25b03868bf7ad600963d6921ee5124`

Its committed `state/` Git tree is:

`9dbc782fd1c36ff3d0374cad7794166c4f21b810`

The complete historical evidence was verified by the existing ministry
review code: remote clock, ledgers, request counts, raw response hashes,
source-specific identities, database chain, all versions, observations and
date/issuer provenance. The review queue writer emitted no source body text
or raw capture bytes. GitHub's one-shot Actions proof passed the focused
`tests.test_vietnam_mps_pilot` and
`tests.test_vietnam_mps_review_queue` suites and uploaded the reproducible
metadata-only queue.

Evidence artifact:
[artifact 11522591730](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37713500055/artifacts/11522591730);
filename `vietnam-mps-unsigned-queue-37713500055.zip`;
expires **2026-11-07** under the declared 30-day artifact retention.
GitHub artifact archive SHA-256:

`e10cc53228b8c4be49f2cb5f4611592de14fa8ecb211cb3b3c1a18dbbc0e92b4`

The deterministically generated `review_queue.json` SHA-256 identity
(internal canonical pre-`queue_sha256` manifest hash) is:

`a32a445f1e6734ca0763ceac30986ce137b305e1130dc447fe40410a2460d582`

## Machine review result

| Source identity | Machine integrity candidate | Blocking observations |
| --- | --- | --- |
| `mps-vi:1791199100` | Yes | None |
| `mps-vi:1791199677` | Yes | None |
| `mps-vi:1790933646` | Yes | None |

**Total:** 3 source records; **3** mechanically reviewable;
**0** machine-held records. The queue also contains exact per-record URLs,
original Vietnamese titles (metadata), publication dates, content and raw
capture hashes, version/run context and explicit non-approval flags.

**No** human has yet checked these three original source pages or full
stored bodies against the publisher. The queue has zero human approvals,
zero established reuse-rights decisions and no production-publication
authorization. Its `approval_template.json` has no reviewer, review
timestamp, selected records or affirmative checks: it will fail PR #127's
authorization validator by design.

The state may advance with normal scheduled collection; any future review
must either use this exact pinned state commit and current-version rows
or produce a fresh queue. A later change to source text/version cannot
inherit a prior signoff. A machine candidate is not an editorial or legal
finding about the completeness, accuracy or rights status of an article.

## Human next step

Individually compare all three URLs against the publisher's live pages
and the corresponding versioned archived originals in the isolated shadow
database. Check dates, complete body, title, publisher and anomalies, and
establish an independent record-specific lawful retention/display basis.
If any record fails, hold or exclude it; don't edit its machine evidence.

After these decisions are documented, populate a **separate** approval
authorization tied to this commit, then dry-run the existing
`prepare_vietnam_mps_pilot.py` against an outside-checkout migrated
disposable SQLite copy. Neither this queue nor a valid authorization alone
modifies the production database or changes Vietnam's desk status.

The three ongoing Vietnam ministry Day 7, 14 and 30 reliability reviews
remain scheduled for October 14, October 21 and November 6, respectively.
