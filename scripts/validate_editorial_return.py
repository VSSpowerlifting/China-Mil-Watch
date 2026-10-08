"""Validate Dylan's returned IPR Briefs .txt against the original attachment.

This is an offline, read-only editorial intake check. It validates the
immutable envelope and source appendix plus mechanical manuscript/citation
structure, NOT semantic truth, editorial approval, or publication readiness.

Usage:
    python -m scripts.validate_editorial_return \
        --original /private/original.txt --edited /private/dylan-edited.txt

Keep both files outside the public repository. Exit 0 means ONLY that a
human editor may review the returned text; never auto-import it to briefs/.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

BEGIN_EDIT = "=== EDITABLE MANUSCRIPT ==="
BEGIN_APPENDIX = "=== SOURCE APPENDIX — DO NOT EDIT ==="
END_APPENDIX = "END OF SOURCE APPENDIX"
END_PACKET = "END OF UNAPPROVED WORKSHEET"
MAX_PACKET_BYTES = 2_000_000
HEADING = re.compile(r"^## ([^\r\n]+)$", re.MULTILINE)
SOURCE_RECORD = re.compile(r"^Record ([0-9]+) \|", re.MULTILINE)
CITATION_LINE = re.compile(r"^SOURCE RECORD IDS:\s*(.*)$", re.MULTILINE)
EXTERNAL_SOURCE = re.compile(r"^External source ([A-Z0-9-]+) \\|", re.MULTILINE)
EXTERNAL_LINE = re.compile(r"^EXTERNAL SOURCE IDS:\s*(.*)$", re.MULTILINE)
EXTERNAL_IDS_LIST = re.compile(r"[A-Z0-9-]+(?:\\s*,\\s*[A-Z0-9-]+)*\\Z")
IDS_LIST = re.compile(r"[0-9]+(?:\s*,\s*[0-9]+)*\Z")


class ReturnValidationError(ValueError):
    """A returned worksheet is not mechanically safe to send for review."""


def _load(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
        raise ReturnValidationError("worksheet missing or larger than 2 MB")
    try:
        data = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReturnValidationError("worksheet must be UTF-8 text") from exc
    if "\x00" in data:
        raise ReturnValidationError("NUL bytes are not permitted in a worksheet")
    return data.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _split(packet: str):
    """Split exactly once; source and status sections are immutable.

    render_packet ends with a trailing newline, while text editors may add
    or remove blank lines at EOF. Normalize only that terminal whitespace
    before comparing the exact immutable header and source appendix.
    """
    packet = packet.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    for marker in (BEGIN_EDIT, BEGIN_APPENDIX, END_APPENDIX, END_PACKET):
        if sum(line == marker for line in packet.split("\n")) != 1:
            raise ReturnValidationError("missing or repeated packet marker: " + marker)
    edit = "\n" + BEGIN_EDIT + "\n"
    appendix = "\n" + BEGIN_APPENDIX + "\n"
    if edit not in packet or appendix not in packet:
        raise ReturnValidationError("worksheet boundaries must occupy separate lines")
    header, remainder = packet.split(edit, 1)
    manuscript, rest = remainder.split(appendix, 1)
    appendix_text = BEGIN_APPENDIX + "\n" + rest
    if not header.startswith("INDO-PACIFIC RECORD | BRIEFS EDITORIAL WORKSHEET\n"):
        raise ReturnValidationError("unrecognized IPR editorial worksheet header")
    if header.count("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED") != 1:
        raise ReturnValidationError("worksheet approval status is not valid")
    if not appendix_text.endswith("\n" + END_PACKET):
        raise ReturnValidationError("worksheet end marker missing or tampered")
    if "\n" + END_APPENDIX + "\n" not in appendix_text:
        raise ReturnValidationError("source appendix terminator missing")
    return header, manuscript.strip("\n"), appendix_text


def _sections(manuscript: str):
    matches = list(HEADING.finditer(manuscript))
    if not matches:
        raise ReturnValidationError("editable manuscript has no known section headings")
    if manuscript[:matches[0].start()].strip():
        raise ReturnValidationError("unexpected content before first manuscript heading")
    items = []
    for index, heading in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(manuscript)
        label = heading.group(1).strip()
        if not label or any(prior[0] == label for prior in items):
            raise ReturnValidationError("duplicate or empty manuscript section heading")
        body = manuscript[heading.end():end].strip()
        items.append((label, body))
    return items


def _cited_ids(section: str):
    citations = CITATION_LINE.findall(section)
    parsed = []
    for raw in citations:
        raw = raw.strip()
        if not IDS_LIST.fullmatch(raw):
            raise ReturnValidationError("malformed SOURCE RECORD IDS list")
        ids = [int(v.strip()) for v in raw.split(",")]
        if len(ids) != len(set(ids)):
            raise ReturnValidationError("duplicate ID within one source citation list")
        parsed.append(ids)
    return parsed


def _external_citations(section: str):
    lines = EXTERNAL_LINE.findall(section)
    ids_by_section = []
    for line in lines:
        line = line.strip()
        if not EXTERNAL_IDS_LIST.fullmatch(line):
            raise ReturnValidationError("malformed EXTERNAL SOURCE IDS list")
        ids = [part.strip() for part in line.split(",")]
        if len(ids) != len(set(ids)):
            raise ReturnValidationError("duplicate external source ID")
        ids_by_section.append(ids)
    return ids_by_section


def validate_return(original: str, edited: str) -> dict:
    """Return safe structural metrics; never approve or import any Brief."""
    base_header, base_body, base_appendix = _split(original)
    new_header, new_body, new_appendix = _split(edited)

    if new_header != base_header:
        raise ReturnValidationError("editor altered immutable header, dates, desks, or status")
    if new_appendix != base_appendix:
        raise ReturnValidationError("editor altered immutable source appendix")
    if not base_body or not new_body:
        raise ReturnValidationError("empty editable manuscript")
    base_sections = _sections(base_body)
    new_sections = _sections(new_body)
    if [key for key, _ in base_sections] != [key for key, _ in new_sections]:
        raise ReturnValidationError("missing, renamed, reordered, or added manuscript heading")
    if base_body == new_body:
        raise ReturnValidationError("no edits or editorial notes detected in returned attachment")

    allowed_ids = [int(x) for x in SOURCE_RECORD.findall(base_appendix)]
    if not allowed_ids or len(allowed_ids) != len(set(allowed_ids)):
        raise ReturnValidationError("original appendix has no unique source record listing")
    allowed = set(allowed_ids)
    allowed_external_ids = EXTERNAL_SOURCE.findall(base_appendix)
    if len(allowed_external_ids) != len(set(allowed_external_ids)):
        raise ReturnValidationError("original packet contains duplicate external sources")
    allowed_external = set(allowed_external_ids)

    edited_sections = 0
    cited_sections = 0
    for (label, old), (_, new) in zip(base_sections, new_sections):
        if old != new:
            edited_sections += 1
        if not new.strip():
            raise ReturnValidationError("blank editorial section: " + label)
        original_ids = _cited_ids(old)
        returned_ids = _cited_ids(new)
        old_external = _external_citations(old)
        new_external = _external_citations(new)
        if (len(returned_ids) != len(original_ids) or
                len(new_external) != len(old_external)):
            raise ReturnValidationError("changed source-citation structure: " + label)
        for row in new_external:
            if not set(row).issubset(allowed_external):
                raise ReturnValidationError(
                    "external citation absent from immutable source appendix: " + label)
            cited_sections += 1
        for row in returned_ids:
            if not set(row).issubset(allowed):
                raise ReturnValidationError("citation not present in original source appendix: " + label)
            cited_sections += 1
        # A citation-only section cannot stand in for actual editorial prose.
        prose = EXTERNAL_LINE.sub("", CITATION_LINE.sub("", new)).strip()
        if not prose:
            raise ReturnValidationError("editorial section contains no prose: " + label)

    return {
        "packet": next((line for line in base_header.splitlines()
                        if line.startswith("Packet: ")), "Packet: unknown"),
        "sections": len(new_sections),
        "changed_sections": edited_sections,
        "source_records": len(allowed),
        "external_sources": len(allowed_external),
        "citation_lines": cited_sections,
        "appendix_sha256": hashlib.sha256(base_appendix.encode("utf-8")).hexdigest(),
        "review_status": "STRUCTURAL REVIEW ONLY — UNAPPROVED",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path,
                        help="unchanged original attachment from the email you sent Dylan")
    parser.add_argument("--edited", required=True, type=Path,
                        help="Dylan's returned edited attachment")
    args = parser.parse_args(argv)
    if args.original.resolve() == args.edited.resolve():
        parser.error("--original and --edited must be different files")
    try:
        result = validate_return(_load(args.original), _load(args.edited))
    except ReturnValidationError as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print(result["packet"])
    print("Source appendix intact: {} records".format(result["source_records"]))
    print("Manuscript structure: {} sections, {} edited, {} citation lines".format(
        result["sections"], result["changed_sections"], result["citation_lines"]))
    print(result["review_status"])
    print("No Brief imported, approved, numbered, committed, published, or sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
