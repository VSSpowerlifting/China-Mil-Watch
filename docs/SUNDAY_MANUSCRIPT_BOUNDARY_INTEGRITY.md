# Sunday manuscript structural boundary integrity

The Sunday AI writer returns tool-schema-constrained prose and enumerated
numeric/typed source IDs. Even a perfectly valid citation vocabulary is
insufficient if a **model-controlled prose string** can imitate a trusted
worksheet section heading, a second fabricated citation line or an immutable
source appendix.

Previously, `render_packet` inserted generated prose directly before the
trusted renderer's `=== SOURCE APPENDIX — DO NOT EDIT ===` boundary. A
malformed or adversarial tool response could put its own `===...` headings,
`SOURCE RECORD IDS:`, `EXTERNAL SOURCE IDS:`, `Record 123 |...` or
`END OF SOURCE APPENDIX` at the start of a prose line. An editor receiving the
attachment could then reasonably confuse model-authored material with the
trusted records and citation accounting.

This change reserves these structural delimiters **for the renderer only**.
`validate_prose_boundaries` rejects embedded packet section lines, Markdown
headings, counterfeit typed source lines and control characters across every
model prose field, including `editorial_focus`. The existing
`validate_manuscript` calls it before accepting Claude's structured tool
input. The actual `render_packet` also repeats the check as a second barrier
if a caller passes model output without having invoked the composer.

Ordinary narrative paragraphs, blank lines, inline emphasis and legitimate
section-level citations in their original structured arrays are still
supported. Actual `render_packet` controls the appendix; there is no automatic
repair of counterfeit source records. If model output fails validation, the
normal bounded retry can regenerate it once, but the handoff CLI does not write
the packet or call SMTP when the final result fails.

Focused tests include forged model-output examples, protections for each
writing field, a stand-alone renderer bypass attempt, correct printing of the
trusted source appendix, and a mocked `--preview-to-owner` CLI where forged
output must block both the attachment and outgoing email. No real model,
collector, SMTP account, publisher request, corpus write or public deployment is
used in this milestone.

No changes are made to external source-rights approval, publisher PDF fidelity,
desk promotion, production collection, delivery enablement, issue numbering,
publication, or Sunday workflow scheduling. The first true owner-only preview
still requires October 11's successful production update and owner source
review. This PR is independent of open source-roster PRs and can be merged only
after its exact-head focused and full offline CI passes.
