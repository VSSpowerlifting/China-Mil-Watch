# Briefs reading design — Phase 2

Owner inspection candidate. Baseline: current clean main
`f469801b9c1ddb21e01188b4bfddf4ffa0c913ae`, fetched after #570 merged as
`64e88541b2`. Branch: `codex/ipr-briefs-reading-phase2`. No merge, deployment,
new Brief, editorial approval, or image admission is authorized by this work.

## Diagnosis and direction

A policy reader following a long argument on a laptop in ordinary office light
needs room for linked prose, clear changes of argument, and quiet access to the
sources. Keep IPR's navy photographic opening and ivory reading environment;
use the established turquoise sparingly for structure. Instrument Serif,
Source Serif 4 and Inter retain their existing roles.

The baseline's 704px article included 36px padding on each side and two 1px
borders: actual prose was only **630px**, at 19px/35.15px. Its 272px navigation
panel and 76.8–86.4px gap made that constraint more conspicuous. The continuous
article borders and filled navigation produced the document-panel impression.
This is measured Chromium geometry, not a deduction from CSS alone.

Two actual full-page trials used the same baseline content at 1440 × 900:

- **A, open journal:** full-width paragraph flow, open navigation, no continuous
  article borders, 74ch maximum prose and 1.75 line-height. It supports sustained
  reading and preserves a stable left edge.
- **B, composed section openings:** headings float alongside the beginning of
  prose, a display finding, and two-column publisher references. It has stronger
  visual variation, but abrupt changes in line length interrupt paragraphs;
  source metadata becomes cramped. It also puts long headings into a narrow
  side column. Rejected.

Choose A. Its final refinement gives approved headings a shorter measure and
more breathing space, and uses existing semantic roles for source and closing
matter. No floating headings, two-column references, paragraph extraction,
position-based emphasis, numbered chapters, or new editorial text is shipped.
The trial CSS and full-page captures remain in the
[evidence index](evidence/ipr-reading-phase2/README.md).

## The shared implementation

Only `site/preview/briefs.css` changes production behavior. All 18 generated
article HTML files are byte-identical to baseline. Historical sidecars, native
Briefs, source-linked manuscript, five Laos section headings, paragraph order,
finding, citations, provenance, metadata, credits and approval manifests remain
unchanged. Existing pipeline/rights/readiness gates and the release allow-list
are unchanged. Future issues inherit the same sheet through their existing
renderer; five existing private fixtures exercise that path.

| Owner concern | Implemented response | Evidence |
| --- | --- | --- |
| Walls of prose | Stable wider measure; 1.75 desktop leading; more distinct space between arguments than between paragraphs; bounded display headings | No. 18 full pages and 25/50/75% prose captures |
| Narrow text | 49rem main track with no internal side padding; actual prose limited to 74ch | Measured 630 → 743.77px at both desktop widths |
| Continuous beige rectangle | Remove article borders and background; remove the outer wrap's edge; one opaque ivory environment keeps contours outside prose | Full-page before/after, including no-photo issues |
| Repetitive section character | Approved argument headings use short structural rules; existing follow-up sections use a closing rule; sources use interface typography; citation retains its compact object material | Nos. 17, 14 and 1, source and citation captures |
| Storytelling disappears after hero | Give existing argumentative transitions space; preserve source-linked hyperlinks and qualifications; distinguish the approved finding and existing evidence/source objects | Mid/later prose and publisher references; see limits below |
| Navigation dominates | 232px open navigation, 51.2–56px gap, lighter summary, 44px minimum links; existing sticky behavior and native mobile disclosure | Desktop and mobile full pages; accessibility matrix |

At 375px the usable prose width remains 331px and source-linked body leading
remains 32.4px on 18px type. At 320px width is 276px. Tablet prose widens from
643.13 to 691.19px. No extra mobile ornament is introduced. Desktop prose
measure is 73.91 computed zero-character widths; actual complete lines average
76.47 characters, longest 86 including spaces and linked text. `ch` is a font
metric, not a promise of that many literal characters. Body size stays 19px.
The Laos desktop page becomes 9,153px tall from 9,866px at 1440px: about 7.2%
shorter despite more pronounced section boundaries. Long arguments remain
long; no paragraph is shortened or omitted.

