# Source-publication boundary: S1 synthetic contract (October 10, 2026)

Parent: [architecture issue #332](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/332). Source-use owner/legal decision: [#326](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/326). Baseline inventory: merged [#331](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/331).

**Status: unapproved synthetic-only engineering prototype.** No production collector, pipeline, renderer, database, deployment, workflow, Brief, Timeline, Dossier, official-source text, or rights policy was changed.

## Why this boundary exists

Public `main` currently tracks `pla_watch.db` (which holds captured originals) and generated record HTML. Daily's success and failure-salvage paths commit the database, and Pages serves `output/` through `gh-pages`. The production render also carries forward `output/data/articles.json`, which has source titles, summaries, links and status information but not the full captured body. Suppressing an HTML section alone would not make captured originals private.

The future goal is an owner-approved, access-controlled original-evidence store plus an independently governed, field-allowlisted public representation. Historical Git commits and third-party caches may remain accessible; this phase does not attempt deletion or make retroactive promises.

## Versioned S1 schemas

| Schema | Scope | Field behavior |
| --- | --- | --- |
| `ipr-private-evidence/1` | Fictional in-memory records | Validates numeric ID, source/institution, language, publisher/capture dates, source URL, original title, captured body, machine summary and domain-separated S1 digest |
| `ipr-source-action-review/1` | Untrusted review-reference shape | Action `link`, `brief_quote`, `full_body`, `photo` or `private_retention`; review status, source/date/reference; **not authority** |
| `ipr-public-record/1` | Strict positive allowlist | ID, source/institution identifiers, language, dates, source digest, proposed `record/<id>.html` locator and accurate text-access state |
| `ipr-public-projection/1` | Deterministic collection | Sorted records, count, digest and unconditional `eligible_for_publication: false` |

The public projection contains **no** original source URL, captured body, source title, editorial quotation, photograph or machine summary. It distinguishes `withheld_pending_rights_review` from `no_captured_body`. An author-supplied receipt marked `approved` cannot enable a source-action release; S1 has no independently verified source-use authority. The actual quote/link/full-body permission workflow is deliberately deferred.

The S1 digest (SHA-256 over a domain-separated title/body encoding) is **not** the existing archive `content_hash` or the production `corpus_fingerprint()`; never substitute it silently for either one. A synthetic citation path is not a release permission.

## Read-only rehearsal and limitations

`core/source_publication_contract.py` validates strictly, rejects extra fields, malformed identifiers, dates, inconsistent digests and fabricated publication authorization, and emits source-text-free public projection values. `scripts/audit_source_projection.py` examines a **synthetic test tree located outside this repository** with a private fictional-marker file, returns only fixed diagnostic codes/counts, and checks:

- plain, HTML-escaped, JSON-escaped, percent-encoded and base64-encoded protected *fictional* tokens;
- nested forbidden JSON keys and duplicate keys;
- symlinks, unsupported file types and oversized text files.

A binary file is **explicitly unscanned**; zero detected tokens cannot establish that binary assets, other encodings, photographs, independently drafted quotations, live CDN delivery, Git history, mirrors or production outputs are safe or legally permitted.

Run focused tests (Python 3.9 compatible):

```sh
python -m unittest tests.test_source_publication_contract -v
python -m compileall -q core/source_publication_contract.py scripts/audit_source_projection.py tests/test_source_publication_contract.py
```

The local synthetic suite has **40 passing tests**. The PR must also pass full exact-head repository CI before merge consideration.

The optional standalone rehearsal requires explicitly fictional tokens in an external temporary file and an external temporary HTML/JSON tree:

```sh
python scripts/audit_source_projection.py --synthetic-only \
  --tree /tmp/ipr-s1-fake-site --synthetic-tokens-file /tmp/ipr-s1-fake-tokens.txt
```

Exit 0 means no specified synthetic marker was found in inspected text, **not** that publication is approved; 1 means synthetic findings, 2 invalid audit input. The command never invokes collection, a model, a renderer or deployment, and it cannot claim publisher permission.

## Stop and follow-up

This S1 PR ends at an isolated contract, synthetic tests, documentation and exact-head full CI. No Live S1 data migration. Future S2 is a **new coherent engineering phase** requiring owner selection of an access-controlled, versioned evidence store, independent backups/recovery, and safe changes to BOTH Daily commit paths and the SQLite reconciler before anything private can be claimed. S3 public renderer/export changes and S4 deployment require separate source-use review and explicit release authorization. Keep #326 open; it is not superseded by a green test suite.
