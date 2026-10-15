# Published China source-trail integrity: Global Times legacy captures (15 October 2026)

**Status: evidence/citation risk research, not an accusation of false reporting,
an editorial correction, publication approval, or site change.**

This escalates beyond routine [China curation #605](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/605),
the historical-source recovery [#613](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/613),
and the specific [No. 10 record defect #623](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/623).

## What can actually be established from preserved evidence

The **October 14, 2026 public compact index** lists 182 records that occur
in published source trails (178 China, four Singapore). Thirteen are
**Global Times** China records. Every one is explicitly included in an
issue's published source-trail list, **and** every one has a stored text
block with truncated-preview indicators (length and ellipses), rather than
a complete-looking copy of its article. All 13 predate the Global Times
scraper's September 16, 2026 extraction repair.

These are **13 strongly suspicious archival source captures, not 13
independently verified editorial errors**. The publisher originals and the
published Brief claims require separate original-source review before any
factual correction is approved. A teaser warning is not itself proof of
corruption and does not make an underlying reported military event false.

| Published issue | Historic citations | What is known from published issue |
|---|---|---|
| [No. 2 — May 16](https://indopacificrecord.org/the-pla-watch/posts/2026-05-16.html) | #241 | Mentions a naval terminal-defense report, explicitly treating the quoted "world-class" language as **messaging**, not technical verification; needs publisher/body fidelity review |
| [No. 10 — July 11](https://indopacificrecord.org/the-pla-watch/posts/2026-07-11.html) | #2265 | The record's **machine summary** incorrectly interprets a Joint Sea-2026 crew-exchange article as Joint Sea-2025 after reading unrelated old teasers. The Brief itself describes Joint Sea-2026; check the Brief's source trail and particular crew-exchange sentence before any correction decision |
| [No. 12 — Aug. 1](https://indopacificrecord.org/the-pla-watch/posts/2026-08-01.html) | #2751, #2752, #2881 | Brief discusses Huangyan Dao Type 071/H-6K claims, Type 076 catapult footage and Atlas drone activity. Their original sources, attribution, footage provenance and any other independent support need human claim-level checks |
| [No. 13 — Aug. 8](https://indopacificrecord.org/the-pla-watch/posts/2026-08-08.html) | #2803, #2804, #2916, #2917, #2993 | Brief discusses DF-17, strike-planning, H-6N, GJ-3A and Y-20B disclosures. Distinguish original CCTV/official footage, a Global Times account and expert interpretations; **do not automatically infer confirmed performance** |
| [No. 14 — Aug. 15](https://indopacificrecord.org/the-pla-watch/posts/2026-08-15.html) | #3084, #3085, #3145 | **Already corrected on Oct. 3.** The published correction acknowledges three corrupted Global Times bodies, limits their role to title-level comparison, and declines to treat them as evidence of military exercise/footage details. Protect this existing editorial caution |

**Editorial triage:** prioritize original-source verification in Nos. 12 and
13, followed by source-level correction of #2265 and the No. 10
crew-exchange citation. No. 14 is a **positive example** of explicit
historical limitation and prior editorial correction, not a candidate
for silently retracting an issue. No. 2 already cautions readers about
expert capability language. A Brief-level correction is warranted **only
if a particular claim cannot be supported after reviewing the original
and other cited sources**.

## Reproducible no-write custody guard

`research/china/published_global_times_trail-risk-2026-10-15.json` freezes
all 13 record IDs, original captured publisher URLs, source-stated titles
and dates, issue numbers/dates, and *preliminary* review categories. Each
entry has `original_publisher_content_checked:false`,
`reviewer:null`, `reviewed_on:null` and `owner_approved:false`.
The classifications name necessary **editorial work** only.

`scripts/audit_published_global_times_trail_integrity.py` validates the
frozen cases against the original `output/record/{id}.html` pages, the
protected `trail_ids` in the exhaustive `output/corpus-index.json`,
and the published `output/the-pla-watch/posts/{date}.json` source trails.
It never scrapes a site, edits the database, re-renders a page, accesses
private original capture bytes beyond the existing public stored body,
uploads a packet or creates a production manifest.

It catches changes to exact record ID/source title/date, missing or
duplicate source-trail links, removed provenance URL or collection date,
missing stored machine summary, removal of No. 14's documented editorial
correction, and changes to the specific No. 10 **machine-summary 2025**
conflict before the original archived version has been accounted for.

For each examined historical stored text it derives a SHA-256 fingerprint
of the parsed stored text and a *non-decisional* truncated-preview warning
and stores them only in the **optional private external JSON** audit report.
The check does **not** use a teaser threshold to mark a human Brief false
or choose editorially approved corrections.

Run:

```sh
python3 -m unittest -v tests.test_published_global_times_trail_integrity
python3 scripts/audit_published_global_times_trail_integrity.py
python3 scripts/audit_published_global_times_trail_integrity.py \
  --private-json /private/tmp/ipr-china-published-trail-review-20261015-new.json
```

That optional report must have a new absolute filename **outside** the
repository. The automated PR workflow creates the private report only in
ephemeral runner scratch, then verifies `pla_watch.db` and `output/`
remain unchanged. **No generated report is deployed**.

## Editorial correction process — not performed by this PR

1. Verify each primary publisher page or preserved publisher HTML and the
   original issuing agency separately. Record exactly what is official
   policy, operational reporting, or sourced expert speculation. Check
   photographic/video rights for cited platforms.
2. Compare each specific sentence of Nos. 2, 10, 12 and 13 to *complete*
   verified original text and any independently relevant alternate sources.
   A citation to an inaccurate captured text does not alone establish a
   false conclusion when other preserved citations might support the claim.
3. Capture correction evidence with original stored-body hash and capture
   metadata, verified original URL/content and rights, separate edition of
   corrected content, reviewer/date, and distinction between archive
   extraction correction and human-authored Brief text correction.
4. Preserve original record IDs, URLs, historical old capture, original
   Brief source trails, and all citations. Do not automatically rewrite
   LLM summaries from incomplete text or alter previously published prose.
5. Seek a **specific owner editorial decision** after source and claim
   checks. Only a separately authorized guarded release may apply public
   correction notices or changed summaries. This PR does not authorize a
   production flag simply because its offline CI passes.

**Important:** This audit targets only the **13 published source-trail
Global Times** articles visible in the October 14 index. Other historical
captures, and citations in future Briefs, require their own checks. A new
daily source collection cannot automatically change or approve this
historical review.
