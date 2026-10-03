# Indo-Pacific Record: Halftone publication-shell prototype

**This is a prototype. It is not the production site and is not deployed.** It tests whether the
MIT-licensed [Astro Halftone](https://github.com/ondelva/astro-theme-halftone) theme (upstream
commit `d389a3d`) can serve as the Indo-Pacific Record publication shell for Briefs, desks and
standing pages. The archive, corpus search and source records stay in the existing production
system, which this prototype links to and does not replace.

Nothing outside `prototypes/ipr-halftone/` is changed. The production renderer (`site/render.py`),
`output/`, the pipeline, the database and the workflows are untouched, and no workflow builds or
deploys this directory.

## Run it

Requires Node ≥ 22.12 and pnpm 10, which corepack provides from `packageManager`.

```bash
corepack pnpm install
corepack pnpm dev          # http://localhost:4321
corepack pnpm build        # static site in dist/
corepack pnpm preview      # serve dist/
corepack pnpm check        # astro check (types)
corepack pnpm lint         # eslint
corepack pnpm check:contrast
corepack pnpm plates       # regenerate the abstract plates
```

`site.url` is `https://example.com` on purpose, so that canonical URLs, the sitemap and the feed
never claim production addresses. Override it with `SITE_URL=… corepack pnpm build`.

## What changed from upstream Halftone

- **Identity and navigation** (`src/config.ts`). The name is Indo-Pacific Record, the byline is
  editorial, JSON-LD is typed as an Organization, and the nav is Home / Briefs / Desks / Archive /
  Records / About.
- **Desks** (`src/content/desks.json`). China and Singapore are collecting desks. Regional Security
  is an editorial grouping. Archive links to the production record system. The schema gains
  `kind` and an optional `notice`.
- **Source records in the rail** (`content.config.ts`, `Rail.astro`). A new `source` rail block
  holds a label, publisher, date, record id, href and a `placeholder`/`linked` status. Placeholder
  sources print "Prototype placeholder, not a citation".
- **Pages.** `briefs`, `desks`, `records` and `about` are added. The theme's `colophon` and demo
  bar are removed, and a site-wide prototype notice replaces the demo bar.
- **Plates.** The sample photographs are replaced by generated abstract plates in the style of
  IPR's Signal Veil: a navy and teal field, strongest at the upper right, with soft radial-mask
  edges, swell bands, faint signal traces, scanlines and grain. Each is credited "Generated
  graphic, not a photograph."
- **Visual direction.**
  - Night Desk (dark navy) is the default; light is opt-in through the toggle.
  - A turquoise accent with cyan and blue-gray support replaces the upstream red.
  - Headlines and the wordmark are set in Source Serif 4 at 700, with Inter for UI and IBM Plex
    Mono for labels.
  - Kickers are tracked mono labels behind a short signal rule, not filled boxes.
  - The home masthead is a serif nameplate with a remit line, not a giant spot-colour word.
- **Font loading fix (upstream theme bug).** Upstream `tokens.css` declared fallback font stacks on `:root` after the
  webfont declarations, so the webfonts never applied. The fallbacks now sit in `:where(:root)`.
- **Content.** There are three prototype briefs and one report. The briefs are layouts with
  labelled placeholders and make no claims about real events. The report's substance follows the
  project's published methodology.

See `INTEGRATION.md` for the recommendation on how this could connect to the production site.
