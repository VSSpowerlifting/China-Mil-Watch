#!/usr/bin/env python3
"""Read-only Vietnam MPS pinned-state vs current publisher-page parity screen.

Strictly NOT editorial signoff or a text reuse-rights determination.
No article prose/HTML/capture bytes in stdout, output, or repo files.
A named human must still inspect the originals and authorize each record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st
from core.collection.contract import CandidateReference, CaptureResult
from core.collection.vietnam_identity import USER_AGENT
from core.collection.vietnam_sources import SOURCES, content_sha256
from scraper.sources.vn_ministries import VNMinistryAdapter
from scraper.sources.vn_shadow_http import (
    parse_robots, robots_rules, robots_crawl_delay, robots_allows,
    rules_file_problem, REQUEST_HEADERS,
)
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal
from scripts.shadow_collect_vietnam_ministry import load_source

SCHEMA = "vietnam-mps-live-parity-screen/1"
SOURCE_SLUG = "vn_mps_foreign_affairs_vi"
PINNED = "46f6a0e59e25b03868bf7ad600963d6921ee5124"
RECORD_IDS = frozenset(("mps-vi:1791199100", "mps-vi:1791199677",
                        "mps-vi:1790933646"))
MAX_GETS = 4
MAX_BYTES = 1_000_000
TIMEOUT = 25
ROBOTS = "https://bocongan.gov.vn/robots.txt"


class ScreeningRefused(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compare_record(record, version, archived_doc, live_doc):
    """Unambiguous comparisons. No human/rights approval is ever returned."""
    def metrics(doc):
        if doc is None:
            return None
        return {
            "title_sha256": sha(doc.title_original.encode("utf-8")),
            "body_sha256": sha(doc.text_original.encode("utf-8")),
            "body_characters": len(doc.text_original),
            "published_date": doc.published_date,
            "extracted_content_sha256": doc.extra.get("content_sha256"),
            "source_byline_meta_sha256": (sha(doc.extra["byline"].encode("utf-8"))
                                          if doc.extra.get("byline") else None),
        }
    archived = metrics(archived_doc)
    live = metrics(live_doc)
    result = {
        "source_identity": record["source_identity"],
        "source_url": record["canonical_url"],
        "published_date_in_pinned_state": record["published_date"],
        "pinned_version_sha256": version["content_sha256"],
        "pinned_capture_sha256": version["first_capture_sha256"],
        "archived_capture_reparse_complete": archived is not None,
        "archive_title_matches_stored": None,
        "archive_body_matches_stored": None,
        "archive_date_matches_stored": None,
        "archive_version_digest_matches_stored": None,
        "live_access_and_extraction": "not_run",
        "live_title_matches_pinned": None,
        "live_body_matches_pinned": None,
        "live_published_date_matches_pinned": None,
        "live_version_digest_matches_pinned": None,
        "archived_metrics": archived,
        "live_metrics": live,
        "human_integrity_review_complete": False,
        "reuse_rights_approved": False,
        "production_publication_authorized": False,
    }
    if archived is not None:
        result["archive_title_matches_stored"] = archived_doc.title_original == version["title_original"]
        result["archive_body_matches_stored"] = archived_doc.text_original == version["text_original"]
        result["archive_date_matches_stored"] = archived_doc.published_date == record["published_date"]
        result["archive_version_digest_matches_stored"] = archived["extracted_content_sha256"] == version["content_sha256"]
    if live is not None:
        result["live_access_and_extraction"] = "success"
        result["live_title_matches_pinned"] = live_doc.title_original == version["title_original"]
        result["live_body_matches_pinned"] = live_doc.text_original == version["text_original"]
        result["live_published_date_matches_pinned"] = live_doc.published_date == record["published_date"]
        result["live_version_digest_matches_pinned"] = live["extracted_content_sha256"] == version["content_sha256"]
    return result


def safe_fetch(session, url):
    """One exact-path GET, no redirects, cookies, errors with source text or retry."""
    p = urlsplit(url)
    if p.scheme != "https" or p.netloc != "bocongan.gov.vn" or p.query or p.fragment:
        raise ScreeningRefused("unexpected MPS host/path")
    response = None
    try:
        response = session.get(url, timeout=TIMEOUT, allow_redirects=False, stream=True)
        raw = bytearray()
        for block in response.iter_content(32768):
            raw.extend(block)
            if len(raw) > MAX_BYTES:
                raise ScreeningRefused("response exceeds byte cap")
        if (response.url != url or response.status_code != 200
                or response.headers.get("Location") or response.headers.get("Cf-Mitigated")
                or response.headers.get("Content-Encoding", "identity").lower() != "identity"):
            raise ScreeningRefused("non-200, redirect or challenge")
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in ("text/html", "text/plain"):
            raise ScreeningRefused("unexpected content type")
        body = bytes(raw)
        if re.search(rb"cf-chl|challenge-platform|just a moment|captcha", body[:4000], re.I):
            raise ScreeningRefused("publisher presented challenge")
        return {
            "url": url, "http_status": response.status_code,
            "payload_sha256": sha(body), "payload_bytes": len(body),
            "content_type": content_type,
        }, body
    finally:
        if response is not None:
            response.close()
        session.cookies.clear()


def extracted(adapter, url, html, date):
    capture = CaptureResult(
        CandidateReference(url, SOURCE_SLUG, SOURCES[SOURCE_SLUG].listing, date),
        st.OK, url, final_url=url, http_status=200, body=html.decode("utf-8", "strict"))
    result = adapter.extract(capture)
    if result.status != st.OK or len(result.documents) != 1:
        raise ScreeningRefused("source adapter could not extract one whole article")
    doc = result.documents[0]
    if doc.url != url or not doc.text_original.strip():
        raise ScreeningRefused("source adapter returned wrong or empty article")
    return doc


def screen(repo, commit, output, session=None):
    out = Path(output)
    if out.exists() or out.is_symlink() or out.resolve() == ROOT or ROOT in out.resolve().parents:
        raise ScreeningRefused("output must be new and outside checkout")
    if commit != PINNED:
        raise ScreeningRefused("only the separately verified pinned state is eligible")
    source_repo = formal.resolve_state_repo(repo)
    provenance = formal.verify_state_commit(source_repo, commit, SOURCES[SOURCE_SLUG].state_branch)
    with tempfile.TemporaryDirectory(prefix="vietnam-mps-parity-") as tmp:
        state = formal.export_state_tree(source_repo, commit, Path(tmp) / "state")
        evidence = ministry.review(state, SOURCE_SLUG)
        records = {r["source_identity"]: r for r in evidence["records"]}
        versions = {(v["source_identity"], v["content_sha256"]): v for v in evidence["versions"]}
        if set(records) != RECORD_IDS or len(records) != 3:
            raise ScreeningRefused("the pinned three-record inventory changed")
        adapter = VNMinistryAdapter(load_source(SOURCE_SLUG), max_requests=0)
        archived = {}
        for ident in sorted(RECORD_IDS):
            rec = records[ident]
            version = versions[(ident, rec["current_content_sha256"])]
            capture = (state / "captures" / (version["first_capture_sha256"] + ".bin"))
            payload = capture.read_bytes()
            if sha(payload) != version["first_capture_sha256"]:
                raise ScreeningRefused("archived capture has changed")
            try:
                parsed = extracted(adapter, rec["url"], payload, rec["published_date"])
                archived[ident] = compare_record(rec, version, parsed, None)
            except (ValueError, UnicodeError, ScreeningRefused):
                archived[ident] = compare_record(rec, version, None, None)
            if any(archived[ident][k] is False for k in (
                "archive_title_matches_stored", "archive_body_matches_stored",
                "archive_date_matches_stored", "archive_version_digest_matches_stored")):
                # Preserve measured mismatch, no publisher requests are
                # required for an already-failing historical candidate.
                pass
        http = session or requests.Session()
        http.trust_env = False
        http.headers.update(REQUEST_HEADERS)
        requests_made = 0
        report = {
            "schema": SCHEMA,
            "source_slug": SOURCE_SLUG,
            "pinned_state_commit": commit,
            "pinned_state_tree": provenance["state_tree"],
            "source_identity": USER_AGENT,
            "read_only_evidence_validator_passed": True,
            "request_budget": MAX_GETS,
            "request_count": 0,
            "raw_capture_bytes_retained": False,
            "publisher_html_retained": False,
            "publisher_article_text_retained": False,
            "human_approvals": 0,
            "reuse_rights_approvals": 0,
            "production_record_imports": 0,
            "records": [archived[ident] for ident in sorted(RECORD_IDS)],
        }
        meta = None
        robots = None
        try:
            meta, robots = safe_fetch(http, ROBOTS)
            requests_made = 1
            if rules_file_problem(robots) is not None:
                raise ScreeningRefused("robots policy is not readable")
            parsed_rules = parse_robots(robots.decode("utf-8", "strict"))
            rules = robots_rules(parsed_rules)
            delay = robots_crawl_delay(parsed_rules)
            if delay is None:
                delay = 2
            if delay > 90:
                raise ScreeningRefused("published crawl-delay exceeds bounded probe")
            report["robots"] = {"request_sha256": meta["payload_sha256"],
                                "tested_paths_allowed": True}
            for ident in sorted(RECORD_IDS):
                row = archived[ident]
                rec = records[ident]
                version = versions[(ident, rec["current_content_sha256"])]
                path = urlsplit(rec["url"]).path
                if not robots_allows(rules, path):
                    row["live_access_and_extraction"] = "robots_disallowed"
                    report["robots"]["tested_paths_allowed"] = False
                    continue
                if requests_made >= MAX_GETS:
                    raise ScreeningRefused("aggregate GET cap exceeded")
                time.sleep(max(2, delay))
                try:
                    meta, html = safe_fetch(http, rec["url"])
                    requests_made += 1
                    current = extracted(adapter, rec["url"], html, rec["published_date"])
                    current_report = compare_record(rec, version, None, current)
                    for k in (
                        "live_access_and_extraction", "live_title_matches_pinned",
                        "live_body_matches_pinned", "live_published_date_matches_pinned",
                        "live_version_digest_matches_pinned", "live_metrics",
                    ):
                        row[k] = current_report[k]
                    row["live_response_sha256"] = meta["payload_sha256"]
                except (requests.RequestException, ValueError, UnicodeError, ScreeningRefused) as exc:
                    row["live_access_and_extraction"] = "unavailable_or_unparseable"
                    row["live_error_type"] = type(exc).__name__
        except (requests.RequestException, UnicodeError, ValueError, ScreeningRefused) as exc:
            report["source_access_gate"] = "blocked_" + type(exc).__name__
        report["request_count"] = requests_made
        report["technical_parity_pass_count"] = sum(
            all(r[k] is True for k in (
                "archive_title_matches_stored", "archive_body_matches_stored",
                "archive_date_matches_stored", "archive_version_digest_matches_stored",
                "live_title_matches_pinned", "live_body_matches_pinned",
                "live_published_date_matches_pinned", "live_version_digest_matches_pinned"))
            for r in report["records"]
        )
        report["technical_parity_only_no_human_signoff"] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-repo", type=Path, required=True)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = screen(args.state_repo, args.state_commit, args.out)
        print(json.dumps({
            "schema": report["schema"],
            "pinned_state_commit": report["pinned_state_commit"],
            "request_count": report["request_count"],
            "technical_parity_pass_count": report["technical_parity_pass_count"],
            "outcomes": [{"identity": x["source_identity"],
                          "archived_exact": x["archive_body_matches_stored"],
                          "live_exact": x["live_body_matches_pinned"],
                          "date_exact": x["live_published_date_matches_pinned"],
                          "source_access": x["live_access_and_extraction"]}
                         for x in report["records"]],
            "human_approvals": 0, "reuse_approvals": 0,
        }, sort_keys=True, indent=2))
    except (ValueError, OSError, formal.ReviewError) as exc:
        print("MPS parity screening refused: %s" % type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
