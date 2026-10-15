#!/usr/bin/env python3
"""Offline custody validator for assistant-prepared China original-source notes.

This is NOT a publisher crawler, editorial approval, archive selection, or
authorization to repair historical captures. Report only; no writes.
"""
import argparse
from datetime import date
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "output" / "corpus-index.json"
PACKET_PATH = ROOT / "research/china/original-source-review-2026-10-15.json"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
KINDS = {"issuer_publication", "publisher_original", "publisher_republication",
         "source_not_independently_checked"}
COMPARISONS = {"apparent_substantive_match", "historical_text_contamination",
               "near_identical_republication", "original_not_checked",
               "historical_body_absent"}
NEXT_STEPS = {"candidate_original_review", "quality_hold", "syndication_review"}


class OriginalBodyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.hits = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div" and "original-text" in attributes.get("class", "").split() and self.depth == 0:
            self.depth = 1
            self.hits += 1
        elif self.depth and tag not in ("br", "hr", "img", "source", "meta", "input", "wbr"):
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        return

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def _review_date(s, field):
    if not isinstance(s, str):
        raise ValueError(field + " missing")
    try:
        if date.fromisoformat(s).isoformat() != s:
            raise ValueError()
    except ValueError:
        raise ValueError(field + " must be YYYY-MM-DD") from None


def _url(s, field, allow_http=False):
    if not isinstance(s, str):
        raise ValueError(field + " missing")
    try:
        parsed = urlsplit(s)
    except ValueError:
        raise ValueError(field + " malformed") from None
    schemes = ("https", "http") if allow_http else ("https",)
    if parsed.scheme not in schemes or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(field + " must be an unambiguous publisher URL")


def _text(s, field, size=8):
    if not isinstance(s, str) or len(s.strip()) < size:
        raise ValueError(field + " needs specific nonempty evidence")


def _original_url(html):
    matched = re.search(
        r'<th scope="row">Original URL</th>\s*<td class="prov-value">\s*<a href="([^"]+)"',
        html,
    )
    if matched is None:
        raise ValueError("record provenance URL missing or template changed")
    return unescape(matched.group(1))


def _original_record(html):
    p = OriginalBodyParser()
    p.feed(html)
    if p.hits != 1 or p.depth:
        raise ValueError("cannot locate one complete original-text block in record HTML")
    body = " ".join(" ".join(p.parts).split())
    return body, _original_url(html)