The opaque wrap shares the page's ivory rather than creating a new contrasting
rectangle. The article and navigation themselves are transparent. Faint
cartographic material survives in the surrounding field and hero, without a
contour behind prose. This deliberately trades some central texture for clean
reading. The existing hero, selected artwork, documentary pixels and all image
admission/rights distinctions are retained.

## Safe storytelling boundary and future proposal

The redesign changes composition, not the editorial architecture established in
`BRIEFS_EDITORIAL_ARCHITECTURE_V2.md`.

**Available now, only with an independently approved presentation:** v1's
`evidence.establishes` / `evidence.uncertain` can present exact supported
manuscript excerpts, with paragraph and publisher traces. The shared evidence
object retains its distinct neutral surface and responsive single-column
fallback. An official claim does not become independently verified because an
editor places it in that object. No new excerpt or classification is selected
for Laos here. Native existing comparisons retain their labels, per-desk
citations and accessible disclosure; coverage remains explicitly bounded.

**Mid-article photography already has a constrained mechanism:** v1 `figures`
can place the article's already admitted photograph after an exact paragraph.
The bound presentation receipt must authorize that placement; the article and
paired media/hash/rights gates resolve the image, and the shared figure macro
carries its caption, alt text, context, credit, licence and non-endorsement
notice. No inline photograph is selected in the approved Laos manifest, so none
is added. No. 10's rights hold and No. 12's denied asset remain intact. Exact
pixels or governed derivatives remain mandatory.

**Separate future work:** to use a second documentary photograph, propose an
optional figure record with a stable admitted media ID, exact paragraph
placement, independently reviewed source/event relationship, contextual scope,
alt/caption/credit and derivative hashes. Bind those fields into the independent
presentation fingerprint and reject absent/revoked rights, unsupported event
claims and missing custody. Do not accept arbitrary URLs or paths. This needs a
reviewed contract extension and exact-content approval before rendering. A
verified chronology or source comparison likewise needs explicit source IDs,
dates or comparison basis and human review; dates or excerpts must never be
assembled by a layout heuristic. No schema, CMS, admission, publication or
workflow migration is part of this PR.

**Remaining design limitation:** the approved Laos body contains long
multi-paragraph arguments without admitted mid-article objects. Their internal
rhythm still depends on typography, links, paragraph space and section openings.
This work does not pretend that typography supplies new evidence-led reporting.
The owner should review the entire page, especially the four-paragraph digital
identity section, before accepting that the reading rhythm is sufficient. More
visual interruptions would require an editorial decision and, where applicable,
new exact presentation approval. Pages without suitable media remain complete.

## Verification and review

The screenshot index records measured geometry, full-page comparisons, both
trials, complete Nos. 17/14/1 experiences, no-photo/rights-held issues, and all
five private fixtures. `verify_brief_reading_design.py` reproduces these and
asserts usable width, reflow, prose contrast and exact preservation of all 18
article HTML files. `verify_brief_journal.py` supplies the existing all-issue
320/375/768/1280/1440 JS/no-JS/reduced-motion/forced-colors, fragments, keyboard,
print, enlarged text and **actual Chromium 200% browser zoom** matrix. It sets
Chromium's own isolated-profile zoom, and records innerWidth, DPR and pinch
scale; CSS scaling is tested separately.

Source plus recursively linked CSS peaks at 95,938 bytes; executable JS peaks
at 5,336 bytes, under unchanged 120,000 / 10,000 limits. Article CSS is 22,031
bytes (67 bytes larger than baseline), gzip 5,148 bytes. There is no new
frontend dependency, JavaScript, font or media delivery. Full receipts and test
outcomes are in the evidence index. Exact-head GitHub checks are required for
review; their live state is reported on the PR, not treated as approved by this
document. Owner visual sign-off, merge and any subsequent deployment remain
separate decisions.

Production regeneration used the historical sidecar renderer and
`site/render.py`. The pre-render output tree was clean. The existing scope
restoration helper removed 26 untracked source-image copies emitted by the
historical renderer, returning them to the baseline inventory. The **only**
generated file difference is `output/briefs.css`; no article HTML, catalogue,
homepage, feed, sitemap, database or image differs. Source and output commits
are separate. The existing render-contract workflow now also runs for changes
to the source/generated article stylesheet, so this visual PR receives exact
committed-output replay in GitHub CI. Only its pull-request path filter changes;
manual release conditions, permissions and deployment scope are unchanged. See the exact [file inventory](evidence/ipr-reading-phase2/changed-files.txt).
