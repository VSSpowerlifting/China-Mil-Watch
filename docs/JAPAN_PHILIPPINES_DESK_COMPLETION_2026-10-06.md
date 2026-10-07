# Japan and Philippines desk completion assessment

Measured 2026-10-06, 04:50–04:57 UTC (00:50–00:57 EDT). **Neither desk can
graduate on this evidence.** Japan discovers substantially more than it can
read. AFP is a promising Philippines anchor, but its existing pilot is still
draft, unscheduled and unqualified; NSC alone is insufficient.

## Evidence and scope

Assigned worktree: `/Users/benjaminyang/.codex/worktrees/3b8d/pla-watch`.
Origin: `VSSpowerlifting/China-Mil-Watch`; clean detached base and live main
both `a259ee6d2e42d90ade1cb0b51fab41a71ce3b430`. Work is now on
`codex/jp-ph-desk-assessment-20261006`. Existing worktrees and open PRs were
inspected before editing; no other worktree or PR branch was changed.

Authoritative remote evidence fetched for this assessment:

| Evidence | Immutable locator | Observation |
|---|---|---|
| Japan state | [`e890112`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/e890112aacc7b9eaa85db4179fef4aedeba81b2b) | 43 ledgers, 5 bodies, 149 outstanding gaps |
| Japan latest Actions run | [37404326269](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37404326269) | success; collector `9bf842f2d`; logical target **October 5**, execution October 6 UTC |
| NSC state | [`05e7f97`](https://github.com/VSSpowerlifting/China-Mil-Watch/commit/05e7f9780ef330d0493f8b7ccf0de67306112b0e) | 4 healthy quiet-window ledgers, 0 bodies |
| NSC latest Actions run | [37362237368](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37362237368) | success; target October 5; six visible statements, newest July 8 |
| AFP existing pilot | [PR #79](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/79), head `b29e7edb047c30c8b878bca0069ba183424e2478` | open, draft, conflicting with main; historical offline CI success is not current merge validation |

The [evidence JSON](research/jp-ph-desk-assessment-20261006/evidence.json)
retains the latest ledgers, state-chain audit, identified request receipts,
capture hashes, distinct-URL inventories and AFP rehearsal results. Exact RSS
bytes, AFP robots responses and two AFP article JSON captures are retained
beside it, with text normalization disabled. Intermediate AFP listing pages
have dated request hashes, but their payloads are not retained in this packet;
the 1,088-item count is an observed live walk, not a retained full-corpus replay.
State was exported to `/tmp` from the named commits and opened read-only.

All first-party probes used the existing full
`ChinaMilWatch-ShadowCollector/0.1 (+https://chinamilwatch.org; research archive; contact via site)`
identity. No browser impersonation, TLS verification disabling, URL enumeration,
challenge solving, alternate identity, state push or production collection.
This task authorizes bounded assessment; it does not settle scheduled AFP
identity, reuse conditions, promotion or outreach. NSC was assessed from its
current Actions state and earlier retained rehearsal, without new NSC probes.

## Japan findings

Only `jp_mod_news_ja` ([news RSS](https://www.mod.go.jp/j/rss/news.xml)) and
`jp_mod_siteupdate_ja` ([update RSS](https://www.mod.go.jp/j/rss/update.xml))
are collected. Both are Japanese. Joint Staff and English MOD sources are
explicitly disabled/not collected. The update feed includes procurement,
profiles, policy and other site revisions; it is not a release wire.

The captured news feed has 167 entries but **164 distinct URLs** (12 PDF,
152 non-PDF); the update feed has 243 entries but **106 distinct URLs**, all
non-PDF. First URL observation wins, matching the existing adapter. Neither
contains `/js/` or `/en/` URLs. Raw entry counts cannot be treated as numbers
of distinct publications.

For the explicit **September 22–October 5 inclusive RSS-date window**:

| Feed | Distinct URLs | PDF candidates | Stored usable bodies | Outstanding outcomes |
|---|---:|---:|---:|---|
| News | 34 | 3 | 1 (2.94%) | 31 access challenges, 1 oversized PDF, 1 PDF without a text layer |
| Site updates | 33 | 0 | 0 (0%) | 33 access challenges |
| Combined, distinct across feeds | 67 | 3 | 1 (**1.49%**) | 66 without usable bodies |

The sole recent stored body is the October 5 PDF
[`05b.pdf`](https://www.mod.go.jp/j/press/news/2026/10/05b.pdf), 580 extracted
characters. These are **observed archived-body shares**, not an estimate of
all MOD publication, not proof of complete PDF text, and not a fresh fetch of
every listed URL. Non-PDF bodies are intentionally withheld under the existing
challenge rule. The latest scheduled run selected 17, retrieved 3, inserted 1,
reported 1 fetch/size failure and 2 extraction failures, and remained `partial`.
The complete state has 146 challenges, 1 size refusal and 2 text-layer failures.

The offline inventory uses the preserved feed bytes and read-only state.
Its whole-feed denominator includes **116 pre-bootstrap URLs**;
those are recorded history, not attempted retrieval failures. Off-feed gaps
remain in the separate outstanding-gap total. PDF candidacy is not a body.
URL-family labels are diagnostics, not claims about a document's substance.

**Dates remain blocked.** Of 160 news-feed URLs with a valid date in the
measured URL forms, 57 disagree with RSS `pubDate` (**35.63%**). For example,
`/j/press/news/2026/10/03d.html` carries October 3 in its URL and October 5 in
RSS. A URL date is only another hint; neither hint may be silently promoted to
verified publication date. Existing records currently use RSS dates. Preserve
both observations, inspect retrievable document datelines, then establish an
explicit rule and discrepancy reporting before production. This change does
not rewrite dates or historical admission decisions.

**No compliant Joint Staff discovery improvement was established.** The
identified client received HTTP 403 with `Cf-Mitigated: challenge` from the
official [Japanese Joint Staff index](https://www.mod.go.jp/js/press/index.html).
English MOD's [release index](https://www.mod.go.jp/en/press-release/) returned
the same challenge. Official search results can surface Joint Staff pages;
that is a lead, not proof that this collector can retrieve their listing.
They were not used as a replacement collection feed or a challenge workaround.
The prior [September 16 feasibility assessment](DESK_RELIABILITY_REVIEW_2026-09-16.md#4-japan--source-feasibility-matrix)
found a served Joint Staff PDF but no usable discovery index, challenged
Joint Staff RSS/sitemaps, and absent English RSS. Those observations are dated,
not universal claims that no other official route exists. No new feed or
structured endpoint advertised by the institution was established here.
Guessing PDF filenames, using search caches as an archive, or fetching an
alternate host to evade refusal is not an acceptable adapter.

**Japanese-language coverage can be sufficient in principle.** This is an
inference from the publication's original-language doctrine, not a new owner
ruling. English duplication is not a mandatory gate. Substantive institution
coverage is: missing Joint Staff operational publication and unarchived
ministerial HTML are material limitations regardless of language. An owner
may consider a specifically bounded public product later; the currently
declared ministry scope fails C4 in `DESK_STRENGTH_CRITERIA.md`. An accurately
disclosed low-yield PDF subset does not itself satisfy that gate.

Both state hash chains are coherent and current DB hashes match the last
ledger. Japan's apparent uninterrupted target-date set does **not** dispose
of its historical scheduling anomaly: pre-fix execution-dated ledgers cannot
prove their nominal slots. The recorded nominal September 2 gap and duplicate
target dates still need explicit review. No checkpoint completion was found.

**Material compliance defect found in code:** at the inspected base,
`scripts/shadow_collect_japan.py` hard-coded `robots_status = "allowed"`, and
the adapter's `assert_robots_allows()` had no runtime caller. Therefore the
historical ledger labels do not prove policy was read or obeyed on those runs.
The identified audit request does establish that policy allowed the assessed
paths at its measurement time. It cannot validate earlier dates. Live enforcement
is this session's selected repair; historical C2 evidence remains unproven.
A later bounded rehearsal of the repaired code at **13:42–13:43 UTC** read the
policy (same 48-byte hash), discovered 165 news URLs and fetched/extracted the
already-listed October 5 PDF (580 characters). It wrote no collector state.
The feed had gained a URL since the initial inventory; the earlier snapshot's
denominators are deliberately not replaced with a later feed.

## Philippines findings

**Continue PR #79, do not replace it.** It contains an AFP adapter, isolated
runner, disabled `shadow/ph_afp/manifest.json`, real fixtures and offline tests.
It walks the site's own public `api.afp.mil.ph/articles/` JSON pagination to
explicit `next: null`, reconciles counts, rejects repeated identities/slugs
and malformed pagination, checks both hosts' robots policy and every redirect,
and stops on challenges including recognizable HTTP-200 interstitials.
Identity is integer `afp:<id>`, cross-checked with the detail slug. Offset-bearing
publisher dates, exact detail bytes, content/capture hashes and provenance are
preserved; revisions are logged, not silently overwritten. Image-only items
remain explicitly text unavailable. There is no AFP workflow or state branch.
Its historical scratch-corpus body claims remain producer-reported; the
discarded corpus was not recreated or validated in this assessment.

**Bounded current AFP compatibility passed.** Existing PR code, loaded without
its runner, read `www.afp.mil.ph/robots.txt` (200, allow-all) and API robots
(404, absent policy), walked 11 pages to terminal `next: null`, and reconciled
**1,088** rows with the API count. API `noindex, nofollow` was retained as an
indexing directive and unresolved owner policy consideration. The September
22–October 6 inclusive window contained 11 eligible references; two newest
samples, `afp:1396` and `afp:1395`, fetched/extracted successfully with 1,481
and 1,291 characters, respectively. Exact response bytes are retained. This
does not measure full-corpus extraction, Actions article egress, periodic
access, proxy equivalence, reuse rights or sustained reliability.

The observed listing has 27 rows dated September 7–October 6, no 2025 rows,
and none dated November 1, 2024–June 11, 2026. These are **listing gaps**, not
evidence of institutional silence. Older publisher dates carry the migration
limitations already documented in PR #79. Cross-id identical text and recurring
titles require provenance-aware duplicate reporting, not title deduplication.

| Institution | Current evidence | Role / disposition |
|---|---|---|
| AFP | Successful identified listing and two bodies; substantial existing pilot | Preferred anchor candidate; still needs scheduled evaluation and reviews |
| NSC | Four healthy scheduled quiet windows; six listed items, June 3–July 8; 0 stored bodies | Narrow policy/statement supplement; not a substantive anchor alone |
| DND | Current robots request failed TLS verification; prior September 26 probe reported a challenge | No current policy basis; no content request or adapter justified |
| Philippine Coast Guard | Current robots request 403, `Cf-Mitigated: challenge` | Access blocked; no content request or adapter justified |

**Recommended portfolio is AFP plus NSC initially**, with distinct institutional
attribution and cross-source occurrence retained. This is an assessment, not
activation approval. DND would add ministry policy and PCG maritime enforcement
if compliant official routes become available. They must not be filled with
secondary reposts presented as institution-authored records. No minimum source
count is invented: evaluate whether the resulting stored corpus represents the
scope, rather than assuming two institutions make a strong desk. NSC's shared
site byline must not be misrepresented as the issuing office.

PR #79's next integration work is resolving its conflict with **current main**
while preserving unrelated work, then validating that exact combined head.
Do not merge or schedule it on the old CI result. Draft [PR #99](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/99)
separately repairs NSC handling of parser-rejected markup; this task does not
duplicate its implementation. AFP/NSC robots harmonization and attribution
integration belong after the existing AFP pilot is integrated and reviewed.

## Graduation checklist

PASS means demonstrated within the stated scope; PARTIAL means bounded or
incomplete evidence; BLOCKED means a material failed prerequisite; NOT STARTED
means no implementation, review or authorization was established. A desk-wide
PARTIAL must not be rounded up from one source's PASS.

| Gate | Japan | Philippines | Exact remaining evidence or action |
|---|---|---|---|
| Declared-source discovery stable | PASS | PARTIAL | Japan's two feeds work; AFP only bounded live, NSC only four days |
| Current robots/access-policy enforcement | PARTIAL | PARTIAL | Japan repaired locally; historical labels unproven; AFP/NSC code gates plus bounded live evidence, no portfolio interval |
| Credible source breadth | BLOCKED | PARTIAL | Japan operational/ministry body gap; Philippines assess AFP+NSC stored substance |
| Full-text retrieval | BLOCKED | PARTIAL | Japan 1/67 recent bodies; AFP two live samples, NSC no Actions bodies |
| Extraction stable | PARTIAL | PARTIAL | Human body checks and sustained served-family evidence; distinguish images/scans |
| Provenance preserved | PARTIAL | PARTIAL | Japan retains PDF hashes but **not original bytes**; AFP/NSC preserve bytes in code but sustained corpus evidence absent |
| Duplicate handling verified | PASS | PARTIAL | Japan URL uniqueness/hash retention tested; AFP cross-id and cross-institution occurrence still needs portfolio review |
| Publication dates reliable | BLOCKED | PARTIAL | Japan conflict rule; Philippines migration and historical completeness review |
| Scheduled workflow healthy | PARTIAL | PARTIAL | Japan persistent partial health; AFP unscheduled, NSC only quiet windows |
| Bootstrap/history explicit | PARTIAL | PARTIAL | Japan RSS/date cutoff uncertainty; AFP migration/gaps, NSC pre-June completeness unknown |
| Known access gaps documented | PASS | PARTIAL | Japan explicit gap rows; AFP policy/reuse and broader Philippines scope remain open |
| 30 consecutive collecting days | BLOCKED | NOT STARTED | Japan needs a fresh policy-observed interval and scope retrieval; Philippines has no portfolio reliability interval |
| Desk-specific review tooling | NOT STARTED | NOT STARTED | Build provenance-verified desk-specific packets; do not borrow Singapore assumptions |
| Human Day 7/14/30 reviews | NOT STARTED | NOT STARTED | Actual analyst review, honest completion dates, preserved receipts and anomaly dispositions |
| Production manifest ready | NOT STARTED | NOT STARTED | Only after source scope and admission are ruled; retain shadow manifests now |
| Production DB integration | NOT STARTED | NOT STARTED | Reviewed mapping, capture/provenance and revision semantics; no shadow-state merge |
| Desk-scoped processing/analysis | NOT STARTED | NOT STARTED | Review relevance and downstream processing before admission; avoid applying China-only assumptions |
| Public site integration | PARTIAL | NOT STARTED | Japan has a shadow-only page; production disclosure/body distinctions still absent; Philippines not declared |
| Tests added/passing | PASS | PARTIAL | Local source/collector/full-suite checks pass; exact AFP combined-head checks remain pending |
| Activation separately authorized | NOT STARTED | NOT STARTED | Owner graduation ruling in DECISION_LOG, after the other gates; no automatic promotion |

## Selected implementation and verification

The highest-value safely resolvable defect is **Japan's missing live access-policy
gate**, rather than production plumbing. `scraper/sources/jp_mod.py` now reads
current robots policy before requesting feeds or PDFs; the runner shares that
observation across the two same-host sources for a run. It caches refusals as
well, so another source cannot retry the host's refusal. Named-agent groups use
longest agent specificity, applicable groups combine, longest path wins and
Allow wins equal specificity. Unsupported wildcard/end-anchor patterns and
non-integer crawl delays conservatively stop collection. Valid integer crawl
delays are observed. A new adapter/run obtains a fresh policy, never old rules.

Policy challenges, 401/403, transport errors, redirects, oversized/non-text
policy and unrecognized policy stop feed/body requests. A genuinely observed
404/410 is recorded as `absent`, not as refusal; an observed empty plain-text
policy has no restrictions. Every actual feed/PDF path is checked. Automatic
redirect following is disabled, so an unchecked destination is never requested.
The additional policy request and spacing are the intentional transport changes;
the user agent and per-source 40-item cap remain unchanged.

`scripts/shadow_collect_japan.py` records the actual per-source robots status,
HTTP status, retrieval time, payload hash and readable policy text. Policy refusal
produces `health: fail`, a typed result, a nonzero CLI exit and no successful-run
clock advance. The already-existing workflow can preserve the completed failed
attempt's ledger while keeping the job failed. Existing HTML challenge-gap
handling and ordinary partial PDF runs keep their prior semantics.

No dates, extraction, source enablement, schema, historical ledger, clock, shadow
state, production DB, manifest, registry, generated output or external PR was
changed. The persisted workflows have **not** run this correctness checkpoint.
Sixteen new tests cover current policy reads, UTF-8 decoding, refusals, missing
policy, matching,
spacing/validators, redirects, fresh-run changes, shared-host refusal propagation,
typed runner failures and preservation of old state. The real measured robots
response is retained as a fixture.

| Local verification | Result |
|---|---|
| Japan adapter/runner/scope/bootstrap | 164 tests passed, including 15 new policy regressions |
| Collector, schedule, PDF, manifest, identity and isolation checks | 495 tests passed |
| Full offline suite with localhost/Chromium permissions | **3,204 tests, OK (skipped=2)**, 1,228 s; exit 0 |
| Final checkpoint review correction | **496 focused tests passed**, including UTF-8 byte parsing/invalid-encoding refusal; the full suite above preceded this correction |
| `scripts/validate_output.py` | Passed with exactly **10 governed warnings**; no new warning |
| Identified repaired-adapter rehearsal | Policy → permitted RSS → already-listed PDF; all HTTP 200, 580 extracted characters, no state writes |
| Original captures/fixture | All retained hashes match; Git filtering does not alter the robots fixture bytes |
| Production preservation | DB SHA-256 unchanged; all **7,410 output files** byte-identical, no SQLite sidecars |
| Diff | `git diff --check` clean; only source, tests, fixture and documentation/evidence changes |

The initial restricted full run had 31 browser setup errors, all localhost
socket-bind `Operation not permitted`, and was not accepted as green. The full
suite above passed after normal sandbox approval, rather than substituting an
isolated pass. An intermediate full run was interrupted when the higher-priority
policy defect changed the implementation; it is not validation evidence.
The worktree has no local `.venv`; checks used the same repository's existing
`/Users/benjaminyang/pla-watch/.venv/bin/python`, with bytecode writes disabled.
No dependencies were installed. AFP's old CI result is separate from these
local results; no new CI, scheduled-run or deployment result is claimed.

Changed runtime files are `scraper/sources/jp_mod.py` and
`scripts/shadow_collect_japan.py`; regression tests are in their existing Japan
test modules. `tests/fixtures/jp_mod/robots.txt` is the measured response.
Documentation changes are this assessment, its retained evidence,
`shadow/jp_mod/README.md` and the current `PROJECT_STATE.md` snapshot.
The assessment was initially delivered uncommitted on
`codex/jp-ph-desk-assessment-20261006`, based on `a259ee6d2`. The subsequently
authorized correctness checkpoint includes explicit UTF-8 policy decoding and
its regression; its final commit SHA is recorded in Git history. PR #79 and
both remote shadow/main heads were rechecked unchanged at checkpoint review.
No push, merge, promotion or publication.

Remaining next actions: Japan needs an openly advertised official discovery/body
route or a separately ruled scope, original PDF preservation and date evidence;
Philippines should integrate and review existing PR #79, then evaluate AFP+NSC
on an explicitly authorized isolated schedule. Both need desk-specific review
tooling and completed human checkpoints before any graduation decision.
