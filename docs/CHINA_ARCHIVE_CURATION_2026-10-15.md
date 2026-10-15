# China archive curation — evidence and release gates (15 October 2026)

**Status:** Review preparation only. No deletion, database edit, search-index
filter, publication allowlist, route removal, site re-render or deployment is
authorized by this phase. The owner endorsed substantial **public discovery**
curation on 15 October, not indiscriminate historical data deletion.

## Observed imbalance (public 14 October snapshot)

Source: `output/corpus-index.json` (generated from the source database).

| Stored source | Records | Processing note |
|---|---:|---|
| PLA Daily | 4,173 | 1,968 analyzed; 2,095 not selected; 100 awaiting; 10 incomplete |
| MND China | 146 | 137 analyzed; contains routine/reprinted unit material too |
| Xinhua Military | 119 | 4 analyzed; 115 not selected |
| Global Times Defense | 158 | 107 analyzed; 32 not selected; 11 awaiting; 8 incomplete |
| China Military Online | 548 | 245 analyzed; 284 not selected; 19 awaiting |
| **China total** | **5,144** | **2,461 analyzed; 2,534 not selected; 131 awaiting; 18 incomplete** |
| Singapore MINDEF | 86 | Distinct desk; must never be swept into China selection |
| **Site corpus** | **5,230** | Source-published document records, not 5,230 editorial endorsements |

Thus **98.4% of stored public records are Chinese**; around 81.1% of the
total corpus is PLA Daily. These are measurements of **stored output**, not
proof of relative military activity, source output, coverage completeness or
editorial value. The baseline changes with each daily collection.

## Proposed three-layer distinction

1. **Preserved corpus:** every original, publisher URL, date, processing
   outcome, provenance, unique ID and any historical errors/gaps remain intact.
   Stored counts stay honest.
2. **Curated public discovery:** target roughly **500–700 China records for
   initial owner review**, not a hard cap. A justified record should never be
   discarded to satisfy a number. Non-China desks use consistent relevance
   criteria as they qualify, with no fake quota parity.
3. **Editorial prominence:** a still smaller editor-controlled selection
   linked to published Briefs. Model analysis and flags are not editorial
   endorsements.

The first candidate review is intentionally **stratified across source and
publication month**, not a publication judgment. It reserves approximately
**15% of its slots for screened-out negative controls** to reveal important
records that automated screening may have missed. On the October 14 snapshot,
a 600-record docket reserves 178 already-cited China source-trail records, 90
screened-out control records, and 332 additional analyzed records. The fact that a record was
`analyzed` is not evidence that its claims are true, its title is relevant,
or it is nonduplicative. Conversely, the `not_selected` state is insufficient
to justify destroying or silently obscuring an irreplaceable original.

## Read-only review ledger

```bash
python3 scripts/audit_china_public_curation.py
python3 scripts/audit_china_public_curation.py \
    --target 600 --out /tmp/ipr-china-curation-review.json
python3 -m unittest tests.test_china_public_curation_audit
```

The script reads `output/corpus-index.json`, never the tracked SQLite DB.
It reads titles, source labels, processing states and publisher-trail record
IDs only; no collection, network access, translation, LLM use or rights
expansion. It refuses an export inside the repository and existing exports
cannot be overwritten. Output is a **private review docket** with a status
for every China record and a reproducible, diverse candidate sample. The
sample is **not** a whitelist and cannot be passed to the renderer as one.

Screened-out controls are not tentative inclusions. They are an independent
false-negative review stratum, and the unreviewed excluded population must
remain in the custody ledger.\n\nPublic Brief-trail records are always sampled even if the machine state
would have excluded them, using the exact-URL-derived `trail_ids` embedded
in the generated index. The audit fails if this protection data is missing,
duplicate or refers to an unknown ID. An increasing number of protected
records may legitimately push the review sample over 600.

### Human audit before the second phase

Review Chinese originals and English titles in source-stratified and
time-stratified samples. Identify, with examples and reasons:

- Original policy statements, substantive operations, doctrine, procurement,
  cross-Strait and maritime activity, institutional changes, and recurring
  information operations worth connecting over time.
- Routine unit profiles, ceremonial material, repetitive morale/features,
  cross-source reprints, publisher-distributed translations and ambiguous
  extraction. **Do not discard political-work material categorically**:
  some official ideological campaigns are strategically significant.
- Items that appear officially authoritative only because the outlet
  reproduced another publisher's text; ministry hostname alone is not enough.
- Records whose processing state is not final, original language is missing,
  whose provenance is inconsistent, or whose prior Brief use is unclear.

The reviewer must record inclusion/exclusion reason, exact record ID and
source, whether an issue cites it, and a reversible override. A small sample
should be independently re-reviewed to estimate missed consequential records.
Preserve cross-time threads rather than over-selecting recent headlines.

## Non-negotiable future implementation gates

- **No row deletion** or rewriting of original title, original text, URL,
  ID, publication date, translation, existing machine labels or Brief sidecars.
- **No existing `/record/{id}.html` or `/article/{id}.html` link breaks**:
  full record pages remain resolvable even if de-emphasized in discovery.
- Distinguish **stored**, **editorially selected**, **review pending** and
  **not selected for discovery**; do not relabel machine `analyzed` as
  editorially significant, or turn no public listing into no held record.
- Keep the method and full corpus discoverable for researchers with an
  explicit route, rather than silently disappearing historical records.
  Any sitemap/noindex changes need search and link-integrity review.
- Gate cross-surface consistency of homepage, corpus weekly pages, finder,
  search JSON, source and desk counts, citation links, RSS, sitemap, and
  accessibility/no-JS behavior. Counts must never mix stored and selected.
- Validate exact-head full CI, historical Brief trails, static page and JS
  budgets, the governed output validator, and 375px/1280px review screenshots.
- Separately approve the actual selected ID manifest and rendered output
  before merge or guarded deployment. Daily regeneration must honor the same
  reviewed selection rather than silently re-admit unreviewed China records.

## Phase boundary

**Phase 1 (this PR):** audit baseline, pure deterministic read-only review
ledger, automated custody tests, and methodology. No production changes.

**Phase 2:** verify 500–700 candidate records against originals, write a
versioned human-reviewed selection/override manifest, and then implement
discovery filtering that retains the full preserved corpus and stable links.
Do not merge an automatic title-filter or quota-based publication cap.
