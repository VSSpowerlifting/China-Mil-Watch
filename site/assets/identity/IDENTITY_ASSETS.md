# Identity assets — Indo-Pacific Record

One file in this directory is canonical. Every other file is derived from it by
`scripts/build_identity_assets.py`, which refuses to run if the canonical
digest has changed.

## Inventory

| File | Role | Dimensions | Bytes | SHA-256 |
|---|---|---|---|---|
| `ipr-compass-logo.png` | **CANONICAL** | 500 × 500 | 36,796 | `7e3f3b606c5d7dcb0bda82d84f888ce2afd903b8229a621b72d66e670645762f` |
| `ipr-compass-mark-small.svg` | derivative | vector (32 × 32 viewBox) | 955 | `6cb7a57686e691dd96fed3ad7e9b426a37cc7ae735bfddb07988c0a337a070bb` |
| `ipr-compass-icon-16.png` | derivative | 16 × 16 | 728 | `76cf4a12c8c91a0121f475ee6b65dc36a1d33446527a89e523706778ab2e079c` |
| `ipr-compass-icon-32.png` | derivative | 32 × 32 | 1,851 | `365a5ecb2b43637eebdc427b4b9f750fe7f4280775f2bf08f31ab450091cdbd7` |
| `ipr-compass-masthead-112.png` | derivative | 112 × 112 | 10,924 | `e5b1d4142c701454bf6835c8f3ab32ea7c8a7b9f8e798af7f6bc0e21cf5cb779` |
| `ipr-compass-touch-180.png` | derivative | 180 × 180 | 21,352 | `6c497b1e1dd738805528060a1bb603805f7dd3e00c0f533cff0ce633282df08b` |
| `ipr-social-card-1200x630.png` | derivative | 1200 × 630 | 59,371 | `ce570069851b03b2fb3a2bcee83e8aa73d6c7889106da92ba9d8a6694c4aba22` |

## The canonical mark

`ipr-compass-logo.png` is owner-supplied artwork: PNG, 500 × 500, 8-bit RGB,
no alpha channel. It is preserved byte-for-byte and is **not** redrawn,
recoloured, cropped, stretched, or replaced anywhere in the site. Its digest is
pinned in three places — the builder, `tests/test_identity_assets.py`, and this
table — so replacing it has to be deliberate in all three.

## Why there are two marks

The 2026-09-04 audit measured the canonical artwork's geometry in **source
pixels**: two outer ring strokes of 4 px each, separated by an 11 px gap, with
4 px diagonal ticks, in a 500 × 500 image.

Three units are involved, and keeping them apart matters. A feature *w* source
pixels wide, drawn into a box *s* CSS pixels across, covers `w × s / 500` **CSS
pixels at 1×**, and `w × s / 500 × DPR` **physical device pixels** on a display
with that device-pixel ratio.

| Rendered box | Ring stroke @1× | Ring stroke @2× | Ring gap @1× | Ring gap @2× |
|---|---|---|---|---|
| 16 CSS px | 0.13 | 0.26 | 0.35 | 0.70 |
| 24 CSS px | 0.19 | 0.38 | 0.53 | 1.06 |
| 32 CSS px | 0.26 | 0.51 | 0.70 | 1.41 |
| 48 CSS px | 0.38 | 0.77 | 1.06 | 2.11 |
| 56 CSS px | 0.45 | 0.90 | 1.23 | 2.46 |
| 64 CSS px | 0.51 | 1.02 | 1.41 | 2.82 |
| 96 CSS px | 0.77 | 1.54 | 2.11 | 4.22 |

(Figures are physical device pixels; the @1× column is also the CSS-pixel
coverage.)

A stroke needs about one physical pixel to exist and about 1.5 to read cleanly.
At 1× the ring strokes reach 1.0 only at a 125 CSS px box; the gap between the
two rings reaches it at 45. **The 48 px floor was set by looking at renders,
not by arithmetic** — the arithmetic explains why the renders look the way they
do. Below roughly 48 CSS px the rings merge into a grey halo, the ticks
disappear, and the mark stops reading as a compass.

So the canonical mark has a floor, and `ipr-compass-mark-small.svg` covers what
is below it. The small mark is the same compass with the features that survive
a downscale: one ring, eight points drawn as filled shapes rather than
outlines, no diagonal ticks, no inner facets. It uses the canonical file's own
palette — `#4DAD99` to `#255E7A`, white rose, `#CBEAE5` secondary points —
sampled from the artwork rather than retyped.

**The small mark is a derivative, not a replacement.** It never overwrites the
canonical source and is never presented as the brand mark at display size.

## Size rules

| Context | Asset | Size |
|---|---|---|
| Masthead, desktop | canonical (via `masthead-mark.png`) | 56 CSS px |
| Masthead, compact | canonical (via `masthead-mark.png`) | 48 CSS px |
| Apple touch icon | canonical (via `apple-touch-icon.png`) | 180 px |
| Social card | canonical, 180 px inside 1200 × 630 | — |
| Favicon (SVG) | small mark | scales |
| Favicon (PNG) | small mark | 16 / 32 px |

48 CSS px is the floor for the canonical mark — a CSS-pixel floor, independent
of the viewer's device-pixel ratio — enforced by
`test_the_mark_is_never_rendered_below_its_measured_floor`.

## Output routes

The record renderer copies these into the build root under names that describe
their job rather than their provenance. `mark.svg` keeps the name it has always
had because 3,950 published pages already reference it.

## Regenerating

```bash
.venv/bin/python scripts/build_identity_assets.py           # rebuild
.venv/bin/python scripts/build_identity_assets.py --check   # verify, write nothing
```

Two kinds of derivative, verified two different ways.

The vector mark and the PNG icons are computed from geometry and are
**byte-reproducible** on any platform. `--check` regenerates them and compares
bytes.

The social card is rendered through Playwright from HTML and CSS — the same
mechanism `scripts/generate_pla_watch_cover.py` uses for edition covers — so
its bytes depend on the platform's font rasterisation and re-rendering it
elsewhere can legitimately **differ**. It is therefore **pinned by its recorded
digest** rather than regenerated: `--check` verifies the committed file against
`SOCIAL_SHA256`, its 1200 × 630 geometry, and the 300 KB budget. Replacing it
is a deliberate act that updates the digest here and in the builder — any other
1200 × 630 PNG under budget will fail the check.

The palette constants are pinned samples rather than live reads, with the
canonical pixel each came from recorded beside it;
`tests/test_identity_asset_builder.py` re-reads the artwork and fails if one
stops matching.

## What is *not* here

`logo-icon.png`, `logo-wordmark.png`, `og-image.png` and `favicon.svg` in
`output/` belong to the retired China Mil Watch identity and to the legacy
rollback renderer (`site/generator.py`). They are still carried forward by
`site/render.py` because published pages that have not yet been re-rendered
still reference them. They are not current identity assets and must not be
referenced by current chrome. Removing them from `CARRIED_FORWARD` belongs to
the post-merge regeneration task, after the weekly pages are re-rendered.
