# T2 — Edition Plate v1: build spec

Status: specified, not built. Supersedes the summary stub at
[ROADMAP.md §T2](ROADMAP.md). Normative design source: V&M §3.2.

## 1. What this closes

The 2026-07-11 ruling demoted photo-overlay cover PNGs to og:image duty "in
favor of generated SVG Edition Plates (ROADMAP T2)". Commit `36510bb`
(2026-07-17) executed the removal half — `issue-cover-thumb` off the index
card, thumbs off archive entries — but the replacement was never built. Three
editions (2026-06-27, 07-04, 07-11) were carried by Signal Veil imagery from
`site/assets/editorial/manifest.json`; curation stopped after No. 10, so
Nos. 11–13 render text-led with nothing in the identity slot.

T2 restores per-edition visual identity without weekly manual artwork. Cover
PNGs stay on disk and stay as og:image. Signal Veil is unaffected — it is
curated photography for editions that earn it; the plate is the deterministic
floor that always renders.

## 2. Data contract

Everything comes from the edition sidecar. Verified across all 13 published
editions (`output/the-pla-watch/posts/*.json`):

| field | range observed | notes |
|---|---|---|
| `issue_number` | 1–13 | present on all; design for 3 digits |
| `week_ending` | — | present on all |
| `edition_label` | `Pilot edition`, `Significant`, `Routine`, `significant` | **casing is inconsistent** — see F2 |
| `n_articles` | 30–154 | not drawn on the plate; aria only |
| `source_trail` length | **3–16** | tick count; not fixed at 13 — see G3 |
| trail `is_significant` count | **0–13** | 0 → no crimson ticks; 13/13 on No. 12 |
| distinct trail sources | 1–3 | not drawn in v1 |
| `first_cjk(term)` | 2 glyphs, all 13 | motif; contract returns `''` when absent |

The V&M spec's "renders for all 9 editions" is stale — the acceptance set is
**13 editions** as of 2026-08-08, and the ticket must re-run against whatever
is published at build time.

## 3. Shared context — parity is the main build risk

`scripts/generate_pla_watch.py` and `scripts/rerender_pla_watch.py` build post
context independently (`_build_context` vs `_build_post_context`). Any plate
logic written twice will drift.

Add exactly one function to `scripts/pw_env.py`:

```python
def edition_plate(sidecar: dict, variant: str = "list") -> dict:
    """Deterministic Edition Plate context. Pure function of the sidecar —
    no disk reads, no clock, no manifest. Returns {} only if issue_number
    and week_ending are both missing (plate does not render)."""
```

Returns: `issue_number`, `week_ending_display` (via `format_date`),
`badge` (`{label, kind}` or `None`), `ticks` (list of bools, trail order),
`n_flagged`, `motif` (str, may be `''`), `aria_label`, `variant`.

Both renderers call it. The Jinja macro receives only this dict — it must not
reach into the sidecar itself.

## 4. Variants

| variant | aspect | placement | ticks |
|---|---|---|---|
| `list` | 16:9 | PW index latest-edition card | see D1 |
| `archive` | 16:9 | PW archive entry, `entry-date-col` slot | yes |
| `hero` | 21:9 | PW post hero, compact | see D1 |
| `mini` | 4:3 | homepage `pw-band` | no (band has its own `pw-ticks` run-of-serial strip — different meaning, do not merge) |

The homepage `.pw-ticks` strip is one tick *per edition*. The plate's tick row
is one tick *per source record*. They must not be visually confused; in `mini`
the plate carries no tick row.

## 5. Structure

Deterministic inline SVG, `viewBox="0 0 640 360"` for 16:9 (`list`,
`archive`); 21:9 → `0 0 640 274`; 4:3 → `0 0 480 360`. All text sized in
viewBox units so proportions hold at any render size.

Z-order, back to front:

1. **Field** — `#0E1520` rect, full bleed.
2. **Motif** — `motif` glyphs, serif, opacity ≤ 0.06, anchored bottom-right,
   overflowing the right edge (clipped by the viewBox). Omitted when `motif`
   is `''`.
3. **Top rule** — 4px crimson (`--signal-bright` equivalent, hard-coded hex in
   SVG since the plate may be reused outside the Night Desk cascade).
4. **Numeral** — `issue_number`, serif, tabular figures, oversized, anchored
   left. `No.` label in mono caps above it at muted color.
5. **Date** — mono, week-ending display string, under the numeral.
6. **Tick row** — one tick per `ticks` entry. Crimson + full height when
   flagged, `#3A4556` + 2/3 height otherwise. Geometry per G3.
7. **Badge** — top-right, `badge.kind` drives fill; omitted when `badge` is
   `None`.

No photography, no gradients, no filters, no embedded fonts (inherit the page
stack via `font-family` on the `<svg>`).

## 6. Fallbacks (F)

- **F1 — no `motif`.** Omit layer 2 entirely. Do not substitute a glyph, a
  latin letter, or a shape. Existing `first_cjk` contract already returns
  `''`; the macro must not paper over it.
