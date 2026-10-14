# Coastal visual identity — owner review evidence

Base: `216dfbb8babc6a0d4d711494c7787a29f84e201e`, exact latest origin/main
at branch creation. #561 merged 14 October 2026 at 13:53:38 UTC. Source-only
migration; no publication output, canonical manuscript, approval, admission,
collector or database change. Laos's v2 manifest is still draft/private-only.

## Active colour inventory

| Previous paint | Active consumers / meaning | Replacement | Contrast / exception |
|---|---|---|---|
| `--crimson`, `--crimson-ink` | shared analysis labels, trail tags/panels, record custody, Brief signal and v2 finding | `--editorial-ink` #23665B; solid rules | 5.32–6.47 on light grounds |
| `--crimson-tint`, `--crimson-rule` | analysis source-trail tag | sea glass via `--editorial-tint`; ink via `--editorial-rule` | tag text 5.64; border >3 |
| `--crimson-text`, `--crimson-mark` | unused lifted legacy declarations | removed; `--editorial-on-dark` #92D5CC | 8.54 on navy |
| crimson edge in `relief.css`, `home.css` | navy human analysis plane | `--editorial-on-dark` | decorative edge, not a status |
| `--signal`, `--signal-tint`, `--signal-rule` | machine evidence labels, processing state, record interpretation/custody | `--machine-ink` #446C79, `--machine-tint` #E7EEF0, `--machine-rule` | 4.53 minimum on light grounds; dotted label rule, square custody marker |
| `--signal-band`, home `#e6ad91` fallback | machine indicator on navy selected record | `--machine-on-dark` #AACFD0 | 8.49 on navy; fallback removed |
| `_plate.html` #B3132B / #D4845F | human editorial edge / tall model-flagged ticks | shared `--editorial-on-dark` / `--machine-on-dark` | existing tall/short tick shape and SVG accessible name retained |
| `--visited` #4A4470 | visited source/citation links on light | #365F68 | 5.55 minimum on light grounds |
| warning #87511A / #D9BE9C / map #93621D | warnings, blocked status and its border | preserved | semantic amber exception; existing words/glyphs persist |

Source evidence retains neutral ink. Active semantic paint is in
`site/preview/{styles,briefs,home,record,relief}.css` and
`site/preview/templates/_plate.html`. Catalogue/reading components share these
rules; already-coastal `briefs-catalog.css` and historical article inline CSS
need no override. Gallery labels track the new names. The edition-plate UI key
now describes tall marks without naming their colour; no manuscript or homepage
copy changed. All retired semantic variable names are removed, without aliases.

## Intentional exceptions and exclusions

- Amber/brown warning paint above is semantic attention, distinct from success.
- Warm tan and low-saturation paper/rule neutrals remain material colours.
- Full-colour national flags, original photographs, admitted media, archival
  evidence and source text retain their colours. The guard inspects first-party
  CSS and inline paint, not image pixels or manuscript words.
- `site/templates/` is the preserved rollback renderer. Its historical palette
  is excluded; current historical article rendering uses the IPR preview shell.
- No decorative/editorial red-family exception remains in active first-party UI.

## Contrast matrix

Ratios use WCAG relative luminance. Normal text requires 4.5; essential markers
and keyboard focus require 3. Pale semantic tones are scoped to dark surfaces.
#456D7A was tuned to #446C79 because its inset contrast was only 4.46.

| Text / indicator | Ivory | Raised paper | Inset paper | Sea glass | Navy |
|---|---:|---:|---:|---:|---:|
| `--editorial-ink` | 6.00 | 6.47 | 5.32 | 5.64 | 2.11 |
| `--machine-ink` | 5.11 | 5.51 | 4.53 | 4.80 | 2.48 |
| `--visited` | 6.25 | 6.75 | 5.55 | 5.89 | 2.03 |
| `--link` | 5.51 | 5.95 | 4.89 | 5.19 | 2.30 |
| `--accent-ink` | 7.72 | 8.33 | 6.85 | 7.27 | 1.64 |
| `--warning` | 5.81 | 6.27 | 5.16 | 5.47 | 2.18 |
| `--positive` | 6.27 | 6.76 | 5.56 | 5.90 | 2.02 |
| `--focus` | 5.51 | 5.95 | 4.89 | 5.19 | 2.30 |
| `--editorial-on-dark` | 1.48 (dark only) | 1.60 (dark only) | 1.32 (dark only) | 1.40 (dark only) | 8.54 |
| `--machine-on-dark` | 1.49 (dark only) | 1.61 (dark only) | 1.32 (dark only) | 1.40 (dark only) | 8.49 |
| `--focus-band` | 1.48 (dark only) | 1.60 (dark only) | 1.32 (dark only) | 1.40 (dark only) | 8.54 |

