# South Korea — complete shared-collector attempt inventory

**October 12, 2026.** This is an *offline, read-only, untrusted-export* audit. It
complements (and does not replace) the source/HWPX/ledger review in
review_desk_shadow, generic slot-candidate classifier, and separately drafted
Day 7 machine preflight in PR #449.

## Why this exists

The Korea and Indonesia collectors share one Actions workflow. A successful
Korea shadow-state ledger proves only that a particular successful run pushed
its receipt. It cannot establish whether other Korea attempts failed, were
cancelled, were rerun, or failed before writing to the shadow branch. The same
workflow also contains Indonesia attempts, which must not become Korean runs by
guessing from their clock time.

The audit consumes **three independent inputs**:

1. Every page of the unfiltered shared workflow's GitHub Actions run export,
   retaining its total_count, including failed/cancelled and manually dispatched
   runs; pages must be complete and have unique run IDs.
2. The individual artifact-list response **for every run in that export**,
   keyed by GitHub's numeric run ID. Artifacts named
   candidate-shadow-korea-<run>-<attempt> attribute a run to Korea; Indonesia
   is treated separately; absent, unselected or contradictory artifacts yield a
   HOLD, not an assumed Korea success.
3. The ledger JSON **from one exact, independently pinned Korea shadow Git
   commit**, with its original local Day 0 bootstrap and subsequent Actions
   receipts. Do not use a live mutable state checkout without a frozen SHA.
   The CLI does not independently authenticate this Git pin.

Example with locally prepared/private JSON files (no tokens in those files):

~~~sh
python -m scripts.audit_korea_actions_attempts \
  --runs-export /absolute/private/korea-all-workflow-runs.json \
  --artifacts-export /absolute/private/korea-all-artifacts-by-run.json \
  --korea-ledgers-export /absolute/private/korea-pinned-ledgers.json \
  --as-of-utc 2026-10-13T23:48:00Z
~~~

Do not describe structurally complete Actions pagination as a verified GitHub
source census: the data is *caller-supplied*. Operator review must separately
prove the workflow ID, date-range completeness, pagination, and artifact
responses came from authenticated GitHub endpoints, and record the read
timestamp, repository identity, API query and source state SHA.

### Important time gates

Korea's scheduled nominal slot is **17:47 UTC**, beginning October 7. GitHub
Actions often starts hours late. A slot must pass **23:47 UTC** (six-hour grace)
before a missing attempt can be evaluated. October 13 at 23:47 UTC is only the
earliest **machine preflight** time for Day 7, not an actual human checkpoint
or source admission. A healthy but duplicate-only release still contributes
a successful scheduled attempt; **zero new articles is not proof that the
government published nothing**.

The census marks manual runs as manual (not as substitute scheduled days),
explicitly holds reruns, unaccounted or unhealthy ledgers, failed/cancelled
attempts and unknown shared-workflow scope, and never turns a clean report into
human reviewer signoff, content reuse permission, production corpus promotion
or Sunday Brief source eligibility.

**Privacy:** output is only run IDs, dates, hold categories and aggregated
counts. Do not include Korean original text, attachments, credentials, reviewer
identity, or write this audit into the public website.
