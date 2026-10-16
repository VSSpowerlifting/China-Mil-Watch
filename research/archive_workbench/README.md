# Archive Research Workbench — private preview

Search published IPR material by keywords, phrases, desk, source, issuer/author,
record type and publication date; inspect processing/provenance labels; open the
canonical record; copy citations; export a tab-local selection as CSV or JSON.
No production renderer, navigation, stylesheet, collection, release or publication
workflow imports this namespace. This is an implementation candidate, not a release.

## Run

From the repository root, with the repository dependencies installed in `.venv`
(Python 3.9; Node 18+; Chromium installed for browser tests):

```sh
.venv/bin/python -m research.archive_workbench.build
.venv/bin/python -m research.archive_workbench.serve
```

Open `http://127.0.0.1:8876/`. Build destinations must be new/empty ignored
subdirectories of `build/`; the builder refuses production paths, symlinks and
existing artifacts. For another build, use `--out build/archive-workbench-review`,
then serve with `--dir build/archive-workbench-review --port 8877`. No files are
written to `output/`. The server binds only to loopback, verifies the Host,
disables directory listing, rejects dotfiles/path escapes, and sends restrictive
CSP, noindex, no-store and no-referrer headers. HTML/robots repeat the private
preview restriction; there is no feed, sitemap, canonical preview URL or service
worker. These controls do not make a publicly hosted copy private: do not deploy it.

```sh
node research/archive_workbench/query.cjs build/archive-workbench/index.json --q '"South China Sea"' --desk china --from 2026-09-01 --sort newest
node research/archive_workbench/benchmark.cjs build/archive-workbench/index.json
.venv/bin/python -m unittest tests.test_archive_research_workbench tests.test_archive_research_workbench_browser -v
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python scripts/validate_output.py
```

Node and the browser execute the **same** `web/search.js` query/export layer;
there are no runtime packages, hosted services, models, embeddings or accounts.
Search/filter/export makes no network requests after the local assets/index load.
Opening an explicitly selected canonical/publisher link is normal external
navigation. Copy uses the browser clipboard, with selectable text on denial.

## Publication boundary

`corpus.py` imports existing contracts; it is not a new rights/publication authority.

| Material | Authority and indexed fields |
| --- | --- |
| Archive records | Existing `output/corpus-index.json` explicit six-field projection, intersected with exact current article metadata and the retirement ledger through `scripts.reconcile_db.read_only`. Titles, date, source/institution/desk, processing state and IPR locator only. |
| Official-link references | Production's reviewed-link, frozen Indonesia/PACOM, public Korea, and admitted USCC/Treasury/BIS loaders. Their permitted titles **or neutral labels**, dates where present, issuing institution and outbound URL. Editorial holds survive in results/citations/exports. No body, summary, capture or model draft. |
| Preserved originals | `core.korea_published_originals.read_release_index`: exact, registered public original text and source attribution. Never private source archives. |
| Reviewed English artifacts | `core.korea_english_publication.public_registry`: registered, source-pinned, editor-reviewed translation/analysis; explicitly machine-assisted. |
| Human-controlled Briefs | `load_editions` plus `load_collection` approval gate; titles/deks, resolved publication identity, authors and existing citation helpers. Separately published desk research uses `load_catalog`. No manuscript body, private draft or unpublished timeline/dossier. |

SQLite existence and generated record HTML never establish eligibility. In
particular, the bulk archive contract forbids captured bodies, machine summaries,
original URLs and capture/model/hash fields. That also applies to CSV/JSON.
Individual record pages' source-text citations do not broaden the bulk contract;
archive exports use the existing **As held** block and canonical IPR locator.

The original-text and reviewed-English adapters read only public release registers;
private capture or model/review packs outside those registers are never enumerated.
Retired exact source-URL hashes and former record IDs are both enforced. An active
retired collision fails the entire build. Stale/mismatched public-index entries
are counted and excluded; there is no reconstruction from old HTML or title matching.
`/article/<retired-id>` cannot bypass the identity check.

A publication date is used only when genuinely recorded: source-stated dates for
source artifacts, registered release dates for reviewed IPR English pages, catalog
publication dates or explicit historical `published_date` for Briefs. Coverage
week endings and approval dates are never substituted. Other Briefs remain undated
in search, with their coverage week identified separately and their original
week-ending citation intact. The two early historical publication dates and stored
historical author identities are read from the same canonical edition records.

`manifest.json` records schema/revision, database/index digests, public snapshot,
record digest, included counts by type, candidate exclusions by reason, and the
retirement ledger size. Private archives/shadow state/held packs/unpublished
chronologies are deliberately **not enumerated**, so the manifest does not claim
a measured count for them. No corpus or build artifact is committed.

## Query, identity and export semantics

Whitespace-delimited terms use AND across fields; ASCII double quotes require a
contiguous phrase within one field. Matching uses NFKC normalization, lowercase
and literal substrings. Punctuation/diacritics remain meaningful; Chinese input
uses substrings, without inferred segmentation, translation, stemming or tags.
Empty queries browse all indexed items. Limits: 512 characters, 32 distinct terms;
unclosed quotes/control characters/invalid dates and reversed ranges give errors.
Unknown facets return zero results rather than broadening the query.