- **F2 — label casing.** `edition_label` arrives as both `Significant` and
  `significant` (No. 2). Normalize **in `edition_plate()`** —
  `kind = label.strip().lower()`, then map to a known set
  (`pilot` / `significant` / `routine`); unknown → render the label text with
  neutral styling, never drop to a wrong color. **Do not edit sidecars to fix
  casing** — sidecars are canonical.
- **F3 — empty `source_trail`.** Omit the tick row; plate still renders.
- **F4 — missing `edition_label`.** No badge. Plate still renders.
- **F5 — missing `issue_number` or `week_ending`.** Render whichever exists;
  both missing → `edition_plate()` returns `{}` and the caller renders the
  current text-led layout unchanged.

## 7. Geometry rules (G)

- **G3 — adaptive tick row.** Trail length is 3–16, not a constant. Fix the
  row's total width and derive pitch from it: `pitch = row_w / max(n, 8)`,
  tick width `min(4, pitch * 0.4)`, left-anchored. A 3-tick row must not
  stretch to full width (reads as a bar chart); an 8-tick floor keeps short
  trails honest-looking.
- **G4 — all-flagged rows.** No. 12 is 13/13 flagged: a fully crimson row.
  Keep it. It is accurate, and capping or de-saturating it would understate a
  real week. Confirm visually at `archive` size before regeneration.

## 8. Accessibility

`role="img"` on the `<svg>`, plus `<title>` and `<desc>`. `aria_label` is
built in `edition_plate()`, format:

> Edition No. 13, week ending 8 August 2026, 13 source records, 11 model-flagged.

Every value drawn on the plate also exists as adjacent HTML text on all four
surfaces — the plate is never the only carrier of a fact.

## 9. Motion

Static in `list`, `archive`, `mini`. In `hero` only, the tick row may bar-fill
on reveal via the existing `[data-reveal]` observer. Nothing infinite. Per the
2026-07-12 first-paint rule, the plate sits in an above-fold identity block on
index and post hero, so it must render statically — `data-reveal="art"` at
most, never a container that starts at opacity 0.

## 10. Files

- `site/templates/_edition_plate.html` — new; macro `plate(ctx)`.
- `scripts/pw_env.py` — add `edition_plate()`; register the macro namespace on
  `make_pw_env()`.
- `site/templates/pla-watch-index.html` — latest-edition card; replaces
  nothing visually except per D1.
- `site/templates/pla-watch-archive.html` — `entry-date-col`, at the reserved
  comment (line ~164, "the Edition Plate (ROADMAP T2) takes this slot").
- `site/templates/pla-watch-post.html` — hero, compact variant.
- `site/templates/index.html` — `pw-band`, mini variant.
- `scripts/generate_pla_watch.py`, `scripts/rerender_pla_watch.py` — pass
  context through; no logic.
- Re-render, then commit output.

## 11. Acceptance

1. Same sidecar in → byte-identical SVG out, across repeated builds **and**
   across the generate and rerender paths (diff both outputs).
2. Renders for all 13 published editions, including No. 2's lowercase label
   and any zero-flag edition (Nos. 1–3).
3. All fallbacks F1–F5 exercised — add fixtures to
   `tests/test_editorial_regression.py` rather than relying on live sidecars.
4. `scripts/validate_output.py` green at the existing historical warning
   count, no new warnings.
5. Archive page weight drops (SVG replaces the PNG thumb slot). Record
   before/after — this is the measurable half of T4's image budget.
6. og:image on post pages still points at `covers/<date>.png`, unchanged.
7. No horizontal scroll and no rendered text under 11px at 375px width.

## 12. Prohibited

Raster generation for in-page use. Invented themes, glyphs, or counts.
Per-edition hand-tuning in the template. Editing sidecars to simplify the
macro. Reading the editorial manifest from plate code — the plate is
photography-independent by design.

## 13. Decisions needed before build

- **D1 — tick-row collision.** `.nd-tickrow` already renders as HTML on the
  index card and post hero ([pla-watch-index.html:484](../site/templates/pla-watch-index.html),
  [pla-watch-base.html:501](../site/templates/pla-watch-base.html)). If the
  plate lands there with its own ticks, the same 13 records draw twice.
  **Recommendation:** the plate owns the tick *marks* on every surface it
  appears; delete the HTML `.nd-tickrow i` bars where a plate is adjacent, and
  keep `.nd-tickrow-label` as HTML — it carries the honest caption ("Source
  trail · 13 records · 11 model-flagged · part of the monitored weekly
  record") and the accessible text. One tick implementation, caption intact.
- **D2 — Signal Veil coexistence.** On the index card the veil is a
  background layer at 58% width, right-anchored; the plate would occupy the
  same corner. **Recommendation:** veil wins when present (curated photography
  outranks the generated floor), plate renders in the archive slot only for
  that edition. Alternative — plate always, veil retired on the index card —
  is a larger call and should be made deliberately, not as a side effect.
- **D3 — backfill.** Whether to resume veil curation for Nos. 11–13 after T2
  lands, or let the plate stand as the permanent identity for editions without
  curated imagery.
