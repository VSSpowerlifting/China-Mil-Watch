#!/usr/bin/env python3
"""Published Global Times source-trail capture-integrity audit (read-only).

Assesses whether protected archived source bodies require a human source
verification; cannot determine the truth of the publisher's reporting, the
correctness of a human-edited Brief, or authorize publication corrections.
"""
import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"
CASES = ROOT / "research/china/published_global_times_trail-risk-2026-10-15.json"
RECORDS = ROOT / "output" / "record"
ISSUES = ROOT / "output" / "the-pla-watch" / "posts"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
CATEGORIES = {
    "claim_level_review", "machine_summary_conflict",
    "already_caveated_in_issue",
}


class ArticleBody(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.hits = 0
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "original-text" in attrs.get("class", "").split() and not self.depth:
            self.depth = 1
            self.hits += 1
        elif self.depth and tag not in {"br", "hr", "img", "meta", "input", "source", "wbr"}:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.fragments.append(data)


def _date(s):
    try:
        if type(s) is not str or date.fromisoformat(s).isoformat() != s:
            raise ValueError()
    except ValueError:
        raise ValueError("invalid source or issue date") from None


def record_evidence(html):
    p = ArticleBody()
    p.feed(html)
    if p.depth or p.hits != 1:
        raise ValueError("missing or ambiguous source body")
    body = " ".join(" ".join(p.fragments).split())
    m = re.search(r'<th scope="row">Original URL</th>\s*<td class="prov-value">'
                  r'\s*<a href="([^"]+)"', html)
    n = re.search(r'<th scope="row">Collected at</th><td class="prov-value">'
                  r'\s*(\d{4}-\d{2}-\d{2})', html)
    summary = re.search(r'<div class="interpretation">\s*<p>([\s\S]*?)</p>', html)
    if not m or not n or not summary:
        raise ValueError("missing original URL, collection date or machine summary")
    _date(n.group(1))
    machine = unescape(re.sub(r"<[^>]+>", " ", summary.group(1)))
    ellipses = len(re.findall(r"(?:\.\s*){3}|…", body))
    return {
        "url": unescape(m.group(1)),
        "collected_on": n.group(1),
        "stored_body_length": len(body),
        "stored_body_sha256": sha256(body.encode("utf-8")).hexdigest(),
        "ellipsis_cues": ellipses,
        "likely_preview_only_review_cue": (
            (ellipses >= 3 and len(body) < 700)
            or (ellipses >= 1 and len(body) < 180)
        ),
        "machine_summary_mentions_2025_joint_sea": bool(
            re.search(r"Joint Sea[- ]2025", machine, flags=re.IGNORECASE)),
    }


def audit(index, docket, pages, issues):
    if index.get("fields") != FIELDS:
        raise ValueError("corpus schema changed")
    trails = index.get("trail_ids")
    if not isinstance(trails, list) or len(set(trails)) != len(trails):
        raise ValueError("published source trail protections absent/duplicated")
    if not isinstance(docket, dict) or set(docket) != {
        "version", "purpose", "publication_enabled", "owner_approved",
        "source_snapshot", "created_on", "series", "notes", "checks"
    }:
        raise ValueError("unrecognized source-trail risk packet")
    if (docket["version"] != 1 or
        docket["purpose"] != "preliminary_published_source_integrity_research_not_publication" or
        docket["publication_enabled"] is not False or
        docket["owner_approved"] is not False or
        docket["series"] != "The PLA Watch"):
        raise ValueError("source-trail risk packet cannot authorize publication")
    _date(docket["created_on"])
    base = docket["source_snapshot"]
    snapshot = index.get("snapshot")
    if (not isinstance(base, dict) or not isinstance(snapshot, dict)
            or type(base.get("records")) is not int
            or type(snapshot.get("records")) is not int):
        raise ValueError("missing dated corpus snapshot")
    _date(base.get("date"))
    _date(snapshot.get("date"))
    if snapshot["date"] < base["date"] or snapshot["records"] < base["records"]:
        raise ValueError("corpus moved backwards; source custody requires reconciliation")
    records = {}
    sources = index["sources"]
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("malformed corpus record")
        ident, when, source_index, state_index, en, orig = row
        if (type(ident) is not int or ident in records
                or type(source_index) is not int
                or type(state_index) is not int
                or not 0 <= source_index < len(sources)
                or not 0 <= state_index < len(index["states"])):
            raise ValueError("corrupt record identity/lookup")
        _date(when)
        records[ident] = row
    if len(records) != snapshot["records"] or not set(trails).issubset(records):
        raise ValueError("corpus count or source trail identities changed")
    if not isinstance(docket["checks"], list) or not docket["checks"]:
        raise ValueError("empty published-source review")
    by_id = {}
    results = []
    for c in docket["checks"]:
        allowed = {
            "id", "issue_date", "issue_number", "expected_original_url",
            "original_source_title", "original_source_date",
            "editorial_attention", "review_question",
            "original_publisher_content_checked", "reviewer", "reviewed_on",
            "owner_approved",
        }
        if not isinstance(c, dict) or set(c) != allowed:
            raise ValueError("invalid source risk case shape")
        ident = c["id"]
        if type(ident) is not int or ident in by_id or ident not in records:
            raise ValueError("missing or duplicate record in source risk docket")
        by_id[ident] = c
        rec = records[ident]
        if (c["original_source_title"] != (rec[5] or rec[4])
                or c["original_source_date"] != rec[1]):
            raise ValueError("original publication source title/date drift")
        src = sources[rec[2]]
        if ((src.get("desk") or {}).get("code") != "china"
                or src["code"] != "global_times_mil" or ident not in trails):
            raise ValueError("source risk must be a published China Global Times trail")
        if (c["editorial_attention"] not in CATEGORIES or
                not isinstance(c["review_question"], str)
                or len(c["review_question"]) < 70):
            raise ValueError("invalid attention status or vague editorial question")
        if (c["original_publisher_content_checked"] is not False
                or c["reviewer"] is not None or c["reviewed_on"] is not None
                or c["owner_approved"] is not False):
            raise ValueError("automated trail inspection cannot assert editor review or approval")
        _date(c["issue_date"])
        if type(c["issue_number"]) is not int or c["issue_number"] < 1:
            raise ValueError("invalid issue number")
        if ident not in pages or c["issue_date"] not in issues:
            raise ValueError("source record or published issue file missing")
        original = record_evidence(pages[ident])
        if original["url"] != c["expected_original_url"]:
            raise ValueError("published original source URL changed")
        issue = issues[c["issue_date"]]
        if (issue.get("date") != c["issue_date"]
                or issue.get("issue_number") != c["issue_number"]):
            raise ValueError("issue identity/date drift")
        matches = [t for t in issue.get("source_trail", [])
                   if t.get("url") == c["expected_original_url"]]
        if len(matches) != 1:
            raise ValueError("cited source URL missing or duplicated in published issue")
        if c["editorial_attention"] == "already_caveated_in_issue":
            note = issue.get("opening_note") or ""
            if ("Correction" not in note or "Global Times" not in note
                    or "unrelated snippets" not in note):
                raise ValueError("previous correction/caveat no longer verifiable")
        if c["editorial_attention"] == "machine_summary_conflict":
            if not original["machine_summary_mentions_2025_joint_sea"]:
                raise ValueError("specific machine summary conflict no longer present")
        results.append({
            "id": ident, "title": rec[5] or rec[4],
            "issue_number": c["issue_number"], "issue_date": c["issue_date"],
            "publisher_url": original["url"], "record_url":
                "https://indopacificrecord.org/record/%d.html" % ident,
            "editorial_attention": c["editorial_attention"],
            "review_question": c["review_question"],
            "stored_body_length": original["stored_body_length"],
            "stored_body_sha256": original["stored_body_sha256"],
            "ellipsis_cues": original["ellipsis_cues"],
            "likely_preview_only_review_cue": original["likely_preview_only_review_cue"],
            "original_publisher_content_checked": False,
            "brief_inaccuracy_established": False,
            "correction_authorized": False,
        })
    results.sort(key=lambda x: (x["issue_number"], x["id"]))
    return {
        "purpose": "published_source_integrity_review_only",
        "publication_enabled": False, "owner_approved": False,
        "source_snapshot": snapshot, "baseline_snapshot": base,
        "historical_record_count": len(records),
        "published_global_times_trails_reviewed": len(results),
        "issues_affected": sorted({r["issue_number"] for r in results}),
        "attention_counts": dict(sorted(Counter(
            r["editorial_attention"] for r in results).items())),
        "stored_snippet_warning_count_not_proven_defects": sum(
            r["likely_preview_only_review_cue"] for r in results),
        "every_publisher_original_needs_claim_level_review": True,
        "cases": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--docket", type=Path, default=CASES)
    parser.add_argument("--record-dir", type=Path, default=RECORDS)
    parser.add_argument("--issue-dir", type=Path, default=ISSUES)
    parser.add_argument("--private-json", type=Path,
                        help="optional NEW report path outside the repository")
    args = parser.parse_args(argv)
    if args.private_json:
        dest = args.private_json.expanduser()
        resolved = dest.resolve()
        if (not dest.is_absolute() or dest.exists() or dest.is_symlink()
                or resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents):
            parser.error("report must be a new absolute file outside the repository")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    docket = json.loads(args.docket.read_text(encoding="utf-8"))
    pages = {}
    issues = {}
    for c in docket["checks"]:
        ident, when = c["id"], c["issue_date"]
        pages[ident] = (args.record_dir / ("%d.html" % ident)).read_text(
            encoding="utf-8")
        if when not in issues:
            issues[when] = json.loads(
                (args.issue_dir / (when + ".json")).read_text(encoding="utf-8"))
    report = audit(index, docket, pages, issues)
    if args.private_json:
        args.private_json.parent.mkdir(parents=True, exist_ok=True)
        args.private_json.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "cases"}
    summary["review_ids"] = [x["id"] for x in report["cases"]]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
