# Archive production integration — source candidate, 17 October 2026

Historical 966-item snapshot. Current reconciliation, 1,006-item corpus and
separately grouped inherited output are recorded in the [release preparation](ARCHIVE_RELEASE_PREPARATION_2026-10-17.md).

The existing `archive.html` gains publication-aware search, citations and a
browser-tab research list. Private reference [PR #766](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/766)
at `cee7f1f6e1248e02cedd0c373d0f5b542a233e8a` remains separate and unchanged.
This branch authorizes no merge, tracked-output regeneration or publication.

## Current-build authority

`site/render.py` remains the production entry point. Its selected database and
current six-field `corpus_index()` projection enter `core/archive_research.py`
explicitly. Desk pages and the Archive consume the same in-memory public-loader
results. Approved Briefs are captured before private review can insert a draft.
Historical canonical edition JSON supplies recorded identity/publication dates;
this is an editorial source, not a generated search input. There is no read of a
previous `output/corpus-index.json` and no dynamic renderer import in the adapter.

The existing `corpus-index.json` schema and bytes are preserved for the same
snapshot. A separate `archive-research-index.json` contains only admitted public
projections. Archive rows have no source URL, captured body or machine summary.
Only public Korea original/English registers authorize their respective text.
Neither a staged review pack nor SQLite existence establishes publication.
Retirement IDs, source-URL hashes, exact identity/deduplication, processing labels,
editorial holds and missing dates retain their reviewed #766 rules. Held-reference
qualifications remain visible before opening citation/provenance details.

Both complete index files are SHA-256-bound to the same generated Archive HTML.
The browser checks exact bytes before parsing/drawing. A stale or altered file
withdraws the finder and retains the 50 server-rendered records and week routes.
HTTPS or a secure loopback context is required for the enhanced finder.

## URL contract

Existing defaults remain `scope=focus`, `sort=new`, page 1. `q` remains a literal,
case-insensitive substring of the English/original title pair, including when an
English title is absent. `scope=all`, `desk`, source **codes**, `status`, institution
**codes**, language **codes**, `from`, `to`, `trail=1`, `sort=old` and `page` keep
their meanings, ordering and 50-result pagination. Existing record, article-alias,
corpus and week routes are unchanged.

Additive controls are `scope=published`, `keywords`, `record_type`, `issuer` and
`sort=relevance`. Keywords use reviewed NFKC/lowercase AND/quoted-phrase matching;
archive terms can match only titles and permitted public metadata. New source
labels select other published material; legacy source codes remain available.
Processing/institution/language/trail filters apply only to archive records.
Dates are inclusive; missing publication dates stay missing. IPR publication dates
come from public release records, never coverage weeks or approval dates.

Selections use `sessionStorage`, are revalidated on reload and never uploaded.
CSV/JSON retain reviewed attribution, formula protection and stable identities.
First selection does not expand the mobile disclosure or move focus/scroll.
Citation copy has a selectable-text fallback. No-JavaScript readers retain the
initial 50 records and complete week browsing; enhancement controls stay inert.

## Assets and budgets

Readable sources are `site/preview/archive-search.js` (reviewed query/export
engine) and `browse.source.js` (production controller). Rebuild the committed
`browse.js` using `python3 scripts/build_archive_js.py`; `--check` compares exact
bytes. Pinned Terser 5.44.0 is development-only: production rendering needs no
Node packages or additional runtime dependencies. Static native HTML templates
avoid duplicate DOM-construction code; stored strings enter through text nodes.
Archive typography uses existing Instrument Serif, Source Serif 4 and Inter.
All new styles stay in Archive-only `archive.css`; shell/fonts/desk CSS are untouched.

The governing limit is **10,000 raw JS bytes per page**, including shell, linked
imports and inline executable code; `browse.js` also retains its 9,500-byte working
target. HTML plus recursively linked CSS has a separate 300,000-byte Archive limit.
Gzip estimates and fonts/images are separate measurements, not substitutes for
these ceilings. [Evidence](evidence/archive-production-integration/README.md)
records exact measurements and actual Chromium font glyphs. Hosting compression
and live production behavior have not been verified.

## Validation and remaining release work

Run the focused contracts before the full offline suite:

```sh
.venv/bin/python -m unittest tests.test_archive_integration tests.test_archive_integration_browser tests.test_china_focus_browser tests.test_research_atlas_hierarchy -v
python3 scripts/build_archive_js.py --check
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python scripts/validate_output.py
.venv/bin/python docs/evidence/archive-production-integration/capture.py
```

The integration PR records final-head/synthetic-merge CI and the full local run,
including environmental failures. Isolated production renders against current
main differ only in `archive.html`, `archive.css`, `browse.js` and the new research
index. Protected-file hashes and a fully assembled scratch validator receipt
are linked in the evidence. No tracked production output is regenerated here.

After owner review, an explicitly authorized release must pin current main,
regenerate through `site/render.py`, inspect the complete generated diff, repeat
validator/budget/Chromium/preservation checks and separately approve publication.
Review any unrelated output drift separately. Keep the new index and its bound
HTML in the same release. Source merge also enables this renderer in future daily
runs, so merge must be coordinated with that release authorization. No deployment
workflow is changed or dispatched by this PR.

Competing #712/#741 and #749/#694 edit the shared renderer; their desk behavior
and public-register authority must survive reconciliation. #769's staging and
subsequent owner publication are inherited from main, not admitted by this change.
#699/#710 remain separate release-contract work; #739 is an opt-in Pages guard,
not an enforced dependency. Recheck main and these paths before landing.