## Comparison index

| Route / component | 375px before → after | 768px before → after | 1280px before → after |
|---|---|---|---|
| home | [Before](shots/before-home-375.jpg) · [After](shots/after-home-375.jpg) | [Before](shots/before-home-768.jpg) · [After](shots/after-home-768.jpg) | [Before](shots/before-home-1280.jpg) · [After](shots/after-home-1280.jpg) |
| analysis | [Before](shots/before-analysis-375.jpg) · [After](shots/after-analysis-375.jpg) | [Before](shots/before-analysis-768.jpg) · [After](shots/after-analysis-768.jpg) | [Before](shots/before-analysis-1280.jpg) · [After](shots/after-analysis-1280.jpg) |
| laos | [Before](shots/before-laos-375.jpg) · [After](shots/after-laos-375.jpg) | [Before](shots/before-laos-768.jpg) · [After](shots/after-laos-768.jpg) | [Before](shots/before-laos-1280.jpg) · [After](shots/after-laos-1280.jpg) |
| historical | [Before](shots/before-historical-375.jpg) · [After](shots/after-historical-375.jpg) | [Before](shots/before-historical-768.jpg) · [After](shots/after-historical-768.jpg) | [Before](shots/before-historical-1280.jpg) · [After](shots/after-historical-1280.jpg) |
| native | [Before](shots/before-native-375.jpg) · [After](shots/after-native-375.jpg) | [Before](shots/before-native-768.jpg) · [After](shots/after-native-768.jpg) | [Before](shots/before-native-1280.jpg) · [After](shots/after-native-1280.jpg) |
| record | [Before](shots/before-record-375.jpg) · [After](shots/after-record-375.jpg) | [Before](shots/before-record-768.jpg) · [After](shots/after-record-768.jpg) | [Before](shots/before-record-1280.jpg) · [After](shots/after-record-1280.jpg) |
| laos-v2-private | [Before](shots/before-laos-v2-private-375.jpg) · [After](shots/after-laos-v2-private-375.jpg) | [Before](shots/before-laos-v2-private-768.jpg) · [After](shots/after-laos-v2-private-768.jpg) | [Before](shots/before-laos-v2-private-1280.jpg) · [After](shots/after-laos-v2-private-1280.jpg) |
| evidence-fixture | [Before](shots/before-evidence-fixture-375.jpg) · [After](shots/after-evidence-fixture-375.jpg) | [Before](shots/before-evidence-fixture-768.jpg) · [After](shots/after-evidence-fixture-768.jpg) | [Before](shots/before-evidence-fixture-1280.jpg) · [After](shots/after-evidence-fixture-1280.jpg) |

[Desktop comparisons](shots/comparison-1280-0.jpg) ·
[Mobile comparisons](shots/comparison-375-0.jpg) ·
[Article comparisons](shots/comparison-1280-1.jpg) ·
[Private v2 comparisons](shots/comparison-1280-2.jpg).
[Dark keyboard focus, mobile](shots/after-home-dark-focus-375.webp) ·
[Dark keyboard focus, desktop](shots/after-home-dark-focus-1280.webp) ·
[Final homepage editorial cue](shots/after-home-editorial-1280.webp) ·
[Native Signal](shots/after-native-signal-375.webp) ·
[Private v2 finding](shots/after-v2-finding-1280.webp) ·
[Custody markers](shots/after-record-custody-1280.webp).
[Print sample](shots/after-native-1280-print.webp) ·
[Forced-colors sample](shots/after-record-1280-forced.webp).
Every normal route also has `after-<route>-<width>-focus/print/forced.webp`
companions at 375 and 1280. Record custody remains hidden in the existing
compact layout; its shape close-up is desktop only.


Public Laos uses its unchanged fallback. `laos-v2-private` uses the existing
draft presentation in an isolated review destination; `evidence-fixture` uses
existing exact-excerpt fixtures and is neither approved nor public. Captures
use Chromium, real local font files and assets, 375/768/1280 widths, 900px viewport,
reduced motion, the intro's existing session skip, and eager loading for complete
screenshot imagery. Full captures are JPEG (long mobile pages exceed WebP's size
limit); supplemental focus/print/forced-colors captures are lossless PNG/WebP.

## Verification

- Focused integration: **110 tests passed**, covering palette, real Chromium
  roles, v2 presentation/fidelity, historical shells, frontend contracts and relief.
  After the final dark-surface correction, print-marker remap and RGB/HSL guard expansion,
  **27 palette/accessibility tests passed** again.
