# Vietnam MOIT — source-first weekly evidence inventory

## Motivation and separation

Indo-Pacific Record's Sunday Briefs writer should receive a **single unified
source pool** and produce one coherent regional article for Dylan to edit.
Two Vietnamese Ministry of Industry and Trade families could eventually
contribute to economic-security and industrial-policy themes. They are
*separate from the MPS foreign-affairs source*, which has already been
source-verified in merged #211.

For MOIT, the minimum safe first step is an official-source record inventory
that is anchored to each family's own immutable shadow Git branch, archive
capture ledger, published dates and Vietnamese-language content versions.
This PR is a **metadata-only source selection milestone**. It does not
automatically inject MOIT material into the writing model, approve publisher
reuse or promote Vietnam production.

## Two distinct source families

| Family | Exact isolated branch | Hash rule |
| --- | --- | --- |
| `vn_moit_energy_vi` | `shadow/vietnam-moit-energy` | `moit-vi-content-v1` |
| `vn_moit_foundational_industry_vi` | `shadow/vietnam-moit-foundational-industry` | `moit-vi-content-v1` |

The source identity prefixes are `moit-energy-vi:` and
`moit-industry-vi:`; they include the ministry's *canonical article path*,
rather than the MPS ten-digit article code. These are never confused with
`VN-MPS-...` private writer IDs or any production database record IDs.

## Actual source-state evidence (Oct 7 collection)

The two source states have the following immutable Git heads from the last
verified scheduled run:

- Energy: `aac24cb4c2bc7e63da80df5212954d48cf492945`.
  A September 30 bootstrap had **two** observed original articles.
- Foundational Industry:
  `5e414cf28cf99bb6ae8b64052f701ea27fcf19b7`.
  A September 30 bootstrap had **one** observed original article.

Both collected again successfully for the October 7 logical date, reporting
`ok_no_publications` in their **bounded October 1–7 listing windows**,
with zero newly retrieved articles and no recorded anomalies. Neither
state therefore has an archived article **dated October 4–10** as of that
October 7 snapshot.

That does **not** establish that Vietnam's government or ministry issued
no other publication; it also cannot establish collection happened through
Saturday, October 10. Do not pad this Sunday's manuscript with the September
material. Both source families remain shadow-only.

## Machine workflow

`scripts/prepare_vietnam_moit_weekly_candidates.py` accepts one source
family, an exact state commit, and an exact reporting Saturday. It verifies
the commit belongs to that family's isolated branch, independently reviews
the full state tree/captured response hashes/SQLite version chain, then
emits an inventory containing **only** canonical URL, original title,
publication date, language, source identity, current version hash, immutable
Git commit and machine review blockers.

For September 27–October 3:

```sh
python -m scripts.prepare_vietnam_moit_weekly_candidates \
  --source vn_moit_energy_vi \
  --state-repo /private/moit-energy-shadow-clone \
  --state-commit aac24cb4c2bc7e63da80df5212954d48cf492945 \
  --week-ending 2026-10-03 \
  --out /private/moit-energy-2026-10-03.json
```

For this Sunday's October 4–10 window, choose
`--week-ending 2026-10-10` instead; the historical October 7 state
has zero qualifying source records for that window. The output file must
be new and outside the tracked repo. The tool never writes captures,
updates the production DB, calls the model or sends SMTP.

A dedicated no-network test suite and a real GitHub Actions historical replay
independently exercise **both MOIT branches** in both reporting windows, proving
that the prior articles remain archived without leaking into the current week.

## Next integration stage

Once verified current-week MOIT publications actually exist, the next
engineering milestone is to generate **version-bound editorial synopses**,
with an independently appropriate source-use decision, and convert only
those reviewed metadata entries to a typed private evidence packet that
the shared Sunday writer can select by relevance. The MPS permissions
in #222 must not be automatically inherited by MOIT: each source may
have distinct terms and exact-capture licensing constraints.

Until then:

- No automatic `VN-MOIT-...` citation vocabulary is introduced
- No source body or full translation is uploaded for external model use
- No claim that the whole ministry has stopped publishing
- No contribution counted merely because an archive contains older records
- No attempt to change the parallel Japan source selection or shared #203
  writer conflicts
- No government-source approval, human signoff, live desk or issue number

A thematic AI draft may legitimately include **MPS + Japan** this week but
no MOIT, based on source relevance and dates. This is not a separate MOIT
supplement assignment for Dylan.
