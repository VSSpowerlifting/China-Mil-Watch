"""Fail-closed, offline identity triage for Vietnam MOD English Defence Relations URLs.

This does not fetch pages, establish publication facts or source-use permission,
collect full text, create a state branch, or admit research to the Sunday writer.
A source listing and a crawler-hosted snippet are NOT proof of article identity.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "vn-mod-en-manual-url-observations/1"
OUTPUT_SCHEMA = "vn-mod-en-offline-url-canary/1"
FAMILY = "mod-en-defence-relations"
PUBLISHER = "Vietnam Ministry of National Defence (official portal)"
WCM_PARENT = "wcm:path:/mod/sa-mod-en/sa-en-news/sa-en-news-rela/"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
STAMP = re.compile(r"([0-2]\d:[0-5]\d) \| (\d{2}/\d{2}/\d{4})\Z")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_ITEMS = 20


class MODCanaryRefused(ValueError):
    pass


def require(value, message):
    if not value:
        raise MODCanaryRefused(message)


def article_identity(url):
    """Require an actual /en/detail WCM content key, not a WebSphere widget URL.

    A content key is only an *unverified identity candidate*. In particular we
    never derive identities from /!ut/p/ navigation state or remove unknown
    query parameters and assume they are irrelevant to article identity.
    """
    require(isinstance(url, str) and len(url) <= 1800 and
            not CONTROL.search(url) and not url.endswith("#"),
            "untrusted or malformed MOD URL")
    try:
        p = urlsplit(url)
    except ValueError as exc:
        raise MODCanaryRefused("malformed MOD URL") from exc
    require(p.scheme == "https" and p.netloc == "mod.gov.vn" and
            p.path == "/en/detail" and not p.fragment,
            "not the exact canonical MOD English article surface")
    try:
        query = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise MODCanaryRefused("invalid WCM identity query") from exc
    require(len(query) == 2 and set(k for k, _ in query) == {"current", "urile"}
            and len({k for k, _ in query}) == 2,
            "WCM article identity has missing, duplicate or unproven parameters")
    params = dict(query)
    require(params["current"] == "true" and
            params["urile"].startswith(WCM_PARENT),
            "not an allowed Defence Relations WCM article identity")
    slug = params["urile"][len(WCM_PARENT):]
    require(len(slug) <= 160 and bool(SLUG.fullmatch(slug)),
            "article path is not a stable content slug")
    uri = WCM_PARENT + slug
    canonical = ("https://mod.gov.vn/en/detail?current=true&urile=" +
                 quote(uri, safe=""))
    return {
        "source_family": FAMILY,
        "source_identity": "mod-en-defrel:" + slug,
        "canonical_url_candidate": canonical,
        "wcm_content_path": uri,
        "identity_observation_only": True,
    }


def visible_portal_stamp(value):
    """Interpret a *supplied* portal label, without claiming it was observed."""
    require(isinstance(value, str), "visible portal timestamp required")
    match = STAMP.fullmatch(value)
    require(match is not None, "expected HH:MM | MM/DD/YYYY portal label")
    try:
        parsed = datetime.strptime(match.group(2), "%m/%d/%Y")
    except ValueError as exc:
        raise MODCanaryRefused("invalid portal calendar date") from exc
    hour, minute = map(int, match.group(1).split(":"))
    require(hour <= 23, "invalid portal hour")
    return parsed.date().isoformat(), "%02d:%02d" % (hour, minute)


def review_observations(payload):
    """Produce an explicitly unapproved identity roster from operator notes."""
    require(isinstance(payload, dict) and set(payload) == {"schema", "items"}
            and payload["schema"] == SCHEMA and
            isinstance(payload["items"], list) and
            0 < len(payload["items"]) <= MAX_ITEMS,
            "invalid or unbounded manual MOD observation input")
    rows, seen = [], set()
    for item in payload["items"]:
        require(isinstance(item, dict) and set(item) ==
                {"article_url", "printed_title", "printed_timestamp"},
                "manual item must contain only the bounded metadata fields")
        ident = article_identity(item["article_url"])
        title = item["printed_title"]
        require(isinstance(title, str) and 12 <= len(title.strip()) <= 300
                and not CONTROL.search(title), "invalid operator-supplied headline")
        date, time = visible_portal_stamp(item["printed_timestamp"])
        require(ident["source_identity"] not in seen,
                "duplicate article identity, including percent-encoded URL aliases")
        seen.add(ident["source_identity"])
        rows.append({
            **ident,
            "operator_supplied_title": title.strip(),
            "operator_supplied_date": date,
            "operator_supplied_time": time,
            "publisher_label": PUBLISHER,
            "verification_state": "url-shape-only-not-publisher-fetched",
            "first_party_page_verified": False,
            "redirect_chain_verified": False,
            "robots_and_terms_reviewed": False,
            "article_body_verified": False,
            "source_use_authorized": False,
            "source_content_sha256": None,
            "shadow_state_commit": None,
            "eligible_for_private_model": False,
            "eligible_for_publication": False,
            "eligible_for_production": False,
        })
    rows.sort(key=lambda x: (x["operator_supplied_date"], x["source_identity"]),
              reverse=True)
    return {
        "schema": OUTPUT_SCHEMA,
        "source_family": FAMILY,
        "status": "offline-metadata-only-unverified",
        "publisher_silence_verified": False,
        "current_week_coverage_verified": False,
        "automated_collection_enabled": False,
        "private_model_contribution_authorized": False,
        "items": rows,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    require(args.input.is_file() and not args.input.is_symlink(),
            "missing or symlinked manual input")
    require(args.input.stat().st_size <= 16000, "manual input too large")
    dest = args.out.resolve()
    require(not args.out.exists() and not args.out.is_symlink() and
            args.out.parent.is_dir() and not args.out.parent.is_symlink()
            and dest != ROOT and ROOT not in dest.parents,
            "output must be new and outside the production checkout")
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MODCanaryRefused("invalid manual input JSON") from exc
    result = review_observations(payload)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"source_family": FAMILY, "url_only_candidates": len(result["items"]),
                      "publisher_verified": False, "source_use_authorized": False,
                      "collection_enabled": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
