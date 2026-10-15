# Japan Joint Staff — official-index source-link research lane (October 13)

**Scope:** official metadata-only discovery review of `https://www.mod.go.jp/js/press/`, **not** a collection job or permission to store original PDFs, images, body text or run automated Briefs.

## Independent publisher evidence

The [Joint Staff press index](https://www.mod.go.jp/js/press/) currently exposes one October 13 original and several October 9 originals under its **2026 October** heading. Its original Japanese dates and publisher PDF URLs are distinct first-party references:

- October 13, **China Y-9 aircraft**, `https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf` (three-page PDF). The original was reviewed separately in merged PR #526.
- October 9, **Russian IL-20 aircraft**, `https://www.mod.go.jp/js/pdf/2026/p20261009_03.pdf` (three-page PDF, **outside** reporting week October 11–17).
- October 9, **Chinese TB-001 UAV**, `https://www.mod.go.jp/js/pdf/2026/p20261009_02.pdf` (three-page PDF, likewise **outside** week 42).

These are **one issuing institution's** linked releases, not cross-confirmations, and the first item is already independently documented in the existing Japan week-42 research note. This directly accessible Japanese index is a different official source family from the MOD's Japanese news RSS and **does not imply its HTML originals or every linked PDF can be fetched by the GitHub Actions collector**. The MOD robots policy was inspected separately: it disallows `/a/` and `/sp/j/`, not this `/js/press/` index. A GitHub-hosted runtime access probe and source-use review remain prerequisites to any scheduled fetch.

## New offline-only parser

`scripts/review_japan_joint_staff_index.py` accepts an **already obtained** original index HTML snapshot. It does not import a network client or issue requests. It requires:

- a valid Sunday–Saturday reporting week, cutoff inside that week, and a bounded original HTML size;
- first-party HTTPS PDF paths in the `/js/pdf/YYYY/pYYYYMMDD_NN.pdf` family, without queries/fragments/credentials;
- matched publisher row date and filename date, uniqueness of canonical original URLs, a bounded year population and refusal of unexpected path shapes;
- no false claim of zero publications when the current-year PDF listing could not be parsed.

Only index date, original headline/label and official PDF link enter a metadata review report; no article body, image, translation, other source issuer, generated production record, source qualification or model-visible factual capsule is produced. Every record explicitly carries `eligible_for_automatic_model_drafting=false`, `editorial_approved=false` and `production_record=false`.

Rehearsal (from a source HTML snapshot an authorized researcher actually obtained, not a fabricated example):

```bash
python -m scripts.review_japan_joint_staff_index \
  --index-html /private/japan-joint-staff-official-index.html \
  --week-ending 2026-10-17 --cutoff 2026-10-13 \
  --output /private/japan-joint-staff-link-review.json
python -m unittest tests.test_japan_joint_staff_index_link_research -v
```

No output is written until all metadata passes identity/date checks, and output location is explicitly named by the operator. To prepare a Sunday research candidate, open each exact original PDF, complete independent semantic/rights review, then separately prepare the existing strictly typed private research synopsis under the Japan source-intake lane in PR #539. **Do not feed link metadata as if it were verified source text.**

## Follow-on path toward routine operations

1. Use an owner-authorized, clearly identified, single-pass runtime probe on the official Japanese index. Confirm parser compatibility with the **live publisher HTML** and direct PDF source access, respecting the original publisher's robots/access refusals.
2. Only with a successful probe, persistent receipt, source-specific text completeness and permission review consider proposing a separate **guarded, disabled-by-default shadow** discovery/collector job. Do not change JCG's independent daily gate or borrow its collection clock.
3. Reconcile named Day 7/14/30 source reviews and official-original custody before any independent producer-class designation; typed editorial link notes are a separate route.

**Not changed by this PR:** `desks/registry.json`, the tracked DB, MOD/JCG collectors, schedule/variables, production artifacts, templates, published site, existing weekend roster, model calls, email or original government assets.

## October 15 — updated Week-42 official-index source leads (metadata only)

The [first-party Joint Staff press index](https://www.mod.go.jp/js/press/) was directly reviewed October 15. Its publication-date labels and linked PDF originals distinguish **four** candidate notices within the Sunday October 11–Saturday October 17 reporting week, through October 15:

| Official publication date | Distinct publisher-index entry | Official original (link only) |
| --- | --- | --- |
| October 15 | 日米共同訓練の実施について (Japan–U.S. joint training) | https://www.mod.go.jp/js/pdf/2026/p20261015_01.pdf |
| October 14 | 中国軍機の動向について（UAV,Y-9,WZ-7） (three categories of observed aircraft) | https://www.mod.go.jp/js/pdf/2026/p20261014_02.pdf |
| October 14 | 中国海軍艦艇の動向について（空母「遼寧」ほか３隻／沖縄本島－宮古島間南東進／発着艦） (Liaoning and accompanying vessels) | https://www.mod.go.jp/js/pdf/2026/p20261014_01.pdf |
| October 13 | 中国軍機の動向について（Y-9） (earlier independently reviewed original, #526) | https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf |

The three newly linked PDFs were opened and their **text** inspected for source identity and date; graphics, maps, photographs, embedded media and publisher rights have **not** been independently approved or admitted. This note preserves links rather than source bodies or media. These records come from the **same issuing institution**, not corroborating independent sources.

**Date distinction:** The October 15 announcement reports **October 14 training**. The October 14 Liaoning notice describes observations spanning **October 13–14**, rather than both being separate October 14 detections. The October 14 aircraft notice describes movements that day. Publication date and activity date must not be conflated. No territorial airspace intrusion, ownership attribution beyond the issuing text, combat conclusion or independent verification should be inferred from index metadata.

The companion tests are constructed HTML rows using the above exact first-party linked identities, **not** a preserved authenticated publisher-index capture or a GitHub Actions network test. Before using this path for automated shadow observation or Sunday research, independently attest the actual publisher DOM and target runtime access, complete original-specific semantic/rights review, verify source custody and obtain separate owner authorization. The parser does not collect, archive, translate, feed a model, publish, or change desk status.
