# Metadata-only source text-gap receipts

## October 9, 2026 motivation

The production Daily [run #37973189996](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37973189996)
successfully collected from PLA Daily: 27 discovered/fetched/parsed; 2
duplicates, 22 new, 3 keyword-rejected, and **one** parsed document without
usable source text. The run's source table held the *count*, but omitted
individual document identity. The pipeline's **zero blank newly queued**
candidate count is a later-stage statistic and cannot identify the unreadable
page. Do not label the source as silent or conclude that extraction regressed.

## Scoped diagnostic

When a source adapter returns documents, the Daily pipeline now logs a
metadata-only record for each document whose normalized body is empty or
whitespace-only. This occurs **before cross-source/title dedup and keyword
filtering**, since any one of those stages could otherwise hide a gap even
though the original page was genuinely parsed. Each log entry includes:

- the source slug;
- the official page locator, with query string, userinfo and fragment removed;
- its publication date if a strict YYYY-MM-DD date was supplied;
- the first 16 hex digits of SHA-256 of the original URL (stable identity);
- a reminder that the page requires source review, not a publisher-silence verdict.

Neither article title nor text, response, API/model content, URL query secrets,
nor source page HTML appears in these logs. The per-source log details are
capped at ten; total unreadable document count is retained even above the cap.
The cap is only on log verbosity, never the source result or storage.

No fetches, model calls, source-content repairs, article metadata changes,
record deletion, database schema change, score change, source-rights decision,
publication or UI addition. Existing source run counts remain authoritative,
with a warning if the diagnostic count disagrees with the adapter's reported
text-unavailable count. Logs are *diagnostics*, not a new persistent corpus.

## Retrospective limit

The original Oct 9 job logs cannot be retroactively made more detailed.
A read-only pinned-database check can list **stored** metadata-only PLA Daily
rows first scraped on October 9, but it cannot prove which parsed page was the
single gap: that page could have been a deduplicated record or otherwise have
been filtered out before storage. Do not invent that identity. Future live
runs with a gap will have a URL-level receipt at extraction time.

## Review gate

Test the pure receipts without network, plus the extraction and PLA Daily
adapter contracts. Check tracked SQLite and public output byte-preservation,
followed by full PR offline/Chromium/render checks. No production rerun or
backfill is needed to prove this change.
