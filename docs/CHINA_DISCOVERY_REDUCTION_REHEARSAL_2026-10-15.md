# China archive reduction: actual dry run, no public cull (15 October 2026)

## What has and hasn't changed

The October 14 published compact corpus index contains **5,230** original
records: **5,144 China**, **86 Singapore**, and **182 protected published
Brief source-trail IDs** (178 China, four Singapore).

As of this document the **live site has not culled a single record**.
The site currently lists and allows searching all preserved records.
Reducing visible China prominence is distinct from irreversibly deleting
primary source holdings, changing the historic record or removing evidence.

### Tested interim cut — *mechanical only*

A simplistic **`state == analyzed`** China slice would render **2,461
of 5,144 China records** and leave **2,683 out of primary discovery**, or
**52.16% fewer prominent China records**.

| Source | Preserved China records | Machine-analyzed slice |
|---|---:|---:|
| PLA Daily | 4,173 | 1,968 |
| China Ministry of National Defense | 146 | 137 |
| Global Times | 158 | 107 |
| China Military Online | 548 | 245 |
| Xinhua Military | 119 | 4 |
| **China total** | **5,144** | **2,461** |

The source proportion still seriously overrepresents PLA Daily and an
analyzed slice **is not the same as editorially curated content**. It also
does not reach the proposed **500–700** curated-China-record target. That
later target is a planning range, never an arbitrary quota or authorization
to publish.

### Exactly why an automatic machine cull is insufficient

Among the sources *hidden by the simplistic analyzed-only cut*:

- [#2849](https://indopacificrecord.org/record/2849.html) is an official
  Chinese Foreign Ministry statement about maritime baselines at Huangyan
  Dao, republished by PLA Daily, but has `not_selected` processing status.
- [#2391](https://indopacificrecord.org/record/2391.html) is another
  `not_selected` Chinese Foreign Ministry statement on the South China Sea
  arbitration anniversary.
- [#2180](https://indopacificrecord.org/record/2180.html) is a potentially
  important submarine-missile original whose archived Global Times body
  was historically contaminated.
- [#946](https://indopacificrecord.org/record/946.html) similarly has
  contaminated old text and requires the source-original review.

Among the sources *wrongly promoted by machine `analyzed`*:

- [#2265](https://indopacificrecord.org/record/2265.html) is cited by
  published PLA Watch No. 10 but carries an unrelated 2025 teaser and
  inaccurate generated summary for a Joint Sea-2026 report.
- [#2881](https://indopacificrecord.org/record/2881.html) is cited by
  PLA Watch No. 12 and was affected by old link-teaser contamination
  contributing to the Atlas/KVD002 attribution issue.

**Never confuse a published source-trail citation with verified capture
quality or automatic relevance.** Likewise, a source-collector or model
screening negative is not a human editor's exclusion verdict.

### Deliverable

`scripts/rehearse_china_discovery_reduction.py` reads only the frozen
October 14 index and
`research/china/discovery-reduction-rehearsal-2026-10-15.json`.
It produces exactly two **private, noindex, no-JavaScript-dependent HTML
views** and a summary in a new, access-restricted directory outside the
repo:

1. `screened.html`: **2,461** links from the model-analyzed China state,
   prominently marked **NOT EDITORIALLY APPROVED**;
2. `preserved.html`: **all 5,230** historical stable source-record links;
3. `summary.json`: exact counts, original-state source breakdown, missing
   human approvals and six exact title/date/source-pinned adversarial
   examples.

```sh
python3 -m unittest -v tests.test_china_discovery_reduction_rehearsal
python3 scripts/rehearse_china_discovery_reduction.py \
  --private-dir /private/tmp/ipr-china-reduction-rehearsal-new
```

The command rejects a reused, relative, symlinked-parent or repo-local
output path. Files are mode 0600 and the new output directory mode 0700.
The GitHub PR workflow uses only **ephemeral runner scratch** and publishes
neither HTML nor JSON as an artifact. Tests verify the full-corpus link
inventory, every published trail still present in the index, fixed 52.16%
rehearsal math, exact source/processing-state identities, known false
negatives and false positives, and unchanged SQLite/output custody.

The snapshot is frozen: when the full corpus changes or the status counts
change, **the rehearsal fails closed**, rather than silently expanding a
candidate set after new daily collection.

### Release engineering and editorial plan

**Phase A — independently approve the source-discovery policy.** Decide
whether a visible "Research-reviewed / all preserved" dual-scope mode is
appropriate as an explicitly *interim mechanical mode*. If deployed, it
must say exactly what it filters and not call itself "curated" or
"quality-controlled"; ensure no-JavaScript view and browser search agree.
This is **not implemented or deployed by this PR**.

**Phase B — review actual records.** Use the 25-record original/source QA
docket [PR #621](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/621),
18-case original research [PR #618](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/618),
and the private ledger [PR #615](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/615).
Retain consequential primary sources even where screening rejected them,
hold polluted captures, compare republication bodies/dates, and record
human editorial decisions. Work through additional batches to establish
an evidence-supported smaller collection.

**Phase C — build and approve an immutable public manifest.** A production
curated-first site can only consume a **separate owner-approved and
source-verified ID selection**, bound to exact source provenance and an
independently approved release. It must retain every existing `record/`,
legacy `article/` stub, Brief, original source URL, search/full-corpus
fallback, and stable source/citation counts. New records must be preserved
but unreviewed—not automatically curated.

**Stop:** This PR has a real mechanical visibility demonstration, not a
public archive change. A passing technical check never confers approval
to hide a record from reader discovery or alter a published issue.
