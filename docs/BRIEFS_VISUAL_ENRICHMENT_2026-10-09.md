# Briefs visual-enrichment pilot — 9 October 2026

Scope: the Briefs catalog at `analysis.html`, plus opt-in decorative primitives,
asset preparation and complete delivery verification. This is a reviewed PR
candidate. It authorizes no merge, deployment, wider route treatment or timeline
publication.

Repository: `VSSpowerlifting/China-Mil-Watch`. Branch:
`codex/ipr-briefs-enrichment-20261009`. Assigned isolated Codex worktree:
`/Users/benjaminyang/.codex/worktrees/ca1c/pla-watch`.
Starting base: `fe5e25064ce09e70789878520e926bbe9f604fc0` (main fetched at start).
Reconciled PR base: `38e1b31620b5ba671831bb865e8f4fe6e0f54c26`.
Released comparison: `4dbf42c5ca778eb5c55a9134fc51cac4fdc16a4f`.
Implementation head: bea0057164b31f9e3da546a49b9f9757ccf9319a. The final PR head is recorded
in the delivery checkpoint; this document's own commit cannot name itself.

Subsequent main changes are Operations Center, stored-backlog/recovery audits,
regional receipt reconciliation and private editorial tooling. They change no
frontend source, generated routes or canonical records. Current main is pinned
at `38e1b3162` for this PR; no frontend dependency is outstanding. Both released
and current-main catalog captures were compared.

## Design and engineering

The released navy opening now carries an asymmetric field of original IPR
curves, strongest in open space and attenuated beneath type. A quiet paper tile
replaces flat reading ground, with a static margin motif confined to the catalog
opening. The desktop lead has a fine vertical separator; stacked layouts keep
the horizontal divider. A turquoise reading button gives the primary action a
clearer hierarchy. Open ledger rows respond with a surface tint and underlined
links on hover/focus; they remain open rows, without shadows or moving text.

`_terrain.html` exposes inert hero/margin primitives. `briefs-catalog.css` and
existing `reveal.js`/`shell.js` are requested by `analysis.html` alone. The original
10,355-byte topography stylesheet and its historical consumers are preserved.
Only the decorative contour field enters, once, through the existing observer
and a 780ms transform/opacity transition. Menus use a 150ms entrance and the
existing native disclosure/Escape controller. There is no ambient loop or new
runtime dependency. Script failure/no-JS, reduced motion and `.no-anim` retain
finished artwork; print/forced colors remove decoration.

No publication wording, sidecars, database records, evidence, dates, citations,
identity derivatives, historical issues or link destinations changed. The lead
has no approved cover, so no decorative documentary photograph was inserted.
Existing native Brief/home photographs remain untouched. Generated paper and
abstract curves have no geographic or evidentiary meaning.

## Actual browser captures and design judgment

These are Chromium implementation captures, not generated concepts:

- [Desktop opening](review/briefs-2026-10-09/briefs-desktop.png) and
  [full catalog](review/briefs-2026-10-09/briefs-desktop-full.jpg).
- [Mobile opening](review/briefs-2026-10-09/briefs-mobile.png) and
  [full catalog](review/briefs-2026-10-09/briefs-mobile-full.jpg).
- [Tablet](review/briefs-2026-10-09/briefs-tablet.png),
  [keyboard focus](review/briefs-2026-10-09/briefs-mobile-focus.png).
- Released [desktop](review/briefs-2026-10-09/released-1440.png) and
  [mobile](review/briefs-2026-10-09/released-375.png) comparisons.

The initial material was too fibrous and the left contours crossed too much
of the title. Both were refined after browser inspection. The final paper reads
as subtle uncoated material; no obvious seams appear in the viewport/full-page
captures. The clean title, asymmetric flow, stronger action and separator make
the catalog more distinctive while retaining its spacious editorial character.
The lower ledger/reference sections stay quiet. No excessive treatment remains.

Independent design review approved final 375/768/1440 captures. The mild weakness
is mobile: its artwork is deliberately faint and the stacked opening remains
long, so desktop gains more character. Still captures do not establish motion
quality; the browser checks and throttled timing sample below supply separate
motion evidence. Physical phones and non-Chromium engines were not tested.

## Verification and delivery

- 42 catalog cases: 320/375/768/960/1280/1440 widths, each with default,
  no-JS, script failure, reduced motion, `.no-anim`, forced colors and print.
  No horizontal overflow; finished content/artwork and one h1 retained.
