# Briefs No. 17 photograph cover: evidence (2026-10-12)

Owner decision: treatment B (authentic photograph, restrained navy-to-transparent
gradient), with G3 approved for editorial and news use. The ruling is in
`DECISION_LOG.md` (2026-10-12). Treatments A (plain photograph) and C were
reviewed and are kept here as comparison evidence only. Neither ships.

## Rights receipt

| Field | Value |
|---|---|
| Source page | https://www.dvidshub.net/image/9957254 |
| DVIDS title | US, Indonesia Co-chair Largest ASEAN Defense Ministers' Meeting (ADMM)-Plus Exercise in a Decade with the Participation of 2,200 Personnel from 19 Countries [Image 9 of 9] |
| DoD visual ID | 260921-A-XH946-9505 |
| Photographer | Sgt. 1st Class Timothy Hughes, 18th Theater Medical Command, U.S. Army |
| Licence | Public domain, as marked on the DVIDS page (read 12 October 2026), subject to https://www.dvidshub.net/about/copyright |
| Notice shown | The appearance of U.S. Department of War (DoW) visual information does not imply or constitute DoW endorsement. |
| G3 scope | Editorial and news publication by IPR, with credit, source link, recorded hash and notice. Use to market, advertise or promote IPR is a different use. It is not covered here and needs its own review. This approval does not say every commercial use is prohibited. |
| Date | Unresolved and stated as such: the DVIDS caption gives 21 September 2026; the DVIDS date-taken field gives 20 September 2026. No capture date is asserted. |
| Subjects | Identified only as BASARNAS personnel (truck lettering, uniform markings). No Chinese or Singaporean personnel are shown or implied. |

## Retrieval

- URL: `https://d1ldvf68ux039x.cloudfront.net/thumbs/photos/2609/9957254/2000w_q95.jpg`
  (the public 2000 px rendition). The 6386×4259 original requires a DVIDS
  sign-in and was not retrieved.
- 2026-10-13T02:44:06Z UTC, HTTP 200, 1,046,870 bytes,
  ETag `"332233605ad9c753fd2ad0e941afdd14"`, Last-Modified Wed, 23 Sep 2026 01:38:40 GMT.
- User agent: `IndoPacificRecord-editorial-review (+https://github.com/VSSpowerlifting/China-Mil-Watch)`.

## Asset hashes (sha256)

| File | Size | sha256 |
|---|---|---|
| `site/assets/editorial/trident-resolve-basarnas-drone.jpg` (retained bytes, unaltered) | 2000×1334 | `6e54dcd6a7e261d60359680ffc9a0fa8029399ae111421f79c7481c608a0b118` |
| `site/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg` | 1600×1067 | `9f7d4969b9aeb68c54e351217a16b3a72b0cde5c862c4db5adc8188159afd3e4` |
| `site/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp` | 1600×1067 | `eaa5e16b2ff6ea7c0ce0c7fc122d3097f720b00cdadb42e8df798c70c1c0025f` |
| `site/assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp` | 800×534 | `76d3359dd571940fd439f42b3c62eedb5c0bcaf2a6967b60bb7479cc2b524d24` |
| `site/assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg` (card, focal 58% 60%) | 720×480 | `ceba1db6c39235b90c1a1490ee6c65abaa8a8e2d5d58c74f5e87d5df98303789` |

The derivatives are untoned LANCZOS resizes built by `scripts/build_brief_cover.py`
(Pillow 11.3.0). `scripts/build_brief_cover.py --check` re-verifies them. The
gradient is CSS only and is never baked into a file. Records:
`site/assets/editorial/manifest.json` (entry `trident-resolve-basarnas-drone`,
granted only to Brief `trident-resolve-regional-scale-specific-chinese-tasks`)
and `site/assets/catalogue/admissions.json` (issue 17).

## Changed routes (fresh render compared with the base branch render)

