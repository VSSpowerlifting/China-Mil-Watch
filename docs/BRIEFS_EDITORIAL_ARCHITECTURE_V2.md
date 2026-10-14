# Brief reading architecture — implementation and authoring

This is a presentation system for `source-linked-editorial-v1`, not a manuscript
migration. Native Briefs retain their Signal and standing sections; historical
issues retain their content, provenance and current IPR shell. No public routes,
collection, desk coverage, source classification or publication approvals change.

## Contract

`briefs/presentation/<slug>.json` uses `brief-presentation-v1`. It records the
article slug, full canonical editorial fingerprint, status, ordered sections and
an independent approval receipt. The canonical Brief JSON is never extended or
rewritten. `core/brief_presentation.py` validates the manifest; the production
renderer and output gate share its rendered-structure check.

Sections have `id`, `heading`, `start`, `end`. Paragraph numbers are **one-based,
inclusive**. They must cover every manuscript paragraph exactly once, in order.
Anchors use the reserved `reading-` namespace; heading IDs are `h-<section-id>`.
IDs must be unique, safe and distinct from component IDs. Headings are bounded
plain text. A deliberately simple layout can consist of one explicitly chosen
section; the helper never manufactures headings from paragraph count.

Optional `central_finding` is an excerpt with `paragraph`, `quote`, `sources`.
Optional `evidence` contains nonempty `establishes` and `uncertain` lists of those
excerpts. **v1 accepts exact manuscript excerpts only**, not new factual prose.
Every source ID must occur in that paragraph's existing support metadata. Human
review still decides whether the excerpt/classification is faithful: a substring
or government statement is not independent verification. Excerpts are attributed
to manuscript paragraph and publisher; there are no confidence percentages.

Optional `figures` contains `after_paragraph` and `media_id`. v1 reuses only the
article's already admitted photograph, resolved through the existing article and
paired catalogue/rights/hash gates. It accepts no URL, file path, caption, licence
override or new media admission. Missing/mismatched admissions fail preview and
release checks. The shared `cover_figure` macro carries its full existing credit,
context notice and rights links. No inline figure is selected for Laos. Other
media classes would need a separately reviewed extension; v1 grants none.

In explicit private review/check commands and approved presentations, unknown
fields, injected HTML, invalid ranges, unsupported references, stale manuscript
bindings and partial receipts fail closed. Rendered checks compare
section headings, ranges, anchors, navigation and excerpts. The independent
`manuscript_html_errors` check compares **exact** paragraph text, ordinal markers,
linked text, destination URLs and source IDs, including whitespace. It runs
during source-linked rendering and in `validate_output.py`.

## Review and approval boundary

Draft presentation has `status: draft`, `approval: null`. Ordinary rendering
withholds a recognized draft before validating its editorial payload, so unfinished
or stale private work cannot interrupt a public build. Recognition requires the
supported version, matching article identity and explicit draft status; corrupt
JSON or an unclassifiable manifest still fails closed. Existing
articles with no manifest continue to render. A private presentation preview
marks the proposed structure, retains the original article's number and credits
when already published, emits no public canonical/feed/sitemap, and uses noindex.
For a future draft manuscript the existing unnumbered/unapproved notice remains.
The preview destination must be new and outside the repository; production
`output/`, existing trees, ancestors and mixed review modes are refused.

An approved presentation needs a **separate actual human authorization**, with
`reviewed_by`, `reviewed_on`, `reference`, `fingerprint`, and `checks`. All four
checks (`headings`, `excerpts`, `media`, `rendered_page`) must be exactly true;
unused optional components are reviewed as absent. `fingerprint` is the helper's
digest of the exact entire presentation payload, excluding status and receipt.
That payload includes the canonical manuscript fingerprint. Altering a heading,
boundary, excerpt, figure placement or bound manuscript invalidates approval.

