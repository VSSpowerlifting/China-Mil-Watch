"""Independent read-only byte-for-byte review-to-HTTPS Korea English readback.

Owner review and workflow dispatch are the ONLY publication authority. This
module never promotes, renders into, commits or repairs public output. It proves
that every already-registered reviewed packet and pinned Korean source renders
to exactly the same bytes in main, gh-pages, and the actual HTTPS response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from core.korea_english_publication import (
    KoreaEnglishHold, public_registry, render_analysis, render_translation,
)

SCHEMA = "ipr-korea-reviewed-english-https-readback/1"
HOST = "indopacificrecord.org"
MAX_HTML = 400_000
ROUTE = re.compile(r"(?:korea-translations|korea-analysis)/[0-9]{9}\.html\Z")
FOLDERS = ("korea-translations", "korea-analysis")


class EnglishReadbackHold(ValueError):
    """Private, fixed reason codes only. Do not expose editorial page bodies."""


def need(condition, code):
    if not condition:
        raise EnglishReadbackHold(code)


def _html(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink()
         and 1 <= p.stat().st_size <= MAX_HTML,
         "korea_english_readback_html_missing_or_oversize")
    return p.read_bytes()


def _inventory(root):
    root = Path(root)
    found = set()
    for folder in FOLDERS:
        directory = root / folder
        if not directory.exists():
            continue
        need(directory.is_dir() and not directory.is_symlink(),
             "korea_english_readback_route_inventory_invalid")
        for p in directory.iterdir():
            path = folder + "/" + p.name
            need(p.is_file() and not p.is_symlink()
                 and ROUTE.fullmatch(path) is not None,
                 "korea_english_readback_route_inventory_invalid")
            found.add(path)
    return found


def validate_branch_parity(main_root, pages_root):
    main, pages = Path(main_root), Path(pages_root)
    records = public_registry(
        main / "research/korea_english_publications.json",
        main / "research/korea_english_reviewed",
        source_index=main / "research/korea_published_original_texts.json",
        source_dir=main / "research/korea_published_original_texts",
    )
    need(bool(records), "korea_english_no_reviewed_releases_yet")
    expected = set()
    for row, review, source in records:
        number = source["source_identity"].split(":")[1]
        expected.add("korea-translations/" + number + ".html")
        expected.add("korea-analysis/" + number + ".html")
    need(_inventory(main / "output") == expected,
         "korea_english_main_route_inventory_drift")
    need(_inventory(pages) == expected,
         "korea_english_pages_route_inventory_drift")

    cname = pages / "CNAME"
    need(cname.is_file() and not cname.is_symlink()
         and cname.read_text(encoding="utf-8").strip() == HOST,
         "korea_english_pages_canonical_domain_changed")

    desk = _html(main / "output/korea.html")
    need(desk == _html(pages / "korea.html"),
         "korea_english_desk_main_pages_bytes_differ")
    desk_text = desk.decode("utf-8", "strict")
    need(desk_text.count("data-korea-english-reviewed=") == len(records),
         "korea_english_desk_reviewed_count_drift")

    checked = {"korea.html": desk}
    for row, review, source in records:
        number = source["source_identity"].split(":")[1]
        need(row["review_sha256"] and
             row["source_sha256"] == source["original_text_sha256"],
             "korea_english_source_or_review_digest_mismatch")
        need("korea-translations/" + number + ".html" in desk_text
             and "korea-analysis/" + number + ".html" in desk_text
             and "korea-originals/" + number + ".html" in desk_text,
             "korea_english_desk_approved_routes_missing")
        for folder, renderer in (
            ("korea-translations", render_translation),
            ("korea-analysis", render_analysis),
        ):
            route = folder + "/" + number + ".html"
            generated = renderer(row, review, source).encode("utf-8")
            on_main = _html(main / "output" / route)
            on_pages = _html(pages / route)
            need(on_main == on_pages,
                 "korea_english_main_pages_bytes_differ")
            need(on_main == generated,
                 "korea_english_rendered_bytes_differ_from_published")
            need(source["original_text_sha256"].encode("ascii") in on_main
                 and source["official_url"].encode("utf-8") in on_main,
                 "korea_english_published_source_provenance_missing")
            checked[route] = on_main
    return records, checked


def _remote_once(url, expected, session):
    parsed = urlsplit(url)
    need(parsed.scheme == "https" and parsed.hostname == HOST
         and parsed.username is None and parsed.password is None
         and parsed.port is None and not parsed.query and not parsed.fragment
         and parsed.path.startswith("/"),
         "korea_english_public_http_origin_changed")
    try:
        response = session.get(
            url, timeout=(8, 15), allow_redirects=False,
            headers={"Cache-Control": "no-cache",
                     "User-Agent": "IndoPacificRecord-EnglishReadback/1.0"},
        )
    except requests.RequestException:
        return "korea_english_public_https_unreachable"
    if response.status_code != 200 or response.url != url or response.history:
        return "korea_english_public_https_status_or_origin_mismatch"
    kind = response.headers.get("Content-Type", "").lower().split(";", 1)[0]
    if kind not in ("text/html", "application/xhtml+xml"):
        return "korea_english_public_https_content_type_mismatch"
    raw = response.content
    if len(raw) != len(expected) or hashlib.sha256(raw).digest() != hashlib.sha256(expected).digest():
        return "korea_english_public_https_content_sha_mismatch"
    return None


def verify_readback(main_root, pages_root, *, require_https=False,
                    session=None, attempts=1, sleep=None):
    records, paths = validate_branch_parity(main_root, pages_root)
    result = {
        "schema": SCHEMA, "status": "GIT_BRANCH_READBACK_VERIFIED",
        "approved_source_pairs": len(records), "html_paths_verified": len(paths),
        "review_and_source_authenticated": True,
        "main_pages_exact_html_parity": True,
        "rendered_to_pages_exact_html_parity": True,
        "public_https_verified": False, "db_changed": False,
        "pages_written": False,
    }
    if require_https:
        need(type(attempts) is int and 1 <= attempts <= 12,
             "korea_english_http_retry_budget_invalid")
        sess = session if session is not None else requests.Session()
        wait = sleep if sleep is not None else time.sleep
        for attempt in range(attempts):
            holds = [
                reason for path in sorted(paths)
                if (reason := _remote_once("https://" + HOST + "/" + path,
                                           paths[path], sess)) is not None
            ]
            if not holds:
                result["status"] = "PUBLIC_HTTPS_EXACT_BYTES_VERIFIED"
                result["public_https_verified"] = True
                break
            if attempt + 1 == attempts:
                raise EnglishReadbackHold(holds[0])
            wait(15)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--main-checkout", required=True)
    p.add_argument("--pages-checkout", required=True)
    p.add_argument("--require-https-readback", action="store_true")
    p.add_argument("--attempts", type=int, default=8)
    args = p.parse_args(argv)
    try:
        out = verify_readback(
            args.main_checkout, args.pages_checkout,
            require_https=args.require_https_readback, attempts=args.attempts,
        )
    except (EnglishReadbackHold, KoreaEnglishHold, ValueError,
            UnicodeError, OSError):
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD",
            "public_https_verified": False,
            "db_changed": False, "pages_written": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