- `analysis.html`: No. 17 catalogue card
- `briefs/trident-resolve-regional-scale-specific-chinese-tasks.html`: article hero
- `briefs.css`, `briefs-catalog.css`
- added: `assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg`, `assets/editorial/derivatives/…`

No other route differs. Tracked `output/` was not modified. An overlay of
tracked `output/` plus the fresh render passes `scripts/validate_output.py`
with 7 warnings, the same count as the base-branch overlay.

## Hardening (2026-10-13)

The standing policy is DECISION_LOG 2026-10-13, and the contract is
`docs/BRIEF_PHOTOGRAPHY_CONTRACT.md`.

- **Source notice.** `core/source_terms.py` lists the publishers whose terms
  require a notice. DVIDS is matched by host or by source label. Both gates
  (`core.brief_cover.problem` and `core.catalogue_media._check`) fail closed:
  `required-notice-missing` or `required-notice-altered`. This is independent
  of whether the two records agree. Commons and NASA records inherit no notice.
- **Two-surface pairing.** The manifest entry now declares
  `surfaces: ["article", "catalogue"]` and `depicts: "event"`. The card gate
  re-runs the cover gate, and the card must equal the manifest on alt,
  caption, creator, source label, date note and depicts. The article keeps the
  photograph only while its own card resolves to the same cover
  (`core.brief_photography`). Failures carry reason codes:
  - `source-not-cover-derivative`
  - `cover-claimed-twice`
  - `cover-names-another-brief`
  - `cover-conflict`

  A catalogue-only record never grants the article.
- **Card copy.** The caption and date note are shorter. Photographer, licence
  link, source link, the event/context disclaimer and the DVIDS notice are
  unchanged. The new date note reads "DVIDS dates: 21 September 2026
  (caption); 20 September 2026 (date-taken field)." It still asserts no
  capture date. The mobile card went from 906 to 888 px; the desktop card
  stayed at 869 px.
- **Tests.** `tests/test_brief_photography.py` has 23 tests, using generic
  fixtures plus a walk over every committed cover. The focused suites
  (`test_brief_photography`, `test_brief_cover`, `test_catalogue_media`,
  `test_article_media`) give 102 OK. The Briefs and frontend-contract suites
  give 715 OK, with 1 skipped.
- **Fail-closed probes on a real render.** I swapped the article's `-800.webp`
  for other bytes, then, separately, the card's JPEG. Both times:
  - the article opened on its Editorial plate (`data-article-media="plate"`);
  - `analysis.html` showed no No. 17 photograph;
  - no No. 17 image files were emitted;
  - Nos. 8 and 9 stayed photographs.

  I restored the files after each probe, and both builders' `--check` pass.
  The unit tests cover the remaining failures: retained source,
  `-1600.jpg`, `-1600.webp`, attribution, notice and identity.
- **Route parity.** Against the pre-hardening render of bb8091cc41, only the
  No. 17 caption and date text differ, on `analysis.html` and the No. 17
  article. Asset hashes are unchanged. The overlay validator passes with 7
  warnings.

## Screenshots

`shots/B-{card,lead,article}-{1280,375}.png` show treatment B as shipped
after hardening. `shots/B-{card,article}-forced-{1280,375}.png` show forced
colours. They were captured with Playwright in Chromium with reduced motion,
using `tools/hard_shots.py`; the machine-readable results are in
`shots/qa-report.json`. Checks at 1280 and 375:

- no console errors;
- no broken images;
- no horizontal overflow;
- the hero loads `-800.webp`;
- the gradient is a CSS `::after` on `.brief-cover-frame`, removed under
  forced colours and print;
- each card link (headline, licence, source) takes visible keyboard focus;
- the DVIDS notice is visible on the card, not hover-only;
- in print emulation the article figure, credit and notice remain, and so do
  the card credit and notice.

`tools/cover_shots_b.py` is the original selection-time capture script.

`comparison/sheet-*.jpg` set A, B and C side by side, as shown to the owner
before the decision. Their captions carry the earlier date wording, which the
decision superseded. They are kept as comparison evidence only.
