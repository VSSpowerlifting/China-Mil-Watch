# Singapore MINDEF generated-record text — measured technical exposure

**Audit date:** 2026-10-09 (Eastern), GitHub execution shortly after midnight UTC on October 10.  
**Subject:** [Source-use issue #326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326), independent of the Living Dossier publication decisions in [#319](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/319) and [#321](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/321).  
**Evidence:** [Successful read-only Actions run #38017599987](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/38017599987). The base repository commit was `0487bfc0480bd94a9d4471f927c449c506f07cbf`. The one-time workflow was removed from the lasting audit PR.

## Executive result

A new read-only checker, `scripts/audit_generated_record_text.py`, reconciled `pla_watch.db` rows for the **exact** `sg_mindef_releases` source against the corresponding `output/record/<id>.html` files. It verified captured-text visibility through the generated HTML's `div.original-text` content and a normalized rendering comparison against the corresponding full **available captured** `articles.text_original` field, without printing or writing any publisher body.

| Measured property | Result |
| --- | ---: |
| Singapore MINDEF records in tracked DB | **84** |
| Corresponding generated `record/<id>.html` pages found | **84** |
| Missing generated record pages | **0** |
| Records with nonempty captured original-text field | **83** |
| Pages containing `div.original-text` | **83** |
| Pages whose displayed original-text container equals the **entire available captured stored body** (normalized) | **83** |
| Pages with displayed body different from archived original | **0** |
| Pages with no original text rendered | **1** — record **#4936** |
| Pages with a link matching the stored publisher original URL | **84** |
| Missing original-source links | **0** |

**Exact interpretation:** this is **83 instances of full captured archival body displayed by the generated static HTML**, not a finding that 83 official first-party websites' complete current articles have been copied byte-for-byte. The capture can be partial or contain page furniture, as the existing record template warns. **The live CDN distribution could not independently be confirmed** through external retrieval of record URLs in this audit. The results certify tracked generated artifacts, not requests served to users or crawler indexing.

An archive/body match does **not** establish ownership, licence, permission, infringement or a legal exception. This is a bounded technical inventory for qualified owner/legal review.

## Method and reproducibility

1. Read the tracked SQLite database using `scripts.reconcile_db.read_only`, which copies the original and its SQLite sidecars to scratch before querying. Select exactly `articles` belonging to the stored source slug `sg_mindef_releases`.
2. For each numeric ID, open the corresponding generated HTML **only if present**. Parse `div.original-text` with Python's standard-library `HTMLParser`; collect only its decoded text. Normalize whitespace in the rendered text and in the archived paragraph text, matching the current Jinja record template's stripped nonblank `<p>` generation. Separately verify that the exact original publisher URL appears as an `a[href]` anchor.
3. Return only **aggregate counts, safe status labels and numeric record IDs**. No raw source title, article text, screenshot, photo, model reasoning, copied passages or personal contact is emitted. The checker itself never writes a report file.
4. Compare the original `pla_watch.db` SHA-256 before/after. The Actions run additionally confirmed unchanged archive and generated output via `git diff`, no WAL/SHM residue, and a reproducible **13/13 synthetic parsing/checker test suite**.
5. A separate Python/HTML validation pass on any proposed remediation must preserve the canonical record ID and citation route, source metadata and links permitted after legal review, while explicitly testing the chosen public-text policy.

Reproduce, read-only:

```sh
python -m unittest tests.test_audit_generated_record_text -v
python scripts/audit_generated_record_text.py \
  --db pla_watch.db --output output --source sg_mindef_releases
```

### Controls, limits and caveats

- Source scope is **one** source slug only. This does not count all IPR sources, China Desk pages, or other institutions' full-text display; don't extrapolate Singapore percentages to the corpus.
- A successful original-body equality test validates the static renderer's **captured text parity**, not that the original publisher's current HTML body is the same, that no extra captured text is present, or that the excerpt/quotation permissions are sufficient.
- HTMLParser audits ordinary generated markup, not CSS/JS/network/CDN policy, actual search-engine indexing, HTTP caching, robots headers, or live visitor exposure.
- No automated lawyer, fair-use/fair-dealing determination, permission grants, contact or source-rights assumptions are produced. The official [MINDEF Terms of Use](https://www.mindef.gov.sg/terms-of-use/) §§5–6 must be assessed by a qualified human for linking and reuse actions.
- The current IPR [content/data rights declaration](https://github.com/VSSpowerlifting/China-Mil-Watch/blob/main/CONTENT_AND_DATA_RIGHTS.md) correctly disclaims third-party text ownership but **is not itself a permission grant** from MINDEF.
- The proposed Dossier B1 pure validator, source reconciler and private CLI are in separate, stacked PRs [#328](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/328), [#329](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/329) and [#330](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/330). This issue is independent and does not import their contracts, approve Singaroo #4428 or authorize a public Dossier.

## Policy/design alternatives for an owner-facing decision

| Option | Benefits | Costs / risks | Decision authority |
| --- | --- | --- | --- |
| **A. Permission-backed full displayed capture** | Retains public original-language document inspection and current researcher experience | Needs defensible action-specific permission/rights basis; capture fidelity and image rights separately assessed | Qualified source-use reviewer, documented publisher scope, owner approval |
| **B. Limited excerpts and metadata** | Source trail remains useful; lower distributed textual volume | Excerpt choice and licence/legal limits require actual source-by-source review; no universal safe character limit can be assumed | Qualified review + editor selection |
| **C. Public metadata-only, private preserved original** | Preserves record ID, date, institution, capture fingerprint, internal archive continuity and citations without publicly emitting full body | Readers lose page-level full-text inspection; public search/indexing and source comparison change; original-site availability becomes more significant | Owner + legal/permissions review; dedicated narrow renderer PR |
| **D. Restrict public access to affected record bodies pending decision** | Limits potential ongoing redistribution while facts are reviewed | Could break reader links, weaken indexing, mislead users and alter published citation expectations if not done carefully | Owner + qualified reviewer; explicit reversible rollout/rollback plan |

**No option is selected by this audit.** A metadata-only public default might be an appropriate future safeguard, but *do not preemptively alter the existing live renderer* or remove the archived private evidence. An unauthorized blanket suppression can itself damage research continuity.

## Technical acceptance for any future renderer amendment

- Source- or rights-decision-scoped behavior with **default-deny for unapproved raw body output**, subject to explicit owner policy choice, rather than geographic inference (“Singapore = prohibited”). Other government issuers' rights are distinct.
- Maintain exact existing record identity `record/<id>.html`, provenance information, citation text, captured body hash and reported original-language status, even where public original text is not displayed. Retain authorized outbound links according to their specific terms.
- Distinguish “archive has original text privately” from “original text is publicly displayed.” Never show “Original unavailable” merely because the public presentation intentionally withholds it; that would falsify capture status. Add precise attribution.
- No changes to archival SQLite, capture/checkpoint logic, publication dates, machine screening outcomes, historical Briefs, existing Timeline sidecars or unrelated desks.
- Deterministic static HTML generation: synthetically test both display-allowed and metadata-only cases; a denied source **must have zero third-party original text in HTML, feeds, snippet metadata or JSON-LD**, not just visually hidden CSS. Verify no raw-body excerpt is echoed into serialized client data.
- Verify source identity, canonical and sitemap routes, keyword/search snippets, accessibility, no-JS, print, existing backlinks, bytewise preservation where expected, and full exact-head CI after the frontend #323 and Timeline #181 integration.
- Human review of legal/source-use decision must precede permission ledger entry; machine audit and CI are **not** evidence of licence or human approval.

## Disposition

This source-specific technical scoping phase is **complete for the tracked generated HTML snapshot**: the previously unknown count is now known (83/84). Keep [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326) **open** until the separate rights assessment, production site delivery confirmation and owner-authorized remediation decision are recorded. Do not accidentally close the source-use ticket based on 13 passing synthetic tests.
