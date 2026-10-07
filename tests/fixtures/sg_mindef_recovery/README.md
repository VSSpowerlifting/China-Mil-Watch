# Singapore recovery fixtures — captured 2026-09-29

Verbatim slices of pages served by mindef.gov.sg, used by
`tests/test_singapore_image_only_release.py`. The HTML and XML files were
produced by a script from the captures and were not edited by hand.

**How they were captured.** Between about 14:12 and 14:19 UTC on 2026-09-29, through
the adapter's own transport (`SGMindefAdapter._get`): the collector's
identifying User-Agent, a fresh `robots.txt` check that allowed the path,
and the adapter's 1.5-second spacing. One GET per page, one for the sitemap, and
two for `robots.txt`. No page was fetched to probe around a restriction.

**How they were trimmed.** Each page is 450–515 KB, almost all script and
site chrome. A fixture keeps the `<meta charset>` and `og:title` tags and the
`<main>…</main>` element verbatim, and drops the rest. The build asserted, for
each page, that the trimmed slice gives **the same `document_title()`, the same
`document_body()` and the same `article_evidence()`** as the full capture, so
the extracted text and its hash are identical to the untrimmed page's.

| Slug | Capture bytes | Fixture bytes | Capture SHA-256 (prefix) | Body chars | Body SHA-256 (prefix) |
|---|---|---|---|---|---|
| `22sep26-infographic` | 451,543 | 7,130 | `ebe45611017ff628` | 178 | `bcf64e9c0f47` |
| `22sep26-nr` | 481,453 | 23,523 | `44a5603d97cb2830` | 4165 | `10866200805d` |
| `22sep26-speech` | 513,519 | 36,394 | `7164bebc5c63a5b6` | 13417 | `0c40feac8102` |
| `23sep26-mq` | 450,086 | 6,703 | `17207d9293897d33` | 391 | `2d0e1a352cba` |

`22sep26-nr`, `22sep26-speech` and `23sep26-mq` bodies equal the shadow
collector's recorded `content_sha256` for the same releases (`10866200805d`,
`0c40feac8102`, `2d0e1a352cba`).

**`sitemap.xml`** keeps 14 `<url>` entries verbatim, real `lastmod` values
included, from a 816,719-byte sitemap (SHA-256 `aa9bbc812f3e7b32`):
the eleven releases the 2026-09-28 window discovers, both governed holds
(`15aug26-speech`, `16sep26-speech`, which MINDEF's sitemap still lists) and
`19sep26-nr` (outside the window). `23sep26-mq` carries `lastmod`
2026-09-25, two days after its slug date.

**Synthetic pages.** The tests also build filler pages in this layout, and a few
sub-200-character pages, in code. They are named `Synthetic …` and make no
claim about any real release. No real Singapore prose release under 200
characters is stored (the shortest is 258), so that case cannot be a capture.

**What is not here.** The image the infographic serves, its file name and its
alt text are not read by the adapter and are not asserted. Nothing was
transcribed from the image.
