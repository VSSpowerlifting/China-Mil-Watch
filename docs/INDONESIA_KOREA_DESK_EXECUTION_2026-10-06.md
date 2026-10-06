# Indonesia and South Korea — execution receipt, 2026-10-06

Ben requested an engineered prompt and full execution, then selected “Research
and build both shadow desks here.” This implements both isolated candidates and
their review/launch machinery. At the end of that initial build, no commit,
push or durable launch had been authorized or done. Ben subsequently authorized
"commit/PR, followed by durable shadow collection" in this chat; that continuation
is recorded in DECISION_LOG.md. Main merge, scheduling, public declaration,
promotion, production integration and deployment remain unauthorized.
The [durable launch receipt](INDONESIA_KOREA_SHADOW_LAUNCH_2026-10-06.md) records
the subsequent PR, fresh published state commits and source-commit CI results.
The [reusable prompt](INDONESIA_KOREA_DESK_EXECUTION_PROMPT.md) states the continuation
contract; the candidate READMEs state each source's limits.

## Repository and implementation

Assigned worktree: `/Users/benjaminyang/.codex/worktrees/88cc/pla-watch`.
Origin: `https://github.com/VSSpowerlifting/China-Mil-Watch.git`.
Initial build base: `a259ee6d2e42d90ade1cb0b51fab41a71ce3b430`, then detached.
The starting worktree was clean; no attached PRs or local Indonesia/Korea branch
dependencies were found. The initial build finished uncommitted; the authorized
continuation uses `codex/indonesia-korea-shadow-20261006`.

| Files | Result |
|---|---|
| `shadow/id_kemhan/{manifest.json,README.md}` | Indonesia scope, source identity, access and evaluation limits |
| `shadow/kr_policy_briefing/{manifest.json,README.md}` | South Korea scope, distinct publisher/issuer and republication limits |
| `scraper/sources/desk_shadow_http.py` | Identifiable, policy-gated, bounded transport and discovery; no existing source refactor |
| `scraper/sources/id_kemhan.py` | Berita discovery/canonical/date checks and original HTML text |
| `scraper/sources/kr_policy_briefing.py` | Published MND filter, complete search traversal and linked HWPX extraction |
| `scripts/shadow_collect_desk.py` | Desk-bound isolated storage, raw captures, atomic batches, append-only ledgers, immutable clock and logical dates |
| `scripts/review_desk_shadow.py` | Read-only rehearsal or pinned Git-object packets; scope/hash/continuity checks; human sign-off left empty |
| `.github/workflows/indonesia_korea_shadow.yml` | Prepared manual, main-only workflow; separate fixed orphan branches, explicit non-force destinations, success-only publication and failure artifacts; no cron |
| `tests/test_indonesia_korea_shadow.py`, `tests/fixtures/indonesia_korea/`, `.gitattributes` | Native exact-byte captures, binary Git preservation and offline refusal/extraction/storage/workflow/review tests |
| Execution documents and `PROJECT_STATE.md` | Reusable prompt, measured receipt and current candidate state |

The manifests are outside `desks/` and absent from `load_all_desks()` and the
public registry. Production adapters, pipeline, schema, templates, public routes,
editorial records and dependencies are unchanged. The only generated project
artifact is the ignored code graph, refreshed under the repository rule.

## Source/access ledger

Retrieval date: 2026-10-06. Identity on every native request:
`IndoPacificRecord-ShadowCollector/0.1 (+https://indopacificrecord.org; research archive; contact via site)`.
Evidence is exact response bytes plus hashes in
`tests/fixtures/indonesia_korea/requests.json` and the isolated native run ledgers.
Search results supplied leads; native policy and response captures supplied
the observations below. None establishes a license to republish source text.

