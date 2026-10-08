# Vietnam: progressive, individually reviewed source links

This is a **narrow early-publication lane**, not desk promotion.

## Why it exists

The Vietnam MPS and MOIT collectors are running under isolated remote shadow
evaluation starting 2026-10-07. Their Day 7/14/30 reviews occur after the
scheduled runs on 2026-10-14, 2026-10-21, and 2026-11-06. Until full promotion,
`desks/registry.json` remains `research`, `manifest: null`,
`has_production_records: false`. The journal, Government News remote source,
and access-blocked sources are excluded.

A separately checked publisher **link**, unlike republishing a source article,
can help visitors find independently verified official publications without
copying the text into the public corpus or pretending there is live coverage.

## What shipped

- `core/reviewed_source_links.py`: fail-closed validator with an exact schema,
  ministry source whitelist, exact official HTTPS domains, chronological dates,
  original Vietnamese title, named human reviewer, pinned 40-character shadow
  commit, and five individually affirmative human attestations.
- `research/vietnam_reviewed_links.json`: **empty by default**, until a real
  editor completes the human review. Empty means no changes to the page.
- `site/preview/templates/desk.html`: when one or more approved references
  exist, displays an explicitly **non-archival** bibliography on Vietnam's page.
  The original source URL opens the publisher's own site. No translation,
  article body, shadow DB record, model label, or corpus count is introduced.
- Only the public desk-page renderer consumes this file. The record archive,
  Briefs selection, production SQLite, source configurations, GitHub Actions
  collection, and qualification clock are unchanged.

This tool checks **consistency of declared approvals**, not whether a named
reviewer actually performed the review, or whether a publisher's live page
still matches a saved version. Those are mandatory editorial tasks.

## Human route from real shadow evidence to a displayable link

1. Begin with the existing October 8 metadata-only MPS candidate packet:
   `docs/VIETNAM_MPS_FIRST_REVIEW_QUEUE_EVIDENCE_2026-10-08.md`.
   It names the Git-provenanced shadow state and three mechanically reviewable
   current-version entries; **all three are still unapproved**.
2. Inspect the exact source URL and full original Vietnamese text yourself,
   independently comparing the publication date, original title, issuing body
   and content version against the pinned source-state capture. Check for
   challenges/templates or stale publisher versions; reject any uncertainty.
3. Make an explicit editorial decision that the **metadata-only link and title**
   may appear publicly. This does **not** authorize copying or redistributing
   article bodies, translate the contents, or admit them to the corpus.
4. Enter a single object in `research/vietnam_reviewed_links.json` containing:
   `id`, `source_slug`, `source_url`, `title_original`, `language: "vi"`,
   `published_date`, `reviewed_by`, `reviewed_on`, `state_commit` and a
   `checks` object with `source_page_opened`, `title_checked`,
   `publication_date_checked`, `issuing_institution_checked`,
   `link_publication_approved` all `true` **only where actually verified**.
   No placeholder reviewer, guessed metadata or synthetic record may be committed.
   Recheck the page before release if the publisher has updated it.
5. Review the PR diff and independent publisher links, run
   `python -m unittest tests.test_vietnam_reviewed_links`, render into a
   disposable output directory, run `scripts/validate_output.py`, and
   inspect the Vietnam desk page at desktop and mobile widths.
6. Obtain owner authorization for the exact content change. Merge and deploy
   through existing production workflow only after complete site-level checks.

## No implied weekly Briefs contribution

The Friday provisional automated Briefs writer reads **only live desks with
production-backed full-text records**. These links are *not* exposed to that
model, nor are they countable source-trail IDs. A human editor may independently
consult the official external links during research, but including any claim
in a numbered Brief requires separate evidence checks and the governing Briefs
approval process. This mechanism will not fabricate a Vietnam desk contribution
for Saturday 2026-10-10.

## Follow-on milestone

After human signoff, separately review either (a) a specific-source,
explicitly owner-excepted and rights-cleared corpus pilot using the existing
`prepare_vietnam_mps_pilot.py` disposable staging, or (b) normal promotion
after Day 7/14/30 completion. Never silently turn the bibliography into
records, enable an automatic publication path, or rewrite the desk registry.
