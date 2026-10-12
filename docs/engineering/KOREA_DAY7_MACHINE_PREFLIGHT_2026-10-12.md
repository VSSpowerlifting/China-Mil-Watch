# Korea Desk — Day 7 source-continuity preflight (October 12, 2026)

**Prepared, not executed.** The last Day 7 Korea collection is scheduled for **October 13 at 17:47 UTC**. Allow six hours for delayed scheduling: do not assess maturity before **October 13 at 23:47 UTC**. Existing day-zero clock started October 6 at 16:52 UTC.

This is deliberately **not a duplicate source-integrity audit**. First run the existing formal pinned original/capture/ledger reviewer:

```sh
python -m scripts.review_desk_shadow --desk korea \
  --state-repo /absolute/private/git-repo --state-commit <EXACT_40_CHARACTER_STATE_SHA> \
  --as-of 2026-10-13 --out /absolute/private/new-korea-formal-report
```

Keep `records.jsonl` and all original Korean source bodies **private**. Separately assemble the generic `scripts.reconcile_shadow_slot_candidates` output for source `kr_policy_mnd_releases`, branch `shadow/korea-policy-briefing`, start `2026-10-07`, cron `17:47`, grace `6`. Its Action identity flags are caller-supplied and **not independent GitHub authentication**. Do not treat them as definitive workflow evidence.

```sh
python -m scripts.korea_day7_machine_preflight \
  --formal-review /absolute/private/new-korea-formal-report/report.json \
  --slot-candidates /absolute/private/korea-slot-candidates.json \
  --receipt /absolute/private/new-machine-preflight-receipt.json
```

The command writes only metadata, exclusively to a new `0600` file. Incomplete, conflicting, early or unreviewed evidence yields a **HOLD**. Clean formal original/capture hashes and seven supplied logical success candidates yield `MACHINE_LEDGER_CANDIDATES_CONSISTENT_ACTIONS_CENSUS_HELD`, **not** a completed Day 7 qualification. Separately authenticate *all* repository Actions runs, failed/cancelled attempts and reruns against their immutable Git state/receipts.

This is not an authorization to collect DAPA, promote the MND collector, publish new Korea source records, generate Sunday Brief text, reuse HWPX/media, or claim independent Korean-human review. Signed source-specific Korean-language, rights and owner decisions remain zero. Existing five-link public bibliography unchanged.
