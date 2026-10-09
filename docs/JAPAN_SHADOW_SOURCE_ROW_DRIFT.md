# Japan MOD October 5 — historical vs current shadow-record drift

This read-only tool compares the **same October 5, 2026 Japanese Ministry
of Defense PDF source** across two *Git-versioned shadow SQLite archives*.
It answers a narrower question than publisher originality: **did our
archived record's extracted Japanese text and source metadata change
between a historically verified commit and a newer shadow commit?**

It deliberately reuses `scripts/audit_japan_oct05_brief_source.py` to
verify that the historical Git commit, SQLite blob, source URL/issuer,
date, complete extracted-text hash, capture checksum and specific Japanese
phrases are exactly the previously audited source. It then resolves the
newer `shadow/jp-mod` Git ref, verifies the historical commit is an
**ancestor** of it, reads its exact Git blob with size/SHA-1 checks, runs
SQLite integrity verification and retrieves **the same official URL's row**.
It does **not** assume the later SQLite blob is identical merely because
Git history is continuous.

The output classifies that source as one of three states:

- `same_archived_extracted_text_and_row_identity`: the shadow row's
  extracted Japanese UTF-8 bytes and issuer/date/title/capture metadata
  match the previously authenticated archive.
- `changed_or_inconsistent_current_shadow_source`: one or more fields
  or the text SHA-256 differ; the private receipt lists changed *field
  names*, never original article content.
- `held_original_row_missing_in_new_shadow_archive`: the source URL
  no longer appears in the current shadow SQLite snapshot. This does
  **not** establish that the ministry deleted the article.

## Local operator example

First obtain the official IPR repository's **already-fetched shadow Git
state**, including the exact October 5 historical commit and current
`shadow/jp-mod` ref. This tool does not perform network requests, clone
repositories or update branches itself.

```bash
python -m scripts.japan_shadow_source_row_drift \
  --state-repo /path/to/locally-fetched-jp-mod-state \
  --current-ref refs/remotes/origin/shadow/jp-mod \
  --out /private/japan-oct05-shadow-row-comparison.json
```

Use an existing private folder outside the repository. The output file is
new, non-overwriting and created mode 0600. Git and SQLite work is read-only
apart from a disposable temporary extraction of archive bytes.

**Important limits:** matching archived extracted text is NOT proof that
the original PDF bytes were ever retained or are identical to the
publisher's current PDF, that a human compared the complete PDF and
translation, or that any publisher reproduction/AI reuse right exists.
All model, Dylan-email, production-desk-promotion and publication
authorization fields remain false on every result. The October 11 first
Sunday attachment's separate owner-reviewed SHA-256 requirement is
unchanged. This is a diagnostic for [Issue #271](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/271),
not a new production collector or an automatic typed-research admission.

The focused unit tests use disposable local SQLite fixtures and mocked
Git lineage to check missing, duplicated, modified and corrupt rows. In an
in-repository PR, a **separate focused CI step** clones the repository's
isolated `shadow/jp-mod` branch read-only via the GitHub-provided checkout
token and runs the real historical/current row comparison. This uses GitHub
Git history, **not the publisher website or PDF download**. The CI prints
only the safe tri-state outcome and changed metadata *field names*, never
the Japanese source text, publisher URL, Git credentials, or a private
receipt artifact. Full PR offline CI remains the merge gate.

If Git history is absent or the source row cannot be compared, the real
step must fail; it cannot invent an unchanged result. A successful real
row comparison still does NOT certify the live MOD publisher original,
human interpretation, reuse rights or editorial authorization.