def validate_packet(packet, index, pages):
    if not isinstance(packet, dict) or set(packet) != {
        "version", "purpose", "publication_enabled", "owner_approved",
        "baseline_snapshot", "checks",
    }:
        raise ValueError("unexpected review packet schema")
    if (packet["version"] != 1 or
        packet["purpose"] != "assistant_research_preliminary_not_editorial_signoff" or
        packet["publication_enabled"] is not False or
        packet["owner_approved"] is not False):
        raise ValueError("the packet must remain preliminary and non-publishing")
    if index.get("fields") != FIELDS:
        raise ValueError("corpus field schema changed")
    if index.get("snapshot") != packet["baseline_snapshot"]:
        raise ValueError("packet is bound to an exact dated compact-index snapshot")
    sources = index["sources"]
    seen = set()
    records = {}
    for row in index["records"]:
        if len(row) != 6 or type(row[0]) is not int or row[0] in records:
            raise ValueError("invalid or repeated canonical record ID")
        if not isinstance(row[2], int) or not 0 <= row[2] < len(sources):
            raise ValueError("invalid source lookup")
        records[row[0]] = row
    trail = index.get("trail_ids")
    if not isinstance(trail, list) or len(trail) != len(set(trail)) or not set(trail).issubset(records):
        raise ValueError("unverifiable published Brief trail protections")
    if not isinstance(packet["checks"], list) or not packet["checks"]:
        raise ValueError("review packet must contain a source-evidence case")

    outcomes = {}
    for c in packet["checks"]:
        required = {
            "id", "source", "published_date", "title", "captured_url",
            "research_url", "research_kind", "comparison", "research_date",
            "issuer_attribution", "source_observation", "stored_body_anchor",
            "next_step", "human_original_review_required", "owner_approved",
        }
        if not isinstance(c, dict) or set(c) != required:
            raise ValueError("review case fields missing or unrecognized")
        i = c["id"]
        if type(i) is not int or i in seen:
            raise ValueError("repeated or invalid case ID")
        seen.add(i)
        row = records.get(i)
        if row is None or sources[row[2]].get("desk", {}).get("code") != "china":
            raise ValueError("unknown or non-China source case")
        if (c["source"] != sources[row[2]]["code"] or c["published_date"] != row[1]
                or c["title"] != (row[5] or row[4])):
            raise ValueError("case source/title/date drift")
        _review_date(c["published_date"], "original source date")
        _review_date(c["research_date"], "source research date")
        if c["research_date"] < c["published_date"]:
            raise ValueError("research cannot predate the captured publication")
        _url(c["captured_url"], "captured source URL", allow_http=True)
        if c["research_kind"] not in KINDS or c["comparison"] not in COMPARISONS:
            raise ValueError("invalid source-evidence classification")
        if c["next_step"] not in NEXT_STEPS:
            raise ValueError("invalid nonbinding research recommendation")
        if c["research_kind"] == "source_not_independently_checked":
            if c["research_url"] is not None or c["comparison"] != "original_not_checked":
                raise ValueError("unverified original must be explicitly unknown")
        else:
            _url(c["research_url"], "source research URL")
            if c["comparison"] == "original_not_checked":
                raise ValueError("checked source cannot claim unknown comparison")
        _text(c["issuer_attribution"], "issuer attribution")
        _text(c["source_observation"], "specific source observation", 45)
        missing_body = c["comparison"] == "historical_body_absent"
        if missing_body:
            if c["stored_body_anchor"] is not None:
                raise ValueError("absent source-body evidence must have null anchor")
        elif not isinstance(c["stored_body_anchor"], str) or len(c["stored_body_anchor"]) < 8:
            raise ValueError("missing specific original-body anchor")
        if c["human_original_review_required"] is not True or c["owner_approved"] is not False:
            raise ValueError("assistant notes cannot stand in for editor/owner approval")
        if c["comparison"] in ("historical_text_contamination", "historical_body_absent") and c["next_step"] != "quality_hold":
            raise ValueError("unfaithful or absent historical captures must remain held")
        if i not in pages:
            raise ValueError("the stored original record page is missing")
        if missing_body:
            parsed = OriginalBodyParser()
            parsed.feed(pages[i])
            if parsed.hits or parsed.depth:
                raise ValueError("original text now present; old absence must be re-reviewed")
            stored_url = _original_url(pages[i])
        else:
            body, stored_url = _original_record(pages[i])
            if c["stored_body_anchor"] not in body:
                raise ValueError("stored body anchor changed; re-review the capture")
        if stored_url != c["captured_url"]:
            raise ValueError("stored source URL changed since research case was entered")
        outcomes[c["comparison"]] = outcomes.get(c["comparison"], 0) + 1
    return {
        "research_cases": len(seen),
        "reviewed_source_notes_not_editorial_decisions": True,
        "bound_snapshot": index["snapshot"],
        "publication_enabled": False,
        "owner_approved": False,
        "source_outcomes": dict(sorted(outcomes.items())),
        "historical_corpus_records_untouched": len(index["records"]),
        "requires_human_verification": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--packet", type=Path, default=PACKET_PATH)
    parser.add_argument("--records-dir", type=Path, default=ROOT / "output" / "record")
    args = parser.parse_args(argv)
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    index = json.loads(args.index.read_text(encoding="utf-8"))
    pages = {}
    for check in packet.get("checks", []):
        ident = check.get("id")
        if type(ident) is not int:
            raise ValueError("noninteger record ID")
        pages[ident] = (args.records_dir / ("%d.html" % ident)).read_text(encoding="utf-8")
    result = validate_packet(packet, index, pages)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
