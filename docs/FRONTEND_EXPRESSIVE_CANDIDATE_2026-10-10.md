# Expressive frontend review candidate — 10 October 2026

Implemented in the assigned isolated worktree, from detached main HEAD
`0487bfc0480bd94a9d4471f927c449c506f07cbf`. Source changes remain uncommitted;
no push, PR, merge, deployment or editorial publication occurred. Tracked
`output/`, canonical sidecars, the database, desk registry/geography and timeline
editorial state are unchanged.

## Review the result

- Interactive candidate: <http://127.0.0.1:8787/>
- Paired desktop/mobile gallery: <http://127.0.0.1:8788/>
- Durable gallery: [evidence/index.html](evidence/frontend-expressive-2026-10-10/index.html).
  Its 52 photographs of rendered pages cover the lower homepage, archive,
  record, Briefs catalog/opening/reading, map, individual desk, methodology,
  historical article/glossary and individual source. Desktop is 1440px; mobile
  is 375px. Static captures use the finished reduced-motion state.

The comparison baseline is a production-source render of the exact starting
HEAD, plus its unchanged carried historical derivatives. It is not an older PR
or a synthetic concept. The attached contour archive is inspiration only; its
sample records and photographic geography were not adopted as evidence.

## Visual and source assessment

The homepage already had a convincing documentary opening and generous
composition. Its lower ivory sections and the inner shells offered too little
authored space; the earlier contour pilot was too faint to establish continuity.
The combined direction makes contour bundles into boundaries and occupied
margins, uses ivory paper and navy chart material, and keeps typography and
documentary photographs central. Reading columns stay clear of decoration.

| Family | Implemented treatment |
|---|---|
| Homepage | Original hero preserved; flowing finder shelf, navy selected-record inset, visible contour seams, layered coast band, occupied desk margin |
| Archive | Broad coastal edge joins opening and finder; strong display heading; clear result ledger and textured processing surface |
| Records | Narrow line-only profile beside source date; tinted provenance/source rail; unchanged original text, processing and citation anatomy |
| Briefs | Navy textured openings, cropped chart bundles and curved ivory transition; distinct inset section navigation; preserved photographs and credits |
| Desk/source/week pages | Cropped margin profiles, textured status/navigation/data surfaces and a shared contour colophon |
| Utility pages | Horizontal contour cuts, editorial display openings and clear reading measures |
| Historical articles and utilities | Current IPR shell; original publication identity, article evidence, citation, glossary text and feed retained |

Instrument Serif, Inter and Source Serif 4 remain the established families.
The supplied selected lowercase ipr lettering and circular accent are unchanged:
the shell continues to use derivatives of `selected-ipr/1.png` and `2.png`.
No lettering was recreated and no older contour logo was substituted.

Three small original SVG compositions have deterministic generators and
receipts. They encode no geography, elevation, record volume or evidence.
Navy material preserves the verified paper tile's pixel topology with a navy
palette; its source receipt and hashes are retained. Existing documentary
photographs and their attributions remain; no invented photograph was added.

The neighboring sitewide candidate PR #314 was inspected read-only against this
HEAD. Only its deterministic navy-material builder, tile and receipt were
reused. Its quieter page treatments and map were not assumed to be the baseline.

## Desks and motion

The chart retains the exact Natural Earth geometry, Miller projection and
registry-provided institutional seats. The directory is a chart beside a
complete register on desktop and a chart followed by entries on phones. Real
country/marker clicks and native desk buttons share persistent selection,
country/seat/entry emphasis, scope details and an announced status/count. The
fragment preserves selection on reload; All desks clears it without a jump.
Arrow/Home/End keys move among buttons; Enter/Space select; Escape resets.
Noncollecting desks retain **None collected** and their actual status meanings.
Phone markers have at least 44px hit targets; tiny coordinate ticks are omitted,
with real coordinates available in the register. Without JavaScript the chart
anchors and all desk links remain usable.

