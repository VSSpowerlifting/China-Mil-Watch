# IPR Deduplication Provenance Workbench

Private, explicit offline use of already-held data. This does not activate
occurrence capture, recover discarded historical URLs, approve source use or
custody, or change collection, canonical authority, publication or native IDs.

## Local commands

Run from the repository with its Python 3.9 dependencies and Playwright
installed. `PY` below names that interpreter. The inspected Mac used
`/Users/benjaminyang/pla-watch/.venv/bin/python` (3.9.6); this worktree had no
own `.venv`. A normal provisioned checkout can use `.venv/bin/python`.

```sh
PY=.venv/bin/python
RUN_DIR="$($PY -c 'import tempfile; from pathlib import Path; print(Path(tempfile.mkdtemp(prefix="ipr-occurrences-")).resolve())')"
LEDGER="$RUN_DIR/ledger.db"
SNAPSHOT_SHA=8d4eb2245d7fe6d86da650f1207162cb91f84e3efbc12e8928dfd75659020c02

$PY -m scripts.source_occurrences init --ledger "$LEDGER"
$PY -m scripts.source_occurrences inventory --ledger "$LEDGER" \
  --archive pla_watch.db --snapshot-sha256 "$SNAPSHOT_SHA" --batch archive-20261011
$PY -m scripts.source_occurrences replay --ledger "$LEDGER" \
  --archive pla_watch.db --snapshot-sha256 "$SNAPSHOT_SHA" \
  --batch saved-mindef-20261011 --saved-mindef tests/fixtures/sg_mindef/items.json
$PY -m scripts.source_occurrences export --ledger "$LEDGER" --out "$RUN_DIR/metadata.json"
$PY -m scripts.source_occurrences serve --ledger "$LEDGER" --port 8767
```

Open `http://127.0.0.1:8767/`. Stop with Ctrl-C; reopen with the same `serve`
command and ledger path. The reader revalidates committed metadata on each
request. Keep the ledger path locally; no source batch is exported. To replay
an existing local array of native article dictionaries, substitute
`--documents /absolute/private/batch.json` for `--saved-mindef …`. In Python,
`build_batch()` also consumes `ExtractedDocument` objects through their native
`as_article_dict()` conversion. `saved_mindef()` calls the actual adapter's
`extract()` on the existing saved HTML, never `discover()` or `fetch()`.
A parser refusal rejects the whole batch; it is not a partial accepted replay.

The displayed pin is the measured 48,263,168-byte native archive at main
`56c1144815f2c6f0d0474ec7f8c6c5db53da3445`. A different input needs its own
explicit measured SHA-256 and new batch identity. Inputs must be externally
quiescent, checkpointed regular SQLite files with no adjacent WAL, SHM or
journal. The original is read through `scripts.reconcile_db.read_only`; its
bytes, inode, timestamps and absence of sidecars are checked before/after the
scratch copy and processing. This is a quiescent-input contract, not a repair
of #349 or an atomic snapshot protocol for active writers.

`init` exclusively creates a new ledger. Destinations must be outside every
Git checkout, with an existing owner-only parent (0700) and owner-only files
(0600). Symlink components, hardlinked ledgers, permissive private directories,
unsafe SQLite sidecars and report overwrites refuse. Resolve the system temp
alias as in the example rather than supplying a symlink path. No permissions
are changed by the workbench. Reports are created exclusively. Filesystem
permissions protect the files; the reader binds only loopback and is accessible
to local clients. `noindex` is not access control. There are no remote assets,
publisher embeds, JavaScript, write endpoints, background jobs or activation
flags. Source hyperlinks only make a request when the researcher chooses them.

## What the ledger means

- **Archive inventory / existing_archive_row:** one observation per retained
  native row. Its historical batch membership and dedup decision are unknown.
  Numeric native pointers resolve in the selected snapshot. This inventory
  cannot reconstruct observations or URLs already discarded by collection.
- **Observed replay:** one identity for every supplied position, including
  repeated identical dictionaries or URL values. Native normalization runs in
  process, then the shared detailed title engine and URL/hash engine execute.
  Title suppression records its selected observation; URL/hash suppression
  records its actual reason and representative or all matching native IDs.
  A prospective survivor with no native pointer is not an archived record.
  Collection holds, keyword filtering, storage, model work and publication are
  outside the replay. In particular the existing historically-held saved
  MINDEF fixture can survive these two stages without being admissible.