- Native menus, Enter semantics, Escape/focus restoration when scripts
  run, native close when scripts fail, keyboard skip/Browse/Brief journey,
  visible row focus, hover response and live reduced-motion changes checked.
- Exact normalized body text, all 60 body-link destinations, IDs/anchors and
  local destinations match the current-main renderer baseline.
- Full-corpus preservation: 4,980 record bodies/titles/dates/URLs/citations,
  compatibility routes and 10 approved native source relations pass.
  No public timeline routes; draft digest unchanged.
- Complete HTML/CSS/JS sweep: all 7,395 rendered routes pass. Index/archive
  hubs (including the desk index) use the governed 300 KB allowance; individual
  documents retain 120 KB. Home retains its separately governed 12 KB script
  cap; other routes retain 10 KB. The gate includes imports/inline code and
  now inventories linked graphics, fonts, image variants and icons.
- Deploy validator: passes with the same 10 governed warnings.
- Offline suite: initial run — 4,986 tests, one setup error and one existing
  stale-prototype readiness skip. The local runtime symlink caused the error;
  the clean broad rerun is in progress. No broad green result is claimed yet. Final focused checks: 13 tests pass, including the complete committed-output
  delivery gate; reconciled-main checks: 19 tests pass for the reconciled Operations Center changes. Additional reconciled-main tests: 62 tests pass for the regional and four Ops/recovery modules. The broad rerun
  was discovered before those unrelated main updates; focused checks cover
  their new/changed tests.

| Surface | HTML + all CSS | JS | Conservative local assets | Change |
|---|---:|---:|---:|---|
| Briefs catalog | 95,313 B | 3,118 B | 262,373 B | +5,353 / +3,118 / +20,148 B |
| Largest record, `record/476.html` | 110,284 B | 5,322 B | 242,225 B | unchanged |
| Home | 58,492 B | 11,940 B | 2,585,195 B | unchanged |
| Record archive | 126,583 B | 9,847 B | 242,225 B | unchanged |
| Desk index | 158,693 B | 0 B | 242,225 B | unchanged |

The asset column conservatively counts every declared font/image variant and
icon, not just browser-selected variants. The catalog total is 360,804 B in that
inventory. Actual loopback Chromium cold delivery was 278,443 encoded body bytes
(283,243 transfer bytes), versus 249,824 body bytes for the release/main baseline;
repeat navigation recorded zero network transfer from cache. These are local
observations, not compressed CDN or field measurements.

Observed cold load layout-shift sums were .02323 mobile / .01848 desktop,
versus .02273 / .01403 for current main, with zero on cached navigation.
The shared swap-font arrival remains visible in both; no zero-CLS claim is made.
The 4× CPU-throttled local sample had 16.7ms median / 17.7ms p95 frame intervals,
with startup outliers of 233ms mobile / 117ms desktop. This bounds one finite
entrance; it does not establish universal 60fps or real-device performance.
See [browser receipt](review/briefs-2026-10-09/BROWSER_QA.json),
[delivery summary](review/briefs-2026-10-09/DELIVERY_SUMMARY.json),
[integrity receipt](review/briefs-2026-10-09/INTEGRITY.json) and
[timing sample](review/briefs-2026-10-09/PERFORMANCE.json).

## Source, generated output and provenance

Source changes:
`site/preview/templates/{analysis,_terrain}.html`, `site/preview/briefs-catalog.css`,
`site/preview/generate_preview.py`, `site/assets/material/`,
`scripts/build_briefs_material.py`, `core/frontend_budget.py`,
`scripts/{verify_frontend_delivery,verify_briefs_catalog,verify_frontend_integrity}.py`,
`tests/test_briefs_enrichment.py`. Documentation/state/review receipts are separate.

The production renderer produces exactly one changed HTML page, `output/analysis.html`,
and four additions: `output/briefs-catalog.css` plus three material assets.
All other tracked generated files remain byte-identical to the main baseline.
The complete production tree has 18 historical weekly HTML routes absent from
the clean scratch render; its existing sitemap is preserved. Catalog/page/asset
bytes match the reviewed scratch render. [Parity receipt](review/briefs-2026-10-09/GENERATED_PARITY.json). Source and
regenerated output are separate commits; documentation/captures are another.
`graphify update .` refreshed the ignored code graph successfully; its 14,063
nodes exceed the HTML visualization limit, so no graph.html was produced.

