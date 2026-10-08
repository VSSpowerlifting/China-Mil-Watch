# Evidence Timelines — contract and review

Implementation for [Issue #158](https://github.com/VSSpowerlifting/China-Mil-Watch/issues/158),
including its T2 design comment. Base: main
`24924c59d2e878bcf97f4d647ec611f59256a84e`, refreshed without feature overlap
to `e0cd41a2eb5ac0a540433859330799354f8b3670`. This feature is ready for review;
the Maritime Cooperation pilot remains **draft and unpublished**. Approval of
Brief No. 15 does not authorize a new timeline.

## Changed files

| Responsibility | Files |
| --- | --- |
| Contract, offline validation, draft pilot | `core/timelines.py`, `scripts/validate_timelines.py`, `timelines/maritime-cooperation-2026.json` |
| Rendering and deploy enforcement | `site/render.py`, `site/preview/generate_preview.py`, `scripts/validate_output.py` |
| Templates | `site/preview/templates/_analysis_nav.html`, `_timeline_macros.html`, `analysis.html`, `base.html`, `brief.html`, `record.html`, `timeline.html`, `timelines.html` (all under the same template directory) |
| Shared navigation and page styles | `site/preview/styles.css`, `site/preview/timelines.css` |
| Contract, integration and accessibility tests | `tests/test_timelines.py`, `tests/test_timeline_rendering.py`, `tests/test_palette_and_accessibility.py` |
| State and architecture documentation | `PROJECT_STATE.md`, `docs/ARCHITECTURE_AND_PUBLISHING.md`, this document |

## Source contract v1

`core/timelines.py` is the executable contract. Canonical JSON lives directly
under `timelines/`, with filename equal to its stable slug. Unknown fields,
duplicate JSON keys, symlinks and unsafe identifiers are rejected. JSON is
plain text data, escaped by Jinja; it accepts no authored HTML or Markdown.

| Field | Meaning and constraint |
| --- | --- |
| `timeline_schema` | Integer `1`; unsupported versions fail closed. |
| `slug`, `title`, `dek` | Stable safe identity and nonempty editorial text. |
| `editorial_status` | Exactly `draft` or `approved`; drafts carry no approval. |
| `scope`, `methodology_note` | Reader question, selection boundary and limitations. |
| `author_name`, `editor_name` | Actual preparation/ownership; the pilot says Codex prepared it and owner review is pending. |
| `reviewed_on`, `updated_on` | ISO dates; review cannot follow update. On this draft, the former is labelled source reconciliation, not human editorial approval. |
| `related_briefs` | Unique safe slugs resolving to approved native Briefs. |
| `entries` | Nonempty, sorted by `(event.start, event.end, id)`; IDs unique and stable. |
| `reconciliation` | Heading/note and exact entry IDs; required for every contested account. |
| `approval` | Approved content only: actual editor, date, human authorization reference and `content_sha256`. Approval must follow the latest editorial version. |

Each entry has `id`, `headline`, `observation`, `event`, `event_kind`,
`evidence` and boolean `contested`. A contested entry also needs a
`disagreement_note`. `event` carries `start`, `end`, `precision`
(`day`, `interval`, `uncertain_interval`) and a textual `date_basis`.
Intervals must be ordered and precision must agree with their endpoints.
`event_kind` distinguishes `occurrence`, `claim` and `report`; a report entry
must cover the publication dates of its evidence. No date is inferred from a
record's publication timestamp.

Each evidence item names exact `record_id`, `desk`, `source_id`,
`institution_id`, `published_on`, `url`, `basis`, `claim` and `excerpt`.
Basis is `reported`, `planned` or `retrospective`. Future-to-the-release
events must be labelled planned; retrospective evidence follows the event
interval. The excerpt must occur verbatim in the preserved original body.
Multiple claims can share a record across entries; the full ledger deduplicates
and orders records by publication date, then ID.

Reconciliation reads the DB through the repository's scratch-copy helper.
IDs, desk/source/institution identity, publication date and original URL must
match exactly. Source institution and language must also agree with an
enabled, contract-validated source in a public collecting desk's manifest.
Shadow, unapproved, orphan and ambiguous sources fail closed. No migration,
collector, model call or database write is involved.

Schema and source parity establish **what text was preserved**, not that a
government's account is true, that the English paraphrase is sound, or that a
human approved it. The exact new editorial artifact still needs owner review.
The module supplies `content_digest()` to bind approval to every editorial
field; it offers no automatic approval command. Later approval must record
actual human authorization, never copy the Brief's existing approval.

## Publication and private review

Ordinary rendering emits timelines, their library, local navigation and Brief/
record backlinks only for approved sidecars. With none approved, Analysis
retains its existing Briefs presentation and seven global destinations; no
Timelines library or misleading public tab is emitted. Approved timeline
routes receive the normal canonical and sitemap treatment, but no new feed.
The deploy validator rejects draft/stale routes, an empty public library,
changed editorial digests, missing citations and indexability mismatches.

```sh
.venv/bin/python scripts/validate_timelines.py
.venv/bin/python site/render.py \
  --review-timeline timelines/maritime-cooperation-2026.json \
  --out /private/tmp/ipr-timeline-review
python3 -m http.server 8782 --bind 127.0.0.1 \
  --directory /private/tmp/ipr-timeline-review
```

Open `/timelines.html` and `/timeline/maritime-cooperation-2026.html`.
The review command requires the canonical draft, rejects a site origin and
legacy mode, and refuses destinations inside or ancestral to the repository
(including production symlink aliases). Every review page is visibly private
and `noindex, nofollow`; no canonical, sitemap or native feed is produced.
The deploy gate deliberately refuses this draft tree.

## Pilot source reading

| Reported date | Attributed account | Publication / record |
| --- | --- | --- |
| September 3–9 | The Chinese ministry's broader interval; earlier boundary unexplained | September 14 / 4164 |
| September 4 | PLA Daily's high-level meetings and planning discussions | September 6 / 3924 |
| September 5 | MINDEF's opening earlier that day; PLA Daily's dated opening report | September 5 / 4466; September 6 / 3924 |
| September 5–9 | MINDEF's participation/exercise interval, repeated in closing release | September 5 / 4466; September 9 / 4472 |
| September 8–9 | MINDEF's prospective sea-phase interval; PLA Daily later reports September 8 transition to sea | September 5 / 4466; September 12 / 4102 |
| September 9 | MINDEF's contemporaneous conclusion; distinct PLA Daily retrospective of a five-day exercise ending that day | September 9 / 4472; September 12 / 4102 |

The two ministry starting boundaries remain visibly separate. Preparations
are not silently treated as the opening, and a plan is not silently turned
into a contemporaneous report. All five original-language titles, institutions,
dates and URLs are derived from preserved records. Brief No. 15 is linked and
its sidecar is untouched.

## Presentation and motion

Paper Ledger tokens, shared typefaces and address-specific topography are
reused. The three coordinated surfaces retain a neutral source layer and a
labelled analysis layer. Desktop uses a quiet date column, continuous SVG
spine and substantial narrative column. Mobile becomes a single-column
chronology. Diamond nodes also label contested boundaries in text; shape
does not express certainty. Two ordinal overview tracks distinguish reported
events from publication dates without suggesting a proportional axis.

Native disclosures preserve always-visible exact record links. The ledger
retains all evidence metadata and original URLs. The background is static on
timeline pages. Existing `reveal.js` supplies the only observer and script:
once-only entry reveal at 14px / 0.65s, transform-based spine growth and opacity
node emphasis. Local navigation/link feedback uses the shared 150ms ease.
No-JS, reduced-motion, `no-anim`, `:target`, print and forced-color fallbacks
remain functional. Closed disclosures expose their evidence in Chromium
print; browsers without `::details-content` support still retain the complete
source ledger and always-visible claims/citations.

The timeline shell stylesheet is deterministically derived from the shared
common sections of `styles.css` (tokens, base, type, masthead, furniture,
labels, footer, motion, responsive and print) plus `topography.css`. It omits
unrelated page-family rules and strips comments/boundary whitespace while
preserving strings. No second token source or CSS dependency is introduced.

## Verification receipts

Measured on 2026-10-08 in Chromium 147.0.7727.15. The local worktree has no
`.venv`; execution used the existing `/Users/benjaminyang/pla-watch/.venv/bin/python`
(Python 3.9). No dependency or browser installation was performed.

| Artifact | Raw bytes | Deterministic local gzip estimate |
| --- | ---: | ---: |
| Detail HTML | 35,076 | 6,530 |
| Library HTML | 9,222 | 2,789 |
| Shared timeline shell CSS | 33,002 | 7,857 |
| Page-specific `timelines.css` | 13,610 | 3,263 |
| Existing `reveal.js` | 2,746 | 1,316 |
| Shared Google Fonts CSS (observed response) | 20,612 | Not measured |

Detail HTML + local CSS is **81,688 bytes**. Including the observed shared
Google Fonts stylesheet, HTML + all linked CSS is **102,300 bytes**, below
the 120,000-byte gate;
JavaScript is below 10,000 bytes. Page-specific CSS exceeds the issue's
suggested 4–8 KB raw target; the complete page remains within the required
budget. Gzip figures are local estimates, not a claim about deployed headers.
No page-specific JavaScript or animation dependency was introduced.

- 43 focused timeline/palette/accessibility tests pass, with real Chromium and
  no skips. The first full run found two feature integration failures in the
  shared accessibility contract; both were fixed and included in this pass.
  The final complete offline suite passes: **4,000 tests in 2,055.162 seconds,
  two existing skips, no failures**. The skipped checks concern a generic label
  now spanning multiple collecting desks and the pre-existing stale declared
  release snapshot (2026-08-26/3,574 versus corpus 2026-10-06/4,930).
  Browser-backed timeline checks ran, rather than being skipped. This complete
  run used a dedicated `TMPDIR` after an earlier repeat encountered a cleanup
  test that scans the shared temporary directory; concurrent scratch reads
  were a plausible source of interference. No unrelated test was changed.
- `scripts/validate_timelines.py`: six entries, five exact preserved records,
  source parity passed; status still draft.
- Production `scripts/validate_output.py`: pass with the same ten governed
  historical warnings. The private pilot is intentionally refused by the
  deploy validator; tests demonstrate both draft refusal and approved-only
  canonical/sitemap behavior using disposable simulated approvals.
- Both private and simulated-approved complete builds are byte deterministic.
  No duplicate IDs, missing anchors or dead preserved-record links. All five
  original-source URLs match the stored records exactly; live availability of
  the original institutional sites is not asserted.
- Both surfaces inspected at 320/375/768/1280px, including an expanded evidence
  disclosure: no horizontal overflow, browser errors or failed local assets.
  No-JS and reduced-motion detail checks run at all four widths, including
  unavailable web fonts. Keyboard skip, disclosure toggle, focus, anchor
  navigation, `no-anim`, print and forced-color focus pass.
- Sampled text contrast on paper is at least 7.07:1. A below-fold section was
  observed hidden before entry, fully visible after the one-time reveal, and
  retained its arrived state after scrolling back. A closed disclosure's
  preserved evidence is visible in Chromium print.
- The database and all 7,456 tracked output files are byte-identical to the
  starting worktree. Database SHA-256:
  `712fa29a5f0356a216d47cd05f69839da757e806d42d04ff7be8d449f8f9f63b`.
  No `-wal`/`-shm` residue; no changes to Brief No. 15's sidecar, collection,
  taxonomy, Vietnam code or workflows in this feature diff. `graphify update .`
  completed (AST-only; its existing zero-node warnings remain).

Local review is served at
`http://127.0.0.1:8782/timeline/maritime-cooperation-2026.html` and
`http://127.0.0.1:8782/timelines.html`. Full-page 1280px/375px captures,
opening/chronology/account captures, the print PDF and `qa.json` are in
`/Users/benjaminyang/.codex/visualizations/2026/10/08/01a1199b-213f-73c2-86bb-4a07f2e43afe/`.
These are private local artifacts, not deployed pages.

Known limits: source-to-excerpt parity is mechanical, while paraphrase and
claim/date interpretation require human editorial review; the packet is
selected rather than exhaustive; source websites were not newly crawled;
print evidence expansion was verified in Chromium, with the source-ledger
fallback for older engines. The next action is owner review of the interface
and separate authorization of this exact timeline before any approved status,
production generation or publication. This PR authorizes none of those actions.