Decorative scroll entrances use CSS view timelines with finished static
fallbacks. The measured homepage field settles from `(-24px,14px)` and opacity
`.65` to `(0,0)` and `1`. Control presses move 2px; disclosures enter briefly.
Reduced motion and `.no-anim` remove motion. Content is never hidden by the new
entrances. Print and forced-color states omit decoration, and forced colors
retain the map's controls and selected state. No new observer, framework or
animation dependency was added to the near-cap homepage/archive scripts.

## Resources that influenced implementation

- Installed **Frontend Design**, **Impeccable** and **UI UX Pro Max** skills:
  authored editorial composition, varied page-family surfaces, clear reading
  measures and control/contrast/phone-target review. The existing Impeccable
  version was retained; no plugin upgrade was performed.
- [React Bits AnimatedContent](https://github.com/DavidHDev/react-bits/blob/main/src/ts-default/Animations/AnimatedContent/AnimatedContent.tsx):
  finite directional entrance of decorative art, adapted to native CSS.
- [21st.dev animated tabs](https://21st.dev/@kuratlielia/components/tabs):
  persistent selected emphasis, adapted to the real desk selector.
- [shadcn Toggle Group](https://ui.shadcn.com/docs/components/base/toggle-group)
  and [Radix keyboard conventions](https://www.radix-ui.com/primitives/docs/components/toggle-group):
  native pressed-state controls and explicit keyboard operation.
- [Type UI animation examples](https://www.typeui.sh/ui-animations): concise
  feedback and disclosure timing.
- Framer's [overflow guidance](https://www.framer.com/help/articles/overflow-clip/)
  and [reduced-motion guidance](https://www.framer.com/help/articles/reduced-motion-settings/):
  scoped decorative fields and deliberately finished fallback states.

The inventory included installed 21st skills, Figma/Mobbin connectors and
Excalidraw export resources. Mobbin's connector was paywalled, and the 21st CLI
and registry MCP were unavailable; public primary examples were used. Figma
and Excalidraw did not contribute artifacts to this source-first candidate.
No third-party runtime code was imported. Bounded read-only specialists
reviewed architecture/overlapping work, design resources/composition and map
behavior; the primary agent owned all source writes.

## Verification and budgets

- Complete route sweep: **7,461 routes, zero HTML/CSS/JS budget failures**.
- Full record integrity: **5,020 records** checked against the database for
  titles, original bodies, summaries, source URLs, dates, provenance, citations,
  compatibility routes and approved source-trail relations.
- Editorial DOM parity: **14 historical articles, three native Briefs and 14
  glossary terms** preserve their source text and citation/evidence links.
  All 14 historical JSON sidecars are byte-identical. Historical utility
  canonical URLs are unchanged.
- **19 protected files** match HEAD byte-for-byte, including the database,
  unpublished timeline, registry, geography and selected identity assets.
- Browser review: **234 passing checks** across 320/375/768/1440px, native map
  selection/reset/keys/fragment, search/reset, citation links, disclosures,
  mobile navigation, no JavaScript, reduced motion, print, forced colors and
  blocked fonts. No sampled local asset failures or JavaScript exceptions. Four additional
  checks pass for native country/seat pointer clicks, exact citation clipboard
  copying and the explicit `.no-anim` state.
- **98 Firefox/WebKit checks pass** for responsive layouts, map selection,
  keyboard/reset, phone marker targets and reduced motion. This supplements
  the Chromium screenshots; it does not simulate real Safari/iOS hardware.
- Focused frontend run: **94 tests pass**. Final historical adapter/browser
  run: **21 tests pass**, including exact glossary and historical utility
  contracts. The complete intro/prototype regression run passes **508 tests**, with its
  one existing frozen-prototype readiness skip. The initial broad run failed
  29 checks: 26 motion-overflow cases, two heading checks and one brittle
  name-based directory matcher. These were investigated and corrected. The final integrated run passes **5,280 tests in 1,142 seconds**, with
  **one existing frozen-prototype readiness skip** and no failures/errors.
  The narrow historical byte-parity comparison also passes after making it
  compatible with a future authorized output refresh; no editorial byte is
  exempted. Exact-head CI remains unrun.
- Deploy validator: passes with the **same ten governed warnings**, using the
  unchanged historical LinkedIn companion directory; gaps were not invented
  away. Exact warnings are in the evidence directory.
- `graphify update .` completed the required AST update. Its generated graph
  is ignored, and its zero-node warnings concern unsupported source formats;
  no semantic claim was taken from that graph.

| Route | HTML + all local CSS | JavaScript |
|---|---:|---:|
| Home | 68,138 B | 11,940 B |
| Archive | 132,897 B | 9,847 B |
| Catalog | 102,296 B | 3,118 B |
| Record 3924 | 64,930 B | 5,322 B |
| Brief No. 15 | 76,451 B | 5,322 B |
| Desks | 178,566 B | 2,681 B |
| China Desk | 83,654 B | 0 B |
| Methodology | 81,232 B | 0 B |
| Historical article, 8 August | 80,703 B | 372 B |
| Historical glossary | 89,441 B | 0 B |

The largest HTML/CSS surface is the desks index, within its 300 KB index cap.
Individual documents retain the 120 KB cap. Home retains its existing 12 KB
script allowance, other routes the 10 KB limit. Shared additions are 5.5 KB CSS;
map JavaScript is route-only. New material/profile assets total about 21 KB.
Conservative inventory counts all linked image variants; actual cold browser
requests are smaller. Desktop samples measured 428 KB home, 265 KB archive,
395 KB desks, 220 KB record and 355 KB Brief. Increases were 26–76 KB, including
fonts/material/markup, with source photography unchanged. The near-cap scripts
were investigated and left with no new shared JavaScript. Receipts include
actual request lists and measured contour movement.

Chromium, Firefox and WebKit were exercised. The real Safari app/iOS devices,
real assistive technology, touch hardware,
deployed/CDN behavior and exact-head CI remain unverified. No release readiness
is inferred from local screenshots or budget checks.

## Engineering handoff

Rebuild a private candidate outside the repository:

```sh
.venv/bin/python scripts/build_frontend_review.py --out /private/tmp/ipr-review/candidate
.venv/bin/python scripts/verify_frontend_delivery.py --root /private/tmp/ipr-review/candidate --receipt /private/tmp/ipr-review/delivery.json
.venv/bin/python scripts/verify_frontend_integrity.py --public /private/tmp/ipr-review/candidate --receipt /private/tmp/ipr-review/integrity.json
```

For the full governed ten-warning validation, copy the existing
`the-pla-watch/linkedin` directory beside the private build, then run
`scripts/validate_output.py` against it. Serve before/after builds on loopback
ports and run `scripts/verify_expressive_frontend.py --evidence /private/tmp/ipr-review/evidence`.
This session used the read-only interpreter at
`/Users/benjaminyang/pla-watch/.venv/bin/python`, because this worktree has no
local `.venv`. Browser and loopback operations required approved sandbox
escalation; no automatic approval rejection remains.

The next action is owner visual review of this candidate. Commit/output
regeneration, draft PR, merge, deployment and timeline editorial approval are
separate actions and have not occurred. A later authorized generated-output
refresh must run both the production daily renderer and historical source
adapter; the private builder demonstrates the combined result without editing
tracked output. Keep the timeline unpublished.

The complete source/evidence inventory is in
[changed-files.txt](evidence/frontend-expressive-2026-10-10/changed-files.txt).
Source roles: shared shell/material styles; five family sheets; map template,
route stylesheet and controller; historical utility template/adapter;
deterministic asset builders/receipts; disposable build/browser verification;
historical contract fixtures; context and handoff documents. Generated evidence
consists of screenshots and receipts only; no public output or editorial content
was regenerated in the working tree.
