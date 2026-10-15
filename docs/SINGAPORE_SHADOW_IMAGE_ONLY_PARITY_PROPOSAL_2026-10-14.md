# Singapore shadow: structurally verified media-only parity — October 14, 2026

**Review-only implementation; stacked on PR #577.** This is not a source-content approval, model-input permission, archive release, source-rights decision or instruction to rewrite a historical collector ledger.

## Problem and rationale

The previously reviewed official September 22 MINDEF infographic `22sep26-infographic` consists of an identifiable, canonical ministry article page with a real headline, release date and one image inside its article container, but no original textual prose. Its 178 characters returned by the legacy HTML body extractor are page furniture (date, navigation and related links). The source was captured using authorized adapter transport on September 29 and preserved as a trimmed, source-backed fixture in `tests/fixtures/sg_mindef_recovery/22sep26-infographic.html`. See `docs/SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md`.

The production Singapore collection path was already repaired to classify exactly this **structurally verified image-only** condition as `media_only`, with the full publisher identity preserved and `text_original=""`. But the isolated Singapore shadow runner still called `SGMindefAdapter.extract()`, which deliberately did **not** perform the structural check. Existing repository documentation predicted that every shadow 30-day lookback including September 22 would continue reporting an extraction failure. A review of the **actual** sixteen September 28–October 13 ledgers showed precisely one extraction failure per day, masked as `health=ok` (see PR #577 and `docs/SINGAPORE_SHADOW_PARTIAL_FAILURE_REVIEW_2026-10-14.md`).

**This historical match strongly implicates the known infographic, but the old receipts do not preserve failed per-item URLs. It is not a proof that no other release failed on any of those dates.** The next real run is still authoritative.

## What changes

1. `SGMindefAdapter.extract_shadow_structural()` delegates to the **existing**, already-reviewed `_extract(capture, structural=True)` classification used by production. The generic `extract()` method remains strict and unchanged.
2. The Singapore-only `scripts/shadow_collect.py` calls the new explicitly named entrypoint. A structurally identified short image-only article preserves the canonical official URL, title and slug-based publication date, but stores **zero characters** and the SHA-256 of the empty string. It does not fetch the image, read alt text, use OCR, or invent descriptive words.
3. The private shadow ledger now reports `text_unavailable` and source-specific `media_only_urls` (selected source URLs, no copied body), including a read-only diagnostic on repeat duplicate runs. An invariant refuses a media-only extracted record if it unexpectedly carries nonempty text or an incompatible content hash.
4. Any unknown short container, failed identity, missing title/date, fetch refusal, template change, or other extraction defect remains a failure. PR #577's **partial-result gate** is still mandatory: successful neighboring documents must never conceal a failed source.
5. The original Singapore production source adapter, pipeline, production database, outputs, source-governance holds, rights, and regional model drafting remain untouched. The shadow branch is still the **only** intended state destination if and when the independently reviewed code is merged and scheduled.

The existing shadow SQLite schema stores empty text and hash; it lacks a separate durable per-record `media_only` status column. The ledger's `media_only_urls` and `text_unavailable` report the status of *that specific collection attempt*, not immutable model/editorial approval. This limitation must be considered at any future desk activation review.

## Verification and decision

The offline test `tests/test_singapore_shadow_media_only_parity.py` replays the **preserved genuine infographic HTML** together with separately labeled synthetic fixture pages. It requires: 11 selected, 11 retrieved, no extraction or fetch failure, 11 isolated shadow inserts, exactly one empty-body image-only record, the exact official publisher title/date and empty SHA, bounded metadata-only diagnostics, no fictitious OCR content, duplicate idempotency and source clock integrity. Other cases reject an unfamiliar short layout, preserve genuine short prose and show that generic `extract()` remains strict.

The enhanced focused Singapore PR checks also run existing production structural-image and source-collection regressions. No fixtures are re-downloaded and no live collector, model, SMTP, main database, rendered output or publication is invoked as part of CI.

**Order:** PR #577 should pass exact-head full offline CI and be reviewed/merged first. Only then retarget this stacked PR onto current main, rerun *its own* exact-head focused/full CI, and separately decide whether to merge it. A fresh real isolated Singapore shadow run afterward must identify any remaining failures via PR #577's source-specific failure logging. If the failure persists, do not bypass the classifier or mark Day-30 continuity complete. Historical misleadingly green ledgers must never be retroactively counted as clean solely because new code handles their suspected cause.
