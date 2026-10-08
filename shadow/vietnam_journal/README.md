# Vietnam — National Defence Journal English source candidate

**Status: declared research candidate, source disabled, no remote collection.**

**Current engineering checkpoint, October 8, 2026:** article extraction and
four-category listing parsers are merged (#138/#143). A bounded in-memory
proof recovered article fields from two desktop pages; the four live category
pages exposed 71 candidate IDs with exact parser/scanner identity parity.
Those results do **not** prove complete history or validated publication
dates for all links. Historical coverage and use/retention rights remain
open in #154/#155.

`readiness.v1.json` records the exact evidence and unapproved-use posture.
`scripts/validate_vietnam_journal_readiness.py` rejects accidental rights
or activation claims against the disabled manifest. This is an offline
preflight only, **not** enforcement inside any future source collector.


Source slug: `vn_national_defence_journal_en`, publisher: National
Defence Journal (`Tạp chí Quốc phòng toàn dân`). This is military-journal
editorial writing and analysis, not the Ministry of National Defence's formal
release or directive channel. Authority tier B; original English as published.
Articles are attributed to the journal and their named authors, not
automatically to the ministry or armed forces as official policy statements.

## The two supplied URLs are one source

- Desktop: https://tapchiqptd.vn/en/default.html
- Mobile: https://m.tapchiqptd.vn/en

Both present the same English articles. For example, the Military Technical
Academy article has ID 26936 at:

- https://tapchiqptd.vn/en/theory-and-practice/military-technical-academy-proactively-embraces-international-integration-and-elevates-int/26936.html
- https://m.tapchiqptd.vn/en/theory-and-practice/military-technical-academy-proactively-embraces-international-integration-and-elevates-int-26936.html

The shared article identity is `vndj-en:26936` and its canonical URL is
the desktop version. The normalization in
`scraper/sources/vn_defence_journal.py` is intentionally narrow: exact HTTPS
hosts, English, observed section slugs and numeric article IDs. It rejects
query/fragment aliases, unknown paths, other languages, ports and unrelated
domains rather than pulling an article through an uncontrolled link.

Offline `discovery_links()` recognizes and deduplicates candidate article
links from supplied HTML. It **does not** run HTTP requests, assign
publication dates from a homepage, infer missing pages, retrieve article bodies
or claim completeness. The same article appears repeatedly on site homepages
under sections and Most Read. Published article date stamps use
`Wednesday, September 30, 2026, 14:48 (GMT+7)` on desktop and
`9/30/2026 2:48:13 PM` on mobile. `stated_date()` preserves date only and
does not invent a UTC instant.

## Activation gates not met

1. **Actions-side desktop access has been established in a bounded probe.**
   Run 37712715499 on 2026-10-08 UTC read the desktop host's robots.txt
   (HTTP 200, paths allowed), English homepage (HTTP 200, 26 unique article
   IDs) and article 26936 (HTTP 200). The mobile robots.txt instead returned
   HTTP 404: that is a missing policy file, **not an explicit prohibition**.
   The probe made no mobile listing or article request and neither host may
   be used to bypass a refusal on the other. The full results and pinned
   payload hashes are in docs/VIETNAM_JOURNAL_ACCESS_FINDINGS_2026-10-08.md. No proxy, challenge solver,
   browser impersonation, alternate host circumvention, undocumented pagination
   or retries.
2. The homepages are *not* an exhaustive timestamped release feed.
   The original access probe exposed a genuine extraction gap and a separate
   live site clock. The later article parser (#138) resolved the article DOM
   fields on **two** real desktop samples, only in memory; it does not verify
   every article genre. The four-category parser (#143) matched an independent
   scanner on **71 distinct IDs** in one bounded live observation. These are
   observed candidate URLs and provisional date hints, not a proven dated
   archive or complete backfill. There is no verified pagination mechanism.
   Future work must evaluate missed-item risk, historically bounded discovery,
   explicit original-text retention rights and an owner-authorized new shadow
   reliability cadence. The parsers are **not** an active remote adapter.
3. Both site footers say **All rights reserved**. Public visibility is not a
   blanket permission for archiving and republishing full article text.
   Evaluate permissions for the precise proposed retention/display behavior;
   citation, source link and minimal factual metadata can be a distinct,
   reviewed product decision. Do not save full-text fixtures in the repository
   without a clear rights basis.

This candidate must not inherit the ministry sources' October 7 reliability
clock or appear as another collecting source in any production count.
It does not modify the three MPS/MOIT ministry branches, the Vietnam ministry
cadence, Government News pilot, `pla_watch.db`, `output/`, or any workflow.

## Evidence and verification

Source-page references observed October 7, 2026: journal desktop/mobile
homepages, article ID 26936 at both hosts, article ID 26919 at both hosts,
and journal footer copyright terms. The two matched article IDs are contract
fixtures *as URLs and dates only*, not republished body text. Tests use
synthetic HTML snippets to prove duplicate and foreign-host refusal; they do
not pretend to prove live CSS selectors or robots permission.

Run offline:

```sh
python -m unittest tests.test_vn_defence_journal -v
```

Promotion path: explicit source-use/retention decision and historical
discovery assessment -> tested fail-closed shadow adapter (with rights
checks integrated, not simply documented) -> separate owner activation ->
journal-specific remote Day 0 -> Day 7/14/30 human reviews -> explicit
production promotion. No MPS/MOIT collection evidence is inherited.

Validate the current research hold offline:

```sh
python -m scripts.validate_vietnam_journal_readiness
python -m unittest tests.test_vietnam_journal_readiness -v
```
