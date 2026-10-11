# Indo-Pacific Record | Desk Capability Engineering Framework
**Technical charter | October 10, 2026**

**Status: offline planning only.** Neither this charter nor the machine-checkable plan authorizes new collection, publisher contact, license determinations, archival retention, AI model use, SMTP delivery, promotion, deployment or public publication.

## Executive decision

We should build **credible source-specific desks**, not merely expand the list of country labels. The next engineering stages must establish three increasingly strong claims:

1. A specific first-party publishing family is discoverable, accessible and reproducibly collected within its declared scope.
2. Its bytes, language, dates, issuer, versions, permissions and continuity are independently reviewed with a named human where required.
3. The complete qualified subset is substantial enough to support a *truthfully bounded* public desk identity and, independently, editorial research use.

A working listing does not prove body retrieval. A successful extractor does not demonstrate permission to archive. A passing scheduled job does not establish full source coverage. The completion of a 30-day clock does not itself approve production. **Do not collapse these boundaries.**

### Baseline from the actual registry and issue queue

| Scope | Current public registry | Actual next blocker |
|---|---|---|
| China | Live and production-backed | Maintain source consistency; no expansion through this plan |
| Singapore | Live and production-backed | Maintain continuity; historical shadow evidence is not additional public coverage |
| Vietnam | Research, no production-backed Vietnam records | Three MPS/MOIT reviews, publisher/use rights, source-specific MOD discovery |
| Japan | Shadow | Japan MOD HTML access constraints, narrower JCG completeness and license review |
| South Korea | Not yet a declared public country desk | Original Korean HWPX fidelity, KOGL scope, independent DAPA source |
| Philippines, Indonesia | Isolated shadow families; not present in the public desk registry | Continue separate source-family review and attestation before proposing registry additions |
| US Indo-Pacific | Access-blocked | Compliant authorized route, not a challenge bypass |

The authoritative public desk roster is desks/registry.json. Configured shadow source-to-workflow/branch identity is declared in config/shadow_source_workflow_bindings.json. Neither a shadow manifest enabled flag nor this roadmap overrides that authority.

## 1. Architectural boundaries

Reuse current infrastructure instead of creating a competing collector or qualification platform.

| Boundary | Existing component | Forbidden substitution |
|---|---|---|
| Desk display/status | core/desk_registry.py and desks/registry.json | Do not publish a country because its shadow branch exists |
| Source/issuer scope | manifests, core/manifests.py | A syndicated article cannot silently become a ministry directive |
| Collector outcome | core/collection/contract.py and source status taxonomy | Zero documents after denial is not ok_no_publications |
| Logical scheduled date | core/shadow_schedule.py | Runner start timestamp cannot quietly rewrite the nominal slot |
| Private state | source-specific orphan branches and append-only ledgers | Never combine source clocks or merge captured bodies into main |
| Checkpoint fidelity | scripts/review_vietnam_ministry_state.py and equivalent Japan/Korea tools | A generated review template is not human signoff |
| Scheduled attempt evidence | bindings audit, shadow-slot reconciler, Ops Center overlay; issue #250 | A static cron declaration cannot prove a real successful slot |
| Original language/rights | original publisher and per-version source-use reviewer | Technical accessibility is not public retention or image licensing |
| Research/editorial | typed synopsis and Sunday source-use receipt | A source offered to the model is not necessarily cited or verified |
| Production/public | explicit admission PR, owner decision, renderer/DB validation | CI success or elapsed time cannot promote a desk |

An eligible source family conceptually advances through proposed → access observed → original identity verified → isolated shadow → continuity reviewed → human reviewed → rights-scoped candidate → separately adjudicated source admission. **This is not an executable state machine.** Different families can occupy different stages and an earlier stage may reopen after a publisher changes URLs, content or terms.

Track four orthogonal evidence dimensions: technical access and integrity; original issuing authority and linguistic/date accuracy; permission for each concrete use (metadata, synopsis, private storage, external model, public translation, images/PDF); and public/editorial approval. None can automatically fill in another.

## 2. Dependency-checked engineering plan

**Source of planning scope:** config/desk_capability_execution_plan.json, 20 bounded packages in five waves. It is a work breakdown, not a status dashboard or release-control variable. It records requirements, issue ownership, dependencies, source slugs, separate proposed source families and stop conditions. Every item has status planned_not_verified and executable_effect none.

**Pure validator:** scripts/validate_desk_capability_plan.py uses only local tracked JSON to ensure correct declared source families, registry scope, non-cyclic dependencies, issue identifiers, real acceptance/stop criteria and review flags. A *proposed* Vietnam MOD or Korea DAPA family cannot masquerade as a source already bound to a collector. Unexpected task fields and any supposed approval/activation fail closed.

Run offline:

~~~sh
python -m scripts.validate_desk_capability_plan
python -m scripts.validate_desk_capability_plan --json
python -m unittest tests.test_desk_capability_execution_plan -v
~~~

The JSON response explicitly refuses execution, admission, desk promotion and publishing. Structural validation proves only that the dependency graph makes sense. It never queries GitHub Actions, remote shadow state, publishers, secrets or databases. Do not import this planner into the collector, scheduler, renderer or Sunday writer.

