# South Korea — Policy Briefing shadow candidate

Built at Ben's request on 2026-10-06; commit/PR and fresh durable shadow collection
were subsequently authorized in this chat (DECISION_LOG 2026-10-06). Not publicly
declared, promoted or part of production discovery. `--desk korea` means South Korea, not North
Korea. Source enablement applies only to the isolated runner.

Direct MND publication access is blocked by the ministry's
[robots policy](https://www.mnd.go.kr/robots.txt): it disallows `/` while allowing
the root and `/mnd/index.do`. No publication page, English release, RSS endpoint
or alternate MND hostname was requested to evade that rule.

The seed is a separate source: the government
[Policy Briefing press-release portal](https://www.korea.kr/briefing/pressReleaseList.do),
under [its own permitting robots policy](https://www.korea.kr/robots.txt).
Its published POST form provides an explicit `A00005` / `국방부` ministry filter.
The collector validates the returned filter, source labels, dates, declared
result count and published pagination controls. Other issuers are refused.

Publisher: `대한민국 정책브리핑`. Issuer: the page's explicit `국방부` label.
The page expressly identifies republication. This Tier B government-republished
source is not direct MND-site retrieval, a complete MND release wire, a peer of
the mature China collection, independent corroboration, or coverage of the Joint
Chiefs and armed services. Any future DAPA source needs its own scope and
measurement; its permitting robots file alone establishes no collector.

Observed release pages contain document-viewer iframes, not release body text.
The adapter reads the single HWPX attachment the page actually links on the same
permitted portal. Both HTML and document bytes are preserved. Bounded ZIP/XML
extraction retains original Korean text in document XML paragraph order, including
tables; that order is not proof of visual reading order. Human comparison with
the original document remains necessary. The viewer, metadata descriptions,
listing previews and republication notice never substitute for body text.
HWP, PDF, HTML-only and multiple-HWPX variants are unsupported and fail explicitly.

Identity is the portal's canonical `newsId`, never the title. The portal posting
date stays a day-precision date. The attachment may carry an earlier distribution
or event date; it remains original text and does not replace the portal date.
No timestamp, issuing unit, translation or analytical assertion is inferred.

Access uses the same full project identity and bounded transport as Indonesia.
At most ten listing pages and forty releases are admitted: at most 91 responses
including robots, listings, release HTML and one document per release. A refusal
stops the batch; a cap breach does not truncate it into a sample.

Live rehearsals on 2026-10-06 passed for one current-date release, then all four
selected releases for 2026-09-30 through 2026-10-06 (10 responses: robots, one
listing, four pages, four documents). These are temporary-state measurements.
A separate fresh authorized run from collector `5ddca377e` stored four releases
on `shadow/korea-policy-briefing` at `bbe2c8a2`; a clean remote clone and pinned
integrity packet verified every state-file hash with zero machine findings.
No scheduled evaluation interval follows. Multi-day reliability,
visual/document extraction review, historical completeness, reuse terms and
cadence thresholds remain open.

The initial durable collection ran locally from the immutable collector commit.
After PR #110 merged, one bounded October 6 Actions run retrieved/extracted all
four releases as duplicates, with zero failures, and published state `a1088ea1`.
Fresh remote-clone and artifact comparisons verified all original rows, captures,
ledgers and the first-success clock unchanged. The manual workflow uses
`shadow/korea-policy-briefing` and enables no cron. Checkpoints use
the new reviewer, require actual human comparisons/sign-off, and qualify nothing
automatically. No rehearsal state or clock is transferred into durable state.

Procedure and reusable prompt are in the two Indonesia/Korea execution documents.
The durable first-success clock, published commit and verification are in
`docs/INDONESIA_KOREA_SHADOW_LAUNCH_2026-10-06.md`. The bounded Actions egress
and persistence check is in `docs/INDONESIA_KOREA_ACTIONS_VERIFICATION_2026-10-06.md`;
it establishes one main-hosted run, not future access or periodic reliability.
