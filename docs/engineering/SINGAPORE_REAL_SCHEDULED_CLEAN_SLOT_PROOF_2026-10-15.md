# Singapore: source-bound verification of first genuinely clean scheduled collection

October 15, 2026. This is an additional evidence gate for a *permanent* desk,
not a beta announcement or automatic source-use approval.

## Why this exact gate

The genuine scheduled Singapore shadow run
[38656815142](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38656815142)
on October 14 failed honestly: 34 MINDEF releases selected/retrieved, 33
duplicates, one extraction failure and zero new source records. Its newly
precise failure log identifies this *specific* official publisher URL:

https://www.mindef.gov.sg/news-and-events/latest-releases/22sep26-infographic/

The run used collector commit
`3236ed09a4abd19c31e8103fd96cac41593e464c`. The structurally
verified image-only extraction parity fix from merged PR #581 was not part of
that older collector state. PRs #577/#581 repair the incomplete-run gate and
only the ministry-pinned infographic exception; neither makes a broken release
silently successful.

## Automatic read-only post-run check

When the existing scheduled **Singapore Shadow Collection** workflow finishes
successfully, the dedicated workflow
`.github/workflows/singapore_first_clean_scheduled_proof.yml` retrieves the
real `shadow/singapore-mindef` Git history with read-only repository permission.
It requires an exact matching immutable ledger for that scheduled run's
GitHub Actions ID **and** its actual collector commit.

`scripts/verify_singapore_clean_shadow_run.py` then checks:
- real scheduled logical-date receipt, permitted robots and successful index;
- complete retrieved/inserted/duplicate accounting, no fetch, access or
  extraction failures and no hidden failed URLs;
- a genuine stored ministry media-only URL for the identified infographic;
- its exact original publisher identity, title, September 22 date, **empty**
  text and SHA256(empty) preserved in the shadow SQLite database;
- every claimed additional media-only URL has an empty text/hash, with no
  OCR/image captions or body content added;
- ledger original count equals SQLite original count, and no state/db rewrite.

The verifier prints only bounded numeric proof and source Git/run identities;
it never exports original article text, HWPX, HTML, photographs or a translated
synopsis. The offline unit tests use wholly synthetic SQLite/ledgers. No
production database, output HTML, model or Pages file is altered.

If October 15's genuinely new run fails again, remains unqualified or is
unavailable, the gate must NOT manufacture a green report. Historical days
with one masked failure remain incomplete no matter what a future success says.

## Operational follow-up

Once this readback is successful, the desk may begin accumulating newly
verified *complete* scheduled days. This does not meet the seven-day
accelerated publication threshold by itself, certify model/source-body rights
or approve Singapore production admission. Singapore's separately governed
source collection and source-use boundaries remain unchanged.

A manual dispatch can recheck a known **existing real scheduled run** by
specifying its exact GitHub Actions ID/SHA; it cannot create a collection day.
