#!/usr/bin/env python3
"""Validate private, unsigned Brief claim/citation review proposals.

Absolutely no edit, model call, source fetch, rendering, publishing or approval.
A syntactically valid JSON docket does NOT authenticate a human reviewer.
"""
import argparse
from collections import Counter
from datetime import date
from html import unescape
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"
PACKET = ROOT / "research/china/brief-claim-review-proposals-2026-10-15.json"
RECORDS = ROOT / "output" / "record"
ISSUES = ROOT / "output" / "the-pla-watch" / "posts"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
STAGES = frozenset((
    "owner_review_required", "claim_check_only_not_a_proposed_edit",
))
EVIDENCE_KINDS = frozenset((
    "publisher_original", "issuing_broadcaster_record",
))


def _date(value):
    try:
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError("invalid ISO publication/review date") from None


def _https(url):
    if not isinstance(url, str):
        raise ValueError("evidence requires HTTPS URL")
    try:
        parts = urlsplit(url)
    except ValueError:
        raise ValueError("malformed publisher evidence URL") from None
    if (parts.scheme != "https" or not parts.hostname
            or parts.username or parts.password or parts.fragment):
        raise ValueError("evidence requires unambiguous HTTPS publisher URL")


def _record_url(html):
    match = re.search(
        r'<th scope="row">Original URL</th>\s*<td class="prov-value">'
        r'\s*<a href="([^"]+)"', html)
    if match is None:
        raise ValueError("published record original URL is missing")
    return unescape(match.group(1))


