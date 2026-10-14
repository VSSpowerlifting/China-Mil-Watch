# Vietnam candidate compatibility with Sunday Briefs

The Friday Vietnam MPS candidate lane merged in PR #197, while Sunday full-week editorial delivery is still being staged in PR #187. The latter will call `weekly_editorial_handoff.main(... --full-week --as-of <Saturday>)`. The original `core.vietnam_briefs_handoff.load_candidates` required **Friday** as its only acceptable as-of date, which would reject Saturday on Sunday, aborting the entire editorial email *before writing the file* even though the two October 5 MPS publisher links were valid metadata.

This narrow fix accepts **only** the reporting week's exact Friday or Saturday as the packet cutoff. It intentionally keeps the shadow candidate publication window frozen at Sunday–Friday. A Sunday full-week draft therefore carries forward the same two links for Dylan's **independent human review**, without pretending this frozen packet includes Saturday's Vietnam articles. Saturday additions require a new evidence/version review, not an extended date filter.

It changes no source collector, registry, shadow state, approval, production corpus, reviewer identity, publication or SMTP delivery flag. The human-only MPS references remain outside the model's full-text prompt and the two-live-desk Briefs minimum. Test coverage confirms a Sunday-as-of-Saturday reader sees the same validated references as Friday, refuses candidates published Saturday and rejects unrelated cutoff dates.

## Coordination with Sunday PR #187

- Merge and test this focused fix before activating the Sunday service.
- Reconcile PR #187's edit to `scripts/weekly_editorial_handoff.py` with the already merged PR #197: **preserve** `vietnam_candidates`, the private appendix that begins `=== VIETNAM SHADOW CANDIDATES — HUMAN REVIEW REQUIRED ===`, and the call to `load_candidates(sidecar["week_ending"], args.as_of)`. Preserve PR #187's `--full-week`, Sunday email wording, source-freshness gate and Saturday cutoff. Neither set of controls supersedes the other.
- Do not merge PR #187 on its failed CI: its earlier suite failure involved an unrelated concurrent Philippines AFP temporary Git cleanup; rerun exact-head tests after resolving that and the upstream integration.
- Only then preview Sunday workflow with `send_email=false`, disable `IPR_EDITOR_DELIVERY_ENABLED` and enable `IPR_SUNDAY_EDITOR_DELIVERY_ENABLED` in that order, using an explicitly authorized owner decision.

The Sunday email is designed for Sunday **19:17 UTC** (15:17 Eastern daylight / 14:17 standard), with Dylan's Monday 8 p.m. Eastern return target. This is an editorial workflow change, **not** an assertion of Vietnam's full production readiness. No scheduled service is activated by this patch.