- **Identity:** source/desk/institution are checked against both the selected
  native source table and existing desk manifests, with governed host aliases.
  Known source identity or locator disagreement refuses. An unknown supplied
  identity is represented as unknown plus a digest, not promoted or guessed.
  Source identity verification does not authenticate publication or grant rights.
- **Evidence:** extracted title/text digests hash those exact fields;
  extracted-document SHA-256 hashes their canonical field representation.
  Normalized text SHA-256 hashes native whitespace-normalized nonblank text.
  The legacy SHA-256 hashes normalized **TITLE PLUS TEXT**, separated by a
  newline. Title grouping uses the existing SHA-1 normalization. Neither the
  extracted-document digest nor the saved-local-input-bytes digest is an HTTP
  capture. A producer capture reference and retrieval date appear only when
  actually supplied; saved HTML replay invents neither.
- **Relations:** `same_title_group` is a candidate signal. `exact_url` does not
  establish unchanged body. `equal_normalized_text` and
  `equal_normalized_title_text` use recomputed retained fields and exclude
  blank/unavailable text. Stored legacy-hash suppression still follows the
  actual production stored lookup even when recomputation disagrees. That
  disagreement remains visible without rewriting the row. Equality is not
  independent corroboration or event equivalence. Native matches can be
  ambiguous; all pointers are retained. There is no transitive event graph.
- **Revision:** a batch identity is hashed; input, selected snapshot and code
  content digests bind its execution. Every valid input is accounted for before
  one SQLite `BEGIN IMMEDIATE` transaction accepts the canonical metadata
  payload. A unique key arbitrates process races. Identical replay is a no-op;
  changed input (including saved-file bytes), snapshot or code refuses under
  the same identity. Use an explicit new `--batch` for a revision. Git HEAD is
  the original execution's informational locator; an unrelated Git commit with
  unchanged bound code does not create a revision. Commit timestamps are kept
  separately and excluded from deterministic identities and metadata exports.

No raw source title/body, translation, summary, excerpt, model prompt or
arbitrary extras is stored in the ledger, JSON, HTML or diagnostics. Entire
input dictionaries contribute only to an in-process SHA-256 fingerprint, so
changes to omitted extras are detectable without retaining them. Diagnostics
use fixed messages; parser errors, filenames and payloads are not interpolated.
URLs with credentials or secret-bearing query keys refuse rather than export a
secret or silently rewrite the exact locator.

The reader offers source/date/mode filters and reset, stable title-group links,
individual observation and representative views, exact native-record locators,
missing/differing-date evidence, unavailable bodies, ambiguous matches, version
and stored-hash disagreements. Inspect a title key across ledger batches while
keeping each execution separately labelled. Native HTML GET forms and
`details`/`summary` work without JavaScript. Pages show at most 100 observations
at a time; archive overview starts with retained recurring-title cohorts.

## Verification map

