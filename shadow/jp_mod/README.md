# Japan MOD / Joint Staff — shadow collection

Shadow evaluation. Nothing here is live, published, or counted in any public
figure. The Japan desk's public status is `shadow`; its source is `enabled:
false`; and `desks/` deliberately does not contain a `japan/` directory, so
production desk discovery cannot see this manifest by accident.

## What the two feeds actually are

Both declared feeds were categorised in full on 2026-08-26. The result corrected
the original scope claim, which called this source "Japan MOD / Joint Staff —
official releases" in languages `["ja", "en"]`. All three parts of that were
wrong.

### `/j/rss/news.xml` → `jp_mod_news_ja`

The ministry's Japanese-language news stream. **142 items**: `/j/press/` 105,
`/j/approach/` 37. **134 HTML, 8 PDF.**

### `/j/rss/update.xml` → `jp_mod_siteupdate_ja`

A **whole-site update stream, not a press-release feed**. It reports any page
the ministry publishes or revises. **391 items**: `/j/press/` 126,
`/j/budget/` 93, `/j/profile/` 76, `/j/approach/` 63, `/j/policy/` 21,
`/j/presiding/` 11, `/j/kids/` 1. **342 HTML, 0 PDF.**

### What neither feed carries

**Zero Joint Staff (`/js/`) items. Zero English (`/en/`) items.** Both are
declared in the manifest as separate, not-collected sources so they stay
distinguishable, and both are unreachable — their index pages are challenged.

### Why they are two sources and not one

They are objectively different streams. Collapsing them into one source called
"official releases" is what let the first manifest describe a budget table as an
official release. Each feed is now its own source, each with one endpoint, and
every stored record carries the source it came from.

Nothing is filtered. Keeping only the items that look like press releases would
be silent sampling, so every discovered item is kept and labelled by its URL
family — a budget page is stored as a budget document, a children's page as a
public education page, and an unrecognised family as "ministry page
(unclassified)" rather than vanishing.

## What access actually looks like

Qualified 2026-08-26 with one honest request per endpoint, using the project's
own user agent. `www.mod.go.jp` is behind Cloudflare, and the edge does **not**
treat every document the same way:

| Endpoint | Result |
|---|---|
| `/robots.txt` | 200 — disallows only `/a/` and `/sp/j/` |
| `/j/rss/news.xml` | 200 `application/xml` |
| `/j/rss/update.xml` | 200 `application/xml`, **304** on `If-None-Match` |
| `/j/press/news/2026/08/25a.pdf` | 200 `application/pdf` |
| `/j/press/news/2026/08/26b.html` | **403**, `Cf-Mitigated: challenge` |
| `/en/press-release/` | **403**, `Cf-Mitigated: challenge` |
| `/js/press/index-en.html` | **403**, `Cf-Mitigated: challenge` |

**XML and PDF are served. HTML is challenged.** Robots permits every path this
collector touches — the challenge is an edge policy, not a robots directive.

### How much of it can actually be read

Across `news.xml`, **8 of 142 items (6%) are PDF and carry full text**; **134 of
142 (94%) are HTML and are recorded as titled, dated discovery records with no
body**. `update.xml` carries no PDFs at all.

This is **partial retrieval, not coverage**, and it is not a qualified desk.
Most sampled bodies remain challenged.

## What the collector does with that

Discovery runs on the two official RSS feeds, which work. Bodies come from PDF
documents, which work, through the existing `processing/pdf_text.py` extractor —
the same one written for these releases, with its own status vocabulary for
scans, encrypted files, malformed files and size refusals. No OCR.

HTML items are discovered, titled, dated, and then **not fetched**. They are
recorded as `access_challenged` and stored as rows in `shadow_unretrieved`, so
the gap is a visible row rather than an absence. Nothing infers that a
challenged item does not exist.

The challenge is not solved. No browser user agent, no cookie replay, no
headless browser, no proxy, no retrying a 403. A challenge is a host telling
this client it is not welcome on that path; the honest response is to record
the refusal where a reader can see it.

## Why a challenged run is not a failed run

Singapore's runner treats an access refusal as a failed run, correctly: MINDEF
serves every release to this collector, so a 403 there means something broke.

Japan is not shaped like that. A *normal* Japan run has most of its discovered
items challenged and a minority retrievable as PDF. Reusing Singapore's
taxonomy would mark every Japan run `fail` forever — an alarm that is always on,
which is the same as no alarm.

So a challenged item is a **disclosed gap**, and the run reports `health:
partial` with the count and the URLs in the ledger. What would be a real
failure is the open routes closing: the feeds going down (`listing_failure`), or
the PDFs starting to be challenged too (`access_challenged`, `degraded`).

## Isolation

* `scripts/shadow_collect_japan.py` never opens the production database and
  never writes `output/`; it refuses any `--state-dir` inside the repository
* state lives on the `shadow/jp-mod` branch, checked out outside the working
  tree by `.github/workflows/japan_shadow.yml`
* the workflow holds `contents: write` and pushes exactly one ref,
  `shadow/jp-mod` — never `main`, never `gh-pages`, never with `--force`
* there is no Pages step, no deploy step, and no analysis call anywhere in the
  collector
* the workflow asserts its own checkout is still clean before publishing state

## Deduplication

By canonical URL, and by content hash of the extracted text. **Never by title.**
Japanese ministry releases reuse titles legitimately — 「日米合同委員会合意に
ついて」 recurs whenever the Joint Committee agrees anything — and title-level
deduplication would collapse a year of distinct agreements into one record.

## What this does not establish

That the Japan desk is ready. It is not. This is qualification and evidence
collection, on a source whose HTML estate this project cannot read. Whether a
PDF-and-metadata record is a good enough basis for a Japan desk is a separate,
later, human decision.
