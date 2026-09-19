# US Indo-Pacific Desk — shadow scope

Shadow evaluation only. This desk collects into an isolated state branch that
reaches neither `pla_watch.db` nor `output/`, renders no records, and is
counted nowhere. **A shadow desk is not a qualified desk.**

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
5. **Not launched.** No workflow is enabled, no state branch exists, and the
   desk has collected nothing. Day zero has not been reached.