Ranking sums the best match for each term: title 12, original title 10, summary
4, original/reviewed text 3, metadata 2; whole-field matches add 5. Relevance ties
use newest date then stable identity. Explicit newest/oldest uses date then stable
identity; undated items sort last both ways and are excluded by date bounds.
Bounds are inclusive. This is document retrieval, not event counting or corroboration.
`fixtures/relevance.json` gives 15 human-readable expected query cases.

Canonical IPR artifact URLs define duplicates; official references use exact
publisher URLs. Public loaders' order defines which duplicate reference wins;
text/claims are never merged. Different documents with the same title survive.
Conflicting IPR artifacts or reused stable IDs fail closed. Selection is an ID
set in `sessionStorage` for this browser tab, revalidated against the loaded
snapshot; it survives sorting/filtering/reload, not account/cloud persistence.
Exports sort by stable identity and drop stale IDs/unknown fields. JSON carries
the corpus digest. CSV quotes every field, uses UTF-8 BOM/CRLF, doubles quotes,
preserves Unicode/newlines, and prefixes potentially executable formula cells
(including leading whitespace/BOM/zero-width markers) with an apostrophe.
Exports preserve attribution and do not grant reuse rights.

## Measured review build

Pinned base: `a736229d17d003ae7db3ca22235a63a3e2df7153`, canonical repository
`VSSpowerlifting/IndoPacificRecord` (the old origin URL redirects there).
Public archive snapshot: 2026-10-15. Source bodies/summaries were not expanded
from that archive. Current build: **962 items** — 873 archive metadata records,
66 official-link references, three preserved originals, one reviewed translation,
one reviewed analysis and 18 Briefs. Five desks occur in indexed results; that
is not a qualification/status verdict for any desk. **4,400 retirement entries**
are enforced. No candidate draft/stale/changed/duplicate/retired entries were
encountered in the selected public inputs; private areas remain unenumerated.

Local macOS review runtime: Python 3.9.6, Node v24.15.0, real Chromium.
Build: **1.414 s**, UTF-8 JSON index **804,727 bytes**. Disk read + JSON parse +
prepare: **48.32 ms**. Warmed query timings (10 warmups, 200 samples/query,
other tests running concurrently; no optimization claim):

| Query | Results | Median ms | p95 ms |
| --- | ---: | ---: | ---: |
| `maritime` | 33 | 0.4145 | 3.6798 |
| `"South China Sea"` | 9 | 0.4947 | 2.2421 |
| `北约` | 2 | 0.2498 | 0.9989 |
| Singapore, 2026-09-01 through 2026-10-15 | 48 | 0.0659 | 0.3378 |
| `nonexistent-token` | 0 | 0.3290 | 1.1893 |

Focused validation: **36 tests pass**, including 15 relevance cases, publication
boundaries, retirement/alias/stale-index attacks, exact duplicate resolution,
missing metadata, guarded destinations, Unicode/CSV formula injection, clipboard,
downloads, selection persistence, back/forward/reset, HTML/script payloads,
malformed URLs/queries, local-only requests and private server protections.
Chromium covers 320/375/768/1280 px, keyboard/visible focus, labels, polite result
announcements, reduced motion and zero horizontal overflow. Core text/ground
contrast pairs exceed 4.5:1. No unexpected network requests or console errors
were observed in the final browser smoke. These checks are not a complete
screen-reader/assistive-technology audit.

[Desktop citation/list capture](../../docs/evidence/archive-research-workbench/desktop.png)
and [mobile filtered search](../../docs/evidence/archive-research-workbench/mobile.png).
The captures use approved published metadata; no source content was invented.

## Private visual revision — PR #766

The workbench uses the existing locally served Instrument Serif for the page
heading, Source Serif 4 for reading-list titles/citations, and regular-weight
Inter for controls and metadata. The builder copies existing production assets;
shared fonts/styles/templates remain unchanged. Search leads the layout, desk/type
stay visible, and native **More filters** holds source/issuer/date controls.
Applied filters remain individually removable. Full processing/date/original-title
notes sit beside the unchanged citation in each result's disclosure; specific
editorial holds remain visible. Search and coverage help retain the limitations,
including the distinction between source and IPR publication dates.

[Comparable before/after captures and verification](../../docs/evidence/archive-research-workbench/visual-revision/README.md)
include desktop/mobile, expanded filters, selected citation/export controls and
empty results. Chromium verifies HTTP 200 font responses **and actual custom font
glyphs**, regular control weights, disclosure keyboard/URL restoration, overflow
at 320/375/768/1280 px, unchanged full provenance/citations and exact exported records.
No query, eligibility, record data, persistence or export-layer code changed.

Output validator: passes with the existing **10 governed warnings**.
Full offline suite and final-head CI status are recorded in the PR.
Protected-file smoke inventory: **1,832** tracked DB/output/Brief files hashed;
no changes observed. Graphify's ignored architecture index was refreshed.

## Integration decision left to the owner

Review the PR and private preview. A separate, explicitly authorized phase must
choose whether/how to integrate this adapter with production archive generation,
public routes/navigation, assets and release gates. No integration, desk change,
rights/approval change, corpus mutation, production output regeneration, workflow
dispatch, merge, publication or deployment is part of this PR.
