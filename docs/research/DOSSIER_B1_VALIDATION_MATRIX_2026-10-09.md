# Living Dossiers B1 — executable test and review blueprint

**Scope:** implementation planning only; tied to [B1 #321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321). This is not a test report or implemented functionality. The [synthetic JSON design example](examples/dossier-v1-synthetic.json) contains invented source IDs and **must never be placed in dossiers/** or published. Use fixture SQLite with equally synthetic source rows to exercise any future implementation; do not edit production database.

## Engineering acceptance in one sentence

A Dossier JSON file becomes a **mechanically verified, unpublished draft** only when its shape, human-authored claim references, preserved original-version digests, published source identities and screening/rights review holds can all be reported distinctly **without altering the source archive or emitting a public page**. This gate cannot certify real-world events, inference quality or copyright permission.

## Test matrix, grouped by trust boundary

| ID | Fixture / adversary | Expected result | Test layer |
| --- | --- | --- | --- |
| D01 | valid synthetic draft, verified fake SQLite sources | passes structure+parity as **draft**, never publishes | contract+DB |
| D02 | absent Dossier directory | no public dossiers; explicit “none” | CLI |
| D03 | source file outside canonical directory / ../ traversal | reject | file loader |
| D04 | symlink to approved-looking JSON | reject | file loader |
| D05 | filename and slug mismatch | reject | file loader |
| D06 | invalid UTF-8 or duplicate JSON object key | reject | loader |
| D07 | unknown top-level, section, claim or source field | reject | schema |
| D08 | bool used for integer revision or source record_id | reject | schema |
| D09 | unsafe slug, HTML tag, control char, double whitespace or overlong prose | reject under precise text policy; harmless prose must remain readable | schema |
| D10 | invalid leap-day/date, reversed scope, publication outside relevant editorial review | reject or explicit out-of-period-context designation | dates |
| D11 | empty title/question/scope/collection limits | reject | schema |
| D12 | no material claim or only a chronological list | reject / mandatory human thematic review depending on machine-checkability | schema/editor |
| D13 | duplicated section, claim, source ID or contradiction ID | reject | schema |
| D14 | claim references orphan source ID | reject | schema |
| D15 | same source appears in two thematic sections | allowed, deduped source ledger; not counted as two issuers | view data |
| D16 | one record describes two activities | no fabricated two-source count | event grouping |
| D17 | two press releases describe the same exercise | source count 2; activity count 1 only after editor-confirmed grouping | event grouping |
| D18 | comparison labels publisher-duplicated text as independent issuer corroboration | hold for human lineage, never machine “verified event” | editor |
| D19 | unsupported “government intended”, actual combat readiness or causal-effect claim | editorial rejection even if IDs valid | human |
| D20 | publisher report of planned future phase mislabeled “completed” | review hold; editor verifies exact tense and dates | attribution |
| D21 | no record event date, publication date inserted as event date | reject/hold; cannot infer event date | attribution |
| D22 | unresolved differing publisher start dates hidden or collapsed | editorial hold requiring disagreement/reconciliation or abstention | editorial |
| D23 | source publisher date mismatches SQLite | reject | DB |
| D24 | source URL/desk/source_id/institution/lang mismatches SQLite | reject | DB |
| D25 | numeric public ID resolves to disabled/noncontract/shadow source | reject public eligibility | registry+DB |
| D26 | typed private Japan/Vietnam shadow ID in numeric source field | reject | schema/registry |
| D27 | stored original text missing or too short for claimed citation | reject claim review; cannot rely on title alone for substantive text claims | DB/editor |
| D28 | original body changes but historical content_hash unchanged | reject using **recomputed stored body SHA-256**, not stale article content_hash | DB |
| D29 | title changes with same record ID | reject/hold when title is a pinned field in approved citation | DB |
| D30 | model screening status pending | expose pending status; explicit human admission needed for Dossier use | admission |
| D31 | model screening not_selected (e.g. #4428) | blocking human-review hold; NEVER flip SQLite | admission |
| D32 | fake “editorial accepted” field with no independent approval receipt | reject promotion | admission |
| D33 | source-use decision missing for one citation | remains private review; refuse public publishing or rights-dependent link/quote | rights |
| D34 | self-declared rights permission but missing signed/owned evidence | reject publish eligibility; never treat JSON checkbox as legal grant | rights |
| D35 | permission to link but not reproduce text | metadata/link policy only; never emit body or image | rights |
| D36 | publisher source body or image copied verbatim into Dossier JSON | reject in v1; no such public-content field | schema/rights |
| D37 | approved Brief linked to draft or absent Timeline | refuse public backlink; no inherited approval | related |
| D38 | previously approved Timeline becomes stale after content edit | target no longer approved; reject link or skip in private review, never public orphan | related |
| D39 | draft has an approval object | reject | approval |
| D40 | approved status without actual owner receipt, approval date and exact digest | reject | approval |
| D41 | approved digest computed over wrong canonical representation | reject | approval |
| D42 | postapproval edit to prose/source hash/rights ref/change log/related link | invalidate exact version approval | approval |
| D43 | copied Brief No. 15 approval as Dossier authorization | reject distinct artifact approval | approval |
| D44 | reviewer name “pending”, “unreviewed” or model name passed as human approver | reject | approval |
| D45 | edited revision number backwards or duplicate change receipt | reject | revisions |
| D46 | same stable slug, legitimate new reviewed revision | fresh approval; original published text not silently overwritten in Git review | revisions |
| D47 | missing review note or source-selection gap under an explicit scope | hold; don't pretend no publication means no activity | editorial |
| D48 | source from one ministry framed as second nation's confirmed position | editorial rejection; originating issuer remains explicit | provenance |
| D49 | malformed source-use decision itself | fail closed; report no permission, not fabricated default | rights |
| D50 | CLI run against tracked SQLite | before/after DB file SHA equal, no WAL/SHM, no output or historical sidecar edits | integration |
| D51 | validator logs on failing malformed publisher text | metadata/error categories only; no raw source bodies or private notes in stderr/Action artifacts | privacy |
| D52 | synthetic fixture passed to production/public publisher path | rejected; cannot publish a fixture or unknown source | deploy isolation |

### Tests that belong in B2, not B1

R01: zero approved dossiers => **no** index or nav tab. R02: a draft/fake approval must not be indexable, linked, canonical or in sitemap. R03: approved route only after the content digest, source-use and independent receipt checks. R04: record links use stable numeric IDs; no broken route and no invented backlink in historic Briefs. R05: long prose, keyboard focus, reduced-motion, forced colors, print and 375/1280 px browser. R06: no-JavaScript remains a complete research reading experience. R07: an approved version update shows dated changes and version attribution, not an imperceptible overwrite. R08: existing Brief/Timeline output byte preservation and no new feed without express authorization. R09: permitted metadata/link display cannot accidentally copy `record.text_original` through a reused template.

**Important:** a source-rights decision is not a substitute for full text being safe to show. The existing rendered record page source-use risk in [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) is a separate review; B1 tests may reason about permissions without implementing any live renderer fix.

## Focused implementation layering

~~~text
Synthetic JSON fixture + fake SQLite
  -> strict parser (key duplicates / path / type / date)
  -> in-memory schema validator (claims + IDs + relationships)
  -> source reconciler (read_only scratch SQLite + live desk registry)
  -> human-screening/rights receipt checker (no self-declared permissions)
  -> exact editorial digest validator (requires separate real human approval)
  -> private machine report: errors, holds, review questions
  -> STOP. No public renderer in B1.
~~~

### Suggested result shape for editor-facing CLI

~~~json
{
  "schema": "ipr-dossier-validation/1",
  "source": "synthetic-draft",
  "status": "draft-only",
  "structure_valid": true,
  "archive_reconciled": true,
  "editorial_review": "pending",
  "source_use": "pending",
  "eligible_for_publication": false,
  "errors": [],
  "holds": ["human-editorial-approval-required", "source-use-review-required"]
}
~~~

The **error** category means the claim, source identity, input safety or approval state is mechanically wrong. The **hold** category means the machine cannot certify an actual human decision, source-use permission, content interpretation or readiness for publication. Passing tests can clear errors without clearing holds.

## Implementation pull-request discipline

- Start B1.1 **only** once B0 #319 has a recorded owner-accepted scope. Until then, this blueprint is design input and the example remains under docs/research, not dossiers.
- On a B1 branch, preserve the actual current main SHA in the PR and recheck after merges; avoid touching the conflicted Timeline #181 and large frontend #323.
- Run synthetic narrow tests first, then strict local schema/DB reconciliation, then full offline repository tests against **the exact PR head**. A green earlier commit is not green for later changes.
- Compare tracked `pla_watch.db` hash, working-tree status, output/ Brief/ Timeline sidecars and absence of WAL/SHM before and after every real-data smoke pass.
- No AI scoring, publisher refetch, email, cron or GitHub automation required for B1. Rights-dependent source reuse remains gated regardless of CI status.
- Stop when the owner receives a deterministic, legible draft-only validation report and test evidence. No publish or merge implied by green CI.

## Explicit future editorial review questions

1. Is one nonchronological subject question genuinely useful beyond the already approved Brief and existing Timeline?
2. Can each material sentence be linked to exact original-language publication wording and distinguish assertion from operational evidence?
3. Have duplicative reports been separated from genuine independent issuers and events?
4. Are the important source gaps and contradictions explained without manufacturing completeness?
5. Is each source's permission to link, paraphrase, quote or republish documented by an independent decision?
6. Are all changes reviewed and visible so a reader can tell what changed in the Living Dossier?
7. Is the owner explicitly approving this **exact Dossier version**, rather than a research topic, related Brief or CI result?

A “no” can properly mean no publication. Institutional credibility is worth more than a filled-out page.
