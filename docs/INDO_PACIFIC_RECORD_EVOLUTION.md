# The Indo-Pacific Record evolution contract

Governing proposal for the release candidate on
`work/indo-pacific-record-evolution-20260825`. It records what the product
becomes, what may not change while it becomes that, and where the boundary
between a candidate and a launch sits.

This is **one evolving project**, not a successor product. The repository, the
corpus, the record identities, the collection schedule, the evidence branches
and the deployment protections are the same ones China Mil Watch has been
running. What changes is the umbrella identity and the information architecture
around them.

---

## 1. Identity

| Field | Value |
|---|---|
| Public name | **Indo-Pacific Record** |
| Tagline | Official defense and security texts, preserved as published and analyzed in context. |
| Corpus eyebrow | As published. |
| Maintainer role | Creator and Editor |

**Retired as working names.** "The Declared Record" is retired — it was a
prototype codename, never adopted, never public. "Western Pacific Record" and
"First Island Review" were retired earlier for the reasons in the naming audit.

**Retired as the active umbrella brand.** "China Mil Watch" stops being the
site-level identity. It does not stop being true: it is the name under which
this record was published from 2026-05 onward, and every page that carried it
keeps carrying it.

**A prior recommendation is overridden, deliberately.** The transition research
recommended deferring any regional name and preferred a methodological one; it
also preferred the label "Western Pacific" over "Indo-Pacific". The owner has
since directed **Indo-Pacific Record**. That direction governs. What the research
flagged and this task does **not** resolve stays unresolved and is listed in §7:
trademark screening, domain, social handles and organization naming are owner
actions and none has been performed.

**Historical names remain in the record.** China Mil Watch and The PLA Watch
appear on the candidate only in explicit archival context — a legacy series
label, a historical issue title, a note about the name change. They never appear
as the current masthead. Tests pin both halves of that: the active branding is
prohibited, and the archival references are required.

---

## 2. Product model

| Surface | Question it answers |
|---|---|
| Records | What did the institution publish, exactly as published? |
| Desks | Which collection scopes exist, and which of them actually collect? |
| Sources | Which institutions and publication surfaces, at what authority? |
| Analysis | What did a human read into it, and citing which records? |
| Coverage | What did and did not collect, per run, per source? |
| Methodology | How is this preserved, translated, labeled and bounded? |
| About | Who maintains it, and what it does not claim. |

### Desk model at candidacy

| Desk | Status | What is true |
|---|---|---|
| China | `live` | The only mature production collection. Inherits the existing corpus, source identities, provenance and record IDs. Not every Chinese official source is implemented — one configured adapter is a documented stub and is reported as such every run. |
| Singapore | `shadow` | Shadow collection into an orphan state branch. Renders no records, appears in no count, and is labeled by its ledger status. It is **not qualified**, and no early packet, verdict or publication is produced here. |
| Japan | `access_blocked` | Researched. PDF extraction capability exists. **No collector, no enabled source, no records.** Blocked on official discovery access, not on engineering. |
| US Indo-Pacific reference | `planned` | Declared scope only. No sources, no records, no statistics. Distinguished visually and textually from an operating desk. |

**Derived, never asserted.** Desk labels, source counts and enabled-source
counts come from `desks/registry.json` and the manifests it points at. Record
counts come from the database and are shown only for a desk that has records.
No changing total — corpus size, shadow day, run count — is written into a
template or a test.

---

## 3. Continuity guarantees

The candidate preserves, and tests pin:

* repository history — no rebase, no force-push, no rewritten commits
* the tracked database — byte-identical; read only through the scratch-copy helper
* record IDs — no historical record id changes, and `/article/<id>` keeps resolving
* canonical URLs — every currently public route has a recorded disposition (§6 of the launch plan)
* source identities — slugs, display names and base URLs are untouched
* content hashes and run attribution
* the PLA Watch archive — 13 published editions, titles and dates unrewritten
* evidence branches, tags and the shadow state branch
* the review machinery — no real `review/*` ref is created
* collection schedules and workflow files — unchanged
* deployment protections — `DEFAULT_SITE_MODE` stays `LEGACY`

---

## 4. Epistemic rules (carried forward, unchanged)

* Official does not mean true.
* Authority tier describes institutional position, not factual reliability.
* No count may be invented. A count with no data is an absence, stated.
* No absence may be interpreted without its collection status. A failed listing
  is not "nothing published".
* Original text, extracted text, translation, machine labels and human analysis
  are four separate layers and are labeled separately.
* Duplicate titles do not establish duplicate records. Corpus-wide title
  deduplication is forbidden.
* Coverage failures are reader-facing facts, not internal telemetry.
* Access controls are respected. No challenge solving, no browser
  impersonation, no proxying.
* Analysis cites exact records.
* A report is not evidence merely because it says it is.

---

## 5. Architecture decisions

**No rewrite.** SQLite-in-git, the existing pipeline, the existing static
deployment and the existing renderer seam are kept. PostgreSQL, FastAPI,
Next.js, Redis and hosted infrastructure are not introduced: no required
capability in this candidate is blocked by the current stack, and replacing a
publishing path that ships every morning to buy an unneeded capability is the
trade this project has already declined once.

**No schema migration.** The schema is already desk-generic — `desks`,
`institutions`, `sources`, `articles`, `scrape_runs`, `source_run_results` — and
migration 0003 already carries desk metadata on `sources`. Nothing needed by
this candidate requires a rename, so nothing is renamed. Source access state
(discovery, robots, adapter implementation) is **configuration**, and lives in
the manifest and registry layer rather than in a column, because it is a
declared fact about a source rather than a measurement of a run. Per-run facts
stay in `source_run_results`, where they already are.

**Three new backend layers, all read-only or configuration:**

1. `desks/registry.json` + `core/desk_registry.py` — the one authoritative desk
   registry. It is not discovered by `core.manifests.load_all_desks()` (which
   globs `desks/*/manifest.json`), so declaring a desk here cannot start
   collection or write a row into the production database.
2. `core/viewmodel.py` — a typed read-only view layer over the database and the
   registry. The renderer asks it for objects; it does not write SQL.
3. `processing/extraction.py` — a generic extraction interface in front of the
   dormant PDF extractor. It preserves the fail-closed status contract and is
   imported by nothing on the collection path.

**One renderer seam, unchanged in shape.** `site/render.py` still selects
exactly one mode in exactly one constant. The non-legacy mode is renamed from
`declared-record` to `indo-pacific-record`; `DEFAULT_SITE_MODE` stays `LEGACY`.

---

## 6. Launch boundary

This branch is a **release candidate**. It is local. Nothing on it is published.

Not done here, and not authorized here: pushing, opening a pull request,
merging, deploying, touching `gh-pages`, dispatching a workflow, creating a real
`review/*` ref, completing a Singapore review, enabling any source, contacting a
source owner, advancing `DECLARED_SNAPSHOT`, or changing `DEFAULT_SITE_MODE`.

The public site continues to serve China Mil Watch under `LEGACY` until a
separately authorized launch.

---

## 7. Open, and owner-owned

* Trademark screening for "Indo-Pacific Record" — not performed; a lawyer's job.
* Domain, DNS, social handles, GitHub organization naming — not selected.
* License — not chosen.
* The public launch gates are unchanged and unmet: one non-China desk collecting
  30 consecutive days, its source universe published, coverage health public,
  the 2026-07-17→24 collection outage disclosed, and owner sign-off recorded.
