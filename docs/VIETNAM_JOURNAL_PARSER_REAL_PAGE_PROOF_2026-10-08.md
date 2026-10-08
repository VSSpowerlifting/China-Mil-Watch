# National Defence Journal — in-memory parser real-page proof, 2026-10-08 UTC

**Status:** two original English article pages successfully parsed *in memory*
using the new strict article field selectors. This validates a bounded parser
candidate; it does **not** license retention/publication, establish full desk
readiness or activate a collector.

## Exact execution

Disposable GitHub Actions proof [run 37715526834](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37715526834),
job 113111001369, exact proof head
`48b4251f02b8b8a8c3977617fbb6ead888a7a1ad`, stacked atop parser
feature PR #138. Synthetic offline journal identity and parser tests passed,
followed by exactly **three GETs** from the published IPR shadow identity:
desktop `robots.txt` and two separately permitted HTML article URLs.
There were no redirects, proxy, browser, cookies carried between requests
or retries. All requests stayed within the declared 256 KiB per-response
budget.

The metadata-only artifact is
[artifact 11523771068](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37715526834/artifacts/11523771068),
archive digest
`sha256:2b3a22f6344c228c6b9a9acde35e8245093c21f01fb292a0d8ad4ccb1a1223d3`.
It expires November 7, 2026. No publisher HTML or article text was
committed, logged or preserved in that artifact.

## Parsed-result metrics

| Measured property | Article 26936 | Article 26919 |
| --- | --- | --- |
| Stable ID | `vndj-en:26936` | `vndj-en:26919` |
| Source-stamped date | 2026-09-30 | 2026-09-28 |
| Extracted body characters | 16,028 | 12,895 |
| Ordered body blocks | 16 | 14 |
| Caption/table blocks | 2 | 1 |
| Explicit terminal-area author credit found | yes | yes |
| Human-verified person entity | no | no |
| Reuse/publication approval | no | no |

The parser found the date at the article-specific
`.newsdt-page-ct-time span` rather than the separate running clock at
`#subTopMenu-time`. Its title is the article's `.newsdt-page-ct-tit`
div (the website does not expose a normal `h1` for these pages), and
prose/captions come only from `.newsdt-page-ct-text`. Sidebar content,
comments, and tags are outside this selected DOM body.

**Important regression uncovered and resolved:** Initial in-memory proof
returned the correct body sizes/dates but missed each named credit. The
structural probe showed that these credits appear in the **last several**
direct paragraphs, *not invariably the absolute last*. The parser was
tightened to find a unique rank- or academic-qualified `strong > em`
credit within the final six direct elements and remove only that
particular paragraph from prose. An affiliation following the emphasized
name is preserved as part of the original credit. Conflicting credits
refuse extraction, and otherwise unsigned paragraphs stay as text.
That correction is included in the exact proof above.

## Not proved, and next gate

The two-page sample does not establish a complete dated listing, robust
article discovery/pagination, source publication cadence, rights to
retain and reproduce copyrighted prose, or extraction of every article
genre. The journal's footer remains **All rights reserved**.
The parser currently returns a complete *candidate* body in memory;
the actual completeness and author attribution must still receive source
integrity review beyond the samples, and any separate future shadow
collector needs explicit authorization and isolated state.

Do not assign this family the MPS/MOIT reliability clock, count the
extracted bytes as archived records, or declare it a Ministry of National
Defence directive feed. Parent source PR #129 stays independently
awaiting its CI and owner merge decision.
