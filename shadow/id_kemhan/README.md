# Indonesia — Kemhan shadow candidate

Built at Ben's request on 2026-10-06; commit/PR and fresh durable shadow collection
were subsequently authorized in this chat (DECISION_LOG 2026-10-06). Not declared
publicly, promoted or part of production discovery. The manifest's enabled flag serves only
`scripts/shadow_collect_desk.py --desk indonesia`.

Scope: the ministry's [Berita institutional-news category](https://www.kemhan.go.id/category/berita)
and the HTML articles it links. This is ministry messaging, including ordinary
institutional activity; no relevance filter is applied. It is not comprehensive
Indonesian defense coverage, TNI command publication, or the separate Siaran Pers
press-release category. TNI's robots request timed out and supplies no permission
basis. Service websites, attachments, images and social media are excluded.

The collector identifies itself as
`IndoPacificRecord-ShadowCollector/0.1 (+https://indopacificrecord.org; research archive; contact via site)`.
It reads robots each run, obeys the most specific applicable group and Crawl-delay,
spaces requests at least two seconds apart, and uses no retries, cookies,
redirect following, browser identity, proxy or challenge solving.

Discovery follows only the listing's published next-page link, at most ten pages.
A seven-date window uses six lookback days. The complete selected window must fit
the 40-record cap; otherwise nothing is fetched. Listing drift, missing pagination,
loops, repeated identities or ordering defects are failures, never empty success.
Stopping below the window start establishes traversal of the dated listing, not
proof that the ministry published nothing outside it or never lists an item late.

Identity is the canonical dated article URL, never its title. The listing date,
URL date and article date must agree. Only the article container supplies text;
prose wrapped by malformed image tags is retained. Publication dates have day
precision. No UTC publication instant, issuing office, event date, translation
or analytical claim is inferred. Raw response bytes and their request provenance
are preserved separately from extracted text.

Two live rehearsals on 2026-10-06 passed: one current-date record; then all 14
selected records for 2026-09-30 through 2026-10-06 (17 responses: robots, two
listings, fourteen articles). Those rehearsal states remain in temporary
directories. A separate fresh authorized run from collector `5ddca377e` stored
14 records on `shadow/indonesia-kemhan` at `8e9ee2e8`; a clean remote clone and
pinned integrity packet verified every state-file hash with zero machine findings.
The launch receipt records the durable first-success clock and verification.

The initial durable collection ran locally from the immutable collector commit.
PR #110 subsequently merged the manual workflow. Its bounded October 6 Actions
run retrieved/extracted all 14 records as duplicates, with zero failures, and
published state `9fe9f6fd`. Fresh remote-clone and artifact comparisons verified
all original rows, captures, ledgers and the first-success clock unchanged.
The workflow uses `shadow/indonesia-kemhan`. Ben authorized daily 17:17 UTC
shadow collection with six lookback days and cap forty; activation awaits separate
owner merge of the cadence PR. Scheduled missing state/clock is fatal. Rehearsal clocks
are not transferred. Failed batches write
attempt evidence but no partial corpus and are not pushed. Stored original-text
changes are refused pending human disposition. State never merges to main.

Checkpoint packets are produced by `scripts/review_desk_shadow.py`. Days 7, 14
and 30 still require actual human source comparisons and durable sign-off; the
machine packet supplies none. Scheduled continuity, long-term
extraction reliability, reuse terms and cadence/silence thresholds remain
unmeasured or unresolved. No promotion or qualification follows from this build.

Full procedure and reusable prompt:
`docs/INDONESIA_KOREA_DESK_EXECUTION_2026-10-06.md` and
`docs/INDONESIA_KOREA_DESK_EXECUTION_PROMPT.md`; durable state receipt:
`docs/INDONESIA_KOREA_SHADOW_LAUNCH_2026-10-06.md`. The bounded Actions egress
and persistence check is in `docs/INDONESIA_KOREA_ACTIONS_VERIFICATION_2026-10-06.md`;
it establishes one main-hosted run, not future access or periodic reliability.
