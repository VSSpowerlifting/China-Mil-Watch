# Integration recommendation: Halftone shell and the production record

_Prototype note, 2026-09-28. This is a recommendation, not an owner ruling, and it is not recorded
in `DECISION_LOG.md`._

## What production is today

- **One Python renderer.** `site/render.py` renders flat `.html` pages from `pla_watch.db` into
  `output/`, which is generated and never hand-edited.
- **Gated deploy.** `scripts/validate_output.py` gates deployment. `daily_update.yml` commits
  `output/` and publishes it to gh-pages as `indopacificrecord.org`.
- **The record surfaces.** The value of IPR is in the record: the archive (`archive.html`),
  corpus search (`corpus.html`, `corpus-index.json`, `browse.js`), source registry
  (`sources.html`) and per-record pages (`article/<id>.html`).
- **A public URL contract.** The flat `.html` addresses are public. They are held in place by
  `url_transition_map.json`, `predecessor_routes.txt` and the legacy redirect site.
- **Briefs have no renderer or route yet.** This is the gap Halftone fills best.

## Options

| | A. Halftone becomes the site; records are ported into it | B. Halftone is the publication shell; records stay in the production app | C. Keep the current frontend; borrow Halftone patterns |
|---|---|---|---|
| **What it preserves** | Must rebuild the archive, search and record pages, and every flat `.html` URL, in Astro | Records, archive, search, URLs and the validator unchanged | Everything |
| **Risk** | High. It creates a second renderer of the record, re-proves the browser and validator contracts, and puts Node in the daily pipeline | Moderate. It adds one Node build step and one new subtree | Low |
| **Maintainability** | Two stacks until the port finishes, then a rewrite of `render.py` | Two stacks with a hard boundary: Astro owns Briefs and Python owns the record | One stack, but Briefs still need a renderer built from scratch in Python templates |
| **What it gains** | One design system everywhere, eventually | A real Briefs surface now, with content collections, RSS, sitemap and schema-validated front matter | Visual polish only |

## Recommendation: B now, and A only if B earns it

The shell should sit on top of the record, not replace it. Option B gives Briefs a home
without touching the parts of IPR that carry its value.

1. **Mount under a subpath** of the same domain (`base: '/briefs'`), so there is one domain and
   one deploy. **The shell owns `/briefs/**` and nothing else.** The prototype's own Home, desk
   fronts, Archive, Records and About exist only to test the shell. Under B:
   - the shell's desk pages become per-desk brief indexes (`/briefs/china/`), not rival desk
     fronts;
   - Home, Desks, Archive, Records and About in its nav point to the production pages
     (`index.html`, `china.html`, `archive.html`, `sources.html`, `methodology.html`);
   - production keeps its homepage and desk fronts, which gain a link into `/briefs/`.
2. **Build through a governed generator step.** A documented script or workflow step runs
   `pnpm build` and writes `dist/` into `output/briefs/`, never a hand copy. Extend
   `validate_output.py` to cover the subtree, and add a Node job to `pr_offline_checks.yml`
   (build, check, lint).
3. **Link records by id.** The prototype's `source` rail block already carries a `record` field.
   Resolve it to the production record page (`/article/<id>.html`), and fail the build if a
   published brief cites an unknown or placeholder record.
4. **Keep one set of design tokens.** The prototype copies IPR's token values into
   `tokens.css`. Before launch, generate those values from the IPR design system so the two
   surfaces cannot drift.
5. **Match the brief contract.** Map the Briefs content schema to the existing brief workflow
   (the `publish-edition` contract and `EDITORIAL_QA_CHECKLIST.md`). Add a brief `number` field;
   Halftone has none.
6. **Consider A later, and only on evidence.** Revisit it after several real Briefs have shipped
   through B without incident, and only if there is a concrete reason to move the record pages.
   Even then, the database stays the single source of truth.

## Fit risks seen in the prototype

- **The theme is photo-led, and IPR has no licensed image pipeline.** The prototype uses abstract,
  generated plates, each credited as such. A text-only brief layout (with `hero` optional) is
  probably the right next change.
- **Tone.** The upstream display type (uppercase, black weight, spot red) read as tabloid.
  The design pass replaced it with Night Desk navy, a turquoise accent, serif 700 headlines and
  Signal Veil-style plates. If B proceeds, the tokens should be generated from the IPR design
  system rather than copied.
- **Toolchain.** The repository is Python-only today. B adds Node ≥ 22.12, pnpm and a dependency
  set to keep patched.
- **A repository-wide test.** `tests/test_site_mode_contract.py` reads every `*.py` in the repo,
  so it also walks a local `node_modules/`. The current tree has one `.py` file, and the test
  still passes (29 tests, OK, 2026-09-28). Re-run it whenever dependencies change.
