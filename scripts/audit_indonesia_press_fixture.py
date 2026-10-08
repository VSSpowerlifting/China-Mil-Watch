"""Read-only, offline fidelity gate for future Kemhan Siaran Pers byte fixtures.

This tool performs NO network requests, makes NO policy/access determination,
and NEVER approves archival admission. Raw fixture identities must be sourced
and independently inspected outside this consistency-only validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scraper.sources.id_kemhan_press import LISTING, parse_press_article, parse_press_listing

MAX_SOURCE_BYTES = 2_000_000


def read_input(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("fixture path must be a regular local file")
    if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("fixture source size outside safe bounds")
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES or len(raw) != path.stat().st_size:
        raise ValueError("fixture bytes or size changed during audit")
    return raw, raw.decode("utf-8", "strict")


def audit(listing_file, article_file, *, source_url, page_number=1):
    """Check local bytes and source identity, not their unproven authenticity."""
    page_raw, page_html = read_input(listing_file)
    article_raw, article_html = read_input(article_file)
    page_url = LISTING if page_number == 1 else LISTING + "/page/" + str(page_number)
    page = parse_press_listing(page_html, url=page_url, number=page_number)
    rows = [r for r in page.records if r.url == source_url]
    if len(rows) != 1:
        raise ValueError("requested press article must appear exactly once in supplied category listing")
    row = rows[0]
    body = parse_press_article(article_html, url=row.url,
                               listed_title=row.title, listed_date=row.published_date)
    return {
        "protocol": "ipr_indonesia_press_offline_audit_v1",
        "finding": "locally_consistent_not_authenticity_verified",
        "source_family": "Kemhan Siaran Pers",
        "listing_url": page_url,
        "article_url": body.url,
        "published_date": body.published_date,
        "title": body.title,
        "language": body.language,
        "publication_kind": body.publication_kind,
        "listing_capture_sha256": hashlib.sha256(page_raw).hexdigest(),
        "article_capture_sha256": hashlib.sha256(article_raw).hexdigest(),
        "extracted_body_sha256": hashlib.sha256(body.original_text.encode("utf-8")).hexdigest(),
        "extracted_characters": len(body.original_text),
        "listed_records": len(page.records),
        "later_page_url": page.next_url,
        "native_source_policy_verified": False,
        "real_source_capture_authenticated": False,
        "human_original_language_review": False,
        "source_admission_approved": False,
        "production_writes": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listing-file", required=True, type=Path)
    parser.add_argument("--article-file", required=True, type=Path)
    parser.add_argument("--article-url", required=True)
    parser.add_argument("--page-number", type=int, default=1)
    args = parser.parse_args(argv)
    result = audit(args.listing_file, args.article_file,
                   source_url=args.article_url, page_number=args.page_number)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
