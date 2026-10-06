# Philippines — AFP shadow collector

**Prepared for review, disabled and unscheduled.** No production desk, public
coverage or graduation is implied. `shadow/ph_afp/manifest.json` is outside
`desks/`, with source `enabled: false` and desk `active: false`. The normal CLI
refuses that disabled source before requests or state creation. Offline tests
inject an adapter; they do not activate the manifest.

The manual `.github/workflows/ph_afp_shadow.yml` runs only on
`workflow_dispatch`, on GitHub-hosted Ubuntu. It has **no cron** and has not
run in Actions. Normal collection remains manifest-disabled; an explicit
manual `--rehearsal` permits at most two samples from a window of at most
14 days. Discovery still walks the entire listing and reconciles its terminal
count. The ledger distinguishes discovered, selected and sample-unselected
items. This sample cannot start or advance the reliability clock and makes
no complete-window retrieval claim. An empty recent window fails because
article egress remains unverified.

`publish_state` defaults to **false**: evidence stays in external temporary
state and a 90-day Actions artifact. Selecting true permits verified public
state publication only to `shadow/ph-afp`, with append-only, non-force history.
No AFP state branch or day zero has been established by this integration.

## Source and scope

AFP is the preferred Philippine anchor candidate. It is the Armed Forces of
the Philippines publishing through its Public Affairs Office on its official
website, a Tier A first-party source. It does not represent DND, the Philippine
Coast Guard, NSC, or comprehensive Philippine defense publication. NSC remains
an independently attributed supplemental source with its existing workflow.
No additional Philippine institution is added here.

The official frontend `www.afp.mil.ph` is a single-page application; its own
public backend `api.afp.mil.ph` provides article JSON. Discovery walks
`/articles/?page_size=100&page=1`, then the returned `next` links. It must reach
explicit `next: null` with a stable count matching every listed row. The
40-page bound, loops, repeated content/identities/slugs, missing/failed pages,
malformed pagination, changing counts and off-host links all fail visibly.
A collection window exceeding the article cap also fails before article
requests; it cannot become a truncated successful window. The count is read
from the source, never hard-coded to a prior measurement.

Only categories `news-blog` and `uncategorised` are admitted. Other categories
have explicit rejection counters; no relevance filter is applied. Malformed
listing identity/title/date metadata fails discovery with reason counters,
because it leaves the window unproven. A new category needs review.
API identity is `afp:<integer>`;
detail id and slug must agree with discovery. Different ids with identical
titles/dates or text stay separate, with duplicate groups disclosed.

Reader URLs are the site's own `/news/<slug>` route, reconstructed from the
slug. Requested and final API URLs are separately preserved. Publisher
`published_at` needs an explicit UTC offset: its local date, original timestamp
and derived UTC instant are retained. No retrieval date or migration timestamp
is substituted for it. Listing/detail date disagreement is disclosed.

Extraction deterministically combines `intro_html` and `body_html`, preserving
migrated split introductions and removing observed field overlap. Empty/image-
only items are explicit `no_text` metadata records; no image transcription or
inferred body is supplied. Tests cover both publishing eras and malformed HTML
field types. Full-body adequacy still requires human sampling.

## Access and preserved evidence

The owner-approved collector identity is:
`IndoPacificRecord-ShadowCollector/0.1 (+https://indopacificrecord.org/about.html; research archive collector; contact via site)`.
The canonical domain is in `README.md`/`PROJECT_STATE.md`; the existing About
page exposes the maintainer email from `site/preview/generate_preview.py`.
No contact route is invented. This new identity has been tested offline;
its live Actions acceptance remains unverified. The October 6 original
captures used the previous China Mil Watch shadow identity.

Direct official infrastructure only: the HTTP session disables environment
proxy inheritance and clears session proxies. No proxy, alternate egress,
CAPTCHA solving or WAF workaround is permitted.
Requests are single-worker, at least two seconds apart. Both hosts' current
robots policies are read on each discovery. Supported integer crawl delays
increase spacing; unreadable/nontext/oversized/invalid-UTF-8 policy and unsupported
patterns/delays stop collection. Named-agent groups use longest matching agent
specificity, applicable groups combine, longest path wins and Allow wins ties.
An observed 404/410 is recorded as absent policy, distinct from refusal.

Every requested article path and redirect destination is checked. HTTP clients
never auto-follow redirects. Explicit challenges, recognizable HTML challenge
pages including HTTP 200, and 401/403 stop further requests; no bypass,
impersonation or alternate identity is attempted. Transport errors have bounded
retries. API `X-Robots-Tag: noindex, nofollow` is preserved as an indexing
signal. Ben approved first-party API use for shadow evaluation on October 6.
The manifest pins the reviewed robots response status/hash and API indexing
header. Fresh policy is fetched every run; any difference stops for owner
review before collection proceeds. This deliberately includes harmless byte
changes rather than guessing which changes are material. Approved baselines
must only change after reviewing retained new evidence.

