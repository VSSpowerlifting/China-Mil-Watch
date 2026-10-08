# Vietnam Desk — weekly AI-editorial evidence readiness

## Purpose

The Vietnam MPS shadow collector can preserve an official Vietnamese article
without that article appearing in the private Sunday model draft. The first
reason is valid: a source can be held by provenance and integrity checks. The
second is an **editorial input backlog**: no current, source-version-bound
English research synopsis is available. The third is **version drift**: a
synopsis targets an older MPS content digest or different official URL.

Treat none of these as proof that the Vietnamese Ministry of Public Security
was silent. This PR makes those distinctions machine-visible **ahead of the
Sunday model-generated Brief**.

## Data path and recurring cadence

- MPS collection remains isolated on the official
  `shadow/vietnam-mps-foreign-affairs` Git branch, never the production DB.
- `scripts.prepare_vietnam_mps_review_queue` independently verifies the
  committed state, SQLite, capture receipts and source-version chain, then
  produces metadata-only `review_queue.json`.
- `scripts.audit_vietnam_weekly_model_readiness` compares that signed queue
  to a private model note catalog for the **exact Sunday–Saturday window**.
  It delegates actual acceptance to #211's
  `scripts.prepare_vietnam_briefs_evidence.make_packet`, rather than
  creating a competing evidence definition.
- The new read-only GitHub Actions workflow
  `.github/workflows/vietnam_weekly_editorial_readiness.yml` is scheduled
  **Sundays at 15:07 UTC** (11:07 Eastern daylight / 10:07 standard), before
  the separately gated proposed **19:17 UTC Sunday handoff**.
- If current notes are missing, the audit still runs and logs the specific
  synopsis backlog. It does not generate synopses without publisher source-use
  authorization, call Anthropic, send SMTP, upload full source contents to
  public artifacts or write the production database.

The counts are deliberately distinct:

| Field | Meaning |
| --- | --- |
| in_window_machine_eligible | Integrity-checked MPS records published within this specific week |
| ready_private_model | Those records that actually pass the unified private research packet validator |
| awaiting_source_specific_synopsis | Valid archived article, but no matching research note |
| stale_source_version_synopsis | A note exists but names an obsolete content hash, URL or publication date |
| machine_held_in_window | A collected record has unresolved source/capture/eligibility blockers |
| blocked_source_with_synopsis | A source has a note but independent machine review still blocks it |
| source_quota_excluded | Valid model source beyond the maximum three Vietnam notes per week |
| out_of_window_observations | Records in the retained shadow inventory but not published this week |
| unused_synopses | Notes with IDs not in this queue; not valid evidence |
| non_vietnam_sources_preserved | Existing Japan/other regional research entries kept in their own family |

The ledger has one of four states: `ready`, `partial`,
`synopsis-gap`, `no-eligible-in-window`. The last state describes only
the **verified subset of this particular official MPS collector and its
known reporting window**, not the Vietnamese government or all Vietnam
Desk sources.

## Manual exact-week review

After generating a fresh, exact-commit independent MPS machine queue:

```sh
python -m scripts.audit_vietnam_weekly_model_readiness \
  --queue /private/verified-mps-queue/review_queue.json \
  --week-ending 2026-10-10 \
  --notes research/vietnam_briefs_candidates/editorial_notes_2026-10-10.json \
  --out /private/vietnam-readiness-2026-10-10.json
```

To rehearse a planned *Vietnam-contributing* model draft and explicitly
refuse silence-by-fallback, add `--require-ready`. This strict option is
an editorial QA demand, not a declaration that real weekly articles must
exist. In the recurring preflight, missing notes merely create a visible
warning; it does not fail unrelated China/Singapore/Japan draft work.

The October 10 seed has two model notes for two pinned October 5 MPS
publications. This is initial research evidence rather than automatically
generated permission, full publisher-source review or live desk status.

## Integration with the single Sunday Brief

The shared PR #203 continues to own the writing model, one regional thematic
argument, Japan research schema, typed external citation IDs, Dylan's single
manuscript and the email gate. This PR **does not change those files**.

If the audit reports ready Vietnam evidence, the already merged #211
producer can hand it to the unified writer via one private exact-week JSON
packet. If it reports a synopsis backlog, that problem should be shown to
the editor and addressed with actual source review / permission-scoped note
creation rather than silently concluding that Vietnam contributed nothing.
Future synopsis generation remains individually source-use-gated by #222.

For published Briefs, the independent source-and-claim review bridge in #225
still governs individually approved MPS external citations. Neither a ready
model synopsis nor a clean audit qualifies Vietnam as a live production desk
or grants a publisher-use license.

## Review and deployment

1. Run `python -m unittest tests.test_vietnam_weekly_model_readiness -v`
   against the synthetic MPS review queue from #211.
2. Require exact-head full offline CI, rendered-output checks and tracked
   database/output preservation.
3. Inspect the first scheduled run on `main` and verify that its counts
   agree with a fresh source-state review. No date, body text, full excerpt
   or private synopsis may be published as a GitHub artifact.
4. This preflight is not the Sunday AI draft. PR #203 must separately resolve
   its writer merge conflict and pass a **real no-email** model preview before
   any editor delivery variable is enabled.
