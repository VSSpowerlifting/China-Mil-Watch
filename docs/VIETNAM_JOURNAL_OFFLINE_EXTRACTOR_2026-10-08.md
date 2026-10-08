# National Defence Journal — offline English article extractor candidate

This stage is **not** an active shadow source, text archive, or source-use
authorization. It introduces an offline parser using measured DOM structure
from a bounded, host-policy-compliant research run, so a future adapter can
have a strict extraction contract instead of treating an HTTP 200 as a body.

## Evidence

Read-only desktop DOM diagnostic:
[Actions 37715012023](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37715012023)
on disposable PR #136. It issued exactly three GET requests: a readable and
permissive 200-byte desktop robots policy and two allowed, 200-status English
journal articles (site IDs **26936** and **26919**). Both exhibited the same:

- Headline: `.page-main-left-newsdt .newsdt-page-ct-tit`, actually a div;
  neither article has the usual `h1` markup.
- Article date: `.page-main-left-newsdt .newsdt-page-ct-time span`.
  A distinct time exists at `#subTopMenu-time`: selecting the first date
  on the page would confuse the *site clock* with *publication date*.
- Body: `.page-main-left-newsdt .newsdt-page-ct-text`, with direct `p`
  and `table` children. The sample pages contain 16 and 14 paragraphs,
  respectively, and caption-bearing image tables.
- A rank/academic-qualified author credit appears inside the body's last
  direct paragraph (separately from the journal's publisher). The extractor
  returns that original credit but does **not** invent a verified structured
  person identity or job title.

The separate DOM probe stored only HTML structure, selectors, lengths,
hashes and response status—**no source HTML or article prose**. Its article
responses were 200 with 3-request total budget. The robots policy was also
verified earlier in Actions run 37712715499.

## Parser behavior

`scraper/sources/vn_journal_article.py` is offline and has **no transport,
filesystem writes or state branch**. It accepts a caller-supplied HTML string
and a URL validated against the disabled source's canonical English desktop
identity. It returns the original-language title, **article-stamped** day,
ordered paragraphs and caption/table text, publisher, article identity and
a separately qualified author credit. Source body text exists **only in
memory** of the caller; do not persist, log or publish it without a separate
source-use determination.

It refuses absent or duplicate article title/time/body wrappers, invalid
source publication stamps or weekdays, non-desktop aliases, unfamiliar body
children, an empty/title-only body and oversized content. Rank mentions in
ordinary body paragraphs do not automatically become a signed byline.
Synthetic fixtures and regression tests contain no copyrighted article prose.

Full source capture, reuse/display rights, dated discovery completeness,
known publication chronology, page-change monitoring and actual shadow state
remain out of scope. Even a parser that extracts two real samples in memory
does not prove a daily source is complete or authorized for permanent
full-text retention.

## Gate to be lifted later

Before production or shadow source activation, require:

1. Verified parse on the two specific reachable HTML pages without saving
   publisher text; compare title, article date, body bounds, nonempty prose
   and byline against the source.
2. A source-specific, date-bounded listing and pagination proof, with a
   separate earliest-known record and missed-item audit.
3. Explicit treatment of captions/attachments, and a reviewed policy for
   article rights/retention/public display (the footer states all rights
   reserved).
4. Owner activation to an isolated new source clock and branch. Never
   reuse the Vietnam MPS/MOIT Day 0 or treat military-journal commentary as
   formal Ministry of National Defence directives.

Only after these gates should a narrowly scoped shadow adapter be proposed.
