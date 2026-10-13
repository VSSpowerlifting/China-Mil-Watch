# Brief Photography Contract

Standing policy (DECISION_LOG 2026-10-13): photography first, a restrained
editorial gradient, full provenance, and one photographic identity across the
catalogue card and the opened article. This contract says what a Brief cover
must carry and how the code enforces it. It applies to native Briefs from
No. 17 on. It changes nothing for Briefs whose imagery is held by an existing
ruling (Nos. 1, 10, 12 and 15) or for the catalogue admissions of Nos. 8 and 9.

A cover is not a Signal Veil. Veils are abstract editorial artwork. A cover
is a verified photograph of a real scene. Neither can stand in for the other,
and duotone, transparency, a gradient or a veil never stands in for image
rights.

## What a cover must carry

| Requirement | Where it lives | Enforced by |
|---|---|---|
| Canonical source identity: source page (https), source label, publisher ID where one exists, retrieval URL, ETag/size/time | manifest entry (`source_page`, `source_label`, `original_url`, `retrieval`, e.g. `dod_id`) | `core.brief_cover.problem` (page, label, https); evidence README |
| Verified licence, creator and receipt | `license`, `license_url`, `license_basis`, `creator`, `credit`; receipt in `docs/evidence/<cover>/` | licence allow-list (public domain, CC BY with link) on both gates |
| Owner use approval | DECISION_LOG entry naming the image and its scope | review. The code never infers it |
| Event or context | `depicts`: `"event"` (the photograph shows what the Brief covers) or `"context"` (it shows something related) | both gates. It must be one of the two and the same on both records |
| Caption and alt limited to what the source states | `caption`, `alt`, `date_note` (state source date conflicts; never assert one) | both gates require them; the card must equal the manifest |
| Explicit surface grants | `surfaces`: `["article"]` or `["article", "catalogue"]`; `match.briefs`: exactly one slug | `surfaces-invalid`, `cover-conflict`, `cover-names-another-brief` |
| One image on both surfaces | the catalogue record's `source_manifest_id` is the cover's `id` | `pair-card-shows-another-image`, `cover-claimed-twice` |
| Separate responsive crops | article: `-1600.jpg`, `-800.webp`, `-1600.webp` (`scripts/build_brief_cover.py`); card: 720×480 cut from `-1600.jpg` around `focal` (`scripts/build_catalogue_media.py`) | `source-not-cover-derivative` |
| Deterministic assets and hashes | retained source `sha256`, each derivative `sha256`, card `source_sha256` and `served_sha256`, `built_with` | `--check` on both builders; hash checks on both gates |
| Source notices | `notice`, word for word, where `core.source_terms.REQUIRED_NOTICES` lists the publisher | `required-notice-missing`, `required-notice-altered` on both gates |
| Treatment and attribution | `cover_treatment` (`gradient` by default, `photograph` where the gradient hurts legibility or fidelity); the change note follows the treatment. The gradient is CSS only and is never baked into a file | `unknown-treatment`, `change-note-not-treatment`, `manifest-changed:*` |

## Fail-closed behaviour

- Each surface runs its own gate. The article runs `core.brief_cover`, and the
  card runs `core.catalogue_media`.
- A paired cover also runs a shared check (`core.brief_photography`). The card
  gate re-runs the whole cover gate, including the article's WebP files. The
  article keeps the photograph only while its own card resolves to a
  photograph from the same cover.
- So a changed or missing retained source, article derivative or card crop
  takes the photograph off both surfaces. So does a mismatched credit,
  creator, caption, licence, source, notice or classification, a held card,
  or a second claim on the image.
- On failure the article opens on its Editorial plate and the card shows its
  plate, with a reason code (`cm.audit_rows`). Nothing generates, re-encodes
  or substitutes a photograph at build time.
- A catalogue-only approval never grants the article. The article grant is the
  cover's `match.briefs`, and a card record cannot supply one. A card from an
  ordinary manifest entry (as for Nos. 8 and 9) stays a card only.
- An article-only cover (`["article"]`) needs no card and is not affected by
  one. A card record that tries to show it is refused.
- Using the same image on the two surfaces is the rule. A different card image
  needs a recorded owner exception in DECISION_LOG and a separate,
  non-cover manifest entry.

## Admitting No. 18 and later Briefs

No code or test changes are needed. Tests use generic fixtures, and the
committed-record test walks every cover in the manifest.

1. **Select by hand.** Pick one photograph from a primary publisher's own page.
   Read the publisher's terms. Do not bulk-admit. Existing 81.cn Signal Veils,
   Joint Staff material, restricted MINDEF images and historical held
   photographs each need their own decision.
2. **Record the receipt.** Create `docs/evidence/brief-cover-noNN-<date>/` with
   the source page, licence as marked, creator, publisher ID, retrieval
   (URL, time, HTTP status, size, ETag, user agent), and any terms read. Never
   sign in, defeat an access challenge or impersonate a browser.
3. **Add the publisher's notice if it has one.** If its terms require a
   notice and it is not yet in `core/source_terms.py`, add one entry with the
   exact text and a comment citing the terms page and read date. Never infer a
   notice from licence or government authorship.
4. **Get the owner's approval.** Record it in DECISION_LOG: image, scope of
   use, treatment, event or context, and any date or identification limits.
5. **Write the manifest entry.** Retain the retrieved bytes unaltered in
   `site/assets/editorial/`. Add the entry with every field above,
   `derivative_builder: "scripts/build_brief_cover.py"`, `match.briefs: [<slug>]`
   and `surfaces`. Then run `scripts/build_brief_cover.py --write`, then `--check`.
6. **Add the card if the cover is paired.** Add the admission to
   `site/assets/catalogue/admissions.json`, copying the manifest fields
   exactly, with `source_file` set to the cover's `-1600.jpg` and a `focal`
   chosen for the 3:2 crop. Then run `scripts/build_catalogue_media.py --write`,
   then `--check`.
7. **Verify.** Run `tests.test_brief_photography`, `tests.test_brief_cover`,
   `tests.test_catalogue_media` and `tests.test_article_media`, then a fresh
   render with a route diff and the validator. The `PHOTO_ISSUES` and
   `SOURCE_HOSTS` sets in `tests/test_catalogue_media.py` list the admitted
   cards on purpose. Adding a card means adding its issue there, as a reviewed
   change.

## Out of scope

- No crawler, image search or collection infrastructure.
- No licence inference.
- No AI imagery presented as documentary.
- No marketing or promotional use without its own review.
