# China archive editorial batch 02 — PLA Daily origin and genre checks

**Oct. 15, 2026 · 25 source-pinned research questions · zero approvals**

The first China archive pilot (batch 01, [PR #621](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/621), merged) was dominated by historical Global Times extraction defects. Batch **02** moves to the real volume imbalance: **4,173 PLA Daily records** in the October 14 source snapshot.

This is a deliberately **contrastive review sample**, not a random sample, a cull manifest or proof that any of these 25 items should be published. The five rows below each contain **one actual PLA Daily record from each month May–September 2026**, bound to its original source-stated title/date and preserved original URL.

| Review lane | Five original records | Editorial question |
|---|---|---|
| **强军论坛** (*Strong Military Forum*) | #479, #1392, #2457, #3227, #4228 | Is a recurring military commentary a unique doctrine/policy source, or mainly repeated editorial framing? |
| **八一锐评** (*August First Commentary*) | #380, #1398, #2610, #3512, #4099 | Does the editorial establish any new verifiable institutional event or merely argue a familiar position? |
| **军营观察** (*Military Camp Observation*) | #545, #1354, #2520, #3228, #4352 | Does the article report useful firsthand unit/training/institutional information? Check photos and rights |
| **外交部** (*Foreign Ministry*) | #459, #1339, #2500, #3394, #4191 | Find the actual issuing ministry statement and compare wording/context to the PLA Daily republication |
| **国台办** (*Taiwan Affairs Office*) | #690, #1268, #2507, #3363, #3997 | Verify exact cross-strait policy messaging, issuer, date, and change-versus-repetition |

The sample includes **automatically analyzed**, **screened-out**, and **awaiting-screening** sources. This is intentional: earlier archive QA found consequential ministerial originals among machine-rejected records. Those are not automatically accepted into the public focus, but must not be dismissed as worthless without original-source review.

**Critically, recurring genre is not exclusion evidence.** The source label
`外交部` also appears on numerous significant official statements; the
Chinese official quote is evidence of an **attributable position**, not
independent proof of disputed maritime or sovereignty claims.

## Safeguards and next editorial step

A second manifest at
`research/china/editorial-batch-02-2026-10-15.json` uses the same
**private research-intake schema** and read-only validation as batch 01.
All 25 sources have null `editorial_decision`, `reviewer`, and
`reviewed_on` values, and the packet expressly sets
`publication_enabled:false`, `owner_approved:false`. The script
validates exact ID/source/date/title identity, historical source URLs,
capture timestamps, citation custody and comparison-link reciprocity.
It generates a private `review.html` and `summary.json` in fresh,
external scratch, never `output/`.

The preliminary batch includes zero existing Brief-cited source records;
that does **not** weaken protection of the separate 182 full-corpus
citations. It is not a basis for deleting any original, editing a
published Brief, or asserting originality/rights.

```sh
python -m unittest -v tests.test_china_editorial_batch02
python scripts/prepare_china_editorial_batch.py \
  --index output/corpus-index.json \
  --batch research/china/editorial-batch-02-2026-10-15.json \
  --records-dir output/record \
  --output-dir /private/tmp/ipr-china-batch02-new
```

A qualified human original-language reviewer must check the 25 actual
publisher texts; note issuing body, documented novelty, context,
provenance, potential republication, source-text fidelity, photographs
and rights; and propose one of the five ledger dispositions:
`retain_primary`, `retain_context`, `group_secondary`,
`exclude_discovery`, `hold_quality`.

Only after independently justified, individually reviewed dispositions
and explicit owner approval can these findings become an approved
curation manifest. Batch 02 **does not modify** the provisional 600-item
focus (PR #636), full browsing, permanent record URLs, database or site.
