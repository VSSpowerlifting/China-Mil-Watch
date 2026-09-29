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
the same rule the Xinhua and Global Times adapters use for `media_only`: report
it only when the body container was found, so "we cannot read this" is never
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
   where before a sub-200-character body was refused. No real Singapore prose
   release is that short: the shortest stored is 4429 at 258 characters, and the
   real `23sep26-mq` is 391. The case is tested with a synthetic page.

## 6. How "body unavailable" is recorded

- **Per record:** an empty `articles.text_original`, the same representation the
  58 China records with no captured text already use in the tracked database
  (Singapore has none). Nothing else per record is
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

## 8. Recovery (not run)

The recovery follows review and merge. The command is the one already
documented:

    .venv/bin/python pipeline.py --date 2026-09-28 --source sg_mindef_releases --no-analysis

Against the tracked database, seven of the window's eleven releases are already
stored (`23sep26-nr`, `24sep26-nr`, `25sep26-speech`, `27sep26-nr`,
`27sep26-nr2`, `28sep26-mq`, `28sep26-speech`; ids 4561-4721). Expected:

- **New:** `22sep26-infographic` (empty body), `22sep26-nr` and
  `22sep26-speech`, plus `23sep26-mq` unless the 2026-09-29 scheduled run has
  already stored it (its window, 09-23 → 09-29, includes it).
- **Duplicates:** the other seven or eight.
- **Run row:** discovered 11, fetched 11, extracted 11, `text_unavailable` 1,
  status `ok`. Both held records absent.

The offline run over the fixtures and an empty database gives 11 new; the live
counts differ only because those releases are already stored.
