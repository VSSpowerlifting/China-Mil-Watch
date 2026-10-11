# Sunday Word-first editorial handoff and returned-document intake

Scope: editor convenience and offline review only. The production Sunday source
eligibility, first-pilot owner approval, SMTP gates and final publication approval
are unchanged. This document is separate from the Sunday scheduling fix.

## Editor-facing attachment format

For an authorized Sunday Dylan send, the canonical immutable audited .txt
remains attached byte-for-byte. A second editable Word (.docx) manuscript
is generated from the SAME already validated manuscript boundary, including
article headings, paragraphs and cited original official-source hyperlinks.
Dylan edits and returns Word; the .txt is a source-audit reference, not his
assignment. The email body remains article-first HTML/plain text.

The Word editing copy does NOT contain source bodies, version hashes, private
research synopses, technical receipts or unpublished source-use appendices.
It is an unapproved editorial projection, not an independently reviewed
publication manuscript or source admission. Missing or unsafe cited URLs
refuse the DOCX projection before SMTP. The exact reviewed original .txt
continues to be approved and attached unchanged.

The owner-only preview continues to carry just the exact original text; no
separate Word editing copy is generated for previews. The first October 11
manual delivery already happened and must not be replayed.

When Dylan returns the edited Word file, use the offline, source-safe converter.
It reads only article section headings and paragraphs, ignores the contextual
source-link appendix in Word, and restores every original protected citation
line and immutable source appendix from the sent TXT:

    python -m scripts.import_sunday_editor_docx \
      --original /private/IPR-Briefs-Editorial-YYYY-MM-DD.txt \
      --edited-word /private/Dylan-return.docx \
      --out /private/Dylan-review-candidate.txt

It rejects missing/reordered sections, injected source IDs, unresolved tracked
changes, unsafe archives and unchanged manuscripts. Its output is a
**review-only local candidate**, never an approved or published sidecar.
Review it for factual/source-language accuracy and perform normal publication
approval separately. The output file must not already exist.

Focused local regression tests:
python -m unittest tests.test_sunday_editor_docx tests.test_sunday_editor_readable tests.test_sunday_editor_word_return


The production workflow attaches a Word editing projection plus the exact
source-audited original text. Never import a returned Word document directly
into a published Brief; reconstruct a candidate and review original sources.
