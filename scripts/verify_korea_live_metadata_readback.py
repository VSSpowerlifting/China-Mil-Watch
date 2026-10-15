"""Read-only cross-branch Korea official-link release verification.

Compares the tracked production SQLite against main:output/korea.html and
gh-pages:korea.html. This proves consistency, NOT collection fidelity,
rights, seven-day reliability, or arrival of a new source in this run.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import quote

PREFIX = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
IDENT = re.compile(r"korea-policy:[0-9]{9}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class ReadbackHold(ValueError):
    pass


def check(ok, reason):
    if not ok:
        raise ReadbackHold(reason)


class KoreaLinks(HTMLParser):
    """Examine rendered source-reference li elements, rejecting unsafe auto rows."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fixed = set()
        self.additional = set()
        self.auto = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tags = ("data-korea-public-link", "data-korea-additional-link",
                "data-korea-auto-official-link")
        populated = [k for k in tags if k in attrs]
        if populated:
            check(tag == "li" and len(populated) == 1,
                  "ambiguous_korea_reference_markup")
            check(self.current is None, "nested_official_reference")
            ident = attrs[populated[0]]
            check(isinstance(ident, str) and IDENT.fullmatch(ident),
                  "invalid_rendered_source_identity")
            if populated[0] == tags[0]:
                check(ident not in self.fixed, "duplicate_frozen_reference")
                self.fixed.add(ident)
            elif populated[0] == tags[1]:
                check(ident not in self.additional, "duplicate_additional_reference")
                self.additional.add(ident)
            else:
                check(ident not in self.auto, "duplicate_automatic_reference")
                self.auto[ident] = {"hrefs": [], "dates": [], "text": []}
                self.current = ident
            return
        if self.current is not None:
            if tag == "li":
                raise ReadbackHold("nested_automatic_link_markup")
            if tag in {"img", "picture", "source", "video", "audio", "iframe",
                       "script", "object", "embed", "form", "button"}:
                raise ReadbackHold("unauthorized_media_or_script_inside_link")
            if tag == "a":
                self.auto[self.current]["hrefs"].append(attrs.get("href"))
            elif tag == "time":
                self.auto[self.current]["dates"].append(attrs.get("datetime"))

    def handle_endtag(self, tag):
        if tag == "li" and self.current is not None:
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.auto[self.current]["text"].append(data)


def _read_rows(path):
    check(path.is_file() and not path.is_symlink(), "database_missing_or_symlink")
    check(not Path(str(path) + "-wal").exists()
          and not Path(str(path) + "-shm").exists(),
          "database_has_live_sidecars")
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro&immutable=1"
    try:
        with sqlite3.connect(uri, uri=True) as db:
            check(db.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                  "sqlite_integrity_failed")
            check(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                             "AND name='korea_official_source_records'").fetchone() is not None,
                  "korea_metadata_schema_not_in_production")
            result = db.execute(
                "SELECT source_identity,canonical_official_url,publisher_posted_date,"
                "official_issuer,official_republisher,public_scope,"
                "candidate_version_sha256,original_title_sha256 "
                "FROM korea_official_source_records"
            ).fetchall()
    except sqlite3.Error as exc:
        raise ReadbackHold("cannot_read_committed_metadata_database") from exc
    approved = {}
    for ident, url, day, issuer, republisher, scope, candidate_hash, title_hash in result:
        check(isinstance(ident, str) and IDENT.fullmatch(ident)
              and url == PREFIX + ident[13:]
              and issuer == "kr_mnd" and republisher == "kr_policy_briefing"
              and scope in {"held", "official_link_only"}
              and isinstance(candidate_hash, str) and HEX.fullmatch(candidate_hash)
              and isinstance(title_hash, str) and HEX.fullmatch(title_hash),
              "unapproved_metadata_row_shape")
        check(isinstance(day, str), "invalid_publisher_date")
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise ReadbackHold("invalid_publisher_date") from exc
        check(parsed.isoformat() == day, "noncanonical_publisher_date")
        check(ident != "korea-policy:156785161" or scope == "held",
              "chronology_exception_released")
        if scope == "official_link_only":
            check(ident not in approved, "duplicate_production_official_link")
            approved[ident] = {"url": url, "date": day}
    return approved


def verify(database, main_html, pages_html):
    database = Path(database)
    main_html = Path(main_html)
    pages_html = Path(pages_html)
    approved = _read_rows(database)
    check(main_html.is_file() and pages_html.is_file()
          and not main_html.is_symlink() and not pages_html.is_symlink(),
          "committed_korea_page_missing_or_symlink")
    main_bytes = main_html.read_bytes()
    pages_bytes = pages_html.read_bytes()
    check(main_bytes == pages_bytes, "main_and_pages_korea_html_mismatch")
    try:
        parser = KoreaLinks()
        parser.feed(main_bytes.decode("utf-8"))
        parser.close()
    except UnicodeDecodeError as exc:
        raise ReadbackHold("invalid_public_korea_page_encoding") from exc
    check(len(parser.fixed) == 5 and len(parser.additional) == 9
          and not (parser.fixed & parser.additional),
          "frozen_korea_reference_count_or_identity_changed")
    known = parser.fixed | parser.additional
    check(set(parser.auto) == set(approved) - known,
          "published_official_links_do_not_match_live_database")
    check(not (set(parser.auto) & known), "duplicated_frozen_link_in_auto_section")
    for ident, entry in parser.auto.items():
        check(entry["hrefs"] == [approved[ident]["url"]]
              and entry["dates"] == [approved[ident]["date"]],
              "public_metadata_href_or_date_mismatch")
        visible = " ".join(" ".join(entry["text"]).split())
        check(visible.startswith("MND official press release " + ident[13:])
              and "Issuer: Republic of Korea Ministry of National Defense" in visible
              and "Republication: Republic of Korea Policy Briefing" in visible
              and "Official government outbound link only" in visible,
              "unauthorized_or_missing_official_link_label")
    return {"status": "VERIFIED_PUBLICATION_READBACK",
            "main_database_sha256": sha256(database.read_bytes()).hexdigest(),
            "main_and_pages_korea_html_sha256": sha256(main_bytes).hexdigest(),
            "live_database_approved_records": len(approved),
            "published_additional_live_links": len(parser.auto),
            "already_in_frozen_directory": len(set(approved) & known),
            "new_source_arrival_proven": False,
            "original_source_fidelity_proven_by_readback": False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", required=True)
    p.add_argument("--main-html", required=True)
    p.add_argument("--pages-html", required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(verify(args.database, args.main_html, args.pages_html),
                         sort_keys=True))
        return 0
    except (ReadbackHold, OSError) as exc:
        reason = str(exc) if isinstance(exc, ReadbackHold) else "readback_io_failure"
        print(json.dumps({"status": "HOLD", "reason": reason}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
