# Singapore: image-only releases no longer block a batch — 2026-09-29

This repairs the collection blocker recorded in
`docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md` §7. It changes how the
scheduled Singapore collection classifies one kind of page. It does not run a
recovery, change a stored record, change a verdict, or change desk status.

## 1. What blocked the recovery

The authorized 2026-09-28 run (window 09-22 → 09-28) discovered 11 releases,
extracted 10, and stored none. The eleventh, `22sep26-infographic`, has a
178-character "body", under `MIN_BODY_CHARS` (200). `SGMindefAdapter.collect()`
withholds the whole batch on any failure, so the three releases production had
missed (`22sep26-nr`, `22sep26-speech`, `23sep26-mq`) were withheld with it.

## 2. What the page contains

No capture of the page existed (the failed run kept no HTML), so it was captured
again on 2026-09-29 through the adapter's transport. The response is 451,543
bytes (SHA-256 `ebe45611…`); see `tests/fixtures/sg_mindef_recovery/README.md`.

- **Title:** "Infographic: Ex Trident Resolve 2026" (the ministry's own).
- **The "body":** `22 September 2026 More Resources Largest ASEAN Defence
  Ministers' Meeting (ADMM)-Plus Exercise in a Decade with the Participation of
  2,200 Personnel from 19 Countries Back to top`: the date line, a "More
  Resources" label, the title of a *linked* release, and a button. None of it is
  this release's text.
- **The article container** (`overflow-x-auto break-words`) holds one `<img>`,
  the "More Resources" label and a paragraph that is only a link. The lede is
  blank. There is no prose.

So the page is an image with incidental page text. Its content is in the image,
and the image is not read.

## 3. The rule

The adapter reads the article container (`article_evidence`). Inside the
existing "body under 200 characters" branch, and only on the scheduled
collection path, a page falls into one of three outcomes:

| Container | Outcome |
|---|---|
| Found; holds an image; **no prose** | **Image-only.** Stored as a text-unavailable record: official title, URL and slug date; empty body; `content_verdict = media_only`. |
| Found; holds **prose** | **Genuine short text.** Stored as text, as a long release is. |
| Not found, or found with neither prose nor an image | **Extraction failure**, as before. |

"No prose" means no words in the lede or the container other than the ministry's
"More Resources" label and paragraphs that are only links. A caption, a lede, or
a sentence that mixes words and a link is prose. Alt text and file names are
attributes and are never read.

**Length is not the test.** A short body is classed by what the container
holds, never by its length. A page whose layout is not understood (an error
page, a stub, a new template) has no container, so it stays a failure. That is
the same principle the Xinhua and Global Times adapters use for `media_only`
(there for an empty body, here for a short one): report it only when the body
container was found, so "we cannot read this" is never
recorded as "there is nothing here".

**Nothing already extracted changes.** A body of 200 characters or more never
reaches the new branch, so every existing record extracts identically. The
tests pin this for `22sep26-nr` and `22sep26-speech`.

## 4. What stays the same

- **All-or-nothing.** Any fetch failure, any extraction failure (including a
  short page whose layout is not understood), and any held record present in the
  results still withholds the whole batch. An image-only release is not a
  failure, so it no longer does.
- **The two held records** (`15aug26-speech`, `16sep26-speech`) are still
  removed at `discover()`. MINDEF's sitemap still lists both.
- **The shadow collector is unchanged.** It calls `extract()`, which still
  refuses a short body, so the shadow corpus and its ledgers do not change.
  Every shadow run whose window contains 09-22 will keep recording one
  extraction failure for this page. Whether shadow should treat it the same way
  is an owner decision (§7).
- **Nothing is analysed.** Singapore stays out of the daily model queue
  (PR #84). The record is stored with `passed_relevance` NULL.

## 5. Two behaviour changes to note

1. **An image-only release is now stored**, with an empty body.
2. **A genuinely short prose release is now stored on the scheduled path**,
   where before a sub-200-character body was refused. In the 2026-09-29
   database snapshot, no stored Singapore prose release was that short: the shortest stored is 4429 at 258 characters, and the
   real `23sep26-mq` is 391. The case is tested with a synthetic page.

## 6. How "body unavailable" is recorded

- **Per record:** an empty `articles.text_original`, the same representation the
  58 China records with no captured text used in the 2026-09-29 database
  snapshot (Singapore had none). Nothing else per record is
  stored; `content_verdict` is not a column.
- **Per run:** `source_run_results.text_unavailable` counts it, the status stays
  `ok`, and `error_detail` says "1 of 11 parsed page(s) carried no usable text;
  their titles, URLs and dates were kept".
- **Published:** the record page already says "Original text is unavailable in
  this stored record." and the coverage page shows "N without text". No template
  changes here, and `output/` is not regenerated.
- **Identity:** the record is keyed by URL like every other. If the ministry later
  adds text to the same URL, this record will not be re-extracted, as for any
  stored record.

## 7. Residual risks and decisions

- **A longer image-only page is not caught.** The structural test runs only when
  the body is under 200 characters. An image-only page whose links push the
  furniture text past 200 would still be stored with that furniture as its
  "body". This was left alone deliberately: applying the test at every length
  would change how every existing release is classified, and a template variant
  would then be recorded as "no text" permanently (the URL is never re-extracted)
  instead of failing closed. Owner decision.
- **Shadow parity.** Production will now store the infographic and shadow will
  not. Owner decision whether shadow should follow (it would drop shadow's
  recorded extraction failure to zero during the Day-30 period).
- **Sub-200 prose is admitted on the scheduled path** (§5). Owner decision
  whether that is wanted or `MIN_BODY_CHARS` should stay a hard floor there.
- **The container is identified by the ministry's current class names.** If the
  template changes, the container is not found and pages fall back to today's
  behaviour: a short body fails the batch, visibly.

## 8. Proposed recovery scope — refreshed 2026-10-06 (not run)

PR #85 still needs an owner merge decision. Current main
`d0c6dbb273501906f10f039467388b0bfd834d37` has not superseded the repair:
its adapter still withholds the eleven-reference fixture batch on the
infographic, returning zero documents. Dependencies #69, #82 and #84 are
merged. Current main was merged into the refresh branch without rebasing or
rewriting the original PR head `04feaa0691255d97ec5380b4c40f961255846142`.
No source correction was required during this review.

The tracked main database SHA-256 is
`b10890ddac59538b66041b10d13d08199f20be2279efa9bcb03a2d991d17decc`.
Read through `scripts.reconcile_db.read_only`, it holds 76 Singapore records,
29 dated in September. `23sep26-mq` is already stored as id 4759 with its
391-character body; it is no longer a proposed insert.

At 2026-10-06 22:19 EDT (2026-10-07 02:19 UTC), the adapter's existing
identifiable transport reread robots.txt and the MINDEF sitemap, both HTTP
200, with normal 1.5-second spacing. Only those two requests were made;
no release body or image was fetched. Robots allowed discovery. The sitemap
was 818,394 bytes, SHA-256
`82644c9fbff3f094360029a74ca95ef387e9c0a2184363bbe22227a8a8cb1712`.
A September-wide discovery with cap 1000 (above the 32 eligible references)
was compared by canonical URL against the scratch-read database:

| September disposition | Count | Releases |
|---|---:|---|
| Eligible and already stored | 29 | Every eligible September reference except the three below |
| Eligible and missing | 3 | `22sep26-infographic`, `22sep26-nr`, `22sep26-speech` |
| Governed hold, excluded before selection | 1 | `16sep26-speech` |

No stored September release was absent from this listing. This is a comparison
with the current official sitemap, not proof of releases the sitemap never
listed. The August hold `15aug26-speech` also remains excluded.

**Proposed owner-authorized recovery, only after merge:**

    .venv/bin/python pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis

That selects slug dates 2026-09-22 through 2026-09-28, Singapore only. Recheck
main, the database and listing immediately before execution. Against this
review's snapshot, acceptance is:

- **Three new URLs:** `22sep26-infographic` with empty original text,
  `22sep26-nr` and `22sep26-speech` with extracted prose.
- **Eight duplicates:** `23sep26-mq`, `23sep26-nr`, `24sep26-nr`,
  `25sep26-speech`, `27sep26-nr`, `27sep26-nr2`, `28sep26-mq`,
  `28sep26-speech`. Existing rows and verdicts must remain unchanged.
- **Source run:** discovered 11, fetched 11, extracted 11, new 3, duplicates 8,
  usable text 10, text unavailable 1, status `ok`. Both held releases absent.
- **Repeat:** zero new URLs and eleven duplicates; no stored row changes.
- **Boundaries:** no screening/model calls, no rendering/deployment, no other
  source collection, no shadow state writes. The command records a production
  scrape run and inserts records; it is proposed here, not authorized or run.

Any unresolved fetch/extraction defect still withholds the whole batch. A changed
listing or body must be inspected rather than forced to fit these counts.
Recovery landing/reconciliation and any later render/deploy require separate
owner scope; merging this code PR alone does not recover the records.

## 9. Refresh verification and remaining decisions

The 146 focused offline tests passed on Python 3.9.6, including all 30 PR tests,
scheduled production, production windows, shadow, desk-scoped screening and
cross-source duplicate authority. They cover structural image-only detection,
caption/lede/mixed-link prose, genuine short prose, missing title/date/layout,
fetch/extraction failures, held discovery and leaked holds, empty-text storage,
duplicates and idempotence. Existing prose fixture hashes remain unchanged.

A separate fixture-only temporary-database rehearsal seeded the eight current
window duplicates, ran the real pipeline, and verified exactly three inserts,
eight duplicates and one unavailable text record. All eight seeded rows remained
identical. Repeating the run produced zero inserts and eleven duplicates with
all eleven rows identical. The seven filler bodies are explicitly synthetic;
this rehearsal makes no new claim about their live prose.

Production uses `collect()` with structural classification; shadow still calls
`extract()` and refuses the infographic and synthetic sub-200 prose. No shadow
collector, workflow, manifest, ledger or record changes are in this PR. Longer
image-only pages remain outside the structural branch. Link-only paragraphs
are treated as resources under the existing rule, so an atypical release made
entirely of linked text could be misclassified; classification is tied to the
known container layout. Empty text is stored without a durable per-record
`media_only` field, and later text at an existing URL is not automatically
refreshed. These are owner tradeoffs, not evidence that image contents were read.

Full-suite, validator and final preservation results are recorded in the PR's
current review evidence. The baseline for preservation is current main, not the
September 29 branch database: main's intervening daily DB/output commits were
inherited by the merge, and are not recovery or generated-output changes made
by this PR. All 7,451 DB/output files are hashed before and after verification;
there are no DB/output differences against the pinned main tree and no SQLite
sidecars. No recovery, workflow dispatch, production render or deploy was run.
