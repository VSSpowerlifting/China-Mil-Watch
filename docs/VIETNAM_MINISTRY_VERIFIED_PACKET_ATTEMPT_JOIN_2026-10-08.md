# Vietnam Day 7: packet-anchored Actions attempt reconciliation

**Status:** offline-only draft integration, dependent on PR #188.
This tool does not fetch publisher content, collect data, contact GitHub,
write files, verify the completeness of the Actions attempt inventory,
complete human signoff, grant rights or promote the Vietnam Desk.

## The actual manual-input problem

The merged [#184](/VSSpowerlifting/China-Mil-Watch/pull/184) tool already
validates SHA256 hashes and independent Git-bound identities for each
of the three Vietnam ministry Day 7/14/30 source review packets.
PR #188 separately checks the (inherently fallible) supplied GitHub
Actions attempt history against seven ledger fields for all three sources.

Requiring a reviewer to **manually transcribe** every stored ledger row
would allow mistakes, particularly the genuine Oct 7 historical Day 0:
MPS's explicitly requested target was Oct 5, but both MOIT sources'
bootstrap targets were Sept 30. None is a scheduled collection gap.
The separate scheduled follow-up of Oct 7 has a single shared logical
target date of Oct 7.

The new pure offline reader
scripts/vietnam_ministry_checkpoint_attempt_join.py first calls #184's
three-packet validator, which confirms SHA256 package integrity,
source-specific branches, a common checkpoint, as-of date, initial clock
bounds and no embedded signoff. It then reads only the existing
**run_inventory.jsonl** from each packet. For each ledger, the reader
selects precisely these fields:

- run_id
- result, health
- target_date, target_date_source
- collector_commit
- finished_utc

It strips everything else, including articles, titles, original body,
source URL, publisher captures, user agents, raw request data and
publication-record metadata.

The reader refuses missing/duplicated source-ledger identities, a row
belonging to a different source, empty/invalid JSONL, a packet claiming
a different latest run ID, or a formally generated packet that has not
reached its machine checkpoint threshold. Per-source state commit,
source packet digest, and run inventory digest are included as metadata
anchors in the resulting report, not as approval flags.

## The one input that still requires real human evidence

The operator supplies a separate local JSON file containing **all
independently verified GitHub Actions attempts** over the period,
including failures and individual earlier reruns, in this shape:

~~~json
{
  "schema": "ipr-vn-ministry-human-verified-actions-receipts/1",
  "github_attempts": [
    {
      "run_id": 37656171920,
      "run_attempt": 1,
      "event": "workflow_dispatch",
      "conclusion": "failure",
      "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37656171920",
      "target_date": null,
      "target_date_basis": null
    },
    {
      "run_id": 37656171920,
      "run_attempt": 2,
      "event": "workflow_dispatch",
      "conclusion": "success",
      "run_url": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37656171920",
      "target_date": null,
      "target_date_basis": null
    }
  ]
}
~~~

This is **not a full valid Oct 14 attempt inventory**. It is only a
demonstration of the two distinct real Day 0 attempts. The reviewer must
add every actual intervening scheduled attempt and any manual recoveries.
Never infer an omitted attempt was successful or that GitHub's latest
attempt represents every earlier attempt. Day 0 attempt 2 intentionally
has no single Actions-level target date since the three source ledgers
have different original lookback targets, enforced by PR #188.

## Run only after the completed review checkpoint

First generate three legitimate formal complete-corpus packets via
scripts/review_vietnam_ministry_state.py, each against its own
verified post-checkpoint source-state commit. For Day 7, the earliest
collection run is Oct 14, 2026 *after* the nominal 18:17 UTC slot;
a delayed GitHub runner does not authorize using earlier state. These
packets contain the original ministry text: keep them in a permitted
external/private working area, never in tracked repository directories.

Then run:

~~~bash
python -m scripts.vietnam_ministry_checkpoint_attempt_join \
  --actions-receipts /private/verified-actions-attempts.json \
  /private/vn-mps-day07 \
  /private/vn-moit-energy-day07 \
  /private/vn-moit-foundational-day07
~~~

The stdout JSON includes (1) #184's three-source packet rollup;
(2) PR #188's attempt reconciliation, with each missing calendar day,
partial publication or conflicting source evidence; (3) per-source
state/packet/run-inventory SHA anchors. No article text or source
request body appears.

The complete daily expected calendar is derived **automatically**
from approved ministry Day 0 (2026-10-07) through the formal packets'
common as-of date. That removes a second potential manual-transcription
error: an omitted or reordered scheduled day.

**Authority limits:** A hash-valid packet does not independently
reverify its Git ancestry (that was established by the formal
per-source packet *producer*); neither a successful run nor this
report establishes that GitHub's attempt inventory is exhaustive,
confirms failed attempt artifacts, licenses source reuse or
authorizes public publication. All positive signoff/qualification
claims remain false, and a human must review every source and all
independent failed-attempt receipts.

The disabled Vietnam National Defence Journal is completely excluded.
Other sources and collection schedules remain unchanged.

## Merge order

1. PR #184 must have already landed on main (confirmed).
2. PR #188 must merge after separate exact-head full CI and owner approval.
3. Retarget this draft PR from #188's head to main, confirm the diff
   contains only this module, synthetic tests and documentation,
   run independent full CI and request separate human review.
4. Merge does not schedule Day 7 review or complete signoff.
