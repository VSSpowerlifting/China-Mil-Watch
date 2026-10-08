"""Bridge human-verified Vietnam official links into a draft Brief's citation contract.

This is NOT a source-review or publication approval action. It reads a
source-version-pinned *private* Vietnam research packet (the producer in PR
#211 and consumer in PR #203), an independently completed HUMAN source-review
receipt, and a DRAFT Brief sidecar containing actual [External mps-vi:...]
citations. It emits only a provisional external_evidence fragment conforming
to core.brief_external_evidence; final Brief approval remains separate.

In particular, a model-generated synopsis or a checkbox-shaped JSON fixture
is not independently verified publication evidence. A named reviewer must
actually compare the original Vietnamese publisher page and captured version.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from core.brief_contract import eligible_desks
from core.brief_external_evidence import (
    CHECKS, REFERENCE, SCHEMA as EXTERNAL_SCHEMA, SCOPE,
    SOURCE_NAME, SOURCE_SLUG, validate_external_evidence,
)
from core.desk_registry import load_registry

SCHEMA = "vietnam-reviewed-brief-citation-receipt/1"
PACKET_SCHEMA = "ipr-private-drafting-evidence/1"
PACKET_STATUS = "unapproved-source-linked-editorial-candidate"
PACKET_SCOPE = "private-model-drafting-only-no-source-body"
OUT_SCHEMA = "vietnam-unapproved-external-evidence-fragment/1"
ID = re.compile(r"VN-MPS-([1-9][0-9]{9})\Z")
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
PACKET_FIELDS = {
    "id", "desk", "source_name", "source_url", "published_date", "language",
    "title_original", "source_kind", "state_commit", "source_content_sha256",
    "hash_rule", "summary", "caveats", "topics", "status", "copy_scope",
}
RECEIPT_FIELDS = {
    "external_id", "source_identity", "source_url", "published_date",
    "original_title", "state_commit", "source_content_sha256", "reviewed_by",
    "reviewed_on", "link_and_summary_use_basis",
    "original_summary", "checks",
}
MAX_ITEMS = 3


class CitationBridgeRefused(ValueError):
    """The verified-source-to-final-citation chain is incomplete."""


def require(ok, explanation):
    if not ok:
        raise CitationBridgeRefused(explanation)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(path, max_size=80000):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= max_size, "missing, linked or oversize JSON file")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              CitationBridgeRefused("non-finite JSON token")))
    except CitationBridgeRefused:
        raise
    except (ValueError, UnicodeError) as exc:
        raise CitationBridgeRefused("bad JSON or encoding") from exc


def _date(value):
    require(isinstance(value, str), "expected exact ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CitationBridgeRefused("invalid calendar date") from exc
    require(parsed.isoformat() == value, "noncanonical calendar date")
    return parsed


def _text(value, min_chars, max_chars):
    return (isinstance(value, str) and min_chars <= len(value.strip()) <= max_chars
            and value == value.strip() and
            not any(ord(char) < 32 or ord(char) == 127 for char in value))


def _published_mps_url(url, digits):
    if not _text(url, 50, 1700):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname == "bocongan.gov.vn" and
                u.port is None and not u.username and not u.password and
                not u.query and not u.fragment and
                u.path.startswith("/bai-viet/") and u.path.endswith("-" + digits))
    except ValueError:
        return False


def _prose(sidecar):
    fields = (
        "title", "dek", "signal", "opening_note", "what_stood_out",
        "why_it_matters", "what_was_routine", "what_im_watching_next",
        "term_to_know_explanation",
    )
    values = [sidecar.get(field) for field in fields]
    development = sidecar.get("development")
    if isinstance(development, dict):
        values.append(development.get("summary"))
    for claim in sidecar.get("cross_desk_claims") or ():
        if isinstance(claim, dict):
            values.append(claim.get("claim"))
    return "\n".join(v for v in values if isinstance(v, str))


def build(sidecar, packet, receipt, registry):
    """Review *all* cited Vietnam IDs against exact source and human metadata."""
    require(isinstance(sidecar, dict)
            and sidecar.get("editorial_status") == "draft"
            and sidecar.get("issue_number") is None,
            "only an unnumbered draft sidecar may receive this review fragment")
    saturday = _date(sidecar.get("week_ending"))
    require(saturday.weekday() == 5 and
            (saturday - _date(sidecar.get("week_start"))).days == 6,
            "draft's Saturday-ending reporting week invalid")
    desks = sidecar.get("desks")
    require(isinstance(desks, list) and "vietnam" not in desks
            and len(desks) >= 2 and len(set(desks)) == len(desks),
            "external Vietnam sources cannot count as live desk coverage")
    eligible = set(eligible_desks(registry))
    require(set(desks) <= eligible, "one or more declared production desks not eligible")
    trail = sidecar.get("source_trail")
    require(isinstance(trail, list) and {r.get("desk") for r in trail
              if isinstance(r, dict)} >= set(desks),
            "two production desk source trails required before external evidence")
    require("external_evidence" not in sidecar or sidecar["external_evidence"] == [],
            "refuse overwriting any existing external-evidence review")

    require(isinstance(packet, dict) and
            set(packet) == {"schema", "status", "week_ending", "items"} and
            packet["schema"] == PACKET_SCHEMA and
            packet["status"] == PACKET_STATUS and
            packet["week_ending"] == saturday.isoformat() and
            isinstance(packet["items"], list),
            "research packet is not exact-week private official-source evidence")
    candidates = {}
    for item in packet["items"]:
        require(isinstance(item, dict) and set(item) == PACKET_FIELDS,
                "invalid private research item fields")
        if item["desk"] != "vietnam":
            continue  # Japan candidates are owned by the Japan workstream.
        ident = item["id"]
        match = ID.fullmatch(ident) if isinstance(ident, str) else None
        require(match is not None and ident not in candidates,
                "invalid or duplicate Vietnam research source ID")
        require(item["status"] == PACKET_STATUS and
                item["copy_scope"] == PACKET_SCOPE and
                item["source_kind"] == "shadow-extracted-original" and
                item["hash_rule"] == "mps-vi-content-v1" and
                item["source_name"] == SOURCE_NAME and item["language"] == "vi",
                "Vietnam source cannot claim production/publication admission")
        require(_published_mps_url(item["source_url"], match.group(1)) and
                isinstance(item["state_commit"], str) and
                HEX40.fullmatch(item["state_commit"]) and
                isinstance(item["source_content_sha256"], str) and
                HEX64.fullmatch(item["source_content_sha256"]) and
                _text(item["title_original"], 8, 350),
                "invalid Vietnam source version or official publisher metadata")
        published = _date(item["published_date"])
        require(saturday.toordinal() - 6 <= published.toordinal() <=
                saturday.toordinal(), "research source published outside the week")
        candidates["mps-vi:" + match.group(1)] = item

    prose = _prose(sidecar)
    cited = REFERENCE.findall(prose)
    require(cited and len(set(cited)) <= MAX_ITEMS,
            "draft contains no bounded Vietnam official-source citations")
    require(len(cited) == len(set(cited)) or all(
        cited.count(ident) <= 8 for ident in cited),
        "excessively repeated external reference")
    cited_ids = set(cited)
    require(all(identity in candidates for identity in cited_ids),
            "draft cites an unknown, unpinned or non-Vietnam external source")

    require(isinstance(receipt, dict) and
            set(receipt) == {"schema", "week_ending", "records"} and
            receipt["schema"] == SCHEMA and
            receipt["week_ending"] == saturday.isoformat() and
            isinstance(receipt["records"], list) and
            1 <= len(receipt["records"]) <= MAX_ITEMS,
            "missing exact-week human-source verification receipt")
    review_ids = [row.get("source_identity") for row in receipt["records"]
                  if isinstance(row, dict)]
    require(len(review_ids) == len(receipt["records"]) and
            len(set(review_ids)) == len(review_ids) and
            set(review_ids) == cited_ids,
            "every and only actually cited Vietnam source must have its own review")
    values = []
    for row in receipt["records"]:
        require(isinstance(row, dict) and set(row) == RECEIPT_FIELDS,
                "human review receipt has missing/extra source fields")
        identity = row["source_identity"]
        item = candidates[identity]
        require(row["external_id"] == item["id"] and
                row["source_url"] == item["source_url"] and
                row["published_date"] == item["published_date"] and
                row["original_title"] == item["title_original"] and
                row["state_commit"] == item["state_commit"] and
                row["source_content_sha256"] == item["source_content_sha256"],
                "review statement is not bound to the exact source version cited")
        source_date, checked = _date(row["published_date"]), _date(row["reviewed_on"])
        require(source_date <= checked <= date.today(),
                "human source review is before publication or future-dated")
        require(_text(row["reviewed_by"], 3, 120)
                and _text(row["original_summary"], 40, 700)
                and _text(row["link_and_summary_use_basis"], 35, 700),
                "named human summary review and source-use rationale required")
        checks = row["checks"]
        require(isinstance(checks, dict) and set(checks) == CHECKS and
                all(checks[k] is True for k in CHECKS),
                "all eight original-source checks require independent human affirmation")
        values.append({
            "schema": EXTERNAL_SCHEMA,
            "source_identity": identity,
            "desk": "vietnam",
            "source_slug": SOURCE_SLUG,
            "source_name": SOURCE_NAME,
            "url": item["source_url"],
            "original_title": item["title_original"],
            "lang": "vi",
            "date": item["published_date"],
            "state_commit": item["state_commit"],
            "content_sha256": item["source_content_sha256"],
            "original_summary": row["original_summary"],
            "human_review": {
                "reviewed_by": row["reviewed_by"],
                "reviewed_on": row["reviewed_on"],
                "scope": SCOPE,
                "checks": dict(checks),
            },
        })
    # Run the same independent validator that governs all published Briefs.
    trial = dict(sidecar, external_evidence=values)
    issues = validate_external_evidence(trial, registry, require_citations=True)
    require(not issues, "Brief external-source contract rejected fragment: " +
            "; ".join(issues))
    return {
        "schema": OUT_SCHEMA,
        "week_ending": saturday.isoformat(),
        "external_evidence": values,
        "publication_approved": False,
        "final_brief_approval_required": True,
        "source_full_text_copied": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draft-sidecar", type=Path, required=True)
    ap.add_argument("--private-research-packet", type=Path, required=True)
    ap.add_argument("--human-source-review", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    out = args.out
    root = Path(__file__).resolve().parents[1].resolve()
    resolved = out.resolve()
    require(not out.exists() and not out.is_symlink()
            and out.parent.is_dir() and not out.parent.is_symlink() and
            resolved != root and root not in resolved.parents,
            "private review output must be new and outside repository")
    values = build(load(args.draft_sidecar),
                   load(args.private_research_packet),
                   load(args.human_source_review, max_size=20000),
                   load_registry())
    out.write_text(json.dumps(values, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n", encoding="utf-8")
    print("Verified {} source-review receipt(s) for a draft ONLY; no "
          "issue approval, archive import, public article body or email.".format(
              len(values["external_evidence"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