Every completed attempt appends `evidence/<run-id>.json` request receipts.
Bounded policy/listing originals and small refusal responses are retained by
SHA-256 under `evidence/payloads/`. Successful new/revised article payloads
are exact UTF-8 bytes in the SQLite `captures` table, with requested/final URLs,
HTTP status, content type and retrieval time. Duplicate article reads have
receipts; unchanged detail bytes are not stored again as a new revision.
Oversized responses have hashes and size receipts, without retained payloads.
Failed discovery leaves the corpus unchanged while appending attempt evidence.

## Isolation and durable state

The runner `scripts/shadow_collect_ph.py` refuses state under any checkout of
this repository, internal symlinks, unsafe attempt ids and reused attempt ids.
It never names a production path in executable code and is not called by the
production pipeline or a renderer. State layout:

```
state/shadow.db                    first-seen records, captures, revisions
state/clock.json                   first clean-run clock, written once
state/ledger/<timestamp>-<id>.json  one completed attempt, exclusive write
state/evidence/<id>.json           identified request receipts, exclusive write
state/evidence/payloads/<sha>.bin   exact bounded policy/listing/error payloads
```

First-seen records and existing captures/revisions are immutable. Changed
publisher content adds a new capture and linked revision rather than replacing
an original. View-count changes alone are not revisions. Held older records
are skipped outside the revision watch window, which is disclosed in the ledger.
This is a prospective evaluation, not automatic full-history backfill.

Only a clean complete ongoing collection run starts/reports the success clock.
A rehearsal never starts/reports a collecting day, even when all samples succeed. Partial retrieval,
extraction failure, collision, redirect refusal, challenge or incomplete listing
exits nonzero and does not advance it. Elapsed days alone are never proof of
consecutive successful collecting dates or qualification.

When publication is selected, the workflow uses a separate orphan `shadow/ph-afp` checkout outside
the collector. Only an absent remote ref permits bootstrap; network/auth
failure stops. Before collection it hashes historical files and database rows.
`scripts/check_ph_afp_state.py` then requires exactly one completed attempt,
correct collector/attempt identity, old-file and old-row preservation, capture
payload hashes, original request payloads, the closed DB hash, valid clock
behavior and no sidecars/unexpected files. A crash or failed verification cannot
be pushed. Completed partial/failure evidence can be preserved while the job
still reports failure. Publication uses a non-force explicit state ref; a
competing writer is rejected. Artifacts retain the failed attempt too.

## Verification and remaining gates

The integration receipt is [AFP shadow integration](../../docs/AFP_SHADOW_INTEGRATION_2026-10-06.md).
All 15 raw responses from the identified October 6 rehearsal are retained in
`tests/fixtures/ph_afp/live_20261006/`, with dated request receipts and hashes.
Offline replay verifies the complete 1,088-row, 11-page walk and the two sampled
recent bodies (1,481 and 1,291 characters). This is captured evidence from that
measurement, not a new live run or a full-corpus extraction claim. The listing has no 2025 rows and no rows dated November 1, 2024 through
June 11, 2026; these are observed archive gaps, not institutional silence.
Historical API timestamps may reflect migration; they do not independently
verify original publication dates. Older fixtures
are from the September 26 pilot. Its discarded scratch-corpus counts remain
producer-reported/unverified in
[PR #79's historical receipt](https://github.com/VSSpowerlifting/China-Mil-Watch/blob/b29e7edb047c30c8b878bca0069ba183424e2478/docs/AFP_PR79_OFFLINE_REPAIR_2026-10-01.md).

Ben's October 6 decisions authorize direct API shadow evaluation, the honest
IPR contact identity and public isolated state. Recurring collection and
production remain unapproved. The required sequence is:

`review draft PR → explicitly authorize and merge shadow-only plumbing → manually dispatch rehearsal → inspect evidence → separately decide whether to enable recurring schedule`

[GitHub requires the dispatch workflow on the default branch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Do not attempt to dispatch this unmerged branch or merge merely to force a run.
After the reviewed merge is explicitly authorized and completed, run:

```bash
gh workflow run ph_afp_shadow.yml --ref main -f publish_state=false
```

An older logical slot requires `-f target_date=YYYY-MM-DD`; an undated UI rerun
is refused. The workflow fixes two samples and a 14-day lookback; it cannot
request full historical article retrieval. Inspect both robots originals and
API headers, complete listing/count reconciliation, sample identities/dates,
exact payload hashes and captures, the finished ledger and immutable-history
verification. Failed/incomplete attempts remain failures, including when their
evidence is preserved. Artifacts must contain no credentials. No outreach is
authorized or sent by this work.

Graduation additionally needs a sustained reliability interval, substantive
AFP body sampling, publication-date/migration assessment, checkpoint review
tooling for the Philippines, completed human checkpoints and an owner ruling
in `DECISION_LOG.md`. NSC supplementation does not fill missing AFP bodies.
DND/Coast Guard scope expansion is deferred until AFP has reliability evidence.
