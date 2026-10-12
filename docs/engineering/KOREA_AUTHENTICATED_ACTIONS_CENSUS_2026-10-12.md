# Korea — authenticated read-only Actions census (manual runbook)

This is the next operational layer after the **offline, caller-supplied**
run/ledger scanner in PR #454 and the fail-closed Day 7 machine preflight
merged in #449. It cannot be used as a source publishing workflow.

## Operator workflow

Use **GitHub Actions → Korea — authenticated shadow Actions census (manual)**,
choose main and intentionally set the acknowledgement checkbox. There is **no
cron**, no third-party Korean-government request, no HWPX extraction and no
automatic promotion. GitHub grants the workflow token only actions:read and
contents:read. All checkouts have persist-credentials disabled.

1. The runner checks out current main as executable, reviewed code and the
   separate Korea shadow branch with a sparse checkout of **state/ledger only**.
   It reports the exact shadow Git commit SHA read, not an assumed mutable
   branch alias; no Korean source texts, captures or source database are copied.
2. With its scoped GitHub Actions token, the runner requests every retained
   page of **the exact shared Indonesia/Korea workflow** (ID 376840713), checks
   consistent pagination and unique run IDs, and then requests artifact pages
   for each in-scope run (including failed, cancelled, rerun and manual runs).
   Expired or ambiguous artifacts produce a **HOLD**, never an inferred desk.
3. It invokes the read-only Korea source/slot ledger census from PR #454. It
   records a metadata-only receipt (run counts, dates, hold codes, pinned
   shadow SHA) as an Actions artifact with 90-day retention.
4. Review the resulting report against the separate original/HWPX audit,
   independent human-review assignments, source rights, and owner's decisions
   **before any further collection or public record-release change**.

This makes a stronger **authenticated GitHub API snapshot** than manually
assembling exported JSON. It is still NOT a cryptographic guarantee that GitHub
has retained every failed historical attempt, nor a human Day 7 or source
reliability certification. The underlying census continues to mark its
caller-supplied interface as unauthenticated; the wrapper separately asserts
only that it made authenticated GitHub requests itself.

## Temporal controls

Korea Day 0 is October 6, 2026. Seven subsequent daily nominal slots run from
October 7 through **October 13**, scheduled at **17:47 UTC**. Every slot is
evaluated only after a six-hour scheduling grace, to **23:47 UTC**. A run before
then will show the latest day as pending, not missing. Even after October 13
23:47 UTC, a machine consistency receipt **cannot** admit a Korean source
or authorize Sunday editor publication; human-source, rights and owner gates
remain false.

Read-only verification can be repeated. It does not retry collectors, recover
missed dates or change private shadow state. The separate DAPA publisher index
is research navigation only and DAPA is not a scheduled Korean source.

## Failure behavior

Incomplete or moving GitHub API pagination; foreign workflow IDs; failed,
cancelled, unmatched or duplicate Korea run attempts; mixed or expired
artifacts; wrong shadow branch; untracked or failed ledgers; missing mature
logical dates; and any mismatch between original receipts and Action
identities all prevent a clean result.

The report contains **no Korean original body text, media, translation,
reviewer identity or access token**. Its output is the same zero-admission,
zero-production, zero-Sunday-authorization provenance vocabulary as the
underlying offline census. Never use a report's count of zero newly ingested
articles as evidence that a publisher issued no official releases.
