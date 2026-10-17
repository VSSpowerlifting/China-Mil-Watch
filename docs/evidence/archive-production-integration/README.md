# Archive production integration — review evidence

17 October 2026. Source candidate based on main `e376bcb6bf`; no deployment.
Private reference #766 remains at `cee7f1f6e1248e02cedd0c373d0f5b542a233e8a`.

- [Desktop search](desktop.jpg) · [research list](desktop-list.jpg) · [citation](desktop-citation.jpg)
- [Mobile search](mobile.jpg) · [compact disclosure](mobile-compact.jpg) · [expanded list](mobile-list.jpg) · [citation](mobile-citation.jpg)
- [Measured dependencies and actual font glyphs](measurements.json)
- [Complete generated-path comparison and protected inventory](preservation.json)
- [Isolated production assembly validator](staged-validator.json)

These are real Chromium captures of a current isolated render using approved
public data, not live-production verification. Desktop is 1280×1200; mobile is
375×900. Tests additionally cover 320/768 px, keyboard, reduced motion, no-JS
week browsing, exact legacy URL results, clipboard denial, CSV/JSON, history,
selection restoration and first-selection focus/scroll/disclosure stability.
Source Serif 4 and Inter Regular custom glyphs were verified through Chromium's
platform-font report. No console warnings/errors or unexpected requests appeared.

## Budget receipt

| Measurement | Raw bytes | Governing limit |
|---|---:|---:|
| Archive HTML | 72,547 | Included in HTML/CSS |
| HTML + all recursively linked CSS | 155,730 | 300,000 |
| `browse.js` | 9,493 | 9,500 working target |
| Complete page JS, including `shell.js` | 9,879 | 10,000 |
| Other static asset inventory, including fonts/image variants | 271,116 | Separate measurement |
| New lazy research index (966 eligible items) | 1,220,147 | Separate data asset |

Separately gzipped JS estimate: 4,458 bytes;
research-index estimate: 116,625 bytes. These are deterministic
reference encodings, not measured hosting transfer sizes. The loopback server
serves raw bytes; production compression is unverified. The static dependency
inventory is conservative and includes variants the browser may not request.
Both indexes load only on search/filter/paging, explicit research-tool activation
or restoration of a saved list; a fresh default visit keeps its server rows.

## Verification scope

The final integration PR records exact focused/full CI results and tested SHAs.
A pre-final broad local run executed 7,159 tests: four failures, 33 errors and 11
skips. One failure was an obsolete literal-source desk-join assertion, replaced
with per-record generated-data checks. The three macOS `/var` versus `/private/var`
failures and 27 store/dependency/GPG errors reproduced on clean initial base
`edf5fa7adc` (28 tests plus two class-setup errors). Six historical Brief browser
navigation timeouts occurred in that broad run; all six passed on clean main
`445592121b` in 123.556 seconds. This is not an all-green local full-suite claim.
After rebasing onto current main e376bcb6bf, the 30 new Archive contracts and
six newly inherited DAPA probe contracts passed together (36 tests). Runtime
source and exact rendered Archive HTML are unchanged by this rebase.
Final Linux full offline CI, including Chromium, is required and recorded in the PR.
No unrelated dependencies, store safeguards or historical browser tests changed.

Scratch production rendering is compared with clean main; every generated path
outside `archive.html`, `archive.css`, `browse.js` and the new research index is
byte-identical. Protected inventory checks include DB, tracked output, Briefs,
publication/desk records, historical companion files and workflows. The fully
assembled scratch site passes the validator with ten governed warnings. Tracked
production output was not regenerated. The ignored graphify code index was refreshed.

## Reproduce

From the repository root, run the commands in
[the integration contract](../../ARCHIVE_PRODUCTION_INTEGRATION.md).
`capture.py` recreates these images and `measurements.json` with the
repository Python/Playwright environment; it builds and serves temporary data,
then removes its scratch site. `scripts/build_archive_js.py --check` confirms
that the committed production bundle matches the readable sources and both JS
ceilings. Review the PR's final SHA/CI receipt before any later release decision.
