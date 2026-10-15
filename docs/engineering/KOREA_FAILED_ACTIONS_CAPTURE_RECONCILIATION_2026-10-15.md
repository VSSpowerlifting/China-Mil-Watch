# Korea failed-attempt source capture reconciliation — offline, read-only

**October 15, 2026.** This is an **engineering audit capability**, not source-original migration, publisher reuse approval, production admission or a completed Korea collection checkpoint.

## Real evidence requiring reconciliation

The public Korea orphan shadow state remains pinned to `0595f0fd29b769cbab5dd57c2ef57af174237a67`: **58 SHA-addressed capture files**, **9 persisted ledgers**, **14 HWPX source-original records**, and original day-zero `2026-10-06T16:52:01.420713+00:00`. The **October 12, 2026 scheduled collector failed** (GitHub Actions run `38323793488`). Its preserved artifact `11779728345` (scheduled expiry January 10, 2027 UTC) predates the switch to metadata-only future artifacts and may include bytes not present in the successful Git branch. No particular unique failed-run body is claimed without inspecting the actual ZIP. Other historical artifacts should be inventoried separately. The [private vault metadata manifest](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/main/manifests/korea_mnd_custody_preflight_2026-10-15.json) preserves all nine artifact pointers and expiry dates.

## What the utility proves

`scripts/audit_korea_failed_action_captures.py` accepts an **already downloaded, local** GitHub Actions artifact ZIP plus a separately checked-out, exact-commit Korea shadow source tree. It **never downloads, extracts to disk, prints or uploads original captures**. It streams captures only in memory to recompute SHA-256, compares each against the SHA-named source-capture files and counts shared versus archive-only evidence. Inputs must be manually provided by an authorized custodian, not a public Actions workflow.

Example **after access, retention and operator scope are approved**:

    python -m scripts.audit_korea_failed_action_captures \
      --actions-zip /absolute/restricted/local/failed-korea-attempt.zip \
      --shadow-checkout /absolute/local/pinned-korea-shadow \
      --expected-shadow-commit 0595f0fd29b769cbab5dd57c2ef57af174237a67 \
      --run-id 38323793488 --attempt 1 \
      --private-manifest-out /absolute/restricted/local/korea-failed-only-sha.json \
      --acknowledge-offline-only

`--private-manifest-out` is optional. If requested, it must be a **new absolute, non-symlink, owner-only 0600 file outside the executing public checkout**. It lists only digests of captures absent from the checked-out shadow; it does **not** copy those captures or approve their retention/redistribution. The normal command stdout contains **counts only, without local file paths, source text, individual capture identities, ZIP filenames, or reviewer details**. Never post the private digest file publicly, upload the actual ZIP, or confuse a JSON metadata report with independently authenticated GitHub artifact provenance.

The verifier holds on wrong shadow HEAD, corrupt capture bytes, SHA/filename mismatch, oversized or malformed ZIP, duplicate ZIP members, mixed capture prefixes, malicious paths or symlinks, a noncanonical capture name, or a missing archived capture set. It intentionally tolerates old GitHub upload-artifact ZIP layouts where capture entries are prefixed either `captures/` or `state/captures/`. Other files are not interpreted as a source-success ledger; the tool cannot claim a failed scheduled run was repaired. Full ZIP member names are checked for safe structure. The run ID passed by the operator is **a claim, not authenticated by this offline tool**; cross-check exact GitHub run/artifact metadata separately.

## Critical limitations and next approval gate

Even if a failed-only capture count is nonzero and hashes verify, **this does not permit transferring those bytes** to the private vault or distributing their content publicly. Qualified owner/source rights review must independently determine permitted restricted retention and handling, including HWPX embedded media. A private repo alone is not a license or backup. Verify restricted GitHub access, an independently encrypted **restore-tested** backup, correctly scoped credentials, and a separate **owner-authorized** lossless transfer before executing it. Preserve the old public source branch and historic artifacts until a separate exposure/remediation decision.

The existing [Korea local Git equivalence proposal #616](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/616) tests full source-vs-candidate byte equality; [private vault preflight #610](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/610) checks initial destination suitability. This new module handles one distinct gap: **unique captures stranded in failed Actions artifacts**, which Git branch parity alone cannot detect. Do not use one as a substitute for another.

The dedicated PR workflow uses fabricated Git trees, ZIPs and fake captures only. It performs **no real original download, private source move, source capture publication, live collector dispatch, AI call, email, source-use decision or site deployment**. Exact-head focused and full repository CI are still required.

**Disposition:** reconciliation utility available for future restricted operator audit; October 12 remains failed, Korea shadow remains separate from production and Sunday model/email until new explicit gates are met.