def audit(index, packet, issue_docs, record_pages):
    expected_top = {
        "version", "purpose", "publication_enabled", "owner_approved",
        "created_on", "series", "cases", "baseline_snapshot",
    }
    if not isinstance(packet, dict) or set(packet) != expected_top:
        raise ValueError("claim-review docket schema changed")
    if (packet["version"] != 1
            or packet["purpose"] != "private_claim_level_correction_review_not_publication"
            or packet["publication_enabled"] is not False
            or packet["owner_approved"] is not False
            or packet["series"] != "The PLA Watch"):
        raise ValueError("claim-review docket cannot authorize publication")
    _date(packet["created_on"])
    current, baseline = index.get("snapshot"), packet["baseline_snapshot"]
    if not isinstance(current, dict) or not isinstance(baseline, dict):
        raise ValueError("missing corpus snapshot custody")
    _date(current.get("date"))
    _date(baseline.get("date"))
    if (type(current.get("records")) is not int
            or type(baseline.get("records")) is not int
            or current["date"] < baseline["date"]
            or current["records"] < baseline["records"]):
        raise ValueError("corpus snapshot custody regressed")
    if index.get("fields") != FIELDS:
        raise ValueError("compact index source schema changed")
    sources = index["sources"]
    trail = index.get("trail_ids")
    if not isinstance(trail, list) or len(trail) != len(set(trail)):
        raise ValueError("protected published source trail invalid")
    rows = {}
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("malformed corpus record")
        ident, pub, src, st, en, orig = row
        if (type(ident) is not int or ident in rows or ident <= 0
                or type(src) is not int or type(st) is not int
                or not 0 <= src < len(sources)
                or not 0 <= st < len(index["states"])):
            raise ValueError("invalid or duplicate source identity")
        _date(pub)
        rows[ident] = row
    if current["records"] != len(rows) or not set(trail).issubset(rows):
        raise ValueError("published corpus count/citation trails changed")
    if not isinstance(packet.get("cases"), list) or len(packet["cases"]) != 2:
        raise ValueError("claim-review packet must contain two named cases")
    seen, checked, counts = set(), [], Counter()
    for c in packet["cases"]:
        required = {
            "case_id", "issue_date", "issue_number", "issue_field",
            "source_record_id", "expected_cited_original_url",
            "existing_exact_text", "proposed_exact_text", "editorial_status",
            "reason", "primary_evidence", "related_existing_issue",
            "possible_correction_notice", "human_original_video_verified",
            "human_editor_reviewed", "owner_approved", "record_source",
            "original_source_title", "original_source_date",
        }
        if not isinstance(c, dict) or set(c) != required:
            raise ValueError("claim-review case schema invalid")
        if c["case_id"] in seen or c["case_id"] not in {
            "PLA-WATCH-12-ATLAS-KVD002", "PLA-WATCH-10-JOINTSEA-CAPTURE",
        }:
            raise ValueError("duplicate or unknown claim case")
        seen.add(c["case_id"])
        _date(c["issue_date"])
        _date(c["original_source_date"])
        if (type(c["issue_number"]) is not int or
            c["issue_number"] not in (10, 12)):
            raise ValueError("claim issue must be one of the reviewed issues")
        if c["issue_field"] not in ("opening_note", "what_was_routine"):
            raise ValueError("unsupported issue paragraph field")
        rid = c["source_record_id"]
        if type(rid) is not int or rid not in rows or rid not in trail:
            raise ValueError("claim source record ID or Brief citation missing")
        row = rows[rid]
        outlet = sources[row[2]]
        if ((outlet.get("desk") or {}).get("code") != "china"
                or outlet["code"] != c["record_source"]
                or outlet["code"] != "global_times_mil"
                or row[1] != c["original_source_date"]
                or (row[5] or row[4]) != c["original_source_title"]):
            raise ValueError("stored source original issuer/title/date drift")
        _https(c["expected_cited_original_url"])
        if rid not in record_pages:
            raise ValueError("preserved record page missing")
        if _record_url(record_pages[rid]) != c["expected_cited_original_url"]:
            raise ValueError("original record publisher link drift")
        issue = issue_docs.get(c["issue_date"])
        if issue is None or issue.get("date") != c["issue_date"] or issue.get("issue_number") != c["issue_number"]:
            raise ValueError("published issue identity/date missing or changed")
        matched = [t for t in issue.get("source_trail", [])
                   if t.get("url") == c["expected_cited_original_url"]]
        if len(matched) != 1:
            raise ValueError("publisher source link removed/duplicated in issue")
        body = issue.get(c["issue_field"])
        before = c["existing_exact_text"]
        if not isinstance(body, str) or not isinstance(before, str) or len(before) < 25 or body.count(before) != 1:
            raise ValueError("existing cited claim substring must occur exactly once")
        if c["editorial_status"] not in STAGES:
            raise ValueError("invalid editorial decision stage")
        if (c["human_original_video_verified"] is not False
                or c["human_editor_reviewed"] is not False
                or c["owner_approved"] is not False):
            raise ValueError("draft cannot impersonate actual owner or video reviewer")
        if not isinstance(c["reason"], str) or len(c["reason"]) < 100:
            raise ValueError("editorial claim reason needs substantive explanation")
        if (not isinstance(c["primary_evidence"], list)
                or not c["primary_evidence"]):
            raise ValueError("publisher evidence must be listed")
        for e in c["primary_evidence"]:
            if not isinstance(e, dict) or set(e) != {"kind", "url", "supports"}:
                raise ValueError("publisher evidence has invalid fields")
            if e["kind"] not in EVIDENCE_KINDS or not isinstance(e["supports"], str) or len(e["supports"]) < 25:
                raise ValueError("publisher evidence needs type and concrete observation")
            _https(e["url"])
        _https(c["related_existing_issue"])
        after = c["proposed_exact_text"]
        if c["editorial_status"] == "owner_review_required":
            if (not isinstance(after, str) or len(after) < 60
                    or after == before or c["possible_correction_notice"] is None):
                raise ValueError("explicit replacement case needs proposed wording and notice")
            if (c["issue_number"], rid, c["issue_field"]) != (12, 2881, "opening_note"):
                raise ValueError("unexpected direct correction proposal")
        else:
            if (after is not None or c["possible_correction_notice"] is not None
                    or (c["issue_number"], rid) != (10, 2265)):
                raise ValueError("claim-check-only case cannot propose a Brief edit")
        if c["possible_correction_notice"] is not None:
            if not isinstance(c["possible_correction_notice"], str) or len(c["possible_correction_notice"]) < 100:
                raise ValueError("proposed notice too vague")
        contexts = body.split(before)
        proposed_paragraph = contexts[0] + after + contexts[1] if after is not None else None
        checked.append({
            "case_id": c["case_id"], "issue_number": c["issue_number"],
            "issue_date": c["issue_date"], "source_record_id": rid,
            "historical_record_url": "https://indopacificrecord.org/record/%d.html" % rid,
            "original_publisher_url": c["expected_cited_original_url"],
            "issue_field": c["issue_field"],
            "current_paragraph_sha256": sha256(body.encode("utf-8")).hexdigest(),
            "current_exact_excerpt": before,
            "proposed_exact_excerpt": after,
            "proposed_full_paragraph_private_not_to_publish": proposed_paragraph,
            "status": c["editorial_status"],
            "editor_reviewed": False, "owner_approved": False,
            "correction_authorized": False,
        })
        counts[c["editorial_status"]] += 1
    return {
        "purpose": "unsigned_claim_review_only",
        "publication_enabled": False, "owner_approved": False,
        "snapshot": current, "case_count": len(checked),
        "unmodified_published_source_record_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "cases": checked,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--packet", type=Path, default=PACKET)
    ap.add_argument("--issue-dir", type=Path, default=ISSUES)
    ap.add_argument("--record-dir", type=Path, default=RECORDS)
    ap.add_argument("--private-json", type=Path,
                    help="NEW absolute report outside the repository, no overwrite")
    args = ap.parse_args(argv)
    if args.private_json:
        target = args.private_json.expanduser()
        resolved = target.resolve()
        root = ROOT.resolve()
        if (not target.is_absolute() or target.exists() or target.is_symlink()
                or resolved == root or root in resolved.parents):
            ap.error("private review report must be a new path outside repository")
    idx = json.loads(args.index.read_text(encoding="utf-8"))
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    issues = {}
    pages = {}
    for case in packet["cases"]:
        day = case["issue_date"]
        rid = case["source_record_id"]
        issues[day] = json.loads(
            (args.issue_dir / (day + ".json")).read_text(encoding="utf-8"))
        pages[rid] = (args.record_dir / ("%d.html" % rid)).read_text(
            encoding="utf-8")
    report = audit(idx, packet, issues, pages)
    if args.private_json:
        args.private_json.parent.mkdir(parents=True, exist_ok=True)
        args.private_json.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "cases"}
    summary["cases"] = [
        {"id": x["case_id"], "issue": x["issue_number"], "status": x["status"]}
        for x in report["cases"]
    ]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
