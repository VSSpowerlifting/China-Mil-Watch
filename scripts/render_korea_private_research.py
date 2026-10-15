"""Private, offline Korea research preview from pinned authored short synopses.

No AI/model/network/source fetches/SMTP/public site/production DB changes.
Outputs one owner-chosen new local file OUTSIDE repository with mode 0600.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.korea_private_research_candidates import (
    COMMIT, ROOT, KoreaResearchHold, load,
)


def preview(rows, *, week_ending):
    """A source-attributed private reading aid, NOT a finished IPR Brief."""
    lines = [
        "# Korea — restricted editorial research candidates",
        "",
        "Reporting Saturday: " + week_ending,
        "Immutable Korean shadow snapshot: " + COMMIT,
        "",
        "**HOLD:** preliminary short research notes, not a published Brief, "
        "public source-admission approval, rights signoff or authorization "
        "for an external AI model or an email to an editor.",
        "",
    ]
    for row in rows:
        lines.extend([
            "## " + row["source_id"] + " — " + row["title_original"],
            "",
            "Official government portal: " + row["source_url"],
            "Issuer: " + row["issuer"] + " (republished by " + row["publisher"] + ")",
            "Portal posting: " + row["published_date"],
            "Original document distribution: " + row["document_distribution_date"],
            "Version of extracted Korean source: " + row["source_content_sha256"],
            "Original HWPX capture: " + row["hwpx_capture_sha256"],
            "",
            "**Attributed analyst synopsis, not original-source text:**",
            row["summary"],
            "",
            "**Cautions:**",
        ])
        for caution in row["caveats"]:
            lines.append("- " + caution)
        lines.extend([
            "",
            "**Text-rights marker observed in archived portal HTML:** "
            + row["text_license_marking"],
            "Publisher HTML response SHA-256: "
            + row["publisher_html_capture_sha256"],
            "**License adjudication:** not complete; no images or HWPX binary "
            "redistribution and no external model use authorized.",
            "",
        ])
    lines.extend([
        "Source 156785161 disputed 2025/2026 Inje excavation year is explicitly "
        "excluded from this packet (issue #601).",
        "Oct 12 historical Korea collection gap remains failed. Named human "
        "source-version signoff, archive custody, rights and owner/email "
        "publication decisions are separate.",
        "",
    ])
    return "\n".join(lines)


def write_private(path, content):
    out = Path(path).expanduser()
    target = out.resolve(strict=False)
    require = lambda ok, why: None if ok else (_ for _ in ()).throw(
        KoreaResearchHold(why))
    require(out.is_absolute() and out.parent.is_dir()
            and not out.parent.is_symlink()
            and not out.is_symlink() and not out.exists()
            and ROOT.resolve() != target
            and ROOT.resolve() not in target.parents,
            "output must be a NEW absolute path outside repo with safe parent")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(out, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except BaseException:
        try:
            out.unlink()
        except OSError:
            pass
        raise
    return str(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", default="2026-10-17")
    parser.add_argument("--as-of", default="2026-10-17")
    parser.add_argument("--out", required=True,
                        help="new absolute local private .md file OUTSIDE repo")
    parser.add_argument("--explicit-local-only", action="store_true",
                        help="acknowledge preview is not a model/email/publication")
    args = parser.parse_args(argv)
    if not args.explicit_local_only:
        parser.error("explicit private no-send preview acknowledgement required")
    rows = load(week_ending=args.week_ending, as_of=args.as_of)
    dest = write_private(args.out, preview(rows, week_ending=args.week_ending))
    print(json.dumps({
        "private_preview_path": dest, "source_count": len(rows),
        "published": False, "model_called": False, "email_sent": False,
        "source_originals_copied": False, "rights_approved": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
