# National Defence Journal — metadata-only listing-window comparison

**Status:** offline diagnostic candidate. No live probe, collector, publisher contact,
scheduled workflow, journal full-text retention, source activation, production
database mutation or generated-site change is authorized or performed here.

This analysis supports [historical discovery issue #154](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154).
Legal permission and retention remain a separate decision in
[issue #155](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155).

## The evidence gap this closes

The initial [four-category discovery proof](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37716446432)
observed **74 IDs** and a later
[independent live parser parity run](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37721439408)
observed **71 IDs**, without article bodies, archived source HTML or publisher text.
The latter's metadata artifact contained *only counts, response hashes and
comparison booleans* — **not per-article ID sets**. Therefore it is impossible
to identify which IDs disappeared, first appeared or were shared between those
two observations. Inferring turnover from the total-count difference would
fabricate evidence.

The script introduced here does not reinterpret those aggregate reports.
It accepts **future, separately authorized, metadata-only observations that
actually include canonical IDs** and computes their cohort changes offline.

## Input contract: ipr-vndj-listing-observation/1

Each future observation supplies all four exact desktop category URLs, the
response SHA-256 for each page, one or more canonical article IDs and URLs
per category, and optional *unverified* local date hints. The observation
requires a UTC instant and a unique identifier (for example the research
Actions run ID). No article title, paragraph, HTML, caption, PDF, image,
snippet or foreign website reference is allowed.

Illustrative structure, **synthetic data** (one section shown; a real valid
input must supply the other three):

~~~json
{
  "schema": "ipr-vndj-listing-observation/1",
  "source_slug": "vn_national_defence_journal_en",
  "observed_at": "2026-10-08T01:00:00Z",
  "observation_id": "synthetic-run-one",
  "sections": [
    {
      "category": "theory-and-practice",
      "listing_url": "https://tapchiqptd.vn/en/theory-and-practice-56.html",
      "response_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "candidates": [{
        "source_identity": "vndj-en:26936",
        "canonical_url": "https://tapchiqptd.vn/en/theory-and-practice/synthetic-article/26936.html",
        "date_hint": "2026-09-30"
      }]
    }
  ],
  "source_html_retained": false,
  "article_text_retained": false,
  "pagination_proven": false,
  "historical_completeness_proven": false
}
~~~

The sample is **not** a complete acceptable input and must never be treated
as a real source observation. Evidence-producing runs must separately
establish source policy compliance, true response hashes, exact observed
URLs and proof identity, then persist *only this validated metadata
structure*. The comparator does not independently attest that an input was
lawfully obtained, that no external copy of source bytes exists, or that
a stated response digest is genuine.

The validator refuses unknown keys (preventing accidental prose embedding),
missing or empty category observations, duplicate IDs, incompatible canonical
URLs for the same numeric ID (within **or across** snapshots), contradictory
local date hints, non-UTC
observation times, false completeness claims, non-HTTPS/foreign URLs and
more than 150 candidates in any category. Sidebars and recommendations may
repeat links across sections; a listing page is **not an authoritative
category assignment for each article**.

## Offline use

From the repository root, with two or more eligible metadata-only JSON files
already supplied by an owner-authorized research procedure:

~~~bash
python -m unittest tests.test_vn_journal_window_drift -v
python -m scripts.vn_journal_window_drift /path/to/observation-a.json /path/to/observation-b.json
~~~

The command prints a deterministic JSON report to stdout. It **never fetches**
a publisher page or writes an output file. Each category and the de-duplicated
four-page union report stored-ID counts and the actual ID sets that are
first-observed (in supplied evidence), no longer visible, or reappearing
after an earlier absence. A reappearance needs at least three snapshots.
Each input must be a genuine complete four-category snapshot, not a
reconstructed subset of the previously published aggregate figures.

## Interpretation gates

- **No longer visible** does not mean an article has been deleted, unpublished,
  retracted, or dropped from the journal archive.
- **First observed** means first seen *among the supplied snapshots*, not
  first published or first historically available.
- **Reappeared** may reflect homepage/sidebar curation or changing visible
  listing windows, not an article's republication.
- Date hints are unverified; no event or publication dates are inferred from
  article IDs, search-result rankings or listing position.
- The four-category union removes duplicate links but does not establish a
  complete historical catalogue, or source-category ownership.
- The output explicitly denies proof of publisher deletion, full-history
  completeness, forward collection reliability and verified publication dates.
- This offline tool does **not** qualify the source for a shadow run. A future
  live observation needs a separately approved bounded, robots-gated procedure,
  and all content-reuse rights remain open in #155.

This component only makes future evidence **comparably measurable**. It does
not satisfy the historical pagination gate on its own.
