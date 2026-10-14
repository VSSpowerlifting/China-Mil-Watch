# Singapore MINDEF shadow — mixed-result integrity correction (2026-10-14)

**Status:** proposed collector integrity fix, not a source parser repair, rights review, production promotion or historical ledger rewrite.

## What actually happened

The latest inspected scheduled Singapore shadow workflow was [GitHub Actions run 38489157243](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38489157243), on October 14 UTC for the **October 13 logical collection slot**. The actual runner log reports:

| Field | Observed |
| --- | ---: |
| Selected / retrieved | 34 / 34 |
| Duplicate originals | 33 |
| New originals | 0 |
| Extraction failures | **1** |
| Fetch / access failures | 0 / 0 |
| Recorded result | `ok_all_duplicates` |
| Recorded health | `ok` |
| Reported shadow day | 55 |
| Stored total | 88 |
| State snapshot hash (before and after) | `5ce96259d0918b74ef4543e9f08eebc36d2a67d5b188cee28127f8c19fdde729` |

The workflow was green, but **34 selected originals were not all duplicates**: one original was fetched and failed extraction. The existing result-ordering logic in `scripts/shadow_collect.py` checked `extraction_failures` only when **both** `inserted` and `duplicates` were zero. Any healthy duplicate concealed the failure and let the day advance as clean.

This is a **receipt and qualification defect**, not proof that the source is newly broken. Earlier [Singapore image-only release findings](SINGAPORE_IMAGE_ONLY_RELEASES_2026-09-29.md) documented a structurally image-only original that production can record with text unavailable while the shadow `extract()` path still refuses it. That is a plausible explanation for the repeated shadow failure, **not a source-specific attribution proven by this ledger**. The current ledger contains no per-item failed URL; we do not assume its identity.

## Correction and operational effects

- Any `access_failures`, `fetch_failures` or `extraction_failures` now takes precedence over new insertions and duplicates when deciding final result/health. Existing `auth_failure`, `fetch_failure`, `extraction_failure` status vocabulary remains unchanged.
- The runner still records counts, stored total, date, source result and a non-empty failure description in its **isolated shadow runner state**. New successful rows can exist only in the temporary checkout of that failed run.
- A failed run returns exit code 1 via the existing `main()` health rule. The scheduled workflow's `Publish shadow state` step is already gated on `success()`, so incomplete runs cannot push a misleading healthy state. Its `if: always()` ledger upload remains available for diagnosis.
- Failed runs do **not** start or advance the shadow day clock. We do not retroactively change the October 13 ledger, date stamp, stored records, or any previously recorded snapshot.
- A complete run with only duplicates and **zero failures** still reports `ok_all_duplicates` / healthy. A complete run with new originals still reports `ok`.
- Production `scraper/sources/sg_mindef.py`, `pipeline.py`, `pla_watch.db`, rendering, Singapore editorial screening, publishing permissions and other collectors are unchanged.

**Important trade-off:** until the specific failed MINDEF release is independently identified and its extraction handling is reviewed, new scheduled shadow runs may now fail visibly. That is preferable to claiming complete coverage. It does not mean the public Singapore records stop updating: the isolated shadow qualification lane and the existing production desk path are separate.

## Follow-up investigation after this PR

1. Inspect the original **October 13** run artifact and source window, then reproduce the one failure under an authorized, bounded original-source check. Identify the actual failing release URL and distinguish known image-only policy from parser drift, refusal, or actual missing text. Do not guess an identity from a prior memo.
2. Determine whether the existing production structural image-only treatment should be introduced into the **shadow** source adapter, with exact-title/date and empty-text provenance, **as a separate reviewed decision**. Do not turn arbitrary short or inaccessible originals into successful captures.
3. Once a genuinely clean, exact-run source process is established, accumulate new honest scheduled-slot evidence. Any historical green workflows with nonzero failure counters should be marked unqualified in a later *read-only* continuity review; never rewrite the published historical ledgers.
4. Only then resume desk-qualification scoring and source-specific reviewer signoffs. Neither this fix nor a green run grants reprinting rights, broad source coverage, external-model claims or publication approval.

## Verification

Offline tests in `tests/test_singapore_shadow.py` now cover all three mixed cases: inserted originals plus a failed extraction, duplicates plus failed extraction, and duplicates plus failed fetch. They also preserve the fully successful all-duplicates path and verify that the clock does not advance on a failed attempt. Run `python -m unittest tests.test_singapore_shadow -v` and the full PR offline suite at the **exact proposed head**.

No source-site calls, SMTP, model calls, database migrations, collector execution, Git-state branch pushes or public updates are authorized by this change.
