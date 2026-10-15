"""Independent, read-only IPR regional SQLite → HTML → Pages parity gate.

The gate never collects official sites, writes source DB/output, or makes any
publication permission decision. It proves exactly which metadata-only links
the approved regional index contains and whether the rendered page reflects
those rows, without mistaking static publisher directories or shadow records
for admitted records. A deploy job may optionally check its isolated gh-pages
checkout byte-for-byte against committed generated HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from core.regional_official_link_render import DESK_TO_FAMILY, load_admitted_links

ROUTES = {"philippines": "philippines.html", "indonesia": "indonesia.html"}
SCHEMA = "ipr-regional-source-link-readback/1"


class ReadbackHold(ValueError):
    """Fixed error code; does not include publisher-controlled HTML text."""


def need(ok, reason):
    if not ok:
        raise ReadbackHold(reason)


class MetadataOnlySourceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section_depth = 0
        self.sections = 0
        self.active = None
        self.link_open = False
        self.rows = []

    @staticmethod
    def attrs(pairs):
        return dict(pairs)

    def handle_starttag(self, tag, attrs):
        a = self.attrs(attrs)
        if tag == "section" and self.section_depth == 0:
            if a.get("data-source-scope") == "official-link-only":
                need("regional-official-live-links" in a.get("class", "").split(),
                     "unexpected_official_link_section_identity")
                self.sections += 1
                need(self.sections == 1, "duplicate_regional_source_section")
                self.section_depth = 1
                return
        elif tag == "section" and self.section_depth:
            self.section_depth += 1
            return
        if tag == "li" and "data-regional-official-source-id" in a:
            need(self.section_depth > 0, "source_index_row_outside_section")
        if not self.section_depth:
            return
        if tag == "li":
            need(self.active is None, "nested_official_source_li")
            need("data-regional-official-source-id" in a,
                 "unidentified_regional_source_row")
            self.active = {"source_identity": a[
                "data-regional-official-source-id"], "url": None,
                           "day": None, "label": "", "links": 0, "times": 0}
        elif self.active is not None and tag == "a":
            self.active["links"] += 1
            need(self.active["links"] == 1, "more_than_one_official_source_url")
            need({"noopener", "noreferrer"}.issubset(
                     set((a.get("rel") or "").split())),
                 "official_external_link_rel_missing")
            self.active["url"] = a.get("href")
            self.link_open = True
        elif self.active is not None and tag == "time":
            self.active["times"] += 1
            need(self.active["times"] == 1, "more_than_one_official_source_date")
            self.active["day"] = a.get("datetime")

    def handle_data(self, data):
        if self.active is not None and self.link_open:
            self.active["label"] += data

    def handle_endtag(self, tag):
        if not self.section_depth:
            return
        if tag == "a":
            self.link_open = False
        elif tag == "li":
            need(self.active is not None, "missing_official_source_identity")
            need(self.active["links"] == 1 and self.active["times"] == 1,
                 "incomplete_official_source_row")
            self.rows.append(self.active)
            self.active = None
        elif tag == "section":
            need(self.active is None, "unclosed_official_source_row")
            self.section_depth -= 1

    def close(self):
        super().close()
        need(self.active is None and self.section_depth == 0,
             "unclosed_regional_source_html")


def validate_page(actual_html, expected):
    parser = MetadataOnlySourceParser()
    parser.feed(actual_html)
    parser.close()
    need((parser.sections == 1) == bool(expected),
         "regional_source_section_presence_disagrees_with_db")
    need(len(parser.rows) == len(expected),
         "rendered_official_source_count_disagrees_with_db")
    expected_by_id = {r["source_identity"]: r for r in expected}
    need(len(expected_by_id) == len(expected), "duplicate_source_id_in_db")
    seen = set()
    for row in parser.rows:
        sid = row["source_identity"]
        need(sid not in seen and sid in expected_by_id,
             "html_contains_unadmitted_or_duplicate_source_id")
        seen.add(sid)
        registered = expected_by_id[sid]
        need(row["url"] == registered["canonical_official_url"] and
             row["day"] == registered["publisher_posted_date"] and
             row["label"].strip() == registered["label"],
             "html_link_date_or_neutral_label_differs_from_db")
    need(seen == set(expected_by_id),
         "admitted_source_missing_from_site")
    return len(seen)


def verify(db_path, site_dir, *, pages_dir=None, require_records=False):
    site_dir = Path(site_dir)
    need(site_dir.is_dir() and not site_dir.is_symlink(),
         "committed_site_directory_missing")
    pages_dir = Path(pages_dir) if pages_dir is not None else None
    if pages_dir is not None:
        need(pages_dir.is_dir() and not pages_dir.is_symlink(),
             "deployed_pages_checkout_missing")
    result = {
        "schema": SCHEMA,
        "metadata_only": True,
        "source_database_changed": False,
        "rendered_html_changed": False,
        "actual_pages_deployed_by_this_check": False,
        "site_bytes_match_deployed_checkout": pages_dir is not None,
        "source_families": {},
    }
    for desk, route in ROUTES.items():
        path = site_dir / route
        need(path.is_file() and not path.is_symlink(),
             "committed_regional_desk_page_missing")
        expected = load_admitted_links(db_path, desk)
        try:
            data = path.read_bytes()
            html = data.decode("utf-8")
        except (OSError, UnicodeError):
            raise ReadbackHold("committed_page_unavailable_or_non_utf8") from None
        count = validate_page(html, expected)
        if require_records:
            need(count > 0, "claimed_live_desk_has_no_admitted_source_links")
        if pages_dir is not None:
            deployed = pages_dir / route
            need(deployed.is_file() and not deployed.is_symlink()
                 and deployed.read_bytes() == data,
                 "deployed_pages_route_differs_from_committed_site")
        result["source_families"][DESK_TO_FAMILY[desk]] = {
            "desk": desk,
            "page": route,
            "admitted_official_link_count": count,
            "page_sha256": hashlib.sha256(data).hexdigest(),
            "released_source_original_text": False,
        }
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--site-dir", required=True, type=Path)
    p.add_argument("--deployed-dir", type=Path)
    p.add_argument("--require-records", action="store_true",
                   help="Refuse to call either desk live without an admitted row")
    args = p.parse_args(argv)
    try:
        receipt = verify(args.db, args.site_dir, pages_dir=args.deployed_dir,
                         require_records=args.require_records)
    except (ReadbackHold, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, ReadbackHold)
                  else "regional_source_index_readback_failed")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "site_deployed": False}), flush=True)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
