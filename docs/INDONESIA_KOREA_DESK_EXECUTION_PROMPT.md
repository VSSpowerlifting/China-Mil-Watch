# Execution prompt — Indonesia and South Korea shadow desks

Use the following prompt to continue or repeat this work in an explicitly assigned
Indo-Pacific Record checkout. The measured implementation receipt is
`docs/INDONESIA_KOREA_DESK_EXECUTION_2026-10-06.md`; refresh live evidence rather
than treating its measurements as current reliability.

---

Act as the builder and executor for Indo-Pacific Record. Research and build an
Indonesia shadow desk and a South Korea shadow desk. Carry the work through a
reviewable implementation, captured-source tests, bounded native-client rehearsals
and evidence packets. Korea means the Republic of Korea. Use one primary writer.

First verify cwd, repository root/common directory, origin, branch, HEAD, status,
worktrees and relevant PR dependencies. Use only the assigned pla-watch worktree;
preserve other work. Read CLAUDE.md, PROJECT_STATE.md, AGENTS.md, product/editorial
doctrine, architecture/publishing, agent workflows, desk-strength criteria and
shadow collection/review rules. The source of truth for public status is
desks/registry.json; source scope lives in each manifest. Existing code and source
captures take precedence over stale document summaries.

Authorization covers research, source/tests/docs implementation and bounded local
collection into fresh temporary state outside all production/collector checkouts.
It does not authorize committing, pushing, merging, publishing state, enabling a
schedule, public desk declaration, production collection, output regeneration,
deployment, paid model processing or promotion unless a later human instruction
explicitly supplies that authorization. Prepare those actions concretely when
needed; do not invent approval or repeatedly ask about routine implementation.

Use these bounded seed scopes:

- Indonesia: Kemhan's Berita institutional-news category and its linked HTML
  articles. Preserve the difference between institutional news and Siaran Pers
  press releases. TNI and service websites are separate candidates, not implied
  coverage. On 2026-10-06 Kemhan's policy allowed this route; TNI robots timed out.
- South Korea: Policy Briefing's government-republished releases carrying the
  explicit A00005/국방부 ministry label, with their linked HWPX documents. The
  portal is publisher, the explicit MND label is issuer, and the source is Tier B
  republication. It is not a complete MND wire. MND's own robots disallowed its
  publication paths on 2026-10-06; stop there. Do not probe another MND route to
  evade that policy. A separately governed official source must be researched and
  attributed independently. Never relabel portal evidence as direct MND access.

For each source, record official discovery locators, policy response/status,
request identity, method/form fields, retrieval time, response/capture hashes,
listed dates/titles/identities, article metadata and body/document extraction.
Search results are leads, not capture or permission evidence. Use the identifiable
project client, re-read and obey robots, honor Crawl-delay and space requests at
least two seconds apart. No browser impersonation, cookie-based challenge solving,
proxy, retries after refusal, guessed article URLs, or undocumented pagination.
If policy cannot be established or a source refuses access, stop that source and
preserve the reason. Do not turn a failure into healthy emptiness.

Reuse the existing candidate modules where they remain correct:
scraper/sources/desk_shadow_http.py, id_kemhan.py, kr_policy_briefing.py;
scripts/shadow_collect_desk.py and review_desk_shadow.py;
shadow/id_kemhan/ and shadow/kr_policy_briefing/;
tests/test_indonesia_korea_shadow.py and its exact-byte fixtures.
Do not refactor existing country collectors merely to share the new machinery.

Keep manifests outside desks/. The runner must refuse state in production or
collector checkouts, symlinks and another desk's state. It must never open the
production DB or output tree. Bound discovery to ten listing pages and the whole
selected window to forty releases, with six lookback days by default. A cap breach,
missing/looping pagination, ordering drift, foreign issuer, changed filter or
unprovable result count fails before any partial listing is admitted. Preserve
all original titles/text/dates; never synthesize missing originals, translations,
timestamps, units, ranks, bylines or claims. Dates are source-stated dates at their
stated precision, not retrieval or event dates.

For Indonesia, compare the URL, listing and article dates and canonical identity;
keep prose that malformed image tags wrap. For Korea, the page's iframe, preview
and description are not the body. Read only the attachment the permitted page
publishes; bound archive size/member count, reject invalid/entity XML, and record
document provenance separately from HTML provenance. Unsupported formats fail
explicitly. Preserve distribution/event dates inside original text without
substituting them for portal posting dates. Record XML reading-order limits.

Store content-addressed captures, original records, an append-only run ledger and
a write-once clock in isolated state. Never commit a partial failed batch or
silently replace a changed original. Distinguish discovery, retrieval, extraction,
storage, duplicate and access outcomes. A quiet proven listing may succeed;
failure neither starts nor advances a successful interval. Preserve failed-attempt
evidence. Logical dates and execution timestamps remain distinct, including
explicit-date recovery and refusal of ambiguous scheduled re-runs.

Run offline, network-guarded tests for exact-byte provenance, source/canonical/date
parity, pagination/completeness, healthy emptiness, policy/challenge/redirect refusal,
unsupported documents, capture corruption, deterministic identity/deduplication,
atomic batches, isolated state, immutable clocks/ledgers, logical dates and
production exclusion. Run related collection/manifest/shadow regression suites.
Use native-client local rehearsals with declared windows/caps, record exact code
state and results, and hash the complete production DB/output set before and after.
One successful rehearsal establishes bounded behavior, never periodic reliability
or permission to republish. Never label these candidates functional or qualified.

Prepare the manual workflow for separate fixed orphan state branches,
shadow/indonesia-kemhan and shadow/korea-policy-briefing. It must verify its exact
collector SHA and state destination, publish successful state only without force,
preserve historical clock/ledgers, reject WAL/SHM, and preserve failures as artifacts.
Keep scheduling off until authorized. Do not copy rehearsal state into a launch.
Only an authorized first durable collection establishes that evaluation's day zero.

Produce review packets from immutable state commits reachable from each desk's
fixed state branch. Loose temporary state is explicitly a rehearsal. Hash inputs
before/after, export original records and flag missing logical days, capture/content
corruption and foreign records. Human sign-off stays unfilled: actual source and
document comparisons around days 7, 14 and 30, actual completion timestamps,
anomaly dispositions and durable preservation are required. No counter, report,
workflow or source enablement promotes a desk. Production promotion still needs
30 consecutive collecting days, completed human checkpoints and owner sign-off
in DECISION_LOG.md, plus a separately reviewed production integration.

Finish the prompt/implementation receipt and current PROJECT_STATE snapshot.
Inspect every changed file and the full diff, preserve public/production files,
run the required graph update if available, and report evidence by stage. State
what changed, why, tests actually run, live rehearsal outcomes, repository/commit/PR
state and the exact remaining action. Record environmental limits and open gates
without manufacturing a source fact or claiming CI/deployment/public verification.
