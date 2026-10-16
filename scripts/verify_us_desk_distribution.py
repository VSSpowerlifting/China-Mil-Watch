"""Read-only U.S. Desk delivery preflight independent of BIS source qualification.

Check the same rendered Git bytes exist on main, gh-pages and fresh HTTPS,
with the already-live USCC, Treasury and static PACOM references intact.
A green preflight is delivery evidence, NOT a BIS collection or release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup


class DistributionHold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise DistributionHold(reason)


def bounded(path):
    p = Path(path)
    require(p.is_file() and not p.is_symlink()
            and 1024 <= p.stat().st_size <= 1_000_000, "missing_or_unbounded_html")
    data = p.read_bytes()
    require(data.startswith(b"<!DOCTYPE html") or data.startswith(b"<!doctype html"),
            "unexpected_html")
    return data


def inspect(raw):
    try:
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    except UnicodeError:
        raise DistributionHold("html_not_utf8") from None
    counts = {
        "uscc": len(soup.select("li[data-uscc-official-link] a[href]")),
        "treasury": len(soup.select("li[data-us-treasury-official-link] a[href]")),
        "pacom": len(soup.select("li[data-us-pacom-link] a[href]")),
        "bis": len(soup.select("li[data-us-bis-official-link] a[href]")),
    }
    require(counts["uscc"] >= 10 and counts["treasury"] >= 10
            and counts["pacom"] == 9, "existing_us_official_links_missing")
    require(soup.select_one("h1") is not None, "us_desk_page_unrecognized")
    for kind in ("uscc", "treasury", "pacom", "bis"):
        selector = {
            "uscc": "li[data-uscc-official-link] a",
            "treasury": "li[data-us-treasury-official-link] a",
            "pacom": "li[data-us-pacom-link] a",
            "bis": "li[data-us-bis-official-link] a",
        }[kind]
        for a in soup.select(selector):
            require(a["href"].startswith("https://") and
                    a.get("target") == "_blank" and
                    "noopener" in a.get("rel", []),
                    "unsafe_or_non_official_outbound_link")
    return counts


def verify(main, pages, http):
    main_data, pages_data, http_data = (bounded(path) for path in (main, pages, http))
    require(main_data == pages_data, "main_and_pages_git_differ")
    require(pages_data == http_data, "public_domain_out_of_sync_with_pages_git")
    counts = inspect(http_data)
    return {
        "status": "PASS_US_DESK_PUBLIC_DELIVERY_PREFLIGHT",
        "sha256": hashlib.sha256(http_data).hexdigest(),
        "official_links": counts,
        "bis_schedule_attested": False,
        "production_mutated": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--main-html", required=True)
    ap.add_argument("--pages-html", required=True)
    ap.add_argument("--public-html", required=True)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(verify(args.main_html, args.pages_html, args.public_html),
                         sort_keys=True))
    except (DistributionHold, OSError) as exc:
        print(json.dumps({"status": "HOLD_US_DESK_PUBLIC_DELIVERY",
                          "reason": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
