# Living Dossiers B1 — engineering architecture RFC

**State:** proposed architecture only; implementation NOT authorized.  
**As of:** October 9, 2026 (Eastern)  
**Parent:** [#318](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/318) | [B0 audit #319 / PR #324](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/324) | [B1 implementation #321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321) | [Source-use audit #326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326).  
**Dependency:** the owner must accept a pilot scope and resolve rights/eligibility before any real Dossier sidecar is authored or any publication integration begins.

## 1. Architectural decision

**One Dossier is a durable, human-edited answer to a bounded research question**, revised as new official evidence arrives. It is **not** a chronology, new Brief number, article-length research paper, automated news stream, or issuer claim promoted to verified fact.

- **Records** preserve documentary text and provenance, with the record ID as the source identity.
- **Timelines** (#158 / PR #181) reconstruct a reviewed sequence of attributed developments and contested dates.
- **Dossiers** accumulate subject-bounded thematic knowledge, unresolved disagreements, source comparison and coverage limits.
- **Briefs** publish fixed, coherent interpretations of concrete developments using their existing approval and numbering contract.

Dossiers should refer to approved Timelines and Briefs without importing their approval, changing their existing text, or re-rendering their preserved URLs. An approved Dossier is **not** a license to publish full publisher text, a declaration of independent corroboration, or proof of the truth of an official press statement.

### Gate now

B0 [PR #324](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/324) has a seven-record Singapore naval-exercise pilot candidate. Its Singaroo record 4428 is **screened not selected**, the archive is overwhelmingly MINDEF-issued, and [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) raised a separate MINDEF links/full-text source-use review. No permission or pilot editorial approval is inherited. This RFC uses **synthetic examples only**, makes no real public claim and must not be interpreted as permission to begin the B1 real-content implementation.

## 2. Minimal implementation surface — after the B0 owner gate

~~~text
dossiers/
    <stable-slug>.json                # Canonical editorial source; only after B0 sign-off
core/
    dossier_contract.py             # Strict schema, source & approved-artifact validation
scripts/
    validate_dossiers.py            # Read-only, offline validation/diagnostics CLI
tests/
    test_dossier_contract.py        # Synthetic source and malicious-input cases
    fixtures/dossiers/              # Made-up records/issuers and drafts, never public
docs/research/
    DOSSIER_B1_ENGINEERING_RFC_2026-10-09.md
    DOSSIER_B1_VALIDATION_MATRIX_2026-10-09.md
    examples/dossier-v1-synthetic.json
~~~

**Not included in B1:** site renderer, public Dossier index or navigation, Jinja/CSS, production SQLite migration, collector, entity graph, semantic search, external AI service, model cost, SMTP, GitHub workflow schedule, or any alteration of the Sunday Brief process. Do not edit Timeline or Brief internals merely to factor an aesthetic abstraction. This design RFC itself contains only documentation under docs/research.

## 3. Dossier data model v1

The synthetic example file is illustrative input for the contract design, **not** a source of truth and **not** a valid public record. Avoid prematurely declaring a JSON Schema file separate from the executable Python validator: choose one canonical validator and derive machine-readable schema only if a downstream consumer actually needs it.

| Level | Proposed fields | Non-negotiable invariant |
| --- | --- | --- |
| Identity | dossier_schema, slug, title, dek, research_question, editorial_status | v1 only; safe slug matching filename; draft or approved |
| Scope | scope.period_start/end, jurisdictions, institutions, included, excluded, method, collection_limits | No blanket comprehensiveness; collection date is not a historical event date |
| Stewardship | author_name, editor_name, prepared_on, updated_on, reviewed_on | Recorded human roles; a machine-prepared draft says so; draft review may be null |
| Evidence ledger | sources[] with ID, desk, source_id, institution_id, language, published_on, url, body SHA-256 | Exact public production ID; pinned archived original, registered enabled desk/source, no shadow IDs |
| Content | overview, sections[] containing thematic claim objects | Several genuine thematic questions; no duplicate chronology in prose |
| Claims | id, claim_kind, text, source_record_ids[], limits, optional counterevidence_ids | Every substantive claim cited; published issuer statement never silently becomes independently verified fact |
| Related | related_briefs[], related_timelines[] | Exact approved artifact slugs only; each artifact independently approved |
| Lifecycle | revision, changes[], approval only when approved | Stable slug, dated human-readable changes, version hash bound to all editorial and cited source fields |

### Source ledger

Keep **one** normalized entry per original production record; claims reference its ID. Reuse one publisher release across multiple topics, but **count sources and activities separately**. Source records must retain exact source-issued URL and original publisher date; no manufactured URL, institution, language or event date.

The validator must recompute SHA-256 over the precise **stored original UTF-8 text** and compare with the expected preserved digest, then reconcile desk/source/institution, enabled public desk membership, original title/language, and publication date in a **scratch-copy read-only SQLite** connection. A later archive correction forces explicit re-review and a revised Dossier digest, never a silent pass.

The stored capture time remains a separate metadata field obtainable from the verified archive; it must not be copied as an event date. If a claim needs an exercise/event date, its evidence must include an attributed **event interval and basis** (reported, planned, retrospective, or uncertain) and not be inferred from the publication date. A one-source press release may describe multiple activities; two releases may describe one exercise.

### Three content claim classes

- **issuer_statement**: “MINDEF reported X on Y”; support requires verbatim source original, attribution and a date-aware reading. The fact verified may be that MINDEF *said* X, not that X occurred.
- **documented_publication**: independently verifiable publishing/document lineage (e.g. two ministries announced different time windows), clearly separate from proving either announced activity actually happened. Independent issuer count is explicit and must not be inflated by copies.
- **editorial_interpretation**: original IPR synthesis that cites its premises, discloses unresolved alternative explanations and never asserts ungrounded strategic intent, operational performance or causality.

Avoid a raw boolean such as “verified_event”: a validator cannot prove the real-world occurrence of a military activity from a press release.

Each claim gets a **stable ID**, bounded text, one or more exact source IDs, attributed event date only when support exists, and an optional/mandatory limitations field as dictated by claim type. Contrary accounts are **first-class**: disagreement group references both claims/sources and includes editorial reconciliation text or explicit abstention. Do not allow “no activity” claims based solely on missing collected records.

### Source admissibility and rights are independent

A source can be:
1. **Preserved** (integrity, identity and exact bytes reconcile).
2. **Eligible for editorial assessment** (live public desk; machine screening state disclosed; human override explicitly recorded where applicable).
3. **Admitted for a particular Dossier claim** (named editor, dated review, actual source reading and independently recorded receipt).
4. **Authorized for a specific public display action** (link, paraphrase, brief excerpt, full text, image — separately evaluated in a trusted source-use decision, not implied by levels 1–3).

Model relevance screening is not a right to publish. An existing “not_selected” flag, such as Singaroo 4428, requires independent owner review; a “pending” flag is not acceptance either. An editorial review of one Brief/Timeline never approves a new Dossier claim.

**Do not add publisher excerpts or third-party images to public Dossier JSON in B1.** Use exact IDs, stored-text digests and original **IPR-authored** claim prose. An optional **private reviewer-only evidence basis** may contain excerpt hashes or small excerpts where permitted, stored outside public site and action logs; source-use terms determine any quoting or linking. Avoid encoding “permission=true” in self-authored Dossier JSON. Public release must consult a separately owned, audited permission decision and should stop on unresolved source-use rights.

The current [MINDEF source-use inquiry](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319) was drafted but **not sent**. The existing [public record full-text exposure audit #326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) is separate and must not be silently “fixed” by this schema work.

## 4. Editorial state machine: one immutable content version at a time

~~~text
IDEA / EVIDENCE CANDIDATE
         |
         v
DRAFT (may change; never included in public build)
  |      |
  |      +--> SOURCE / RIGHTS HOLD --> REVIEW / SCOPE REVISION
  |
  v
SOURCE-RECONCILED DRAFT (machine gate only; NOT editorial approval)
         |
         v
HUMAN EDITORIAL REVIEW (substantive claim/source matrix)
         |
         v
EXACT CONTENT-DIGEST APPROVAL (owner authorization receipt)
         |
         v
APPROVED SNAPSHOT (release eligibility, subject to rights gate)
         |
         v
PUBLICATION (separately authorized B2 rendering + deployment)
         |
         +--> proposed revision -> new DRAFT -> fresh review -> fresh approval
~~~

The validator must never itself manufacture approval, sign editorial receipts, assume a human review from “updated_on” or infer publication from a merged branch. Explicit approval needs actual editor name, approval date, source of authorization and SHA-256 over **all** public editorial fields, source identities, revision notes and source-use decision references, excluding the approval object itself. A timestamp check alone cannot verify human authorization. Require an independently owner-controlled approval receipt/check before deployment rather than trusting user-edited JSON that calls itself approved.

**Digest rule:** UTF-8 canonical JSON with sorted object keys, no extra whitespace, ensure_ascii false, list ordering preserved, and an exact list of fields excluded from the approval digest. Reject duplicate JSON object keys before hashing; never silently choose last occurrence. Changed claim wording, coverage limits, source hash, linked artifact, rights receipt reference, or revision history invalidates the digest. **Approval applies to a version of the Dossier, not the stable slug forever.**

**Revision minimum:** one slug and monotonically increasing integer revision. Append dated, reader-readable changes describing material added, amended, withdrawn, or re-attributed claims, with source references. A Dossier can be reviewed with **no changes** and an updated review date (which still changes digest if public). Commit history assists provenance, but is not the reader-visible change log. Decide permanent snapshots separately in B2; do not expose older versions with newly discovered attribution errors as automatically authoritative.

## 5. CLI and repository behavior

Planned offline commands after B1 implementation:

~~~shell
python scripts/validate_dossiers.py --fixtures tests/fixtures/dossiers
python scripts/validate_dossiers.py --db pla_watch.db --dir dossiers --report /tmp/dossier-review-local.json
~~~

- CLI **reads** canonical JSON and read-only production DB; explicit root/directory; no archive/content rewrites.
- Filename must match slug and remain under canonical directory; reject symlinks, path traversal, malformed encoding, duplicate JSON keys, unknown fields and invalid dates.
- If directory is missing or empty, report “no dossiers” and exit safely (decide separate zero-exit vs required-fixture modes). Do not publish an empty Dossier library.
- Machine review report uses metadata/IDs/digests/error categories only. Never echo private research notes or publisher original bodies to Actions logs, stdout or site.
- A rights or machine-screening hold is **not** the same as corrupted source bytes. Diagnostics must distinguish preserved integrity, provenance eligibility, editorial review and source-use permission.
- Do not allow “--approve”, “--publish”, or editor impersonation commands in B1. Do not alter site/render.py or import dossier modules into production path.

## 6. Two gates to reconcile before any B2 implementation

**A. Frontend/Timeline integration:** PR #181 (Timelines) and sitewide frontend #323/#317 currently touch Analysis and templates. B1 stays away from site and uses the existing Timeline data contract as conceptual precedent only; no second timeline engine or templates. B2 needs the then-merged base and an owner-reviewed URL/design decision. No empty public library.

**B. Publisher/source-use policy:** #326 needs evidence of the actual public record-page display and an owner/legal decision. A future Dossier UI must default to **IPR-authored summaries and source metadata** and not inherit the record renderer's indiscriminate full-body display; source links/quotations remain governed by rights decisions. The security posture is **do not assume archival possession grants permission to display or redistribute**.

## 7. Questions intentionally deferred (with recommendations)

1. **Who updates living Dossiers?** Assign a single owner/editor, not an AI auto-update schedule. A private weekly *suggestion* queue may emerge later; no auto-admission of collector records. An optional 60–90 day review reminder is editorial hygiene, not a requirement to fake ongoing activity.
2. **How many Dossiers at launch?** One narrow, reviewed subject. Two or three weak collections give a worse institutional signal than one maintained source-linked dossier.
3. **Do Dossiers get issue numbers or DOI-style citation identities?** No issue numbers. Stable slug plus human-readable revision and last-review date; external DOIs only if there is a later scholarly citation demand.
4. **Are entity graphs and cross-desk timeline rollups part of v1?** No. Claims/source IDs supply future structured links without building a premature graph.
5. **Should publisher text be replicated into the public sidecar?** No. Keep source-specific rights and reviewer-only audit separate; public Dossier serves original analysis and bounded citations only after clearance.
6. **Should every source be “fully screened” first?** No model spending/reanalysis just to satisfy a new schema. Human source-by-source admission controls are independent and stronger; screened-out evidence requires an explicit documented exception.
7. **Should the Dossier be longer than a Brief?** Not by design. A Dossier needs richer reference structure and longitudinal utility, not word count.

## 8. Build sequence, no concurrent file collisions

**B1.0 — Owner evidence gate** (outside code): approve or reject the *exact pilot question/period*, inspect Singaroo screening reasoning, make documented source-use decisions, review a claim/source matrix. A code scaffold is not authorization for a live pilot.

**B1.1 — Pure strict contract + synthetic fixtures** (dedicated PR only after B1.0): shape, dates, duplicate JSON keys, safe types/slugs, claim kinds, source/claim relations, exact editorial approval digest invalidation. No DB or site dependency in the initial tests.

**B1.2 — Read-only source reconciler** (same B1 branch after contract): live public source/desk/institution identity, source content hashes and publication dates, read-only SQLite scratch copy, screening holds, drift and rights receipts. Do not modify existing Timeline or Brief validator.

**B1.3 — Review-only CLI and test matrix**: explicit error vs review hold vs editorial/publisher permissions; strict no-write proofs and full offline exact-head CI; private owner review packet; no publication, no repo output mutation.

**B2 — Public presentation** (separate authorization, branch and PR): only after B1 approval and frontend/Timeline reconciliation; minimal Analysis sub-navigation, approved-only static detail, canonicals/sitemaps/links; human layout QA and publisher rights gate. Avoid duplicating or retroactively amending fixed Briefs.

**Stop condition of this RFC:** owner and implementer can agree on the data contract, reviewer authority and exact test/phase boundaries. No production module or public Dossier content is implemented by this document.