| Observation / source locator | Evidence type and status | Limitation |
|---|---|---|
| [Kemhan robots](https://www.kemhan.go.id/robots.txt) permits [Berita](https://www.kemhan.go.id/category/berita) | Direct policy/HTML captures, HTTP 200; native adapter passed | One ministry news family, not whole-of-defense or TNI coverage |
| [Kemhan Siaran Pers](https://www.kemhan.go.id/category/siaran-pers) is a separate category | Direct listing capture; excluded from the seed scope | The Berita stream is not mislabeled a press-release wire |
| [TNI robots](https://tni.mil.id/robots.txt) timed out after 20 seconds | Native transport failure; policy unestablished | Not evidence of an institutional refusal; no TNI listing/body was fetched |
| [MND robots](https://www.mnd.go.kr/robots.txt) disallows publication routes, allowing the root and `/mnd/index.do` | Direct plain-text policy, HTTP 200; offline policy test | Publication/RSS/English paths and alternate MND hostnames were not probed |
| [Policy Briefing policy](https://www.korea.kr/robots.txt) permits its [release search](https://www.korea.kr/briefing/pressReleaseList.do) and linked same-host documents | Direct policy, published form and returned filter/issuer captures; native adapter passed | Separate government-republished source; not direct MND access or complete MND output |
| Policy Briefing's `A00005` control explicitly names `국방부` | Source-stated issuer; direct form/page labels | Portal is publisher; issuer is not inferred from the subject matter |
| Korean release pages carry viewer iframes; HWPX attachments carry the original text | Direct HTML/document captures and ZIP/XML extraction | XML paragraph order can differ from visual reading order; HWP/PDF/multiple-HWPX/HTML-only variants remain unsupported failures |
| [DAPA robots](https://www.dapa.go.kr/robots.txt) permits access | Direct policy capture; source not implemented | No DAPA publication corpus, extraction or reliability claim follows |

Confidence is high for these bounded response/policy observations. Access and
markup may change; every collector run rechecks them. Cadence, missed-publication
rates, historical completeness and reliable Actions egress remain unmeasured.
Original source assertions are preserved as assertions, not validated events.

## Native rehearsals and evidence

First, each candidate passed a one-date rehearsal for 2026-10-06 into fresh
temporary state, storing one record each. Then each passed its default seven-date
window, 2026-09-30 through 2026-10-06, with a cap of 40.

| Measure | Indonesia | South Korea |
|---|---:|---:|
| Selected / retrieved / extracted / inserted | 14 / 14 / 14 / 14 | 4 / 4 / 4 / 4 |
| Native responses | 17 | 10 |
| Listing pages | 2 | 1 |
| Article HTML / linked documents | 14 / 0 | 4 / 4 |
| Fetch / extraction / access failures | 0 / 0 / 0 | 0 / 0 / 0 |
| Result / health | `ok` / `ok` | `ok` / `ok` |

These are bounded native-client observations. No reliable daily interval or
formal evaluation day zero was established. The local clocks remain rehearsal
evidence and will not be copied into durable state. Collector provenance in the
run ledgers honestly says the base SHA plus `+uncommitted`; there is no immutable
collector commit yet. The final extractors reproduce all original title, text,
date and language fields from all 18 captured window records without network I/O.

Local evidence:

- `/private/tmp/ipr-indonesia-window-rehearsal-20261006/` and its `.log`
- `/private/tmp/ipr-korea-window-rehearsal-20261006/` and its `.log`
- `/private/tmp/ipr-indonesia-review-rehearsal-20261006/`
- `/private/tmp/ipr-korea-review-rehearsal-20261006/`
- `/private/tmp/ipr-indonesia-korea-evidence-20261006.tar.gz` — preserved evidence
  bundle and initial build source snapshot; temporary storage, not a remote evaluation branch

Both review rehearsals export the complete stored corpus, have zero machine
integrity findings, identify themselves as rehearsals and leave human review
incomplete. A formal packet additionally requires an exact state commit reachable
from the desk's fixed branch, a state-only tree and regular recognized files.
The reader exports commit objects, ignoring uncommitted state changes. No report
supplies a reviewer identity, approval, anomaly disposition or promotion.

## Verification

Using the existing primary-checkout Python 3.9 environment read-only (this
worktree has no `.venv`), the following focused regression group passed **330
tests**. The new candidate suite contains 40 tests. Initial reviewer tests found
that the path whitelist omitted the `+` in actual UTC ledger filenames; the
whitelist was corrected and the complete regression group was rerun successfully.

```sh
python -m unittest \
  tests.test_indonesia_korea_shadow tests.test_manifests \
  tests.test_manifest_note_sync tests.test_ph_nsc_adapter \
  tests.test_ph_nsc_shadow_runner tests.test_shadow_logical_target_date \
  tests.test_desk_rollout_contract -q
```

Coverage includes raw capture hashes, genuine short documents, malformed image
markup, canonical/date/issuer parity, pagination/result counts, healthy empty
searches, robots/refusal/challenge/redirect gates, HWPX bounds/entity refusal,
production exclusion, source-bound state, duplicate preservation, failure after
one successful extraction without partial storage, immutable historical state,
explicit-date recovery, workflow shell syntax and pinned-state review isolation.

The unchanged public tree passes `scripts/validate_output.py` with the same ten
governed warnings. A full SHA-256 file-list comparison confirms all **7,411**
production DB/output files unchanged against the session baseline. No production
render, paid processing, full CI run, Actions collection, deployment or live-site
review was performed or claimed.

`graphify update .` refreshed the ignored code graph without model calls. Its
code graph exceeds the tool's 5,000-node HTML limit, so HTML visualization was skipped.
Fifty-four non-code inputs yielded no AST nodes; no semantic document indexing
is claimed. This graph check is separate from collection validity.

## Continuation and exact open gates

The initial build's next action was source/docs/fixtures commit and push for
review, followed by durable shadow launch. Ben has now authorized the commit/PR
and fresh durable collections on the two public same-repository state branches.
Those collections use an immutable collector commit and do not require changing
main. A main merge and scheduling remain separate, unauthorized actions.
The prepared workflow is manual-only and main-only; each dispatch selects one
fixed state branch and persists successful state there. Its first authorized
successful collection creates its own clock. A refusal, divergence, malformed
state or failed batch prevents a state push; artifacts preserve the attempt.

Before scheduling, authorize public same-repository state for each desk and the
full collector identity, confirm reuse-policy treatment, and choose non-colliding
slots against the then-current workflows. Wire the chosen slot to the logical-date
resolver; do not use an ambiguous Actions re-run for recovery. Verify actual Actions
egress and persistence before describing ordinary scheduled collection.

After ordinary runs, produce pinned Day 7, 14 and 30 packets and complete real
human comparisons against each source page and Korean document. Preserve the
actual sign-off dates and anomaly dispositions durably under separate authorization.
An unsigned packet or elapsed counter cannot substitute for these reviews.
No cadence threshold is guessed. Any production promotion remains a distinct
integration requiring 30 consecutive collecting days, completed checkpoints,
substantively sufficient records and owner sign-off in DECISION_LOG.md.
