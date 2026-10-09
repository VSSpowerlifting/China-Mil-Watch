# Japan MOD: bounded live HTML observations — still unsigned

This optional operator-only tool addresses the two Japan Ministry of Defense
English-language press releases for the October 10, 2026 research week:
`JP-W41-01` and `JP-W41-02`. The existing research packet contains only
their official publisher URL/date/title and analyst synopsis, **not an immutable
captured HTML original**. This tool can check what bytes the two live pages
return *now*, producing hashes and visible-text matching indicators, while
**discarding all page body text**.

## Exact scope and operation

On an operator's explicit request (never scheduled):

```bash
python -m scripts.japan_mod_html_observation \
  --fetch-live \
  --out /private/mod-two-html-observations.json
```

The `/private` path represents an already existing private directory
outside the source checkout. A new JSON receipt is created exclusively,
mode 0600, and is never overwritten or uploaded to a CI artifact.

- Before network access, the tool validates the exact 3-item Japan research
  source roster; it can fetch **only two hardcoded** official
  `https://www.mod.go.jp/en/article/2026/10/…html` URLs. It makes at most
  two HTML GET requests, rejects redirects and final URLs other than the exact
  expected source, enforces status 200, identity content encoding, an HTML
  content type, strict UTF-8 and a 1.5-MB response budget per page.
- It computes SHA-256 of the **exact received raw HTML bytes** and the
  decoded visible text, noting whether the known title and publication-day
  wording is present in the body. It refuses to count an HTML `<title>`
  metadata field, a string placed in the HTML head, JavaScript or explicitly
  hidden body text as evidence of visible article wording; a real HTML body
  is required. This is still a coarse signal, not rendered-page verification.
  Missing body wording is a human-review task, not silent success.
- The output contains only source IDs, observation time, byte count, digests,
  matching booleans, and strict FALSE source-use/release fields. It does
  **not** retain raw HTML, article text, publisher links, synopses, thumbnails,
  stylesheets or other externally fetched resources. The report itself
  cannot reconstruct its source page or prove a historical HTML edition.
- There is no third-party model call, release authorization, Dylan SMTP
  send, country desk promotion, Git branch write, production SQLite or site
  mutation. Tests use synthetic HTML and mocked HTTP only; CI does **not**
  fetch live ministry pages.

## Evidence and rights interpretation

A live response hash is an observation, not proof that the *same* byte stream
existed on publication day. It **does not** replace independently preserving
the publisher original, conducting human source/factual review, checking the
Japanese-language original or establishing rights to copy/translate/reuse
the publisher text. MOD terms of use, editing and attribution conditions,
third-party image/figure restrictions and changed site terms still need
human review. As before, the two English-language MOD page pointers remain
on regional source HOLD, and **the separate October 11 exact-manuscript
owner-release SHA rule remains binding**.

This PR is a small, manual observation utility under
[Issue #271](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/271),
independent of open #293 and #295 archived source-version comparisons.
