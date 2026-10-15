"""Read-only, source-link-only review of Japan Joint Staff's official press index.

No network is performed. Pass an independently acquired publisher HTML snapshot.
The result contains source pointers only, never PDF bodies or model-ready facts.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

INDEX = "https://www.mod.go.jp/js/press/"
HOST = "www.mod.go.jp"
PDF = re.compile(r"/js/pdf/(20[0-9]{2})/p(20[0-9]{6})_([0-9]{2})\.pdf\Z")
PUBLISHER_DATE = re.compile(r"(20[0-9]{2})\s*年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日")
MAX_HTML_BYTES = 2_000_000
MAX_YEAR_PDFS = 500


class JointStaffIndexError(ValueError):
    """Refuse an ambiguous source identity or incomplete index parse."""


def inspect_index_html(html: str, *, week_ending: str, cutoff: str):
    try:
        saturday, as_of = date.fromisoformat(week_ending), date.fromisoformat(cutoff)
    except (TypeError, ValueError) as exc:
        raise JointStaffIndexError("invalid ISO calendar date") from exc
    if saturday.isoformat() != week_ending or as_of.isoformat() != cutoff:
        raise JointStaffIndexError("noncanonical calendar date")
    start = saturday - timedelta(days=6)
    if saturday.weekday() != 5 or not start <= as_of <= saturday:
        raise JointStaffIndexError("cutoff must be inside Sunday-Saturday reporting week")
    if not isinstance(html, str) or not html.strip() or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise JointStaffIndexError("empty or oversized index original")
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    entries = []
    current_year_links = 0
    for anchor in soup.select("a[href]"):
        url = urljoin(INDEX, anchor.get("href", ""))
        parts = urlsplit(url)
        # Only first-party Joint Staff PDF originals, no query, fragment,
        # credentials or non-HTTPS targets. All other site navigation ignored.
        if parts.hostname != HOST or not parts.path.startswith("/js/pdf/"):
            continue
        if not parts.path.startswith("/js/pdf/{}/".format(saturday.year)):
            continue
        current_year_links += 1
        if current_year_links > MAX_YEAR_PDFS:
            raise JointStaffIndexError("publisher index unexpectedly large")
        if (parts.scheme != "https" or parts.port is not None or
                parts.username or parts.password or parts.query or parts.fragment):
            raise JointStaffIndexError("unsafe Joint Staff PDF URL")
        match = PDF.fullmatch(parts.path)
        if not match:
            raise JointStaffIndexError("unrecognized current-year original PDF path")
        if match.group(1) != match.group(2)[:4]:
            raise JointStaffIndexError("PDF directory/year mismatch")
        try:
            dated = date.fromisoformat(
                "{}-{}-{}".format(match.group(2)[:4], match.group(2)[4:6],
                                  match.group(2)[6:8]))
        except ValueError as exc:
            raise JointStaffIndexError("invalid dated PDF filename") from exc
        if dated > as_of or dated < start:
            continue
        # In the publisher index, a dated link is either itself date-bearing
        # or inside its own list item. Never borrow another row's date.
        parent = anchor.find_parent("li")
        source_label = (parent or anchor).get_text(" ", strip=True)
        dates = set(PUBLISHER_DATE.findall(source_label))
        if len(dates) != 1:
            raise JointStaffIndexError("missing or ambiguous source-row publication date")
        year, month, day = next(iter(dates))
        indexed = date(int(year), int(month), int(day))
        if indexed != dated:
            raise JointStaffIndexError("PDF filename disagrees with publisher row date")
        if url in seen:
            raise JointStaffIndexError("duplicate Joint Staff original link")
        seen.add(url)
        if len(source_label) > 400:
            raise JointStaffIndexError("unexpectedly long publisher row label")
        entries.append({
            "publisher": "Japan Joint Staff",
            "official_url": url,
            "published_date": dated.isoformat(),
            "publisher_label": source_label,
            "format": "pdf",
            "original_language": "ja",
            "source_scope": "linked_publisher_original_only",
            "archived_source_body": False,
            "eligible_for_automatic_model_drafting": False,
            "editorial_approved": False,
            "production_record": False,
        })
    if current_year_links == 0:
        raise JointStaffIndexError(
            "no in-scope publisher PDF links were parsed; not proof of silence")
    return {
        "schema": "ipr-japan-joint-staff-index-review/1",
        "publisher_index": INDEX,
        "week_ending": week_ending,
        "cutoff": cutoff,
        "saw_current_year_pdf_links": current_year_links,
        "in_window_official_links": sorted(entries, key=lambda row: (
            row["published_date"], row["official_url"]), reverse=True),
        "complete_japan_defense_coverage": False,
        "publisher_original_bytes_verified": False,
        "source_rights_approved": False,
        "model_called": False,
        "email_sent": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index-html", type=Path, required=True,
                        help="already acquired publisher index HTML; this tool never downloads it")
    parser.add_argument("--week-ending", required=True, help="reporting Saturday YYYY-MM-DD")
    parser.add_argument("--cutoff", required=True, help="last reviewed UTC date within week")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        content = args.index_html.read_text(encoding="utf-8")
        report = inspect_index_html(content, week_ending=args.week_ending,
                                    cutoff=args.cutoff)
    except (OSError, UnicodeDecodeError, JointStaffIndexError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
