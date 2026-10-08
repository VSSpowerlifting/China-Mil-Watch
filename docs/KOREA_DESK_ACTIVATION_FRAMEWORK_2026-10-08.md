# South Korea Desk: activation framework and executable source-fidelity gate

**Operational scope:** South Korea (`korea`), not the DPRK. This is a governed multi-institution desk-development program, not an authorization to bypass a publisher's restrictions or change its official release terms.

## Starting evidence (checked October 8, 2026)

- A source-specific, native Korean collector is merged (#110) for Korea Policy Briefing's ministry-filtered `A00005 / 국방부` republications. It preserves the original linked HWPX, HTML page, Korean extracted text, source identity, publisher date, hashes and immutable state.
- `shadow/korea-policy-briefing` is the only durable Korea state branch. First success: October 6. Four records stored. A successful October 7 scheduled logical run selected two releases, both duplicates, with zero fetch/extraction/access failures; the branch reached one new commit after the initial manual Actions receipt.
- A merged daily 17:47 UTC schedule (#113) runs with six-day lookback and cap 40; a checked-in cron is **not** evidence that every scheduled Action completed. The present source is a Tier B **government republication**, not a direct release wire of the Ministry of National Defense (MND).
- MND's own `robots.txt` refuses the requested publication paths. This project will not access alternate paths, impersonate browsers, bypass refusals or silently widen collection. Other institutions are not covered by this collector.
- PR #210 is the open unified Japan/Vietnam Sunday writer; draft #214 adds Korea's metadata-only research lane atop #210. Neither constitutes Korea's production activation or permission for substantive Korean-source event claims.

## Seven explicit gates

| Gate | Machine or human proof | Owner/operator behavior |
|---|---|---|
| K0 — Compliant discovery | Published, authorized Korea Policy Briefing ministry filter and source-specific robots/host validation | Stay on the separate government portal; MND direct site remains blocked |
| K1 — Continuity | Every nominal daily collection has an accountable successful state ledger; compare missing logical dates to GitHub Actions unsuccessful attempts | Review daily; repair real failures without rewinding first-success clock |
| K2 — Original-byte fidelity | `audit_korea_source_fidelity.py` reparses each archived **HWPX** and matches its derived original Korean text against the stored database *and* expected hashes | Any mismatch is a source-integrity incident; do not pass to analyst model |
| K3 — Human/source review | Actual Korean-language reviewer compares portal URL, issuer, page title/date, original HWPX visual order, tables, technical terms and extracted text; independently checks any translation | Blank review template never counts; named reviewer and source-version-bound timestamp necessary |
| K4 — Source rights and editorial claims | Source-specific reuse-policy check; evidence-bound, independently reviewed English editorial synopsis, with exact publisher URL/portal date/original text hash and limitations | Permit claims only via explicit, version-pinned human-approved evidence; no source-body copying by default |
| K5 — Regional generator | Korea evidence delivered to **one** Sunday source pool alongside production and other reviewed sources, with typed non-production IDs and source-specific verification | Model may omit Korea when irrelevant; Dylan edits a single thematic draft, Ben approves publication separately |
| K6 — Production and breadth | 30-day continuous evidence plus real Day 7/14/30 review, C1–C13 criteria, institutional/subject diversity, reuse authority and explicit owner sign-off | Only then consider appropriate honest registry status, migration, rendering and production activation |

No upstream gate implies a downstream gate automatically. **K2 passing does not approve interpretation, publisher reuse, AI claims or a live desk.**

## Executed phase: K2 machine audit and K3 reviewer preparation

`scripts/audit_korea_source_fidelity.py` now reopens immutable stored HTML and HWPX capture blobs from the exact branch tip, checks their SHA-256 hashes and issuer/provenance constraints, independently reruns the existing bounded HWPX XML parser and compares every reconstructed paragraph against the archived Korean text. This closes a gap in the earlier state reviewer: a forged Korean text body could have matched its own recomputed hash without actually matching the original HWPX.

The tool also audits ledger DB-hash continuity and checks for missing logical dates. It writes three **metadata-only** files to a new directory outside the repository: `machine_fidelity.json`, `human_source_review_BLANK.json` and `REVIEW.md`. No Korean source body is recopied into main or a public artifact. The blank review template contains no reviewer identity, language judgments, editorial synopsis, rights approval or source authorization. Source URL and original attachment link allow humans to inspect at the publisher.

The separate **manual-only** workflow `.github/workflows/korea_source_fidelity_review.yml` clones the Korean state branch read-only, audits its literal current commit, checks the core Korean collector tests and retains a 30-day reviewer packet. It never calls an LLM, sends an email, edits the source branch, promotes a desk or deploys. A healthy machine source pass does not override an incomplete daily continuity result or an absent human review.

### How to run after merging this PR

In **GitHub Actions → South Korea HWPX Source-Fidelity Review (Manual)**, select Run workflow on `main`, leaving `as_of` blank to evaluate the current UTC date. Inspect the JSON verdict and the blank review assignments inside the uploaded artifact. For reproducibility outside Actions:

```bash
git clone --single-branch --branch shadow/korea-policy-briefing \
  https://github.com/VSSpowerlifting/China-Mil-Watch.git /tmp/ipr-korea-state
KOREA_SHA="$(git -C /tmp/ipr-korea-state rev-parse HEAD)"
python -m scripts.audit_korea_source_fidelity \
  --state-repo /tmp/ipr-korea-state --state-commit "$KOREA_SHA" \
  --as-of 2026-10-08 --out /tmp/ipr-korea-source-review-20261008
```

Use a new output directory for each audit. The sample date is a **historical review cutoff**, not a readiness result. A missing scheduled date must appear as a failed continuity gate; do not backfill a fabricated successful ledger.

## Ongoing execution plan

**Track A — acquisition:** maintain daily scheduled runs at 17:47 UTC and a forward report of source-listing count, selected/retrieved/extracted/new/duplicates, newest publisher date, missing attempts and malformed HWPX releases. Reconcile GitHub Actions failures separately because unsuccessful workflows may never publish their ledgers. Review the sample of original captures and extraction differences at Day 7, Day 14 and Day 30. First-success clock was October 6, so these are earliest calendar checkpoints October 13, 20 and November 5, provided intervening collecting evidence exists; dates grant no approval.

**Track B — source depth:** have a Korean-language reviewer disposition the four original HWPX files in the audit packet against the publisher pages, including tables, reading order and distribution dates. Establish source-specific rights and an evidence-bound, separate English synopsis that can be revised or invalidated when the source changes. Do not write fake approvals on behalf of a person. After K3/K4, integrate only a strictly validated Korea *source-specific* factual card into #214's unified Sunday writer; until then the Korea lane must remain metadata-only and may be omitted.

**Track C — institutional breadth:** research separate, independently permitted official source paths for the Defense Acquisition Program Administration (DAPA), the Republic of Korea Joint Chiefs, Navy/Air Force, Ministry of Foreign Affairs, and other defense-relevant ministries. Create one source-scoped adapter and isolation test per eligible original full-text stream. Record robots access, canonical identity, date authority, completeness, language and reuse terms before any collection. Do not treat one Korean government portal as a comprehensive South Korea Desk.

## Definition of done and stop conditions

This **engineering phase** is complete when the HWPX source-byte fidelity validator, manual workflow, offline adversarial tests and blank reviewer packet are committed as a PR with exact-head offline CI and database/output preservation. It stops before actual human signing, automatic source-claim approval, new collector expansion or Sunday activation.

The **desk program** is done only after a separately authorized, source-verified and reusable Korea pipeline produces reliable multi-institution records, powers substantive article research when relevant, meets full promotion gates and truthfully renders public provenance. Public desk coverage must never be inferred from the present four shadow originals.
