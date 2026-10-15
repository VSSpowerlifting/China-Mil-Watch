# US Indo-Pacific Desk — shadow scope

Shadow evaluation only. This desk collects into an isolated state branch that
reaches neither `pla_watch.db` nor `output/`, renders no records, and is
counted nowhere. **A shadow desk is not a qualified desk.**

## Current operational status — paused 2026-10-07

The DVIDS adapter remains built and the September 19 manual run remains valid
state evidence, but **scheduled collection is paused**. Eighteen consecutive
scheduled runs from September 20 through October 7 failed before RSS discovery
because the policy request to `/robots.txt` returned HTTP 502/504 from GitHub
Actions. The durable state branch therefore remains at the September 19
successful corpus.

This is recorded as unresolved GitHub-hosted egress/access reliability, not a
publisher refusal. The workflow is manual-only and a re-probe requires explicit
owner authorization. Do not add a proxy, browser identity, alternate host,
robots bypass, or automatic retry. Restart criteria and exact run evidence are
in `docs/US_DVIDS_EGRESS_PAUSE_2026-10-07.md`.

## What this source is

**DVIDS USINDOPACOM-tagged reference stream.**

* A **Tier B DoD media-service feed**. The publisher is Defense Media Activity,
  a DoD field activity — not U.S. Pacific Command.
* **Unit tagging does not imply command authorship or comprehensive
  Indo-Pacific relevance.** The tag is applied by the submitting unit.
* It is **not a complete USINDOPACOM command-release wire**.
* It is **not presently a peer of the China Desk**.
* **The public US Indo-Pacific Reference Desk remains `access_blocked`.**
* **Shadow collection evaluates whether this source can support that desk
  later.** It does not presuppose that it can, and reaching a day count does
  not decide it.

No record may be called Indo-Pacific-relevant merely because DVIDS tagged it to
the unit. That inference is the specific error this framing exists to prevent.

## Measured shape of the feed

The route is `https://www.dvidshub.net/rss/unit/USINDOPACOM`. Measured on the
live feed, 2026-09-17:

| measure | value |
|---|---|
| items in feed | 428 |
| `/news/` (text) | **171** |
| `/video/` | 99 |
| `/audio/` | 100 |
| `/image/` | 58 |
| news date span | 2026-09-01 → 2026-09-16 (16 days) |
| news cadence | 10.7 items/day |
| unique `guid` | 171 / 171 |
| unique `link` | 171 / 171 |
| titles carrying **any** Indo-Pacific keyword | **15 / 171 (9%)** |

That last row is the number that governs how this desk may be described. It is
an indicative keyword count over titles, not a classification, and it is
deliberately generous — it counts `alaska`, `pacific` and `hawaii` as hits. On
the most favourable reading available, roughly nine in ten items in this feed
do not announce themselves as Indo-Pacific material at all. Sampled
non-matching items include a Kosovo school pen-pal programme, a Fort McCoy
retiree appreciation day, an Arkansas Air National Guard communications
exercise and a chief-petty-officer pinning announcement.

**Therefore**: this desk collects *public affairs carrying a USINDOPACOM tag*.
Any scope text, registry entry, site copy or summary that describes it as US
Indo-Pacific Command releases, or as a US counterpart to the China desk's
institutional sources, is a misrepresentation of the corpus.

## Why DVIDS and not pacom.mil

`www.pacom.mil` and `www.defense.gov` return **HTTP 403 for `robots.txt`
itself** (probed 2026-08-26, re-probed 2026-09-16). That finding stands
unchanged and is not reinterpreted here. A host that will not serve its own
rules has not granted permission, and an RSS endpoint that happens to answer
does not supply the permission the rules file withheld.

DVIDS is a **different host with a readable, permissive policy**, not a
workaround for the blocked one:

```
User-agent: *
Disallow: /mediarequest/ /hometownheroes/ /ajax/ /search/ /tags/
Disallow: /download/ /holiday/ecard/ /comment/ /map/
Allow: /
```

`/rss/` and `/news/` are permitted. `/search/` and `/tags/` are **Disallow**
and are never used: discovery is the feed alone. No identifier is ever
enumerated, no challenge is ever solved, and no proxy or alternate identity is
ever used.

The `us-indopacific` entry in `desks/registry.json` **stays `access_blocked`**.
That status is about `pacom.mil` and remains true until this desk has actually
collected through a route that is not `pacom.mil` and the result has been
reviewed.

## Collection policy: the complete eligible stream

**No relevance filter is applied, by design.** Every eligible `/news/` item is
collected. Filtering on title keywords at collection time would decide the
usefulness question this shadow phase exists to measure, and would leave a
corpus shaped by a guess rather than by the source. The keyword indicator in
the checkpoint report is a **diagnostic**, never a gate and never dispositive.

## Included

* `/news/` items from the USINDOPACOM unit feed, with a body retrieved from the
  article page.

## Excluded — counted, never silently dropped

| reason | meaning |
|---|---|
| `not_news_media` | an `/image/`, `/video/`, `/audio/` or `/publication/` item. A photo is not a document with a body. |
| `foreign_host` | a link outside `PERMITTED_HOSTS`. Refused, never followed. |
| `unparseable_url` | not `/news/<id>/<slug>`. |
| `missing_guid` | no stable source identifier. |
| `identity_mismatch` | the `guid` id and the link id disagree; the feed contradicts itself about which document this is. |
| `missing_link` / `missing_title` / `missing_pubdate` | a required field is absent. |
| `unparseable_pubdate` | a timestamp we cannot read, **or one with no offset**. Guessing a zone invents a fact about when something was published. |
| `outside_window` | published outside the requested collection window. |
| `duplicate_in_feed` | the same identity appears twice in one feed body. |

