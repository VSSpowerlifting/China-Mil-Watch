# Philippines — AFP shadow collector

**Status: scheduled shadow reliability evaluation. Not production.**
Owner authorization is recorded in `DECISION_LOG.md` (2026-10-06). **Activation
is pending the scheduling PR's separate reviewed merge; no AFP cron is live yet.**
The manifest is outside `desks/`, with source `enabled: true` for shadow collection
and desk `active: false`. Production discovery, DB, rendered site and deployment
are untouched; no public Philippines coverage or qualification is implied.

The proposed `.github/workflows/ph_afp_shadow.yml` accepts exactly two events:

| Event | Collection | State publication | Clock |
|---|---|---|---|
| `schedule`, daily `40 6 * * *` (06:40 UTC) | Normal eligible 14-day window, cap 100, existing 14-day revision watch | Automatic after collection success and completed-attempt verification | Only complete normal success is eligible |
| `workflow_dispatch` | Rehearsal, at most two recent bodies, same complete listing | Artifact-only by default; explicit `publish_state=true` opts in after success/verification | Never starts or advances collecting days |

The scheduled invocation passes `--event-name schedule --cron-utc "06:40"`
through the existing shared logical-date resolver; YAML duplicates no date logic.
Manual target-date input remains optional. An undated rerun is refused, rather
than assigned a new logical date. A manual dispatch remains a rehearsal even
with explicit state publication; it is not a normal recovery/backfill mode.
The first scheduled run may initialize the orphan `shadow/ph-afp` branch.
No 1,090-record historical body backfill is part of activation.

Both modes inspect fresh policy and reconcile the full terminal listing. Successful
scheduled collection retrieves the entire eligible window subject to the visible
cap; manual sampling records `sample_unselected`. Every attempt preserves evidence
in a 90-day artifact. Failed/partial collection or failed verification prevents
state publication; existing durable state stays unchanged and failure artifacts
remain inspectable. Publication is explicit, non-force and confined to `state/`
on `shadow/ph-afp`; a divergent writer fails. No branch or clock is initialized
merely by merging source. No AFP durable branch existed at the reviewed rehearsal.

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
No contact route is invented. Actions rehearsal `37527985057` accepted this
identity on October 6. The earlier retained offline replay captures used the
previous China Mil Watch shadow identity; they are separate measurements.

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
be pushed. Completed partial/failure evidence remains in artifacts while the job reports
failure; it is not published into durable state. Publication uses a non-force explicit state ref; a
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

## Live rehearsal and activation gate

[Actions run 37527985057](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37527985057)
on merged collector `cc8d36646af1e2eb6026a17eaefd20378585faac` succeeded:
1,090 unique listing rows over eleven pages with terminal reconciliation,
two bodies requested/retrieved (`afp:1398`, `afp:1397`), no challenge, access,
extraction or identity/date mismatch. Fresh www robots returned HTTP 200/Allow;
API robots matched the reviewed 404 and `noindex, nofollow` indexing header.
Exact captures and the completed ledger are in
[artifact 11442459154](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37527985057/artifacts/11442459154).
State publication was disabled and `shadow_day` was null. The detailed reviewed
checkpoint is [AFP Actions gate](../../docs/AFP_ACTIONS_GATE_2026-10-06.md).
These measurements make no full-window body or historical completeness claim.

The owner has reviewed that live evidence and authorized recurring shadow
collection, isolated state and the scheduling PR. After clean exact-head CI,
report for a separate merge authorization. Do not merge or dispatch another live
run during this implementation step. Until the scheduling PR merges, default
main still exposes only the prior manual rehearsal workflow.

## Scheduling verification

The focused AFP suite passes 238 tests, including execution of the actual YAML
collection/bootstrap/publication shell blocks against original-payload fixtures
and a local bare remote. It checks cron-aware date resolution, normal-window
selection, failed/partial nonpublication and clock preservation, safe manual
modes, exact cron, isolated refs and divergent writers. Local validation passes
with the ten governed warnings; tracked DB/output/desks and DB sidecars are
unchanged. The PR must also pass the full offline suite and validator on its
exact final head before a separate merge authorization.

## Seven-day reliability and human review

After activation, require seven consecutive terminal-successful **scheduled**
logical collection days, inspected through event provenance and ledgers rather
than elapsed clock age. Listing reconciliation, access policy, truncation,
identity/date failures and state history must have no unresolved failures.
Artifacts and ledgers must be available; only verified complete successful runs
may advance the state branch. A proven quiet window is not a failed day.

During those days, manually inspect every newly inserted record if five or fewer
are inserted, otherwise at least five representative new records. Keep durable
review evidence tied to run, collector commit, source IDs and capture hashes,
covering title fidelity, publisher date, body extraction, canonical/requested URL,
identity, provenance, and absence of site furniture or invented text. Scheduling
a collection does not perform or substitute for this human review.

After seven days, produce a new readiness assessment covering reliability,
human reviews, NSC supplementation, whether AFP + NSC provides sufficient breadth,
another first-party Philippine source, and whether historical backfill should
precede production activation. No automatic graduation: standing qualification
and owner sign-off gates remain. NSC does not fill missing AFP bodies. Japan
source coverage is a separate task.
