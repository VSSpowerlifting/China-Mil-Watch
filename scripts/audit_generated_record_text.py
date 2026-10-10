#!/usr/bin/env python3
"""Read-only audit of stored third-party body text in generated IPR record pages.

This verifies the *tracked/generated static files*, not live CDN delivery,
publisher permissions, ownership, public-domain status or an infringement.
It deliberately NEVER prints, stores or returns any captured original body.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_db import read_only  # noqa: E402

DEFAULT_DB = ROOT / "pla_watch.db"
DEFAULT_OUTPUT = ROOT / "output"
DEFAULT_SOURCE = "sg_mindef_releases"


class CapturedTextParser(HTMLParser):
    """Extract only Jinja's original-text DIV plus outbound source link HREFs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.has_original_container = False
        self.fragments = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if self.depth:
            self.depth += 1
        elif tag == "div" and "original-text" in (attrs.get("class") or "").split():
            self.depth = 1
            self.has_original_container = True

    def handle_startendtag(self, tag, attrs):
        # A self-closing element within the captured DIV adds no nesting.
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and v)

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.fragments.append(data)


def _norm(value):
    return " ".join(value.split())


def _expected_body(original):
    """The real record.html template strips blank lines and paragraph ends."""
    return _norm(" ".join(p.strip() for p in (original or "").split("\n") if p.strip()))


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_generated_record_text(db_path=DEFAULT_DB, output_dir=DEFAULT_OUTPUT,
                                source_slug=DEFAULT_SOURCE):
    """Return safe aggregate findings and numeric IDs, with no original content."""
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    if not isinstance(source_slug, str) or not source_slug or "/" in source_slug:
        raise ValueError("unsafe source identifier")
    if not db_path.is_file():
        raise ValueError("archive database missing")
    if not output_dir.is_dir():
        raise ValueError("generated site directory missing")
    before = _sha(db_path)
    with read_only(db_path) as db:
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("archive integrity check failed")
        rows = [
            dict(row) for row in db.execute(
                "SELECT a.id, a.text_original, a.url "
                "FROM articles a JOIN sources s ON s.id = a.source_id "
                "WHERE s.slug = ? ORDER BY a.id", (source_slug,)
            )
        ]
    if not rows:
        raise ValueError("no archive records for requested source identifier")

    counters = {
        "archived_records": len(rows),
        "generated_page_present": 0,
        "generated_page_missing": 0,
        "original_text_container_present": 0,
        "archived_body_nonempty": 0,
        "captured_body_rendered_exact": 0,
        "captured_body_rendered_different": 0,
        "captured_body_not_rendered": 0,
        "original_url_link_present": 0,
    }
    ids = {"missing_pages": [], "exact_full_body_rendered": [],
           "body_mismatch": [], "body_not_rendered": [], "missing_official_link": []}
    for row in rows:
        rid = row["id"]
        path = output_dir / "record" / ("%d.html" % rid)
        if not path.is_file():
            counters["generated_page_missing"] += 1
            ids["missing_pages"].append(rid)
            continue
        counters["generated_page_present"] += 1
        parser = CapturedTextParser()
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        if parser.has_original_container:
            counters["original_text_container_present"] += 1
        if row["url"] in parser.links:
            counters["original_url_link_present"] += 1
        else:
            ids["missing_official_link"].append(rid)
        original = _expected_body(row["text_original"])
        observed = _norm(" ".join(parser.fragments))
        if original:
            counters["archived_body_nonempty"] += 1
        if not observed:
            counters["captured_body_not_rendered"] += 1
            ids["body_not_rendered"].append(rid)
        elif original and observed == original:
            counters["captured_body_rendered_exact"] += 1
            ids["exact_full_body_rendered"].append(rid)
        else:
            counters["captured_body_rendered_different"] += 1
            ids["body_mismatch"].append(rid)

    if _sha(db_path) != before:
        raise RuntimeError("tracked DB changed during read-only audit")

    # These words deliberately qualify the result. A tracked HTML file is not
    # independent evidence that the same bytes were served from a CDN.
    return {
        "schema": "ipr-generated-third-party-body-audit/1",
        "source_slug": source_slug,
        "surface": "generated-static-archive-files-not-live-cdn",
        "source_use_permission_checked": False,
        "legal_conclusion": None,
        "archive_sha256_before_after_unchanged": True,
        "counts": counters,
        "record_ids": ids,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit generated stored-body display without copying publisher text")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    args = parser.parse_args(argv)
    report = audit_generated_record_text(args.db, args.output, args.source)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
