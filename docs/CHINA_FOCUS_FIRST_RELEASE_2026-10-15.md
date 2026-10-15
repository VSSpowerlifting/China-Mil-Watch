# China source archive: focus-first browsing with complete preserved access

**15 October 2026 · source-balanced, algorithmic research shortlist**

**Owner direction:** aggressively reduce the *prominence* of China's
5,144-source-record historical mass (4,173 from PLA Daily), while
preserving every original record, stable link, source trail and historic
original source material. This implements that product direction without
claiming the shortlist has 600 separately signed human reviews.

## Release surface

On `archive.html`, show a source-diverse **provisional 600-record China
research focus** instead of the full 5,144-record China listing by
default. Leave **all records from other desks** in the focused view.

A clearly visible **Browse collection** selector offers:
- **Research focus** (default): an automatically assembled, diverse
  research discovery aid. It is **not individually fact-checked or
  editor-approved**.
- **Full preserved record**: the *complete* public index, all
  source-state categories, original-language title search, source and
  institution facets, date filtering, published Brief trail filter and
  paging.

The `?scope=all` URL is shareable and back-button-restored; the
`?scope=focus` state is the default without a URL query. Clearing
filters retains the focus until the reader explicitly chooses full.
With JavaScript disabled, the server renders the newest focus items
and `corpus.html` still links **all** original records by week.

The header states **both** the full stored count and the smaller
algorithmic-focus count, rather than quietly replacing one with
the other. When the exact published snapshot advances, both
derivations advance *together* from the same read-only corpus.

## Explicit selection method

`core/china_discovery.py` is deterministic and offline. The first
600 China slots are diversified by source, then filled by a
transparent monthly-round-robin topical/title signal with
a small down-weight on repetitive editorial series.

**Initial source targets:** PLA Daily **300**, China's Ministry of
National Defense **130**, China Military Online **140**, Xinhua
Military **10**, Global Times **20** (total **600**).
If a source has fewer safe candidates, its slots are reallocated
to other eligible machine-analyzed China records. This is *not*
a claim that one source is truthier or more important than another.
It is a guard against the previous distribution being almost
entirely PLA Daily. No nationality, ideology, or government
position is ranked for its political favorability.

Eligibility is **not** proof of authenticity, source fidelity, or
editorial worth. It uses a prior `analyzed` processing status as
one automated research signal; two important screened-out Chinese
Foreign Ministry records (#2391 and #2849) are explicit
provisional leads, not represented as human approved.

All published source-trail IDs remain in the full corpus, but
known historically faulty original-text captures are **held out
of focus**, including #2265 and #2881, whose source pages were
analyzed before the historical Global Times extraction correction.
All remaining old Global Times collections before September 16
are conservatively **held from focus** pending individual
source-fidelity review. They are NOT removed from their permanent
record URLs, source trails, full archive, machine exports or the
canonical database.

Within a source/month bucket, exact Unicode-normalized repeated
titles are represented once in the focus. Underlying source
occurrences, IDs and cross-publisher records are never collapsed or
deleted. New as-yet-unconfigured **China** sources are preserved in
the full corpus but never automatically admitted to the focus.
Future Singapore, Korea, Japan and other non-China desk records
remain visible; the China cull is not an excuse to suppress those
desks.

## Release safeguards

- Full `corpus-index.json` still includes **every** stored record
  and all original trail IDs, with two extra fields:
  `focus_ids` and `focus_policy`.
- `browse.js` verifies the exact corpus snapshot, full record count,
  schema, unique focus IDs and their membership in the original record
  index before drawing. On any mismatch it withdraws interactive
  filtering and leaves the server-rendered focus intact with an error
  message, not a dishonest empty-result count.
- Every `record/{id}.html`, `article/{id}.html` legacy redirect,
  `corpus.html` week, existing Brief and original URL remains
  generated and accessible. This PR does **not** change indexability,
  sitemap, archive source retention, database, publication dates,
  author bylines or article text.
- The automated focused view is *not titled "editorially verified",
  "fact checked" or "the only IPR archive"*. This matters
  especially because the Global Times source-extraction
  audit identified consequential incorrect derived summaries.
- Focused unit and regression tests plus full repository offline
  CI and guarded preview/browser validation must pass at the **exact
  PR head** before merge/publish.

## Browser-level release proof

`tests/test_china_focus_browser.py` now performs a **real Chromium**
render of the whole static site from an isolated, read-only database
build, served from ephemeral localhost scratch. It tests 375px and
1280px widths, both scope selections, the shareable `?scope=all`
deep link, browser back navigation, ordinary original-language search,
error-free script loading, actual public focus-ID/source-trail custody,
and a genuine **JavaScript-disabled** path from the focus to
`corpus.html`. Missing Chromium is a failed gate, not an assumed pass.

Archive `browse.js` remains under the existing **10,000-byte JS
budget**, including the newly added focus and full-corpus selection
logic. Earlier pre-change build exceeded this cap; the implementation
was trimmed to restore compliance. Every full test and browser check
must pass on the latest code head before release.

## What this does not do

It does not deliver the final genuinely **human-curated** 500–700
China records. It is a materially smaller, openly automated
research landing view consistent with an aggressive public cull,
and gives the owner time to turn the independent editorial review
ledger (#615) and evidence batches (#621) into a genuinely
source-approved selection manifest.

A later **versioned, individually reviewed and owner-approved**
manifest can replace automated focus selection *without touching
the full-corpus escape, canonical record routes or historical
citations*. Do not silently relabel these present 600 as signed
human reviews merely because this release is owner-authorized.

**Release checklist:** verify the actual corpus supports ~600
focus IDs, compare on/off-JavaScript archive views, source-balance
and desktop/mobile finder, saved `?scope=all` deep-link,
unchanged full `corpus.html`, published source trails and
page counts, and pass exact-head full CI. No daily/site deployment
while an incomplete check remains unresolved.
