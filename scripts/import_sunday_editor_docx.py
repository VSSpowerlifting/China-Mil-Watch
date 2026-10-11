"""Turn Dylan's edited Word manuscript into an offline review-only TXT candidate.

Only human-editable article paragraphs are taken from Word. Every original
record/source citation line, editorial question, header and appendix is copied
from the unmodified original and checked by validate_return. No publication,
mail, model, source rights approval, or repository writes are performed.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import os
from pathlib import Path

from docx import Document

from scripts.sunday_editor_readable import (
    BEGIN, APPENDIX, HEADINGS, PROSE_TITLES, editable_sections,
)
from scripts.validate_editorial_return import (
    ReturnValidationError, _sections, _split, validate_return,
)

MAX_DOCX_BYTES = 3_000_000
NO_COPY_MARKERS = (
    "SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:",
    "=== SOURCE APPENDIX", "=== EDITABLE MANUSCRIPT",
    "END OF UNAPPROVED WORKSHEET",
)


def _word_sections(word_bytes):
    if not isinstance(word_bytes, bytes) or not word_bytes or len(word_bytes) > MAX_DOCX_BYTES:
        raise ReturnValidationError("Word return must be nonempty and at most 3 MB")
    try:
        document = Document(BytesIO(word_bytes))
    except Exception as exc:
        raise ReturnValidationError("Word return is not a valid DOCX") from exc

    expected = ["WORKING TITLE", "DEK", *list(HEADINGS[2:])]
    inverse = {label: key for key, label in PROSE_TITLES.items()}
    result = {}
    current = None
    ended = False
    for paragraph in document.paragraphs:
        style = paragraph.style.name
        value = paragraph.text.strip()
        if style == "Title":
            key = "WORKING TITLE"
        elif style == "Subtitle":
            key = "DEK"
        elif style.startswith("Heading"):
            if value == "Source links for context":
                ended = True
                current = None
                continue
            key = inverse.get(value)
            if key is None:
                raise ReturnValidationError("unknown or altered Word section heading")
        else:
            key = None
        if key is not None:
            if ended or key in result:
                raise ReturnValidationError("duplicate or misplaced Word manuscript heading")
            result[key] = []
            current = key
            if value not in (PROSE_TITLES.get(key), "Source links for context"):
                if key in ("WORKING TITLE", "DEK"):
                    result[key].append(value)
            continue
        if not ended and current and value:
            result[current].append(value)

    if list(result) != expected:
        raise ReturnValidationError("Word manuscript headings missing or reordered")
    completed = {}
    for key, paragraphs in result.items():
        text = "\n\n".join(paragraphs).strip()
        if not text or any(marker in text for marker in NO_COPY_MARKERS):
            raise ReturnValidationError("Word manuscript is empty or contains protected source markers")
        completed[key] = text
    return completed


def reconstruct_return(original, edited_word):
    """Return candidate TXT and mechanical receipt; NEVER call publish/send."""
    editable_sections(original)
    new_text = _word_sections(edited_word)
    header, manuscript, appendix = _split(original)
    source_sections = _sections(manuscript)
    rebuilt = []
    for key, old in source_sections:
        if key in new_text:
            # Keep the exact ledger-citation lines; the editor's Word document
            # never gains authority to add IDs, alter appendices, or claim review.
            citations = [
                line for line in old.splitlines()
                if line.startswith(("SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:"))
            ]
            body = new_text[key]
            if citations:
                body += "\n" + "\n".join(citations)
        else:
            # Private editorial focus and questions are intentionally absent
            # from Dylan's Word copy and remain byte-equivalent here.
            body = old
        rebuilt.append("## " + key + "\n" + body)
    candidate = (
        header + "\n" + BEGIN + "\n" +
        "\n\n".join(rebuilt) + "\n" + appendix + "\n"
    )
    receipt = validate_return(original, candidate)
    return candidate, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--edited-word", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path,
                        help="new local private TXT; must not already exist")
    args = parser.parse_args(argv)
    if args.original.resolve() == args.out.resolve() or args.edited_word.resolve() == args.out.resolve():
        parser.error("input and output files must differ")
    try:
        original = args.original.read_text(encoding="utf-8")
        if args.edited_word.is_symlink() or not args.edited_word.is_file():
            raise ReturnValidationError("Word return must be a regular file")
        candidate, receipt = reconstruct_return(original, args.edited_word.read_bytes())
        fd = os.open(str(args.out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(candidate)
    except (ReturnValidationError, OSError, ValueError) as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print("Created unapproved local review-only candidate")
    print("Changed sections:", receipt["changed_sections"])
    print("Source appendix SHA-256:", receipt["appendix_sha256"])
    print("No Brief imported, approved, numbered, sent or published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