## 3. Work waves and acceptance

### Wave 0 — authentic scheduled observations (REG-01 / issue #250)

Existing Ops Center and shadow workflow-binding reports are useful configuration evidence, but they do **not** authenticate actual collection. The next isolated engineering stage joins, per family, the declared source slug, workflow ref, cron, state branch, actual Actions run ID/attempt/event/time/conclusion and immutable corresponding state ledger.

Separate skipped or manually recovered attempts, delayed slots, missed dates, partial multi-branch publication, source anomalies and a green job with no complete ledger. Reports use verified observation, needs review, unobserved and blocked, with precise source identity and evidence pointers. An unknown dimension remains unknown. Neither public country-wide health nor license status is inferred.

**Exit test:** offline fixtures for wrong state branch, mismatched run/ledger, cancelled run, partial three-branch push, late start across date boundary, duplicated logical date, inaccessible source and stale state commit. No writes to production DB or output, no UI badges based solely on declarations.

### Wave 1 — Vietnam, existing three sources first (VN-01 to VN-09)

**Core MPS/MOIT reviews (issue #186):** collect nothing outside approved cadence. The *earliest* scheduled checkpoint slots are October 14 (Day 7), October 21 (Day 14), and November 6 (Day 30), 2026. Each review waits for its actual completed logical run. Pin all three separate exact source-state commits, preserve failed attempts, verify source versions and original Vietnamese with a named reviewer, and complete three distinct evidence packets. Do not bulk-sign off, infer publisher silence or borrow another source's clock.

At the observed October 10 scheduled run 38088742605-1, MPS reported one newly stored record (six stored total), and the two MOIT families reported none (two and one stored total). Both MOIT ledgers flagged robots.txt being served as text/html although the rules were readable. That anomaly is an explicit human-review item, not a reason to falsely mark the cohort pristine.

**Source-use (issue #196):** metadata and hyperlinks, private source-linked analyst synopsis, complete retained text, external-model transmission, public translation and images/PDF are separate use cases. They require actual publisher terms and independent original-version review. The expanded Sunday five-record Vietnam research set does not mark either MPS or MOIT as human approved.

**Vietnam MOD (issue #236):** MOD is a separately proposed source, not part of the MPS/MOIT reliability clock. The merged manual canary in scripts/probe_vietnam_mod_defrel_access.py can attempt exactly one robots request and (if permitted) one first-party Defense Relations listing request after an explicit one-time authorization. Its prior offline WCM URL gate is only an identity hypothesis. A 403, challenge, redirected listing, unreadable robots or unclear terms is a legitimate **blocked** outcome; no mirrors, proxies, rotating identities, guessed URL namespace or covert browser retry.

Only if access and rights are independently established should the next PR prepare a legally reusable offline truth table covering article identity across reloads, printed publication date versus posting date, original issuer/byline versus host syndication, body segmentation, missing/partial text, pagination, duplicate versions, and denials. A separate explicit later approval would be needed to create an isolated MOD state/clock, with its own 7/14/30 reviews. Never inherit existing MPS qualification.

**Potential promotion (VN-08):** After actual source-bound Day 30 and rights decisions, open a new owner-only proposal identifying which MPS/MOIT subfamilies actually qualify under C1–C13. A narrow desk decision must honestly name institutions still excluded. Nothing here promotes Vietnam or enables production.

### Wave 2 — Japan, compliant body access before broad coverage (JP-01 to JP-04)

For Japan Coast Guard, verify original publisher article/PDF identity, copyright scope, accurate extracted text, dates, missing entries, actual scheduled continuity and independently reviewed checkpoint evidence. That is a *distinct* JCG institutional scope.

Japan MOD can list many items via RSS yet fail retrieval of its official HTML. The existence of a few PDF items, successful RSS metadata or open-source references must never be called full MOD collection. Require real first-party permitted body access; record Cloudflare/403 challenges as blocked, without bypass, cookie replay or source substitution. Joint Staff, MOFA and METI must be independently scoped where they issue substantive original documents rather than syndicated coverage.

A future owner decision for a narrow Japan public scope is separate from the source pipeline. The word Japan does not imply every ministry and service is represented.

### Wave 3 — South Korea original text and a second official issuer (KR-01 to KR-04)

The existing Policy Briefing MND/HWPX evidence requires real Korean-language review: preserve content/order of tables, issuer authority, visible versus distribution dates, version identity and legally applicable KOGL text licensing. A license on an HTML publication does not blanket-authorize embedded images or HWPX contents.

DAPA should enter through its own first-party access and source-identity canary, then independent shadow continuity if approved. DAPA cannot inherit MND metadata, state clock or review outcomes. Korea is absent from the authoritative public registry; create a separate owner-approved registry proposal only **after** source-specific qualification and rights evidence, not as a side effect of this scaffolding.

### Wave 4 — one regional intelligence system (REG-02, REG-03)

The existing Sunday Briefs path should receive a **single coherent thematic manuscript** grounded in eligible records and bounded reviewed research. Inspect offered versus actually cited source IDs, unsupported assertions and translation limits. Dylan edits human prose; technical source auditing, use-rights checks and final publication remain internal. Avoid country-count quotas and duplicate drafts.

Evidence Timelines and Living Dossiers should reuse the *same* canonical document identities and event/entity relationships instead of building parallel manually copied evidence. Timelines describe dated official observations; dossiers record competing interpretations and what remains uncertain; Briefs are selective arguments. None of those additional research views automatically qualifies a source or permits publication.

Philippines and Indonesia remain in separate existing source-specific implementation lanes. Connect them to the eventual regional attestation model but do not fold their collectors into a Vietnam or Japan PR just to increase country coverage. The U.S. Indo-Pacific route stays blocked unless a lawful publisher-supported access path is proven.

## 4. Per-work-package PR contract

Keep a source-specific PR small enough to audit. It must name:

1. **Authority and scope:** original publisher, producing institution, source family, explicit permitted routes, issue/owner, repository branch and concurrent work boundaries.
2. **Evidence:** real network observation if authorized, otherwise labeled fixture-only; actual run/attempt/state commit; source-specific issuer/date/body proof; permissions and limitations.
3. **Failure table:** denied/unreadable robots, redirects, challenge pages, timeout, wrong host or source family, incorrect date, empty body, duplicate ID, source version change and partial push.
4. **Integrity:** deterministic unit tests, exact-head CI, version pin, side effects limited to declared paths, no database/output drift and no generated captured-source material in main.
5. **Human scope:** which original-language and source-rights checks remain held, who must review them, explicit non-authorization of publication and production changes.
6. **Rollback:** how to disable or revert the optional future source without modifying old state or losing provenance. Never rewrite evidence to make a failed checkpoint green.

Recommended split: pure parser/identity + offline fixtures → separate approved access canary → separate optional isolated shadow collector → independent review tools and actual source evidence → typed private editorial evidence → owner-only production/registry proposal. Avoid a single mega-PR that collects, licenses, promotes and publishes at once.

## 5. Formal later promotion control

Any proposed production-backed country desk must present **C1–C13**, as defined in docs/DESK_STRENGTH_CRITERIA.md, for **each admitted source** as PASS/FAIL/UNMEASURED with actual evidence references. Attach complete scheduled-attempt history and state/ledger chain, Days 7/14/30 distinct human review, explicit source-use rights, immutable version pins, accurate official issuer and original language verification, and the precise public scope/exclusions.

Then and only then obtain an explicit owner decision before changing the registry, production manifest, public renderer, generated records or deployment. Publication QA must also prove DB integrity, duplicate/version handling, original attribution, translated display conditions and honest no-content/error states. Source rights, desk promotion and *individual Brief approval* remain separately governed decisions.

### Mandatory negative cases

| Observation | Appropriate verdict |
|---|---|
| Scheduled job green but one source has access anomaly | Source-specific needs-review, no blanket country-green |
| Robots 403 / unreadable rules | Block, without a follow-up article fetch |
| Listing empty in a bounded window | No eligible discovered entries **there**, not general governmental silence |
| RSS item exists but official HTML inaccessible | Discovery observed; retrieval blocked |
| Translation says a different event date from original | Preserve both and hold unsupported chronology |
| Parser detects a changed article body | New version evidence and re-review; don't overwrite prior review |
| Reviewer unnamed or source hash drifted | Review and use rights held |
| Source has license for metadata but not body | Permit only governed metadata/link use |
| Newly proposed DAPA/MOD family has no binding | Candidate only, no collecting status |
| One service operates reliably | Name that service; don't claim full national MOD coverage |
| Owner review SHA differs from Sunday manuscript | Block editor send, never regenerate to defeat approval |

## 6. Delivery sequence, not a promise of automatic completion

- **Near-term:** record October 14 actual Vietnam Day 7 and MOIT anomaly evidence. Run a Vietnam MOD first-party access canary **only after a separate owner authorization**; an access denial is useful documented research.
- **Next checkpoints:** October 21 Day 14 and November 6 Day 30, with source-specific human review before any promotion suggestion.
- **Parallel but separate engineering:** Japan JCG original-body reliability; compliant MOD retrieval options; Korean HWPX truth checks and a proposed DAPA official source.
- **Cross-desk layer:** source-specific Actions/state attestation, then source-permitted regional analysis, then entity/timeline/dossier reuse. No new weekly research packet for Dylan.

**Definition of this framework phase completed:** a coherent, tested roadmap and dependency graph with no executable route to collection, source admission, public registry changes, user-facing publication or email. Completion of this *planning* phase does not count as completion of any source work package.

### Files in the framework PR

- This internal technical charter.
- config/desk_capability_execution_plan.json — 20 linked work packages, all unverified.
- scripts/validate_desk_capability_plan.py — read-only validation of declarations, scope and prerequisite ordering.
- tests/test_desk_capability_execution_plan.py — negative tests for fake approvals, source misattribution and dependency cycles.
- One offline CI workflow scoped to these files.

All production desks, source manifests, data/state branches, workflows that collect, DB and generated output stay unchanged.
