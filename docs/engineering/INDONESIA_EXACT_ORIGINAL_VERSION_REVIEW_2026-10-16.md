# Indonesia Kemhan — source-version-bound private human review

This phase does **not** turn the Indonesia desk live. It makes the existing
31-original private reviewer handoff version-specific, so a later real human
decision cannot silently drift onto a different preserved original.

## Source and scope

The original evidence is frozen at Git SHA
`0595c6677be24f8f0f33aecb28eec0050e36e8f9` on
`shadow/indonesia-kemhan`: 31 first-party Berita originals. The pre-existing
directory contains 15 external official links that are **not** human approval
of original-source claims. The private queue contains 15 additional unreviewed
candidates and one geographically inconsistent original that must remain held.

The existing private reader first validates the complete Git+SQLite source,
including the stored Indonesian text's SHA-256 digest, declared publisher,
dated official URL and source identity. The new
`scripts/bind_indonesia_review_versions.py` then re-opens the **same
immutable** SQLite blob read-only and matches all 31 metadata-only queue rows
against stored identity, title, source URL, date and first-seen run. It binds:

- `original_title_sha256` — hash of original archived title bytes
- `original_text_sha256` — recalculated hash of preserved Indonesian text
- `archived_capture_sha256` — captured source payload's recorded digest
- `source_version_sha256` — deterministic hash tying the above to Git SHA
  and exact original identity/URL/date/first-seen run

The third digest is a **stored capture reference**, not fresh network
authentication of the original publisher response. No capture bytes, article
text, images, translation, title text or model output are exported into the
new source-version manifest.

## Private outputs

A manual run of the existing
`indonesia_pinned_reference_review_queue.yml` generates three prior
metadata-only files plus:

- `original_version_manifest.json` — all 31 exact per-original digests and
  explicit false authority claims; one permanent semantic hold
- `review_decisions_UNSIGNED.csv` — identical version identifiers, first-party
  official URLs and deliberately **blank** reviewer/date/rights/factual-review
  cells. Its held row is premarked *YES — MUST REMAIN HELD*.

The private artifact retains the prior **14-day** retention. The CSV is a
working template, **not a signed or authenticated review receipt**. Existing
human review need not be repeated if actual original-specific evidence is
recoverable; it must be bound to the exact hashes before any release. Never
populate approval automatically or infer permission from the owner's general
metadata-only decision.

## Remaining admission boundary

A separate independent verifier must authenticate: the actual reviewer and
their per-item dated evidence, exact source-version matches, any rejected or
revised sources, publisher-specific **link** and **body/translation/media**
reuse scope, an exhaustive meaningful Actions attempt/collection census, and
the known Yonif 880 exception. The current source-index writer in #749
correctly defaults to HOLD without that verifier; #753's empty migration is
not authorization. Do not put these private files in `output/`, tracked
`pla_watch.db`, `gh-pages`, or the public site.

The first production success criterion remains a real newly scheduled
Kemhan item passing collection → verified review policy → authorized
metadata-only database admission → exactly matching public page readback.
Nothing in this phase establishes that chain.