Extraction refuses, rather than storing a partial record, when the body
container is absent (**template drift**) or present but carrying under 200
characters (**a news item with no prose**). Those two are distinguished, which
is the lesson the China desk paid for: an empty body stored as a real record is
how a parser bug becomes a permanent, invisible corpus defect.

## Mechanisms

* **Identity** — the feed's own `guid` (`news:574946`), cross-checked against
  the numeric id in the item link. Never a title, never a listing position,
  never a slug, which can be re-worded.
* **Dates** — each item's `pubDate`, kept in **the offset that item itself
  declares**. Every sampled item carried a US Eastern offset, so a 22:13 -0400
  item is published on the 16th in the publisher's reckoning and on the 17th in
  UTC. Recording the UTC date would silently re-date an evening-heavy feed, so
  the UTC instant is preserved *beside* the date, not instead of it.
* **Bodies** — `div.news-body` on the article page. The feed's `description` is
  a teaser (median ~311 chars) and is never stored as a body.
* **Politeness** — project user agent, robots re-read every run, 2.0 s between
  requests, one worker, retries for transport errors only. A 403 or 404 is an
  answer, and asking again is how a collector turns a refusal into hammering.
* **Isolation** — the runner refuses to write inside the repository working
  tree and never names `pla_watch.db` or `output/`.

## Historical launch and current pause — not a new Day 0

The DVIDS shadow experiment **did launch once**: authenticated GitHub Actions
manual run [#35476931301](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/35476931301)
succeeded September 19, 2026 and committed 40 eligible records on the isolated
`shadow/us-indopacom` state ref (`a36f67aee80e7520fb9fb401f69ca7c0ce112ce5`).
That is genuine historical shadow state, **not** a public desk, a production
record, permission for publisher reuse, or a completed reliability window.
Earlier notes claiming the branch never existed or Day 0 was never observed
described a **pre-launch** state and are superseded here.

The experimental daily `08:40 UTC` schedule subsequently ran September 20
through October 7, 2026. All 18 consecutive logical collecting dates failed
*before feed discovery* at the `robots.txt` request (502/504). The cron was
removed October 7. `.github/workflows/us_shadow.yml` now offers a **manual-only**
diagnostic dispatch requiring explicit authorization for the individual reprobe;
it is not an automatic collection service. No successes are to be inferred from
the missing dates, and the one old successful collection does not qualify this
source for publishing.

Reactivation of a DVIDS shadow schedule requires separate owner authorization,
a readable policy permitting both declared RSS and article paths, a bounded
authenticated runner collection, and independent subsequent reliability review.
It would **not** unlock a command-authored first-party feed: DVIDS unit tagging
is a separate Tier B source, not US PACOM press-release authorship. Full
attempt/run evidence and the current restart contract are in
[`docs/US_DVIDS_EGRESS_PAUSE_2026-10-07.md`](../../docs/US_DVIDS_EGRESS_PAUSE_2026-10-07.md).

**Separate first-party PACOM research:** a
[nine-URL indexed link review](../../docs/engineering/US_PACOM_FIRST_PARTY_LINK_RESEARCH_2026-10-15.md)
now documents only official PACOM URL/date leads. It neither retrieves source
bodies nor resolves the command site's access restrictions. The public U.S.
Indo-Pacific Reference Desk stays `access_blocked` and no public data changes.

### Retention is a count, and there is no backfill

This is the single operational fact that makes a missed run different here
than on the other two desks.

The DVIDS feed carries a **fixed window of ~428 items across all media types**,
not a date range. When measured on 2026-09-17 that was 171 `/news/` items
spanning 16 days -- but volume is uneven (1 news item on 2026-09-05, 37 on
2026-09-15), so the window is a count that **shortens as volume rises**.

Consequences, stated plainly:

* **A missed collecting day is permanent.** Items that fall out of the window
  cannot be retrieved from this route, at any later time, by any means this
  project permits.
* **There is no historical backfill.** The feed is the only permitted
  discovery endpoint; `/search/` and `/tags/` are `Disallow` in DVIDS robots.
  No archive endpoint has been identified, and none may be improvised.
* **Day one of collection is the earliest recoverable day.** Nothing published
  before launch enters this corpus.
* `scripts/review_us_shadow_state.py` therefore reports a gap between
  collecting days as a **FAIL marked UNRECOVERABLE**, not as lateness.

## Known limitations

1. **Scope.** ~9% of items announce Indo-Pacific content. See above. This is
   the dominant limitation and it is editorial, not technical — no amount of
   collector work fixes it.
2. **Retention.** The feed carries a fixed ~428-item window across all media
   types, which was 16 days of news when measured. Because volume is uneven
   (1 item on 2026-09-05, 37 on 2026-09-15), that window is a count, not a
   duration, and it will shorten as volume rises. **Anything older than the
   window is unrecoverable from this route**; a gap in daily collection is a
   permanent gap. No backfill mechanism exists and none may be improvised.
3. **Authority tier B.** The publisher is a DoD media service, not the command
   speaking for itself. This is not a peer of the China desk's Tier A sources
   and must not be counted as one.
4. **No bilingual dimension.** Every item is English. The desk contributes
   nothing to the project's translation or original-language evidence work.
5. **Paused after Day 0.** One manual shadow collection succeeded on September 19,
   2026 (40 eligible records), but 18 subsequent scheduled slots failed on
   robots-policy access and the schedule is disabled. The old state branch is
   not a live collection service and supplies no public IPR records.
