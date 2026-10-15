"""Deterministic offline Korea Week-42 manuscript rehearsal, NEVER a release.

Uses only pre-authored staged synopses. No HWPX/body data, government access,
LLM, Sunday evidence, editor email, public records, or production mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

from core.korea_private_research_candidates import (
    COMMIT, ROOT, KoreaResearchHold, load, require,
)
from scripts.render_korea_private_research import write_private

SCHEMA = "ipr-korea-week42-no-send-manuscript-rehearsal/1"
WEEK = "2026-10-17"
FIXED = (
    ("KR-MND-W42-01", "Pangyo defense AI research hub"),
    ("KR-MND-W42-02", "South Korea–Japan defense consultations"),
    ("KR-MND-W42-03", "Gwangju readiness inspection and proposed relocation"),
)
HOLD = ("NOT APPROVED FOR DISTRIBUTION, MODEL USE, SUNDAY EMAIL, "
        "PUBLICATION OR SOURCE ADMISSION.")


def compose(rows, *, week_ending=WEEK):
    """Source-bound editorial manuscript, without unsourced analytical claims."""
    require(week_ending == WEEK and type(rows) is list
            and len(rows) == len(FIXED), "unexpected rehearsal source scope")
    require(rows == load(week_ending=WEEK, as_of=WEEK),
            "manuscript sources must exactly match staged validated packet")
    for row, (ident, _) in zip(rows, FIXED):
        require(type(row) is dict and row.get("source_id") == ident
                and row.get("status") == "held-not-sunday-or-model-eligible"
                and row.get("copy_scope") ==
                "authored-editorial-synopsis-only-no-original-text-or-media"
                and row.get("claim_kind") == "reported_action",
                "source unpinned, reordered, or unexpectedly promoted")
    lines = [
        "# Korea — Week 42 source-linked manuscript rehearsal",
        "",
        "**RESTRICTED LOCAL REHEARSAL — " + HOLD + "**",
        "",
        "Reporting week ending: " + week_ending + ".",
        "Research evidence frozen from Korea shadow Git commit " + COMMIT + ".",
        "This is a preliminary assembly of three held authored summaries, "
        "not a complete or approved weekly regional review.",
        "",
        "## Working desk digest",
        "",
        "South Korea's Ministry of National Defense reported an initial defense "
        "AI research hub opening, defense consultations with Japan, and a "
        "ministerial readiness inspection. These claims are solely "
        "attributed to that ministry and remain unapproved for publication.",
        "",
    ]
    for i, (row, (_, heading)) in enumerate(zip(rows, FIXED), start=1):
        note = "K" + str(i)
        lines.extend([
            "## " + heading,
            "",
            row["summary"] + " [^" + note + "]",
            "",
            "**Interpretation limits for editorial review:**",
        ])
        for caveat in row["caveats"]:
            lines.append("- " + caveat)
        lines.extend([
            "",
            "**Status:** Original-language review, reuse-rights review and "
            "owner manuscript approval are still pending.",
            "",
        ])
    lines.extend([
        "## Canonical citations and immutable source identities",
        "",
        "All three documents were issued by South Korea's Ministry of National "
        "Defense and republished by Korea Policy Briefing. Historic KOGL Type "
        "1 text-only markings do not authorize embedded HWPX media, "
        "external model use, or full-body redistribution.",
        "",
    ])
    for i, row in enumerate(rows, 1):
        lines.append(
            "[^K" + str(i) + "]: " + row["source_id"] + " — "
            + row["title_original"] + ". " + row["issuer"] + ", "
            + "distributed " + row["document_distribution_date"]
            + "; portal posted " + row["published_date"] + ". "
            + row["source_url"] + ". Text SHA-256: "
            + row["source_content_sha256"] + "; HWPX capture SHA-256: "
            + row["hwpx_capture_sha256"] + "; portal HTML SHA-256: "
            + row["publisher_html_capture_sha256"] + "."
        )
    lines.extend([
        "",
        "## Unresolved production and editorial holds",
        "",
        "- Obtain authenticated exact-version Korean language review, mapped "
        "original lines and independently adjudicated source-reuse rights. "
        "A completed-looking review form is not proof of a human signature.",
        "- Source 156785161 has an unresolved Inje excavation-year "
        "contradiction (#601) and is excluded.",
        "- The October 12 scheduled collector failed; lookback captures "
        "cannot retroactively turn it into a successful scheduled run.",
        "- Complete independently backed-up restricted archival custody, "
        "with owner-approved original-byte retention and one-writer cutover.",
        "- No Sunday source admission, paid AI processing, editor email, "
        "public record, Brief publication, or production deployment.",
        "",
        "**" + HOLD + "**",
        "",
    ])
    return "\n".join(lines)


def check_exact(rows, document):
    """Verify deterministic manuscript equality; grant no permission."""
    require(type(document) is str and len(document.encode("utf-8")) <= 25000,
            "invalid or oversized manuscript")
    require(document == compose(rows),
            "rehearsal manuscript changed or source version no longer pinned")
    for i, row in enumerate(rows, 1):
        citation = "[^K" + str(i) + "]"
        require(document.count(citation) == 2
                and document.count(row["source_url"]) == 1
                and document.count(row["source_content_sha256"]) == 1
                and document.count(row["summary"]) == 1,
                "missing, duplicated, or unpinned source citation")
    return {
        "schema": SCHEMA,
        "frozen_shadow_commit": COMMIT,
        "source_ids": [row["source_id"] for row in rows],
        "citation_count": len(rows),
        "exact_manuscript_sha256": hashlib.sha256(
            document.encode("utf-8")).hexdigest(),
        "source_attribution_contract_passed": True,
        "human_review_authenticated": False,
        "publisher_originals_loaded": False,
        "model_called": False,
        "email_sent": False,
        "sunday_admission_authorized": False,
        "source_rights_approved": False,
        "production_or_publication_authorized": False,
    }


def check_local_file(filename, *, rows):
    path = Path(filename).expanduser()
    target = path.resolve(strict=False)
    root = ROOT.resolve()
    require(path.is_absolute() and target != root and root not in target.parents
            and path.is_file() and not path.is_symlink()
            and not path.parent.is_symlink() and path.stat().st_size <= 25000,
            "private manuscript must be an existing safe file outside repo")
    if os.name == "posix":
        require(stat.S_IMODE(path.stat().st_mode) == 0o600,
                "private manuscript is not owner-only")
    try:
        document = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise KoreaResearchHold("unable to read private manuscript") from exc
    return check_exact(rows, document)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--create", help="new absolute private Markdown file outside repo")
    action.add_argument("--check", help="existing private Markdown file outside repo")
    parser.add_argument("--explicit-local-no-send", action="store_true")
    args = parser.parse_args(argv)
    if not args.explicit_local_no_send:
        parser.error("--explicit-local-no-send acknowledgement required")
    rows = load(week_ending=WEEK, as_of=WEEK)
    if args.create:
        document = compose(rows)
        check_exact(rows, document)
        write_private(args.create, document)
        receipt = check_local_file(args.create, rows=rows)
    else:
        receipt = check_local_file(args.check, rows=rows)
    # Only bounded non-content facts; no names, manuscript, paths or source prose.
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