The helper never creates approval receipts. Once a human actually approves the
exact preview, an editor records that real authorization and exact digest; do
not copy manuscript attestations, fabricate reviewer/date/reference, or treat a
successful check as editorial approval. As with the existing publication
receipts, validation checks consistency, not the identity of the approving human.
The original manuscript's independent policy, rights and editorial gates remain
required. New source-linked manuscripts need a presentation for `author_brief.py
ready`, and an approved presentation before `author_brief.py approve` numbers
them. Already numbered publications are exempt from this new authoring gate.

## Editor workflow

1. Import/freeze the exact manuscript using `scripts/import_brief_manuscript.py`
   and complete the canonical source-linked Brief fields and source support.
   Keep the existing manuscript/source review and §5b exception workflow.
2. Prepare an explicit outline (repeat `--section` for every section):

   ```sh
   .venv/bin/python scripts/brief_presentation.py scaffold briefs/<slug>.json \
     --section 'reading-introduction|1|1|Introduction' \
     --section 'reading-analysis|2|11|<editor-selected heading>'
   ```

   This refuses existing files. Edit the separate manifest to adjust ranges or
   add selected exact excerpts/admitted-media identities; no model writes prose.
3. Check structure and the existing manuscript contract:

   ```sh
   .venv/bin/python scripts/brief_presentation.py check briefs/presentation/<slug>.json
   .venv/bin/python scripts/author_brief.py ready briefs/<slug>.json
   .venv/bin/python scripts/brief_presentation.py preview briefs/presentation/<slug>.json \
     --out /tmp/<new-private-preview>
   ```

   Structural checking does not imply manuscript readiness. Preview can precede
   final human source review; readiness still requires all existing attestations.
   Review paragraph fidelity, attribution, headings, source boundaries, media,
   keyboard use, 375/768/1280px layouts and print.
4. Complete actual human review, calculate `brief_presentation.py digest PATH`,
   and record the separate exact presentation approval described above. Run
   `brief_presentation.py check PATH --release`. For a new Brief, record actual
   manuscript publication approval through the existing `author_brief.py approve`
   command. For an already published Brief, retain its canonical source byte for
   byte; approval of its presentation does not amend the manuscript receipt.
5. Use existing authorized rendering, validation and release machinery. This PR
   authorizes none of those external release actions. A code merge alone leaves
   the Laos draft layout withheld.

## Laos and Sunday compatibility

Laos No. 18's review candidate divides paragraphs 1 / 2–5 / 6–8 / 9–10 / 11.
Its headings accurately distinguish Vietnam's assistance to **Laos's** identity
system and China's aviation training **and border exchanges**. Both headings and
the central-finding placement await owner review. The finding quotes paragraph
10 verbatim and does not repeat the dek. All eleven original paragraphs, seven
references, support metadata, joint authorship, photography, dates, number and
canonical manuscript fingerprint
`3ff586938e7680a014a7b6b6c60449327c9d07dcb12b2f6845fc0d3749a44c57`
remain unchanged. No evidence/uncertainty component is selected for Laos.
`tests/fixtures/brief-presentation/evidence-excerpts.json` demonstrates that
component separately using exact excerpts, with government-count and imagery
limitations retained. It has no approval and is never loaded by production.

The Sunday writer's `PROSE_FIELDS` already uses the native editorial field names
`opening_note`, `what_stood_out`, `why_it_matters`, `what_was_routine`,
and `what_im_watching_next`; `sunday_editorial_handoff.py` retains the section
labels for human review. Its intermediate manuscript is not itself an approved
canonical Brief. The minimum native integration is to carry the reviewed prose
and citations into the existing Brief contract; the native renderer supplies its
standing headings and any separately authored Signal. That anatomy supplies the hierarchy;
no competing Sunday schema, schedule, evidence eligibility or Dylan handoff is
introduced. If an approved Sunday manuscript deliberately uses the source-linked
exception instead, the editor adds this manifest after freezing it and before
numbering. The automated writer does not select or approve headings/excerpts.

Verification and screenshots: [evidence README](evidence/briefs-editorial-v2/README.md).
