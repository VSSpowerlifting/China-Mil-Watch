# Briefs: individually reviewed external Vietnam source references

**Scope:** Permit a numbered Indo-Pacific Record Brief to cite a particular
Vietnam Ministry of Public Security article as an independently reviewed,
publisher-hosted source **without** presenting Vietnam as a live collection
desk, fabricating a production record ID, or republishing Vietnamese text.

This is a source-attribution capability, NOT a decision that any source is
already approved. It does not relax Vietnam's October 14/21/November 6
collection reliability checkpoints.

## Editorial contract

The existing `desks` and `source_trail` continue to describe only live,
production-backed evidence; the normal two-desk comparison requirement and
exact-DB trail parity remain unchanged. A separately admitted, optional
`external_evidence` array on a Brief sidecar holds **up to five** explicitly
human-reviewed, publisher-linked items. Supported source family in this
first implementation: only `vn_mps_foreign_affairs_vi` at the exact official
`https://bocongan.gov.vn/bai-viet/…-<article id>` URL.

No external material is put in `pla_watch.db`, the production collector,
the public archive, its record counts, or the automatic model's existing
source-trail selection. External entries do not count toward the two-live-desk
Briefs minimum. The Brief page displays a separately labeled publisher-hosted
reference section with source-language title, review date, and an *original*
analyst-written synopsis. No copied article body or full machine translation
is admitted.

## What a human must verify

For EACH official article, the editor must:

1. Open the live official URL and compare the original Vietnamese title,
   issuing institution, full text, date and page state (including challenges).
2. Retrieve the **pinned version** from the existing immutable shadow state,
   reconcile its content SHA-256 with the original actually reviewed, and
   record the full 40-character source-state Git commit. A live URL alone is
   not evidence that a prior capture had that text.
3. Write a fresh short English synopsis in the editor's own words, fact-check
   it against the original Vietnamese, and include no publisher article body.
   An article's accessibility is not permission to reproduce its prose.
4. Record their REAL name/date and eight separately checked booleans.
   Checkboxes assert actual manual actions; validation cannot establish that
   an alleged reviewer exists or independently verified a source.
5. Put a specific citation marker such as
   `[External mps-vi:1791199100]` in the paragraph whose claim relies on the
   source. The same exact source ID then becomes an anchor to the reviewed
   external bibliography at the end of the Brief. A fabricated or unlisted
   ID fails validation, as does a listed source never cited in the prose.
6. Check `python -m scripts.author_brief check briefs/<slug>.json`, perform
   the normal private render/source-to-claim QA, obtain separate human Brief
   approval, then publish through the normal owner-controlled process.
   Approving the Brief does not confer source collection qualification.

## Structure

The optional `external_evidence` is an array whose item uses the fields
below. The values in angle brackets are ***placeholders***, not verified
records or an authorization to fill checkboxes automatically.

```json
{
  "schema": "brief-external-official-source/1",
  "source_identity": "mps-vi:<actual source ID>",
  "desk": "vietnam",
  "source_slug": "vn_mps_foreign_affairs_vi",
  "source_name": "Vietnam Ministry of Public Security",
  "url": "https://bocongan.gov.vn/bai-viet/<exact article path and ID>",
  "original_title": "<publisher's exact Vietnamese headline>",
  "lang": "vi",
  "date": "<YYYY-MM-DD source publication>",
  "state_commit": "<40-character audited shadow commit>",
  "content_sha256": "<64-character checked version digest>",
  "original_summary": "<a new, independently verified English synopsis>",
  "human_review": {
    "reviewed_by": "<actual human reviewer>",
    "reviewed_on": "<YYYY-MM-DD of completed source review>",
    "scope": "publisher-link-and-original-analyst-summary-only",
    "checks": {
      "source_page_opened": false,
      "original_title_matches": false,
      "publication_date_matches": false,
      "issuing_institution_matches": false,
      "complete_original_body_reviewed": false,
      "pinned_content_version_checked": false,
      "original_summary_fact_checked": false,
      "no_copied_article_body": false
    }
  }
}
```

All eight checks must be literally true before validation passes, and that
may happen **only after the human has completed them**. No example object
here is valid for production. The independently verified article date must
fall within the Brief's stated reporting week; the source-review date may
be later for a retrospective Brief, but not after the Brief's approval date.
No human source review or rights judgment is inferred by the code.

## Separation from the unapproved Friday handoff

PR #197 offers two October 5 MPS publications to Dylan in the **private**
unapproved Friday packet. Those links are **not** automatically included in a
numbered Brief and are **not** model evidence. This new external-source schema
is the formal, published-prose bridge after independent human source review.
The original October 5 articles may be considered for it, but no review
checkbox or authorization is prefilled by this engineering PR.

## Invariants and tests

`python -m unittest tests.test_brief_external_evidence tests.test_ipr_briefs tests.test_brief_publication`

Contract tests cover URL spoofing, identity/content version, missing source
or human review, outside-window dates, no-copy restrictions, unknown citation
markers, duplicate references, HTML escaping, and the unchanged live-desk
coverage count. Run the full suite, site render, validator and preservation
diff on the exact PR head before owner merge. The repo's normal independent
Brief approval, not this validation, is the authority to publish.
