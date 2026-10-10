# S2.3a — Fictional collection and analysis checkpoint recovery

**October 10, 2026.** Parent architecture [#332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332). Stacked on the conditional object transport [PR #337](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/337), itself stacked on offline SQLite snapshot foundation [PR #336](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/336). Separate public/private projection: [#334](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/334). Source permissions [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) are not adjudicated.

## What this rehearses

IPR's real Daily succeeds only after output validation, public commit and Pages deployment; **the existing failure-salvage path also commits the tracked public SQLite database**. S2.3a is deliberately not a replacement for those paths. It is a **fictional offline state-transition harness** exploring how captured rows can become durable *before* analysis and remain recoverable if analysis, storage or publication fails.

The test-only \`checkpoint_fictional\` refuses any SQLite connection that lacks the exact \`ipr_s2_fictional_gate\` fixture row and refuses uncommitted transactions. This is an accident-prevention guard, not a security boundary. The harness does not accept a filesystem path to the real archive. Neither the script nor the test imports \`pipeline.py\`.

The rehearsal performs:

1. \`collected\` — capture a consistent SQLite backup, commit an immutable snapshot and manifest, conditionally claim \`(run, stage)\`, and conditionally advance the private generation reference; never touch public Git.
2. \`analyzed\` — only after a verified \`collected\` parent from the **same run**. Separate evidence generation, never conflated with a published site.
3. Failed/blocked persistence — no alternative Git/public storage path, no loss of the previously committed generation, and no implicit retry that rebases on a concurrent writer.
4. Retry — same backup/generation may be replayed after an acknowledgement is lost; conflicting bytes for one run/stage are rejected. A different run may follow the prior collection generation (representing a new day's capture after an analysis failure).
5. Restore — restore an explicitly chosen generation to a fresh temp path, check SQLite and the exact fictional fixture gate; reject non-fictional archives and remove their restored copy.
6. Recovery decision — safe fixed status only: \`fictional_initial_collection\`, \`fictional_resume_analysis\`, \`fictional_private_validation\` or \`rehearsal_only\`. The result **always** states \`eligible_for_publication: false\`.

Do not implement a production task scheduler, authorized-retention policy, LLM retries, public website integration or automated publication from these results. There is no durable external storage or access control.

## Files

- \`core/evidence_checkpoint_rehearsal.py\` — fictional-only checkpoint transition/restore/status contract.
- \`tests/test_evidence_checkpoint_rehearsal.py\` — 23 controlled failure scenarios and recovery checks, including CLI fail-closed invocation and end-to-end fictional execution.
- \`scripts/rehearse_evidence_checkpoint_failures.py\` — standalone no-arguments (except \`--synthetic-only\`) demonstration, creates and destroys its own fake SQLite database.
- This design and stop-gate note.

## Offline acceptance and known limitations

\`\`\`sh
python -m unittest tests.test_evidence_checkpoint_rehearsal -v
python scripts/rehearse_evidence_checkpoint_failures.py --synthetic-only
python -m compileall -q core/evidence_checkpoint_rehearsal.py scripts/rehearse_evidence_checkpoint_failures.py tests/test_evidence_checkpoint_rehearsal.py
\`\`\`

The full repository offline suite and Python 3.9 exact-head CI must pass separately; no assertion of passing results should precede that check.

**Important boundaries:** tests exercise logical stages, not real pipeline sequencing, old+new source rows, all desk collectors, publication/billing markers, source rights, rights grants, the deployment branch, failure salvage, Git reconciliation, credentials, model costs, or a provider's actual read-after-write/CAS guarantees. A successful synthetic WAL backup is not evidence that the public \`pla_watch.db\` has been removed or private.

The current stacked code accesses the test coordinator's validated \`_registered\` method for parent provenance. Before production integration, this should become a reviewed public API, with a separate real archive migration and identity-reconciliation plan. This S2.3a module is **never** production compatible by simple import or dropping its fictional guard.

## Next gate

After the full CI and review, return to [#332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332) to scope S2.3b (comprehensive dry-run failure matrix) and S2.2b (owner-chosen, access-controlled provider). No provider credentials, spend, live captures, source permission requests, production DB or site changes, commit-path switches, auto-merge, release or Git history rewriting in this PR. #326 remains the independent human source-use decision.
