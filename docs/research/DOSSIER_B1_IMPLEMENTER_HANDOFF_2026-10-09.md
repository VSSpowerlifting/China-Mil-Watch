# Dossier B1 — implementer cut list and signoff packet

**Planning handoff only; no production validator or public Dossier has been implemented.**
Dependencies and scope: [RFC](DOSSIER_B1_ENGINEERING_RFC_2026-10-09.md), [normative v1 fields](DOSSIER_B1_NORMATIVE_FIELD_CONTRACT_2026-10-09.md), [52+ test blueprint](DOSSIER_B1_VALIDATION_MATRIX_2026-10-09.md), [B0 #319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319), [B1 #321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321), [rights audit #326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326).

## Four narrowly scoped steps

| Slice | Owned files (future only) | Implementation | Pass/fail evidence | Approval boundary |
| --- | --- | --- | --- | --- |
| B1.0 — human evidence gate | No new code; [#319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319) private decision packet | Select exact subject, period and primary-source set; resolve #4428 screening or exclude, decide rights scope with qualified reviewer; approve/decline real pilot | Owner's explicit decision and source eligibility matrix | Without this, **do not** create \`dossiers/<slug>.json\` or declare a real Dossier |
| B1.1 — pure parser and draft schema | \`core/dossier_contract.py\`, \`tests/test_dossier_contract.py\`, synthetic fixtures | Implement only local object validation, duplicate-key detection, canonical paths, claim/source ID graph, date semantics, digest/checks, explicit draft/approved input constraints | D01–D22, D39–D46 shape cases; no real database | Do not interpret valid JSON as real source review |
| B1.2 — preserved citation reconciliation | Extend \`core/dossier_contract.py\` and tests, read-only fixture DB; optionally read-only production smoke | Resolve exact public numeric IDs, original text SHA-256, original title/source/desk/institution/lang/URL/pub-date against registered live source through \`read_only\`; report screening and source-use holds separately | D23–D36; DB SHA/status preservation; fake source is rejected against real DB | Original-body fidelity is not legal reuse or operational fact |
| B1.3 — review CLI and stop | \`scripts/validate_dossiers.py\`, focused tests and documentation | Structured deterministic errors+holds; no source-body log, write, external fetch or model calls; clear abstention, rights and exact-revision approval hints | D37–D52; full repository offline CI on exact PR SHA | Ends at owner-facing *private* report; no site integration, no public release |

Do not create independent, overlapping branches editing the same contract: implement B1.1–B1.3 serially on one clearly owned feature branch once B1.0 is actually approved, or stack branches and merge in order. PR #324 is **B0 evidence audit** and must remain a separate research review. PR #325 is **Briefs editor standard** and must remain independent. PR #181 (Timeline) and PR #323 (frontend) are owned elsewhere; these B1 slices do not touch their files.

## Exact minimum Python API, proposed

~~~python
class DossierValidationError(ValueError):
    """Invalid structure, provenance or approval state (not editorial judgment)."""

def read_dossier(path: Path, source_dir: Path) -> dict:
    """Strict UTF-8/JSON, no duplicate keys/symlink/path escapes; validate shape."""

def validate_dossier_shape(sidecar: dict) -> dict:
    """Pure, deterministic v1 constraints; does not read real evidence."""

def dossier_content_digest(sidecar: dict) -> str:
    """Canonical SHA-256 of every field except approval."""

def reconcile_dossier_sources(
    sidecar: dict, db_path: Path, registry=None
) -> dict[int, dict]:
    """Scratch-copy SQLite; exact source provenance and frozen UTF-8 original SHA."""

def build_dossier_review_report(
    sidecar: dict, records: dict[int, dict], *,
    admission_decisions=None, rights_decisions=None,
    trusted_owner_receipt=None
) -> dict:
    """Errors, review holds and permission gates separately; defaults deny."""
~~~

These signatures are **a proposed design**, not Python currently callable in the repo. Do not import from the unmerged Timeline #181 implementation as a runtime dependency just because its primitives look similar. Compatible strict parsing may be shared after both are merged and tests show actual duplication.

### CLI behavior, proposed

~~~shell
python -m unittest tests.test_dossier_contract -v
python scripts/validate_dossiers.py \
  --source-dir dossiers \
  --db pla_watch.db \
  --report /tmp/ipr-dossier-private-review.json
~~~

Read inputs only. The report path must be an explicit, safe outside-repository review location; private reports must never be committed or uploaded as public Actions artifacts. There is **no** \`--approve\`, \`--publish\`, \`--generate\`, or background model mode.

**Exit policy:** 0 if structure/source checks finished with no errors, even when an editorial/rights **hold** remains; nonzero for invalid input or broken source identity. The \`eligible_for_publication\` field remains **false** unless independent editor and rights gates are verified. If a deploy gate later invokes this CLI, it must explicitly fail when publish eligibility is false even if the diagnostic CLI itself exits 0; do not confuse an informational check's exit 0 with publishing authority.

Return categories: \`structural_integrity\`, \`archive_parity\`, \`source_admission\`, \`source_use\`, \`editorial_approval\`, \`publication_eligibility\`. Report discrete evidence with \`pass\`, \`error\`, \`hold\`, or \`not_checked\`; no blanket \`validated=true\` that collapses human authority into one boolean. Include exact sidecar file path and content digest, safe IDs and categorical reasons. Never emit original publisher text, model reasoning, private permissions correspondence, full private shadow packets, or authentication tokens.

### Separate trust sources — never self-sign

1. Source ledger entries in author-editable JSON can state **what record they cite**, not that a right exists.
2. A reviewer-controlled source admission record (private, authorization traceable) confirms the **particular claim's** use of that precise original edition. Screening flags remain unchanged. If unavailable, hold.
3. A rights decision record specifies **allowed actions** (may link to publisher? refer to public IPR record page? brief quotation? public body reproduction? photographs?), publisher and scope/date. A permission to link is not a licence for full-body display. If unavailable, hold; only qualified reviewers determine law/permission.
4. A human owner's exact Dossier approval separately binds the canonical public-content digest to the authorization reference. Hash alone is not identity proof. A GitHub PR comment/README string is not independently authenticated permission in the offline validator.

**Threat model:** a malicious or mistaken contributor can author any JSON key and calculate a matching digest. Therefore \`editorial_status: approved\` plus a self-reported \`approval\` object cannot, alone, confer publish permission. The release gate must use a separately configured, human-owned trust anchor (such as branch protection plus a verified explicit owner review of the exact commit and publication artifact). This is a B2 implementation and operations decision, not invented B1 tooling.

## Deliberate abstentions and known deficiencies

- **Document preservation:** does not confirm operational occurrence or performance.
- **Source-use rights:** current MINDEF terms have unresolved conditions; do not turn a stored SHA, government URL or “noncommercial” description into permission.
- **Screening:** 70 Singapore MINDEF records were pending and 14 not-selected in the audited B0 snapshot, including #4428. A model-negative classification is an editorial lead, not an automatic permanent fact; a human may review an exception explicitly, without rewriting the archive.
- **Unapproved Timeline:** PR #181 draft does not become publicly approved because related Brief No. 15 is approved. A Dossier cannot publish a link to its draft route.
- **Public distribution:** #326 found captured originals emitted into generated IPR record HTML; separate renderer/permissions review is necessary. Do not use a blanket template change in this B1 PR.
- **Source coverage:** single-publisher Singapore Dossier never becomes “corroborated bilateral defence cooperation” just because counterpart navies are named.
- **Revocation/corrections:** B2 must decide preservation and reader treatment of previously published revisions if a source, permission or interpretation is withdrawn. B1 records claims and versions but does not implement immutable public history.

## Owner review checklist for next transition

- [ ] Specific Dossier pilot title, reader question, institutions, dates and exclusions accepted (or alternate selected).
- [ ] Source list and exact publication/version identities approved for *research drafting*, not just an automated shortlist.
- [ ] Singaroo #4428 human screening hold resolved in a recorded decision **or removed from the proposed public evidence**.
- [ ] MINDEF citation/link/excerpt rights scope evaluated, with existing record full-text display issue #326 considered independently.
- [ ] Source-to-claim matrix drafted, with disagreements/negative evidence and limitations explicit.
- [ ] Contract field names, receipt ownership and cross-artifact linked-approval treatment signed off.
- [ ] Future B1 engineering PR assigned **one owner** and a fresh current \`main\` commit, without editing Timeline/frontend code.

When these are done, B1.1–B1.3 can be executed as an isolated, test-driven Python contract slice. If they are **not**, the correct output remains a clean, reviewed RFC, not an unapproved Dossier page.
