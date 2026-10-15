# Vietnam — three real Day-7 source-capture parity checks, no source-body publication

**October 15, 2026. Review candidate.** These are the genuine source states as preserved **after the October 14 scheduled collection**, not new or automatically approved Vietnam production sources. The existing commit-bound review engine and three-packet rollup can check all original HTTP capture hashes, immutable Git ancestry, SQLite record identity, ledger integrity, and corpus/clock consistency, but no real combined three-source execution receipt had been retained.

This additive PR introduces one **PR-only**, **read-only**, **no external publisher contact** workflow. A public-repository Actions job clones the **already public isolated state branches** (without writing them or changing their privacy), verifies all three literal Oct 14 commits remain ancestors of the correct source branch, executes the *existing* formal Day-7 review engine against those commits, and runs the merged three-packet rollup. Source files and all complete review packets remain under `RUNNER_TEMP`, are **not** uploaded, and are deleted on success. Only an explicit machine-only allowlisted summary is uploaded for 30 days.

| Source | October 14 pinned full Git SHA | Expected original records |
|---|---|---:|
| MPS Foreign Affairs | `cb607582eda7bd8760663540c33de2f73da411ff` | 11 |
| MOIT Energy | `5d25d68ee5bd3d1e8e5c7759db880a30d172491a` | 2 |
| MOIT Foundational Industry | `75035550a2f9db4f7a1cac57925141961b390d60` | 1 |

## Acceptance and safe failure

- **Fail** on malformed or missing original HTTP capture, immutable tree/ledger mismatch, incorrect source branch identity/ancestry, wrong document roster, machine Day-7 threshold failure, missing MOIT recorded source-surface anomalies, broken packet digest, duplicate source family, or attempted production eligibility. Failure means **HOLD**, not permission to move a clock or rewrite history.
- **Pass** requires real successful capture integrity for all three frozen historical source states, plus the model-free rollup and explicit negative editorial/rights gates. It does **not** mean all eight days were independently complete, all failures/cancelled attempts are attested or the archived original is semantically accurate versus publisher revisions.
- The eight positive Oct 7–14 scheduled day ledgers and full bounded Actions run census are documented in [Vietnam Issue #186](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/186), including a separate *failed* Oct 7 bootstrap attempt. The MOIT `robots_content_type` anomalies recur on all eight scheduled days in both source families and cannot be cleared by a green job.
- **No automatic human checkmark.** The owner reports external reviewers found the originals good; reviewers' individual identities, source-version decisions, review timestamps and publisher/media/source-use rights must still be recorded genuinely. The machine-only summary always contains `human_original_language_review_authenticated=false`, `source_rights_approved=false`, `production_admission_authorized=false` and `weekly_ai_or_editor_email_authorized=false`.
- No secrets, external model/SMTP, source authorization variable, collection schedule, production registry/database, public page/brief, copy of original source body or rights grant. **This does not change the existing public source-custody exposure**: #332 remains an owner-selected restricted archive decision.

## Actual post-PR execution proof

Review the **exact PR head** and the extra `Vietnam Day-7 Exact Originals — Read-Only Source Proof` workflow's real `prove-three-source-captures` job, not merely the repository-wide offline CI. Confirm the uploaded `vn-day7-original-machine-summary-<run>-<attempt>` artifact contains only the documented allowlist, with source digests and accurate anomaly counts. If the job fails, inspect whether the reason is a source-integrity defect, type/census expectation problem, or a workflow implementation bug; never amend original source snapshots to make it green.

**Do not merge** unless both the actual real-source proof and full offline CI are green and the diff is independently reviewed. A subsequent secure human-review packet handoff remains separate and should not publish complete source captures as GitHub Actions artifacts.
