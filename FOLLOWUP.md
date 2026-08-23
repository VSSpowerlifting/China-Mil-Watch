## Followup: persistent title-hash dedup

> **BLOCKED — do not implement as written.** Making the title check corpus-wide
> is safe only for a source that reuses a title for *the same story*. It is
> destructive for a source that reuses a title for *different events*, and the
> second-desk research found one: on the Japan Joint Staff feed
> "Japan-U.S. Bilateral Exercise" titles **27 distinct exercises**, and
> "Chief of Staff's press conference" recurs likewise. A global
> `title_hash_exists()` check inside `dedup_articles()` would erase 26 of those
> 27 — silently, as duplicates, with no failure and no ledger entry.
>
> The correct dedup rule is therefore **a property of the source, not of the
> pipeline**, and belongs in the desk manifest beside `expected_cadence_days`.
> It is deliberately not added yet: like the cadence thresholds, it is an
> observation output, and inventing it before a second desk has collected would
> produce a false rule with the authority of configuration. Revisit when the
> Japan desk has 30 days of shadow data, and see
> `tests/test_dedup_authority.py::TestScopeIsPartOfTheContract`.

Current dedup_articles() only checks within the current batch. URL and content_hash DB checks won't catch syndicated reposts on later dates because both diverge across reposts. Sketch, subject to the block above:
- Add title_hash column to articles table with an index.
- Populate at insert time in processing/metadata.py alongside content_hash.
- Add db.title_hash_exists() and call it inside dedup_articles() **only for sources whose manifest declares that titles identify stories rather than events**.
- Migration to backfill title_hash for existing rows.
Do not bundle with the current dedup patch. Land this as a separate change after the current fix has been live for a few days.

## Followup: site generator hygiene
- Orphan article HTML cleanup is now in site/generator.py (added with the
  title-dedup patch). If we add other generated artifact types in the
  future (per-category pages, per-source pages, RSS items), each new
  generator function needs its own orphan-cleanup pass or a shared
  utility for "given a set of expected output files, prune everything
  else in this directory."