| Requirement | Test / receipt |
| --- | --- |
| Authority, batch-local title scope, host governance, default wrappers | Existing `test_dedup_authority`, `test_source_host_governance`, `test_host_gate`, `test_manifests`, `test_pipeline_compat`; `test_dedup_trace` adds explicit permutation/order/object-identity, spec-title and precedence expectations plus wrapper delegation |
| Lookup order and asymmetric seen sets | `TraceCompatibility.test_lookup_precedence_and_asymmetric_seen_sets`: exact expected calls, survivors, reasons and representatives for both APIs |
| Distinct positions, missing fields, title-only suppression, same/different bodies, recurring dates/batches | `OccurrenceContracts.test_every_position_body_variants_missing_and_recurrence`, `test_same_title_different_body_only_candidate_signal`, `test_different_titles_same_normalized_text_and_cross_batch_reader`, `test_batch_hash_and_url_matches_after_title_stage` |
| URL match, stored hash, stale hash, ambiguity, body equality evidence | `test_hash_equality_requires_nonblank_body_and_recomputed_retained_hash`, `test_url_hash_precedence_ambiguous_ids_and_prospective_pointer` |
| Native adapter → normalization → both engines → selected SQLite → commit/reopen → reader | `test_actual_saved_html_adapter_normalize_engines_selected_archive_reopen`; actual metadata corpus/replay receipt below; real-browser local reader inspection |
| Transactions, rollback, idempotency, explicit revisions, real process races | `test_transaction_idempotency_revision_rollback_and_determinism`, `test_real_cross_process_same_and_conflicting_writers`, `test_same_code_at_another_git_head_is_noop_but_changed_code_refuses`, `test_saved_fixture_byte_changes_refuse_existing_identity_and_exact_locator_survives` |
| Path guards, corruption, missing/changed snapshot, source mismatch, malformed payloads | `test_unsafe_destinations_permissions_links_and_overwrite`, `test_corruption_schema_missing_snapshot_and_digest_mismatch`, `test_snapshot_wal_changed_bytes_and_source_guard`, `test_identity_source_and_host_mismatch_fail_closed`, `test_malformed_inputs_no_partial_acceptance_or_secret_echo` |
| Redaction and producer-only references | `test_redaction_ledger_export_html_and_safe_diagnostics`, `test_supplied_producer_capture_and_media_only_metadata`; distinctive fictional title/body/summary/extra sentinels checked across all new output formats, not a claim of copyright compliance |
| Working no-JS/reduced-motion/keyboard reader at 375/1280 | Mandatory real Chromium `test_source_occurrences_browser` matrix: eight combinations; focus, disclosures, filters/reset, stable groups, observation/native views, no overflow, no unexpected requests or console errors |
| Actual corpus inventory and larger fictional fixture | `test_source_occurrences_scale`: dynamic native row/pointer checks, 20,000 fictional positions and indexed memberships; timing/peak-allocation receipts in test output |
| Existing pipeline behavior and preservation | `tests.integration.test_pipeline_run`, `tests.integration.test_end_to_end`; full Python 3.9 offline PR job; unchanged-output validator; all tracked protected-file hashes and sidecar/status check |

Focused command:

```sh
$PY -m unittest tests.test_dedup_trace tests.test_source_occurrences \
  tests.test_source_occurrences_browser tests.test_source_occurrences_scale \
  tests.test_dedup_authority \
  tests.test_source_host_governance tests.test_host_gate tests.test_manifests \
  tests.test_pipeline_compat tests.integration.test_pipeline_run \
  tests.integration.test_end_to_end -v
$PY -m unittest discover -s tests -t . -v
$PY scripts/validate_output.py
```

Chromium and local fixture servers require normal local process/socket access;
the Mac sandbox blocked those until supported command approval was used.
Browser failure in the new mandatory test is a failure, never a skip. Existing
PR offline checks run the entire suite on Python 3.9 at the PR merge ref;
draft/path-filter skips are not a passing receipt. No new workflow is added.

## Measured local receipt (October 11, 2026)

The archive pin above has **5,097 retained rows**: China 5,011 and Singapore 86.
It has **35 normalized-title cohorts / 78 rows**, including 30 cohorts spanning
publication dates and six spanning source slugs. There are zero duplicate
nonempty stored legacy-hash groups. Recomputed title-plus-text hashes disagree
with **57 stored legacy hashes**; those stored values were not altered. Every
inventory native pointer resolves in the selected snapshot. These are retained
archive measurements, not historical occurrence or event counts.

The nine existing MINDEF HTML fixtures yielded nine actual adapter documents.
Replay recorded **eight stored URL matches and one prospective survivor**, then
committed and reopened the metadata ledger. Eight matching native IDs resolved;
no invented HTTP capture reference or retrieval timestamp was attached.

Initial observed timings with `tracemalloc`, including build, transactional
commit and reopen: archive 11.395 s / 181.18 MiB peak Python allocations;
saved-fixture replay 4.932 s / 85.52 MiB; **20,000 fictional observations**
10.966 s / 165.36 MiB, yielding 6,764 indexed relation sets. Measurements are
local observations, not service limits; Python allocations exclude browser RSS.
The implementation is in memory, proportional to input text plus metadata,
uses digest buckets rather than all-pairs body comparisons, and has not been
qualified for arbitrary archive sizes. Ledger payloads are validated on reopen.

Final-head CI and preservation receipts are recorded in the PR. Owner review
of the detailed API compatibility, metadata semantics and private reader is the
next action; merge/deployment and continuous custody integration are separate,
unauthorized phases.
