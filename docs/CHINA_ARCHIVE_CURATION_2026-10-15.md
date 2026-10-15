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
remain in the custody ledger.

Public Brief-trail records are always sampled even if the machine state
would have excluded them, using the exact-URL-derived `trail_ids` embedded
in the generated index. The audit fails if this protection data is missing,
duplicate or refers to an unknown ID. An increasing number of protected
records may legitimately push the review sample over 600.

### Targeted false-negative review

A headline-only sweep of the October 14 **2,534 China records already marked
not selected** found **70** with conservative Taiwan, maritime, strategic
weapons or U.S.-military keyword cues. The exact count and reason codes are
regenerated in the audit ledger. This is a **review warning**, not 70
incorrect model decisions or 70 records cleared for publication.

Especially inspect record **2849** (an original headline describing a Chinese
Foreign Ministry statement about Scarborough Shoal baselines), **2391**
(a headline describing a Foreign Ministry statement about the anniversary of
the South China Sea arbitration decision), and **2180** (a Global Times
headline describing a submarine-launched strategic-missile test). These were
screened out, but their headlines warrant verification against the originals,
document genre and provenance. Do not infer that a publication's claim is true
from the headline or that its citation should be elevated automatically.

All 70 cue hits should be reviewed in addition to the stratified screened-out
control sample. Those populations may overlap; keep distinct reason flags.

### Original-publication spot checks (15 October 2026)

These are **editorial leads, not verified claims about external events**. The
source record establishes what a publisher said. It cannot establish that
the government claim is true.

| Stored ID | Processing outcome | Source-specific spot check | Editorial disposition |
|---|---|---|---|
| `2849` | Not selected | The captured original Chinese body materially matches the July 31, 2026 Foreign Ministry statement independently located at `https://www.fmprc.gov.cn/wjbxw_new/202607/t20260731_11996501.shtml`. IPR's stored URL is a PLA Daily republication, so the outlet is **not** the statement's issuing institution. | **Retain candidate:** primary diplomatic-legal position on Scarborough Shoal. Mark issuer MFA; retain PLA Daily as the captured outlet. |
| `2391` | Not selected | The captured body contains the numbered sections of the July 12 Foreign Ministry declaration; the matching Xinhua publication cites the Foreign Ministry as source: `https://www1.xinhuanet.com/world/20260712/81756443caa14e029ca5be5680412ef3/c.html`. IPR's collected `81.cn` URL is a republication. | **Retain candidate:** authoritative South China Sea official position, with original issuer identified. |
| `2180` | Not selected | Global Times article `https://www.globaltimes.cn/page/202607/1365233.shtml` and defense-ministry Xinhua republication `https://eng.mod.gov.cn/2025xb/N/T/16472056.html` both describe a July 6 strategic missile test attributed to the PLA Navy. IPR's 3,000+-character stored-text block is mostly unrelated article teasers/navigation and lacks the core test account. | **Hold for source-text repair:** topic is significant; do not treat stored body as complete, nor auto-promote it. |

The first two records are strong **curated-inclusion candidates**, not final
editorial approvals; they still need duplicate-event clustering and reviewer
sign-off. The third should enter a quality-repair queue and retain its source
record/citation unchanged until corrected through the governed correction
process. Do **not** silently replace its original captured text or hide the
historical extraction error.

**Issuer/outlet distinction:** the site's displayed institution attached to
both `81.cn` records is the CMC Political Work Department (outlet ownership),
while the texts themselves are Foreign Ministry statements. A curation
classification must have separate `issuing_institution` (evidenced from the
document) and `captured_publisher` (from the source manifest). Neither
should be guessed merely from the hostname.

### Human review dispositions (proposed)

An evidence-bound reviewer should record exactly one of:
`retain_primary` (substantive original statement/operation/technical
disclosure), `retain_context` (useful messaging context or continuing
thread), `duplicate_cluster` (secondary occurrence with a canonical event
representative and visible surviving link), `exclude_discovery` (routine,
off-scope, or low-value), or `hold_quality` (missing/polluted text,
uncertain issuer/date, or unresolved rights/provenance). All statuses keep
the stored record. Record the stable ID, issue/author attribution, capture
outlet, evidence URL, date, exact section checked, 1–2-sentence reason, and
reviewer/date; never publish the label as a verified fact about operations.

A small second-review sample of both proposed inclusions and exclusions
must be independently assessed. Published Brief-trail references **protect
direct links and provenance**, not automatically curated placement: a Brief
may cite an otherwise routine record for context.

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