The supplied `IPR_Visual_Enrichment_2026-10-09 (2).zip` was read as design evidence,
not as additional authorization. Its README/VERIFICATION were inspected and both
`index.html` and `IPR_Briefs_Enriched.html` were opened in Chromium. The previous
managed-preview error did not apply: installed Chromium launches through the
approved local execution path here. Review files remain outside production. The worktree had no runtime; an initial
ignored `.venv` symlink to the main checkout runtime triggered an existing
shadow-isolation test. It was removed, the 14 isolation tests passed, and the
broad suite was rerun using `/Users/benjaminyang/pla-watch/.venv/bin/python`
directly. No collector/isolation implementation was changed.

[Asset receipt](../site/assets/material/ASSET_RECEIPT.json) binds the 2,600,875-byte
supplied paper master by SHA-256. Its original generation prompt/model were not
supplied; no provenance is invented. A 256px luminance crop is reduced, mirrored
into a seamless 256px tile and remapped to eight neutral paper tones. Delivered
PNG: 14,086 B (99.46% smaller), 262,144 B decoded RGBA. Two contour SVGs are
3,031 B each, using the surviving 12 cubic paths unchanged. The master stays
in the supplied bundle; the builder accepts it by verified digest. The selected
lowercase ipr logo/lettering/turquoise accent remains bound to
`site/assets/identity/selected-ipr/ASSET_RECEIPT.json` and its supplied derivatives.
The seven existing OFL font assets/licenses are unchanged.

## Resources and specialist work

Actually used: installed Frontend Design skill
(`/Users/benjaminyang/.agents/skills/frontend-design/SKILL.md`),
Pillow asset preparation, Chromium/Playwright, in-app browser review, the repository's
production renderer and motion controllers. Read-only design and engineering
specialists exercised judgment, reviewed actual captures/source, and caught an
initial fallback-opacity QA assertion that was corrected.

Researched/read instructions: installed Impeccable skill plus init/brand/polish
references; [official OpenAI frontend builder](https://github.com/openai/plugins/blob/main/plugins/build-web-apps/skills/frontend-app-builder/SKILL.md);
[Motion performance](https://motion.dev/docs/performance) and [animate](https://motion.dev/docs/animate);
[Framer reduced motion](https://www.framer.com/help/articles/reduced-motion-settings/);
[shadcn navigation](https://ui.shadcn.com/docs/components/base/navigation-menu);
[21st.dev](https://21st.dev/) and its installed review skill;
[UI Skills directory](https://github.com/ibelick/ui-skills);
[React Bits topography](https://reactbits.dev/backgrounds/topography).
No third-party component, framework or motion runtime was copied/installed.
The [CLS guidance](https://web.dev/articles/cls) informed honest lab/field distinction.
Figma/Sites tools were discovered but were unnecessary for this renderer pilot.

Blocked: Mobbin connector still requires [paid access](https://mobbin.com/pricing),
so no references were retrieved. React Bits' client page did not expose inspectable
source/license text through the web tool. Impeccable's context bootstrap requested
a PRODUCT.md, but its `.agents` setup write hit a protected directory and was
stopped; no tooling configuration or automatic skill update was performed. The
repository's existing authoritative editorial/design documents governed refinement.

## Reproduce and wider-phase checkpoint

```sh
.venv/bin/python scripts/build_briefs_material.py --master '/path/to/extracted/assets/chart-paper.png'
.venv/bin/python site/render.py
.venv/bin/python scripts/validate_output.py
.venv/bin/python -m unittest tests.test_briefs_enrichment tests.test_frontend_production -q
.venv/bin/python scripts/verify_frontend_delivery.py --root output --receipt /tmp/ipr-delivery.json
.venv/bin/python scripts/verify_frontend_integrity.py --public output --receipt /tmp/ipr-integrity.json
# Serve the released/baseline/candidate trees on loopback, then:
.venv/bin/python scripts/verify_briefs_catalog.py --url CANDIDATE_URL --baseline-url MAIN_URL --released-url RELEASE_URL --root CANDIDATE_DIR --baseline MAIN_DIR --out /tmp/ipr-browser-review
```

Wider phase should reuse owned curves, restrained material and finite decorative
motion through different route compositions. Keep photographic quality and clear
reading columns. Explore a stronger mobile edge composition, not reduced reading
type or filler. Home/archive have only 60/153 script bytes remaining: consolidate
existing behavior before adding runtime. The largest record has 9,716 HTML/CSS
bytes remaining, so avoid restoring the complete terrain stylesheet globally.
Homepage, archive, record and individual Brief treatments remain subsequent work;
the timeline remains unpublished. This session stops with the pilot PR.
