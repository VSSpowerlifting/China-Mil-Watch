# Dossier v1 — normative field and lifecycle design

**Status: proposed v1 API, not an implemented validator or an approved publication.**
See [engineering RFC](DOSSIER_B1_ENGINEERING_RFC_2026-10-09.md), [test matrix](DOSSIER_B1_VALIDATION_MATRIX_2026-10-09.md), and [synthetic draft fixture](examples/dossier-v1-synthetic.json).

## Canonical source, parsing and identities

Use a single file \`dossiers/<slug>.json\` per subject only after #319 owner scope approval. No executable import of this design package into production. The proposed Python validator is authoritative in B1; do not maintain two divergent JSON Schema and Python interpretations.

- JSON must decode as UTF-8 and be a root object; reject duplicate object keys at **every depth** with \`object_pairs_hook\` and reject NaN/Infinity. No comments, unsafe URLs, symlinks, directory traversal, unrecognized fields or silent coercion of booleans to numbers.
- \`slug\`, \`sections[*].id\`, \`claims[*].id\`, and \`disagreements[*].id\`: lowercase ASCII slugs matching \`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$\`, at most 80 characters. The root slug equals the canonical filename and cannot change through revisions; a renamed subject becomes a deliberate new publication identity.
- Text is trimmed, nonblank, Unicode NFC, with no C0/C1 control characters or markup: no HTML, scripts, Markdown links/images, Jinja delimiters or third-party source-body fields. Avoid inventing a word-count requirement for original analysis; enforce bounded strings and meaningful human editorial review separately.
- ISO date means exactly \`YYYY-MM-DD\` and \`date.fromisoformat\` successful. Dates are source-published, actual claimed event interval, collection/capture time and human editorial timestamps **as distinct fields**. Source-published date is never a proxy for an exercise/event date.
- For this v1 prototype, scope is **retrospective**: \`scope.period_start <= scope.period_end <= updated_on\`. Future-looking official statements may appear as issuer claims, but unsupported predictions do not extend the Dossier's observed coverage.
- Lists preserve authorial order where meaning depends on it; source ledger entries and related-slug lists should be canonically sorted for deterministic serialization. Reject repeated IDs, not merely deduplicate input silently.

## Exact proposed root keys

| Field | Type and semantics | Required / conditional validation |
| --- | --- | --- |
| \`dossier_schema\` | literal integer \`1\` | Required, reject \`true\`, \`1.0\` |
| \`slug\` | string, stable URL identity | Required, safe and matches file stem |
| \`title\` | nonempty original IPR heading | Required, no publisher headline pasted as a Dossier title |
| \`dek\` | concise original description | Required |
| \`research_question\` | one bounded subject question | Required |
| \`editorial_status\` | \`draft\` or \`approved\` | Required; never infer from approval on a related Brief |
| \`author_name\` | actual author / preparer | Required; may disclose AI preparation in drafts |
| \`editor_name\` | human responsible editor, or explicit pending in draft | Required; cannot be a machine or “pending” when approved |
| \`prepared_on\` | ISO date | Required; <= updated_on |
| \`updated_on\` | ISO date for this editorial content revision | Required; >= prepared_on |
| \`reviewed_on\` | ISO date or null | Required; null allowed for draft, approved requires >= updated_on |
| \`revision\` | integer >= 0 | Draft may be 0; approved must be >= 1; historical increase checked against prior version separately |
| \`scope\` | strict object defined below | Required |
| \`overview\` | original IPR-written bounded thematic synopsis | Required |
| \`sources\` | nonempty list of source-ledger objects | Required; no duplicated public record IDs |
| \`sections\` | >=2 distinct nonchronological thematic sections | Required; per-section claim list nonempty |
| \`disagreements\` | list of explicitly unresolved/reconciled claim comparisons | Required; [] allowed when no conflict exists |
| \`related_briefs\` | list of native Brief slugs | Required, [] allowed; approved target only |
| \`related_timelines\` | list of Timeline slugs | Required, [] allowed; approved target only |
| \`changes\` | chronological, monotone version-change entries | Required; [] for unreleased revision 0 |
| \`approval\` | owner authorization receipt object | **Only** when \`editorial_status == approved\` |

## \`scope\` — exact required fields

\`period_start\` and \`period_end\` are ISO dates. \`jurisdictions[]\` and \`institutions[]\` are unique, canonical identifiers or unambiguous editorial labels, not a machine-derived jurisdiction count. \`included\`, \`excluded\`, \`method\`, and \`collection_limits\` are explicit nonempty original text. **Collection limits are not optional**: even a well-covered bounded case must not pretend that inaccessible outlets, uncollected source pages or unpublished activities were observed. A period extension requires a content update and new approval; it is not an automatic crawl setting.

## \`sources[]\` — exact required fields

| Field | Meaning |
| --- | --- |
| \`record_id\` | strict positive Python \`int\`; resolves to one stored **public production** record, not shadow string/UUID/boolean |
| \`desk\` | exact registered live desk slug for that record |
| \`source_id\` | exact registered enabled, contract-validated source slug |
| \`institution_id\` | exact issuing-institution identifier |
| \`language\` | exact original source language; never inferred from desk |
| \`published_on\` | issuer-stated publication date, not capture date |
| \`url\` | original official source URL as preserved in DB; exact match after canonical safety checks, not a guessed website root |
| \`stored_original_sha256\` | lowercase 64-hex SHA-256 of UTF-8 preserved \`text_original\`, recomputed at audit time |
| \`editorial_admission_ref\` | external human source-review receipt identifier, or null in draft |
| \`source_use_decision_ref\` | external, separately owner-reviewed rights-scope receipt identifier, or null in draft |

**Never** turn \`editorial_admission_ref\` or \`source_use_decision_ref\` into a self-attesting permission. A string that merely resembles a receipt does not prove the decision exists or was authorized. Release checking must verify its authority and scope in an independently controlled source, which a purely offline fixture cannot authenticate. If that authority is unavailable, return a **hold**, not “approved.”

No raw full source body, copied image, raw excerpt or third-party HTML is admitted as a Dossier source field in v1. Even where a source is archived, its public redistribution permissions are separate. The default user-facing Dossier is IPR's **original analysis** plus source provenance, subject to approved linking policy.

## \`sections[]\` and \`claims[]\`

Each section: exactly \`id\`, \`heading\`, \`intro\`, \`claims\`. Section IDs are unique and stable across revisions; section order reflects **themes**, not an events-by-day duplicate of the Timeline. A human editor assesses genuine thematic distinction; a validator cannot prove two sections are substantively independent.

Each claim: exactly \`id\`, \`claim_kind\`, \`text\`, \`source_record_ids\`, \`event_period\`, \`limits\`, \`counterevidence_ids\`. Claims have globally unique IDs, unique positive numeric source references already present in \`sources[]\`, and nonempty original text and limitations.

\`claim_kind\` must be one of:

- \`issuer_statement\`: precisely attributed wording, **not independent proof of the activity described**.
- \`documented_publication\`: observation about publication itself or a documentary comparison, **not** an independently verified military outcome.
- \`editorial_interpretation\`: IPR's argued synthesis, with explicit source premises and limitations. Where competing interpretations materially matter, record them in \`limits\` or \`disagreements[]\`.

\`counterevidence_ids\` means **source record IDs**, not claim IDs. Each must resolve to the source ledger; repeated positive and contrary evidence may be legitimately drawn from a single record, but this must never count as two independent issuers. For two disputed *claims*, use \`disagreements[*].claim_ids\` instead. **An empty counterevidence list does not mean no contrary evidence exists outside the collected corpus.**

\`event_period\` is null when no actual event interval can be attributed. Otherwise it is an object with exactly \`start\`, \`end\`, \`basis\`, and \`date_basis\`: ISO ordered event interval; basis one of \`planned\`, \`reported\`, \`retrospective\`, \`uncertain\`; \`date_basis\` is human-authored explanation of who supplied the date and from which record. Planned phases must not be stated as completed, and an after-action document cannot simply retroactively establish the advance publisher's knowledge. Distinguish reported dates from verified real-world dates.

## \`disagreements[]\`, \`changes[]\` and \`approval\`

**Proposed \`disagreements[]\` item:** exactly \`id\`, \`claim_ids\` (two or more extant claim IDs), \`status\` (\`unresolved\` or \`reconciled\`), and \`note\` (written explanation or explicit abstention). Every *known* material contradiction belongs here after human review; a machine can verify references but cannot detect all substantive conflicts.

**Proposed \`changes[]\` item:** exactly \`revision\` (strict positive integer), \`changed_on\` (ISO date), \`summary\` (human-readable substantive change), \`affected_claim_ids\` (list of extant claim IDs, [] allowed for a scope-only revision). On an approved v1, there is one entry for each released revision \`1..revision\`, and the latest entry agrees with \`revision\`. A removed claim can be named in its prose summary even if it no longer appears in current \`claims[]\`; do not falsely relink it to a different current claim. Diffing prior revisions requires a prior-review snapshot in the future B2 gate.

**Proposed \`approval\` item:** exactly \`approved_by\`, \`approved_on\`, \`reference\`, \`content_sha256\`. This binds a human authorization to the exact editorial/source-use-reference version after review; \`approved_on >= reviewed_on >= updated_on\`, actual editor matches \`editor_name\`, and SHA-256 equals the canonical digest of every root field **except the \`approval\` object**. The validator checks internal coherence, **not** that the human signer truly authorized it. Release must also check a separately trusted owner-gated approval record (PR review/owner-receipt under controlled permissions); a typed JSON label alone cannot authenticate a person.

### Content digest in proposed Python

~~~python
def dossier_content_digest(sidecar: dict) -> str:
    # Called after strict parsing and key/type validation.
    import hashlib, json
    payload = {key: value for key, value in sidecar.items() if key != "approval"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
~~~

Lists retain authorial order. A change to claim text, sources, source hashes, scope, review dates, related links, or recorded changes **invalidates approval**. This is only a content-integrity hash, *not a digital signature* or independently verified permission.

## Approval lifecycle and blockers

| Input | Structure result | Editorial result | Rights result | Allowed action |
| --- | --- | --- | --- | --- |
| Valid synthetic fixture, all fictitious record IDs | shape-only pass possible | not admitted | no permissions | private fixture tests only |
| Draft with genuine preserved but pending-screened record | schema/source parity possible | explicit human hold | separate rights hold | keep private draft |
| Valid original + prior \`not_selected\` (Singaroo #4428) | integrity may pass | **blocking source admission hold** | separate | no public Dossier claim |
| Source reviewed and admitted; linking permission unresolved | source/edit pass | reviewed | **public link/display hold** | local private review only |
| Legitimate rights receipt for link but not full-body reproduction | source/edit pass | reviewed | link only | allowed link after owner publication approval, **never copy full body** |
| All source admissions/rights and exact version approved | pass | human-approved | scoped to particular public actions | candidate eligible for separate B2 publication/deploy gate |
| Approved JSON edited or imported old Brief approval | fail hash/authority | stale/unauthorized | irrelevant | withdraw from publication pending fresh approval |

B1 must stop after offline validation and an owner-facing report. B2 is the **only** layer that will produce canonical HTML, index/sitemap routes or public cards, and B2 must revalidate all gates against the current exact source version. No B1 approval emerges automatically from B0, a published Brief, a Timeline or green CI.

## Intentional v1 boundaries

No automated claim truth judgment, event graph, entity resolution, web scraping, LLM generation, source-rights legal determination, public text copies, user account system, database migration, new editorial series, or changed Brief/Timeline route. The contract is precise enough for a narrow Python implementation; it does not pretend that a file format can replace qualified human source analysis.
