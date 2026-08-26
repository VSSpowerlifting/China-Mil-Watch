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

---

## 8. Regional allocation — collect everything, allocate analysis

Two different scarcities, and conflating them is how a multi-desk publication
starts lying about its own coverage.

**Collection is not scarce, and is never rationed.** Within each declared source
scope, preservation is comprehensive: every qualifying official record that is
discovered is collected and stored. Nothing is dropped to make desks look
balanced, and no keyword filter sits inside a collector deciding what the
ministry "really" published. A corpus that has been quietly sampled cannot
support any claim made on top of it.

**Analysis is scarce, and is allocated deliberately.** Screening and analysis
cost money per record, under a hard daily cap. That budget may be pointed
preferentially at underrepresented desks, because a new desk that receives
capacity only after the largest desk is satisfied never becomes readable.

### What follows from that

* **Comprehensive within scope.** Collection is capped by politeness and by
  what a source serves, never by a target count per desk.
* **No artificial balance.** China publishes more than Singapore. The corpus
  will say so. Equalising by discarding Chinese records would be falsification.
* **Analysis may be weighted.** Underrepresented desks may hold explicit floors
  or weights, disclosed publicly rather than applied quietly.
* **Unused capacity returns to a common pool.** A floor is an opportunity, not
  a reservation: slots a desk does not use spill to whoever has the oldest
  backlog, so a quiet desk cannot idle the budget.
* **The inherited China record stays intact.** Nothing about desk expansion
  deletes, downsamples, or de-prioritises the existing China corpus.
* **Balance is measured over recent periods.** The all-time corpus is
  overwhelmingly China and always will be; that is history, not policy.
  Reporting it as though every desk had always existed would be dishonest, so
  balance is stated over a recent window and the all-time figures are shown
  separately.
* **Per-desk counts and awaiting-screening rates stay visible.** A reader can
  see what each desk holds and how much of it has not yet been screened. A
  desk's backlog is part of its coverage, not a defect to be hidden.

### What is deliberately not built yet

No production allocator exists, and none should be written until there is a
real multi-desk queue to allocate. Today exactly one desk collects into the
production corpus; Singapore is in shadow qualification, Japan has just begun
shadow collection, and U.S. Pacific Command is access-blocked. An allocator
tuned against a queue of one desk would encode assumptions nobody has tested,
and its numbers would be invented rather than measured.

`docs/COLLECTION_HEALTH.md` already records the same conclusion from the
collection side: no per-desk budget is needed with one desk, and one is
required before a second is activated.

When a second desk does reach production, the shape to build is configurable
weighted fairness, not a hardcoded split:

1. a minimum current-item opportunity for every active desk, so a new desk is
   readable from its first day
2. weighted round-robin for the rest of the budget
3. oldest-global-backlog spillover for anything unclaimed
4. no starvation — every active desk advances every run
5. unused-slot recovery within the same run, not carried forward
6. per-desk reporting of what each desk was allocated and what it used

The weights belong in configuration and in this document, where a reader can
check them, not buried in a scheduler. Any provisional split discussed while
planning — 15/10/5/15/10 or otherwise — is illustrative only and is
deliberately not encoded anywhere in production.