- Actual routes: **48 captures**; HTTP 200, loaded fonts/images, no overflow.
  **24 before/after comparisons** preserve text, links, image attributes and
  measured main/header/title/nav/image geometry exactly. Receipts contain
  SHA-256 values rather than duplicated manuscript text.
- **64 migrated text consumers** measured against actual inherited/composited
  rendered backgrounds: no contrast failures. The token matrix additionally
  checks inset/tinted surfaces and visited/hover/focus/warning/positive colours.
- Lead and read-only QA helper inspected contact sheets and close component
  crops. One missed dark homepage cue was corrected centrally and recaptured;
  its regression test checks the rule's ≥3:1 contrast. Labels, shape distinctions,
  grayscale-compatible hierarchy, restrained accents and existing imagery remain.
  Scoped Refactoring UI diagnostics: 8/8 (10/10); this is visual judgment, not
  a full accessibility certification or editorial approval.
- Focus is visible on paper and navy at 375/1280; print and forced-colors samples
  retain labels and readable text. These are targeted browser checks and visual
  samples, not a claim that every interaction or print pagination was audited.
  Print remaps semantic label markers to black and applies white grounds to
  homepage/Brief heroes with legible, non-transitioning button text (the earlier dark print ground
  is visible in `shots/before-home-1280-print.webp`). Final media captures were refreshed
  with `capture.refresh_modes()` after this print-only refinement. Normal before/after
  paint and geometry are unchanged by a print media rule.
- Tracked-output and isolated-overlay validators both **pass with ten governed
  warnings**. The overlay carries existing canonical historical records/assets
  and exports in /tmp for the full validator; no warning is suppressed.
- Protected-file diff is empty for `output/`, `pla_watch.db`, `briefs/`, source
  records, admissions, desk/shadow state and workflows. No public output change,
  merge, deployment or public-site verification is claimed.

The full local run is **not green**: 6,254 tests in 2,215 seconds, one failure,
22 errors and one skip. Twenty-one errors are `tests.test_evidence_store.StoreTests`
setup refusing the macOS temporary storage root (`unsafe_store_root`). The exact
main export at `216dfbb8babc6a0d4d711494c7787a29f84e201e` reproduces all 21 errors
with the same interpreter/environment (44 targeted baseline tests, 21 errors).

The other findings are homepage-intro timing tests: first-visit overlay attachment
timeout, and lost WebGL context ending by the timeline. Both pass in the targeted
main run. The intro implementation and its tests are byte-unchanged; palette
changes do not amend the intro. These broader-run findings remain recorded,
not converted to a green full-suite claim by an isolated pass. CI on the final
PR head remains the engineering gate; no unrelated intro/store repair is included.

Candidate intro-only characterization: **23 tests passed** in isolation. This
does not override the broader-run failures above; CI is still pending.

[Full local summary](verification.json) records counts and exact baseline identity.
The source-only PR is ready for owner visual review, with full-suite limitations
and pending CI disclosed.

## Reproduction

Use the project Python (`.venv/bin/python` in the primary checkout). This
worktree has no venv; verification reused `/Users/benjaminyang/pla-watch/.venv/bin/python`.
Its missing existing `python-docx` requirement was installed into an isolated
`/tmp/ipr-coastal-python-deps` target; no application dependency was added.
The run used `TMPDIR=/tmp` and `PYTHONPATH=/tmp/ipr-coastal-python-deps:.`.
The macOS storage-root failures persist under that configuration; no guard was
bypassed or weakened.

1. At the base commit, render with `site/render.py --out /tmp/ipr-coastal-before`.
   Run `render_isolated_history.py /tmp/ipr-coastal-before` to render unchanged
   historical contexts and carry existing assets/exports without replacing fresh
   assets. The same command uses `after` for the candidate.
2. Render private v2 with `site/render.py --out /tmp/ipr-coastal-before-review
   --review-presentation briefs/presentation/what-is-being-built-in-laos.json`.
   Render the existing evidence fixture with
   `docs/evidence/briefs-editorial-v2/render_fixture.py --out
   /tmp/ipr-coastal-before-fixture --style-base /ipr-coastal-before-review`.
3. Repeat on the candidate using `after` in the destinations, then run
   `capture.py` and `rendered_contrast.py`. They serve only the private /tmp
   renders on localhost; no external collection is performed.
4. Run `python -m unittest tests.test_coastal_palette
   tests.test_palette_and_accessibility tests.test_brief_presentation
   tests.test_brief_presentation_integration tests.test_frontend_production
   tests.test_relief_primitives tests.test_historical_brief_shell`, followed by
   `python -m unittest discover -s tests -t .` and
   `python scripts/validate_output.py`. Do not regenerate tracked output.
