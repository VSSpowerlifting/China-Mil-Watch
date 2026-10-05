# Homepage topographic release evidence — 5 October 2026

Ben explicitly authorized completion of PR #101 through merge, deployment and
live desktop/mobile verification in Codex chat
`01a10816-1238-7b03-89fb-9ef9cb3ccde6` on 2026-10-05, after the disconnect.
The completed No. 15 release is preserved.

## Frontend scope and final candidate

Three abstract contour fields and polygon washes continue across the homepage
hero and paper sections. The field is static, homepage-only, responsive, and
removed in print and forced colors. The dark Briefs band and reading panels
retain their own surfaces. No geography or quantitative data is represented.

Final contour stroke opacity is **.12**, in both canonical
`site/preview/styles.css` and generated `output/styles.css`. The original .17
candidate passed sampled layouts but its maximum stroke-over-wash paint could
fall below the body-text floor. The final mathematical worst overlap is
**4.5752:1** against the muted text token; all-visible glyph minima are
**4.806:1 at 1280**, **4.967:1 at 375**, and **4.743:1 at 1920**.

The implementation delta is source CSS, generated CSS and the existing
homepage visual-contract tests. Documentation records the release. Article
copy, source records, identity assets, photographs, JavaScript, feed and sitemap
are unchanged from main after PR #100. Shared CSS adds 2,938 bytes (106,235 total)
and no HTTP requests; homepage HTML remains 22,452 bytes.

## Verified checks

- Homepage/hero suite: 113 tests passed, one skipped, before opacity refinement.
- Final .12 refinement: 17 affected shape/hero tests passed.
- Validator: pass, ten governed historical warnings.
- Independent final 1280/375/1920 rendered review: GO; all visible paper text,
  keyboard focus, overflow, no-JS, reduced motion, print, forced colors and
  route isolation pass. Root inspected the final desktop/mobile opening proofs.
- Final required CI, merge SHA, deployment run and live receipt are recorded
  in [PR #101](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/101).

Local final evidence is `/private/tmp/ipr-topo-releaseqa-20261005/report.json`
and `home-{1280,375,1920}.png`; refinement logs are
`/private/tmp/ipr-topo-contrast-tests.log` and
`/private/tmp/ipr-topo-contrast-validator.log`. Post-deployment evidence is
recorded in PR #101 and the final task delivery; these local paths are review
artifacts, not public source records.

## Preserved No. 15 release

PR #100 merged at `0e21083d6510c28e8f02daeca64e3a3d074ac8bd`.
[Required CI 37267976634](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37267976634)
passed 3,156 tests (two skipped), validation with ten warnings, and tracked
database/output immutability.
[Deployment 37273065804](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37273065804)
passed. At 07:11 UTC on 2026-10-05, article, homepage, Analysis, feed, sitemap,
both stylesheets and photograph all returned 200 and matched committed bytes.
The article SHA256 is
`3ed7d5df4c761b8a892af6218b70e67433a8e51288872913be0d955f1e31de29`.
Independent live article/home/Analysis review at 1280/375 passed; evidence is
`/private/tmp/ipr-no15-live-proof/report.json` and
`/private/tmp/ipr-no15-live-verification.json`.
