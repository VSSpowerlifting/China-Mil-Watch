# Japan Coast Guard Day 0: immutable machine-integrity audit

**This is not human source approval or a collection job.**

The first owner-dispatched Coast Guard collector created state branch `shadow/japan-jcg`, immutable Day 0 state commit `81558026117067cbcf54bd7a7859a2d9db168a0c`, and three official English release records on `2026-10-08`. The existing pinned reviewer from merged PR #224 requires an owner to click a separate GitHub Actions workflow. This small PR creates a **read-only CI execution of the same established reviewer** against the exact frozen Day 0 state, to get one objective machine-integrity packet now. It does not replace the long-term manual reviewer.

## Review identity and expected counts

- Branch: `shadow/japan-jcg` (existing separate state-only branch; no writes).
- Exact Git commit: `81558026117067cbcf54bd7a7859a2d9db168a0c`.
- Report cutoff: `2026-10-08`.
- Expected: **3 original English HTML records; 1 successful Day 0 ledger; no missing collection days inside the Day 0-only cutoff; zero machine-integrity findings**.
- The reviewer verifies commit-on-branch ancestry, tree allowlist, stored records, first-party URL identities, original publication dates, capture SHA-256, original-text SHA-256, and append-only ledger integrity. The test explicitly expects at least one **human source-review hold** due to publisher's stale `datetime=2021-3-1` value.
- A failure to meet any expected invariant fails CI. The report is evidence of the actual source snapshot, not a source or editorial decision.

## Access, output and authority

The Actions job has only `contents: read`; source checkout is credential-free. It clones the named state branch into a temporary directory, executes `scripts/review_desk_shadow.py` and `scripts/japan_jcg_pinned_review_receipt.py`, and uploads **only** `report.json`, `report.md` and `receipt.json`. It does not upload the source-text `records.jsonl`, database, or original publisher captures.

The receipt must say `human_review_completed=false`, `promotion_authorized=false`, and `editorial_release_authorized=false`. These values remain false even if every integrity check passes. The source archive stays at three actual records; no automatic historic backfill, daily enabling, Japan production admission or AI writer contribution is caused by this job.

This report should be considered by the independent human reviewer along with the actual three official publisher original articles, their visible vs stale dates, the linked-PDF scope audit, and original-source reuse terms. There is no substitute for a signed review decision.

## Relation to pending historical scope work

[#230](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/230) is a separate reviewed one-time backfill for two early-September releases, and is **not authorized for merge or owner dispatch by this machine audit alone**. The daily collector from #227 is installed but remains **disabled by default**. This PR does not touch either workflow or reset the original Day 0 clock.

This one-time PR review workflow can be retired after its pinned source-evidence artifact has been recorded in [Japan's activation tracker #205](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/205).
