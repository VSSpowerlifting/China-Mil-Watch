# IPR Briefs consolidation — 2026-10-09 review candidate

Older articles now open in the current Indo-Pacific Record shell instead of
the predecessor masthead. This applies the owner's latest ruling while keeping
the public editorial structure to Records and IPR Briefs. No specialist journal
or additional public component is introduced. A future PLA Watch collection
remains a separate editorial decision.

## Implementation

Both `scripts/generate_pla_watch.py` and `scripts/rerender_pla_watch.py` now render
posts through `scripts/historical_brief_render.py` and
`site/preview/templates/historical-brief.html`. The latter extends the existing
IPR `base.html` and reuses its logo, navigation, footer, fonts, reading styles,
Brief hero and native disclosure behavior. Its two-level asset root is explicit.
Historical pages omit the live-site dates disclosure rather than show empty dates.

All 14 existing weekly article HTML files were regenerated from the existing
sidecars. The article body, source trail, issue number, dates, title, canonical
URL and exact citation remain intact. The browser-tab and social-sharing titles use the displayed IPR headline; the
original title remains intact in the sidecars and the exact historical citation.
A short provenance note names the original
series and publisher. Historical author wording remains verbatim inside a
labelled disclosure; the normal byline names the author. Adjacent issue URLs and
original feed IDs/URLs continue to work. Ordinary browsing returns to IPR Briefs.
The old post templates remain available as a legacy reference and rollback path.

This changes article presentation. The compatibility index/archive/terms/feed
outputs are byte-identical to their previous versions. The canonical database
and sidecars are not migrated or edited.

## Verification

- Focused collection, identity, frontend and date tests passed: 206 tests.
- New preservation and browser suite passed: 13 tests, using all 14 real issues.
  The browser suite covers 56 viewport cases (320, 375, 768 and 1280 pixels),
  plus 28 no-JavaScript/reduced-motion cases, keyboard skip/menu behavior and
  local asset delivery. No overflow, JavaScript errors or local asset failures
  were observed. Mobile and desktop screenshots were also visually reviewed.
- Browser checks used Playwright 1.59.0 with local Chromium 153.0.8010.0;
  GitHub Actions remains responsible for its own declared browser installation.
- The governed validator passes with the same 10 existing warnings before and
  after regeneration. A pre/post fingerprint comparison found no change to the
  database, 36 canonical JSON files or the original feed (38 files total).
- The normal production renderer built 7,377 native IPR HTML pages into a
  temporary directory. Every existing native page is byte-identical to the
  committed output. Generated changes in this patch are confined to the 14
  weekly article HTML pages.
- The largest historical page plus local CSS is 73,585 bytes; shared JavaScript
  is 372 bytes. There are no external CSS/JavaScript dependencies.
- Full repository run: 4,916 tests in 861 seconds, four failures, three errors
  and seven skips. This is **not** a passing full-suite result. All four failures
  and the legacy veil browser error reproduced with the same messages on
  unchanged main `fe5e25064ce09e70789878520e926bbe9f604fc0` (five selected tests).
  They concern legacy fallback-font/veil measurements and compact-date parsing
  in unrelated Friday/Sunday window checks under local Python 3.12. The other
  errors were a missing `httpx` dependency (after installation, all 57 telemetry
  tests passed) and the repository-isolation test encountering the local venv's
  symlinks (it passed in a clean baseline checkout). Neither those templates nor
  those window/isolation implementations changed in this patch. Exact-head CI
  in the repository's declared environment is required before release; no full
  green result is claimed here.

## Frontend integration boundary

The adapter and article template are new files. The existing post entry points
receive small render-call changes. The only shared-shell changes are the root
path override and suppression of an empty dates disclosure.

The published frontend branch `codex/ipr-frontend-production-20261008` was checked
at `0825ee369591a42bacfb853af1172c05f42d2450`. Its versions of the three existing
rendering files changed here match this patch's starting versions byte for byte.
The render-file patch also passed `git apply --check` against that candidate,
supporting a clean integration. Changes still unpublished in the other frontend
session have not been inspected and must be checked at merge time. The other
branch has not been edited.

This is a review candidate, not a merge or deployment. Exact-head CI and the
normal publication gates still apply before release.

## Historical graphics and author links — preservation follow-up

The first shell pass omitted resolved legacy Signal Veils and historical author links. The corrected current-shell render preserves both curated and source-derived dated imagery, source/attribution links, alt text, original crop position, and the original issue's LinkedIn, email and historical organization links. A selected veil replaces, rather than duplicates, any in-page cover photograph. Unsafe historical link schemes are rejected. Every checked-in article must now match its deterministic sidecar render exactly. No sidecars, citations, feed identities, underlying archive records or publication URLs change. The corrective commit requires new exact-head CI before release.

Supplementary attribution check: when a historically published Signal Veil replaces a distinct in-page cover photograph, the original cover image's source credit remains as text beside the coverage snapshot (the original OG cover URL remains unchanged). This retains both credited visuals without duplication.
