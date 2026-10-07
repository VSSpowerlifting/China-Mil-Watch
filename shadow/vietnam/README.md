# Vietnam — Viet Nam Government News (English), `defense` tag

The additional Public Security and Industry and Trade ministry research is
separate, in `shadow/vietnam_ministries/`. It does not widen this adapter or
reuse this source's clock. Both runners now pass the shared cross-process
host gate; the original rehearsal's inter-process spacing lapse is historical.

**Built and rehearsed outside production; not launched.** The workflow is
manual-dispatch only and declares no schedule. It has never run in the
project's automation, and origin has no `shadow/vietnam` branch. A bounded
live rehearsal on 2026-10-06 UTC ran the collector and pushed its state only
to a local bare remote.
`desks/registry.json` lists the Vietnam Desk as `research`, with no manifest
and no record count.

| | |
|---|---|
| Adapter | `scraper/sources/vn_vgp.py` (`VNVgpAdapter`) |
| Manifest | `shadow/vietnam/manifest.json` (`enabled: true` for the shadow runner only; deliberately not under `desks/`) |
| Runner / workflow | `scripts/shadow_collect_vietnam.py` / `.github/workflows/vietnam_shadow.yml` (dispatch only) |
| State branch | `shadow/vietnam`, orphan, outside every checkout. It does not exist on origin yet. |
| Review kit | `scripts/review_vietnam_shadow_state.py` (Day 7 / 14 / 30 packets; no publisher) |
| Tests | `tests/test_vn_vgp_adapter.py`, `tests/test_vietnam_shadow_runner.py`, `tests/test_vietnam_shadow_review.py` (offline; real sockets refused) |
| Fixtures | `tests/fixtures/vn_vgp/` (byte-exact, hash-pinned; `requests.json` is the probe's full request log) |
| Evidence | `docs/VIETNAM_DESK_FEASIBILITY_2026-10-05.md` |

`load_all_desks()` cannot see this manifest. No code in `pipeline.py`,
`core/` or `desks/` imports the adapter, and no Vietnam row exists in the
production database. Nothing here qualifies the source. Retrieval on one day
is evidence of bounded access, not of reliability. No shadow desk is promoted
automatically, and none may be described as qualified.

## Scope

The page `https://en.baochinhphu.vn/defense.html`, which labels itself
"Tags: defense", and the English article pages it lists. Nothing else is
requested: not the Politics or Policies sections, not other tags, not the
Vietnamese edition, not the Government portal, not the Ministry of National
Defence and not the People's Army Newspaper.

- **A tag, not a category.** Editors apply it. When it was measured, the
  2026-08-04 national security strategy summary carried no tags at all, and a
  2026-09-23 Politics item on a meeting with the acting U.S. Navy Secretary
  did not carry this one. Items the tag does not list are not collected, and
  nothing is claimed about them. No keyword, topic or model filter widens or
  narrows the scope.
- **Tier B.** Government News is the Government's newsroom: its reporting is
  institutional public affairs. It is not Tier A because it is
  government-hosted, and not Tier C because it is a newspaper. A report that
  names a resolution or quotes a minister remains a newsroom report about it.
  The ministry (Tier A), the army newspaper (Tier B) and formal documents
  (`vanban.chinhphu.vn`, Tier A) are separate institutions and families.
- **English as published.** An English article is the English text the
  newsroom published, not a recovered Vietnamese original. Nothing is
  translated.

## What is collected

| Field | Source on the page |
|---|---|
| identity | `vgp-en:<id>`, the trailing digit run of the article path. The listing item's `data-id`, the URL it links and the article's canonical link must name the same id. It is never parsed for a date, and a title is never an identity. |
| canonical URL | `link[rel=canonical]`. A different id is a refusal; the same id at a different URL is kept as an anomaly. |
| title | `h1.detail-title[data-role=title]` inside `div.detail-mcontent` |
| lead | `h2.detail-sapo[data-role=sapo]` (`VGP - …`), stored on its own and as the first line of the text |
| publication time | `meta[property="article:published_time"]` in the offset it declares, with the UTC instant beside it. A stamp with no offset keeps its date and gets no instant; no offset is assumed. |
| modification time | `article:modified_time`, stored separately, never as the publication time |
| cross-checks | JSON-LD `datePublished` and the visible header (`… GMT+7`). A disagreement is recorded as an anomaly, never used as a substitute. |
| byline | `.detail-author-top-name`, cross-checked with JSON-LD. It is the page's byline, not an author, writer, translator or issuer. |
| body | the single `div.detail-content[data-role=content]`: paragraphs, headings, list items, quotations, table rows and figure captions in page order, each labelled with its element |
| category, tags | the breadcrumb category and the tag list, as metadata only |

**Excluded from the body:** the related-stories box (and its `data-date`
values), the CMS comment at its end, scripts, images and the tag list. Photo
credits stay inside captions as published.

**Characters.** Every character is kept as published, including the `./.`
end marker, no-break spaces and soft hyphens. Only the ASCII whitespace that
HTML itself collapses is collapsed, and no Unicode normalization is applied.
**Length.** A body is accepted on its structure, never on its length. A body
with no text but with images or embedded media is kept as `media_only`; a body
with neither is refused.

**Versions.** `content_sha256` (rule `vgp-en-content-v1`) covers the title, the
lead and the labelled blocks. An edit to any of them is a new version beside
the old one. A re-served page whose only changes are its sidebars or its
modification time is an observation, not a version. Duplicates never
overwrite.

## Retrieval, in the order it happens

1. `robots.txt` is read once per run, before anything else. A 404 or 410 means
   the host publishes no policy, so nothing is restricted. A 401 or 403, any
   other failure, or a 200 that is not a plain-text policy (an HTML page or a
   challenge) gives no permission basis, so nothing is collected.
2. Every request is checked against those rules first. A disallowed URL is not
   requested, and the refusal is a status.
3. The one tag page is read. Items come only from its
   `div.timeline > div.box-stream` stream; sidebar widgets never become
   references. Each item's day-first text time and month-first title time must
   agree. A window counts as covered only when the oldest listed item is older
   than the window start. Otherwise, or if the stream repeats, loops, is out of
   order or is truncated, the run fails whole with zero references. Older items
   load by script from `/timelinetags/…`, which the page never links, and that
   address is never requested.
4. More in-window items than the cap fails before any article is fetched, with
   every candidate URL recorded. Each article is fetched once: no redirects, no
   retries, no cookies, and no compressed replies.
5. Every page is screened first. A challenge on any status, a cookie gate, a
   non-UTF-8 or non-HTML body, an oversized or truncated document, or a page
   without the Government News frame is refused, and no document is produced.
   Whitespace and complete comments after `</html>` are accepted (the site
   appends a cache stamp); anything else is possible truncation.

Requests carry the full identity
`IndoPacificRecord-ShadowCollector/0.1 (+https://indopacificrecord.org; research archive; contact via site)`
with `Accept-Encoding: identity`. Spacing is at least two seconds from the end
of the previous request; a longer published `Crawl-delay` wins, and one over
120 seconds stops collection. Timeouts are 30 seconds.

## Isolation

- The manifest is under `shadow/`, so production discovery cannot find it.
  Tests assert that `desks/` gains no Vietnam manifest, that
  `load_all_desks()` has no `vietnam`, and that the production database has no
  source with desk `vietnam` or a `vn*` slug.
- State lives only in a separate checkout of `shadow/vietnam`. The runner
  refuses a state directory inside this worktree, the primary checkout, or
  behind a symlink.
- The fixtures are byte-exact copies of the 2026-10-06 UTC captures, pinned
  by SHA-256. `tests/fixtures/vn_vgp/.gitattributes` marks them binary. Never
  re-encode them. Failure cases are derived from the real bytes in memory and
  are never written back.

## Running the tests

```bash
.venv/bin/python -m unittest tests.test_vn_vgp_adapter tests.test_vietnam_shadow_runner tests.test_vietnam_shadow_review -v
```

`TestStateBranchRehearsal` runs the workflow's own shell steps against a local
bare remote, with a fixture-backed adapter. That covers bootstrap, two runs, a
refused divergent writer, a rewritten ledger or capture, and WAL sidecars.

## Local live rehearsal

This makes live requests to `en.baochinhphu.vn`. Write the request cap down
first: each run makes at most cap + 2 requests. Stop at the first failure, and
never repeat a refused or challenged request. **Leave at least a few seconds
between runs.** Spacing is enforced within a run, not across processes; the
2026-10-06 rehearsal recorded one gap under two seconds between back-to-back
runs. The commands below push only to a local bare remote.

```bash
REH=$(mktemp -d) && git init -q --bare "$REH/remote.git"
git init -q "$REH/s1" && git -C "$REH/s1" checkout -q --orphan shadow/vietnam
.venv/bin/python scripts/shadow_collect_vietnam.py --state-dir "$REH/s1/state" --target-date 2026-08-05 --lookback-days 0 --cap 4 --run-id local-1 --commit "$(git rev-parse HEAD)" --event-name workflow_dispatch
git -C "$REH/s1" add state && git -C "$REH/s1" commit -qm "shadow(vietnam): run local-1" && git -C "$REH/s1" push -q "$REH/remote.git" shadow/vietnam
```

For each later run, wait a few seconds, then clone fresh, run without a date
(today's UTC date, seven Ha Noi dates) or with the same historical date, and
push:

```bash
git clone -q --branch shadow/vietnam --single-branch "$REH/remote.git" "$REH/s2"
.venv/bin/python scripts/shadow_collect_vietnam.py --state-dir "$REH/s2/state" --lookback-days 6 --cap 4 --run-id local-2 --commit "$(git rev-parse HEAD)" --event-name workflow_dispatch
git -C "$REH/s2" add state && git -C "$REH/s2" commit -qm "shadow(vietnam): run local-2" && git -C "$REH/s2" push -q origin shadow/vietnam
```

`origin` in the second block is the local bare remote the clone came from.
Every successful run adds its own ledger, so each one commits. 2026-08-05 is a
date the tag lists two articles for, so that run retrieves bodies. A quiet current
window measures listing access only. The 2026-10-06 evidence came from a
scratch harness that ran the workflow's own shell steps around these same
runner calls (feasibility report §9).

## Shadow operation and recovery

The workflow runs the collector with `--lookback-days 6 --cap 40`: seven Ha
Noi calendar dates and at most 42 requests per run. Successful runs commit only
`state/`, with `shadow.db`, append-only `ledger/*.json`, write-once
`clock.json` and hash-named exact captures. It pushes without force; a
divergent remote fails the job. Failed collection pushes nothing, and the
complete attempt state and log stay as a 90-day Actions artifact. The
collector checkout must stay clean, and no historical ledger, capture or clock
may change. There is no analysis, rendering, Pages or promotion step.

Day zero is the first successful run's finish time, written once, so
`shadow_day` never moves with the target date. Recovery is **Run workflow →
target_date = the intended logical date**. An empty input uses the actual UTC
date. A scheduled first attempt (once one exists) uses the most recent 17:35
UTC slot, which is the Ha Noi date just ended. A UI re-run without a date is
refused. Recovery writes a new ledger and never edits a failed attempt's
evidence.

## Activation — Government News remains unapproved

PR #107's engineering implementation is merged; PR #114 prepares ministries.
The owner approves public shadow retention and one first ministry batch only,
not Government News. Do not dispatch `vietnam_shadow.yml` or create
`shadow/vietnam`. Government News's source-byte/public-retention question remains
separate because of the documented rights notice. The new shared Vietnam
identity above is verified offline only; it does not grant collection permission.
No Government News dispatch, schedule, production admission or promotion is
approved. Ministry budgets and the exact post-merge-only command are in
`docs/VIETNAM_REMOTE_ACTIVATION_PROPOSAL_2026-10-07.md`.

## Review path

Checkpoints are Day 7, 14 and 30 from day zero. Build each packet from a
named state commit, outside the repository. The clone below assumes the
state is public, as for the Philippines; use wherever the owner decides it
lives.

```bash
git clone -q --branch shadow/vietnam --single-branch https://github.com/VSSpowerlifting/China-Mil-Watch.git <state-clone>
.venv/bin/python scripts/review_vietnam_shadow_state.py --state-repo <state-clone> --state-commit <40-hex commit on shadow/vietnam> --checkpoint day-07 --as-of YYYY-MM-DD --out <directory outside the repository>
```

The packet holds record, capture and run inventories, every anomaly to
dispose of, late listings (items that appeared on the tag page after their
window was read) and an unfilled sign-off template. The same commit and
`--as-of` give byte-identical files. The kit refuses a commit not reachable
from `shadow/vietnam` and any state that is not Vietnam's. The reviewer
compares every record with its live page, then fills the sign-off:

```bash
.venv/bin/python scripts/review_vietnam_shadow_state.py --out <the packet directory> --check-signoff <filled signoff.json>
```

Preserving a completed sign-off is a separate, owner-approved step. There is
no Vietnam publisher, and Singapore's is not reused. Promotion requires 30
consecutive collecting days, the Day 7, 14 and 30 human reviews, the
applicable criteria in `docs/DESK_STRENGTH_CRITERIA.md` and an owner sign-off
in `DECISION_LOG.md`.

## Limits

- One tag on one newsroom's English edition, reaching 24 items back to
  2023-11-16. No archive completeness is claimed.
- Not measured live: recurring titles, accented names (the English text
  publishes names unaccented), short or image-only items and translator
  credits. Derived tests cover each.
- Open: Actions egress, multi-day reliability, reuse permission, collection
  health thresholds (calibrated only after shadow collection), and official
  routes to the ministry and the army newspaper.
