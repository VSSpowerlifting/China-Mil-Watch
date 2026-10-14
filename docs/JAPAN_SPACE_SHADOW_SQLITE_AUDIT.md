# Japan space-security candidates — immutable shadow SQL audit

Status: read-only research infrastructure; not a collector, classifier, source-admission approval, or a claim of complete history. Supports #168 and the six source candidates in #169 without modifying that branch.

## Why this matters

IPR's 2026-10-06 Japan readiness assessment found one usable original-language body among 67 distinct URLs in its 2026-09-22 through 2026-10-05 RSS-date window (1.49%). Discovery of a page is not preservation of its full body. The 2026-10-07 GitHub Actions probe separately confirmed challenge-gated official military HTML indexes for the declared collector.

A prior read-only byte-string scan of the shadow database found none of #169's six exact URLs. A row-level audit independently inspected the four SQLite table URL fields and established the same scoped result. This tool makes that result reproducible without trusting a manual inspection.

## Pinned checkpoint and measured data

- State ref observed: shadow/jp-mod on 2026-10-08
- Immutable commit: d57f0a94b2134a68b9f13fb35a0a0b8c8a4ffe13
- Historical path: state/shadow.db
- Expected blob SHA-1: 60f126db5a36369ade81f44f12c3a838cddbfb59
- Size: 212,992 bytes = 52 SQLite pages x 4,096 bytes
- State-head commit message: shadow(japan): run 37716894616-1

| Table | Rows | Interpretation |
|---|---:|---|
| shadow_records | 5 | Five preserved text bodies, all jp_mod_news_ja |
| shadow_unretrieved | 155 | 152 access_challenged, 2 pdf: no_text_layer, 1 oversized_response |
| shadow_pre_bootstrap | 288 | 141 news and 147 site-update discoveries before collection bootstrap; not retrieval failures |
| shadow_validators | 5 | Source validators, not additional archive bodies |

Unretrieved items: 80 from jp_mod_siteupdate_ja, 74 from jp_mod_news_ja, one legacy unassigned. Stored dates are RSS-derived and subject to the documented Japan dateline mismatch. The six source URLs from #169 are absent by exact URL from all four tables in THIS checkpoint. No wider absence claim is authorized.

## Reproduce without network access

Once the separately reviewed candidate source file from #169 is present in the checked-out tree, run:

    python3 scripts/audit_japan_space_shadow.py > /tmp/ipr-japan-space-audit.json

Alternatively, pass the exact separately available file with:

    python3 scripts/audit_japan_space_shadow.py --candidates /path/to/reviewed/source_candidates.json

The local repository must have the exact historical commit and blob. Missing objects fail closed; the tool does not fetch or silently substitute the advancing state branch.

The code resolves only the supplied 40-hex commit:path Git object and validates the exact blob SHA-1. It copies that blob to an auto-cleaned temporary directory outside the tracked checkout, then uses an immutable read-only SQLite URI, PRAGMA query_only and PRAGMA integrity_check. A missing table, unknown table or malformed body fails closed. The optional --commit and --blob flags must agree on the exact same historical object and cannot refer to symbolic branches. Running against another commit is a different checkpoint, not a replacement for the October 8 measurement.

The source-admission input is also **pinned**: JSP01–JSP06 must match the six exact official URLs in PR #169. Even another plausible official URL under the same host is rejected until a newly reviewed audit contract is created. This prevents a silently altered candidate list from producing a misleading report. These URLs are research candidates, **not archived-body identities**.

The JSON report contains historical commit/path/blob and SHA-256 provenance, counts per table, source/reason breakdowns, exact URL hits for each of six candidates and limits on interpretation. It produces no labels, accuracy estimates, owner approvals or source collection.

## Tests

    python3 -m unittest tests.test_japan_space_shadow_sqlite_audit -v

The tests build SYNTHETIC temporary Git/SQLite fixtures. They verify exact URL equality, distinct database state types, immutable-input behavior, missing/corrupted/wrong objects, duplicate candidate and false-approval rejection, and a direct CLI invocation. No synthetic row is archival evidence or a human label. Ordinary CI can run these without historical shadow objects; full real historical replay requires an explicit local checkout containing the exact Git object.

## Admission and editorial constraints

1. An actual body is admissible for consideration only after verifying its original-language full text, issuer identity, source-stated date, capture time, immutable commit/blob/checksum and legal reuse context.
2. A URL in shadow_unretrieved is NOT an archived full-text source. Pre-bootstrap rows are history of listing discovery, NOT attempts to retrieve and not confirmed coverage.
3. No exact matches for these six candidates in the pinned snapshot does NOT rule out alternate canonical forms, other snapshots or other preserved sources. Do not invent absent record IDs.
4. The Japan shadow scope remains two enabled Japanese MOD RSS feeds; the specific JASDF unit page and MOFA/JAXA sources are not independently enabled. No collector, broad crawl, bypass, topic attachment, classification, production admission or deployment is authorized.
5. This tool and its results are editor-facing. A human source reader must not be fed proposed topic roles as independent evidence. #164's separate HADR process is not a Japan label approval mechanism.

Phase stop: reproducible, read-only audit for subsequent separately authorized source-admission review.
