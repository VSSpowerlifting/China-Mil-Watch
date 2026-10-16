"""Independent, read-only deployed Korean original HTML readback.

Proves registered source UTF-8 SHA -> deterministic rendered body inside the
shared site shell -> main output -> gh-pages blob -> optional real HTTPS served
bytes. Never uploads source bodies, makes publication changes, or treats branch
parity as HTTP proof.
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

from core.korea_published_originals import (
    read_release_index, render_original_body, PublishedKoreaHold,
)

SCHEMA = "ipr-korea-public-original-https-readback/1"
CANONICAL_HOST = "indopacificrecord.org"
MAX_HTML = 400_000
ROUTE = re.compile(r"korea-originals/[0-9]{9}[.]html\Z")


class ReadbackHold(ValueError):
    """Safe fixed reason codes; never include source, page bodies or URLs."""


def need(ok, reason):
    if not ok:
        raise ReadbackHold(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _html(path):
    need(path.is_file() and not path.is_symlink()
         and 1 <= path.stat().st_size <= MAX_HTML,
         "original_deployed_html_missing_or_oversize")
    return path.read_bytes()


def _routes(root):
    directory = root / "korea-originals"
    if not directory.exists():
        return set()
    need(directory.is_dir() and not directory.is_symlink(),
         "original_deployed_routes_unexpected")
    items = set()
    for p in directory.iterdir():
        need(p.is_file() and not p.is_symlink()
             and ROUTE.fullmatch("korea-originals/" + p.name) is not None,
             "original_deployed_routes_unexpected")
        items.add("korea-originals/" + p.name)
    return items


def validate_branch_parity(main_root, pages_root):
    main_root, pages_root = Path(main_root), Path(pages_root)
    index = main_root / "research/korea_published_original_texts.json"
    source_dir = main_root / "research/korea_published_original_texts"
    rows = read_release_index(index, source_dir)
    need(len(rows) > 0, "original_release_registry_still_empty")
    wanted = {row["route"] for row in rows}
    need(_routes(main_root / "output") == wanted,
         "main_published_original_route_inventory_drift")
    need(_routes(pages_root) == wanted,
         "pages_published_original_route_inventory_drift")

    main_desk = _html(main_root / "output/korea.html")
    pages_desk = _html(pages_root / "korea.html")
    need(main_desk == pages_desk, "korea_desk_main_pages_bytes_differ")
    main_desk_text = main_desk.decode("utf-8", "strict")
    need(main_desk_text.count("data-korea-original-text=") == len(rows),
         "korea_desk_original_links_count_drift")
    need((pages_root / "CNAME").read_text(encoding="utf-8").strip()
         == CANONICAL_HOST, "korea_pages_canonical_domain_changed")
    page_bytes = {}
    for row in rows:
        route = row["route"]
        # The page is the shared IPR shell around this body. The shell moves
        # with the site (masthead, freshness line), so it is the escaped body
        # that must be found intact; main and Pages must still match exactly.
        rendered = render_original_body(row).encode("utf-8")
        main_file = _html(main_root / "output" / route)
        pages_file = _html(pages_root / route)
        need(main_file == pages_file,
             "korea_original_main_pages_bytes_differ")
        need(main_file.count(rendered) == 1,
             "korea_original_rendered_bytes_differ_from_published")
        need(row["official_url"] in main_desk_text and route in main_desk_text,
             "korea_original_desk_link_missing")
        need(row["original_text_sha256"] in main_file.decode("utf-8", "strict"),
             "korea_original_page_source_sha_missing")
        page_bytes[route] = main_file
    return rows, {"korea.html": main_desk, **page_bytes}


def _remote_once(url, expected, session):
    u = urlsplit(url)
    need(u.scheme == "https" and u.hostname == CANONICAL_HOST
         and u.path.startswith("/") and u.username is None
         and u.password is None and u.port is None,
         "korea_original_public_http_origin_changed")
    try:
        result = session.get(url, timeout=(8, 15), allow_redirects=False,
                             headers={"Cache-Control": "no-cache",
                                      "User-Agent": "IndoPacificRecord-Readback/1.0"})
    except requests.RequestException:
        return "korea_original_public_https_unreachable"
    if result.status_code != 200 or result.url != url or result.history:
        return "korea_original_public_https_status_or_origin_mismatch"
    content_type = result.headers.get("Content-Type", "").lower().split(";", 1)[0]
    if content_type not in ("text/html", "application/xhtml+xml"):
        return "korea_original_public_https_content_type_mismatch"
    data = result.content
    if len(data) != len(expected) or sha(data) != sha(expected):
        return "korea_original_public_https_content_sha_mismatch"
    return None


def verify_readback(main_root, pages_root, *, require_https=False,
                    session=None, attempts=1, sleep=None):
    rows, verified = validate_branch_parity(main_root, pages_root)
    result = {
        "schema": SCHEMA,
        "status": "GIT_BRANCH_READBACK_VERIFIED",
        "registered_originals": len(rows),
        "korea_html_paths_verified": len(verified),
        "main_pages_exact_html_parity": True,
        "rendered_body_in_pages_exact": True,
        "public_https_verified": False,
        "db_changed": False,
        "pages_written": False,
    }
    if require_https:
        need(type(attempts) is int and 1 <= attempts <= 12,
             "korea_http_retry_budget_invalid")
        sess = session if session is not None else requests.Session()
        wait = sleep if sleep is not None else time.sleep
        paths = sorted(verified)
        for attempt in range(attempts):
            holds = []
            for path in paths:
                url = "https://" + CANONICAL_HOST + "/" + path
                reason = _remote_once(url, verified[path], sess)
                if reason is not None:
                    holds.append(reason)
            if not holds:
                result["status"] = "PUBLIC_HTTPS_EXACT_BYTES_VERIFIED"
                result["public_https_verified"] = True
                break
            if attempt + 1 == attempts:
                raise ReadbackHold(holds[0])
            wait(15)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--main-checkout", required=True)
    p.add_argument("--pages-checkout", required=True)
    p.add_argument("--require-https-readback", action="store_true")
    p.add_argument("--attempts", type=int, default=6)
    args = p.parse_args(argv)
    try:
        out = verify_readback(args.main_checkout, args.pages_checkout,
                              require_https=args.require_https_readback,
                              attempts=args.attempts)
    except (ReadbackHold, PublishedKoreaHold, UnicodeError,
            ValueError, OSError):
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD",
            "public_https_verified": False, "db_changed": False,
            "pages_written": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
