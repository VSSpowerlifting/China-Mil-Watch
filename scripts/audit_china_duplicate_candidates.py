#!/usr/bin/env python3
"""Read-only China record duplicate-candidate and extraction-quality audit.

Headline matches are never evidence of duplicate *events*, identical bodies,
issuer authority, or permission to remove source records. This tool makes no
changes to the canonical database or rendered site.
"""
import argparse
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
LEADING_TAG = re.compile(r"^\s*(?:【[^】]*】|\[[^\]]*\])\s*")


def normalized_title(title):
    """Unicode- and punctuation-tolerant *review cue*, not a dedup key."""
    text = unicodedata.normalize("NFKC", title or "").strip().casefold()
    while True:
        stripped = LEADING_TAG.sub("", text)
        if stripped == text:
            break
        text = stripped
    return "".join(ch for ch in text
                   if unicodedata.category(ch)[0] not in "PSZ"
                   and not ch.isspace())


def title_key(row):
    title = row["title_orig"] or row["title_en"] or ""
    key = normalized_title(title)
    han = bool(re.search(r"[\u3400-\u9fff]", title))
    return key if len(key) >= (10 if han else 24) else ""


def china_rows(index):
    if index.get("fields") != FIELDS:
        raise ValueError("index field schema changed")
    sources, states = index["sources"], index["states"]
    trails = index.get("trail_ids")
    if not isinstance(trails, list) or len(trails) != len(set(trails)):
        raise ValueError("missing or duplicated source-trail protections")
    protected, seen, rows = set(trails), set(), []
    for raw in index["records"]:
        if not isinstance(raw, list) or len(raw) != 6:
            raise ValueError("invalid index row")
        rid, day, source_id, state_id, en, original = raw
        if (type(rid) is not int or rid in seen or type(source_id) is not int
                or type(state_id) is not int):
            raise ValueError("invalid record id or index")
        seen.add(rid)
        if not (0 <= source_id < len(sources) and 0 <= state_id < len(states)):
            raise ValueError("index out of range")
        try:
            date.fromisoformat(day)
        except (TypeError, ValueError):
            raise ValueError("invalid stored publication date: %d" % rid) from None
        if not isinstance(en, str) or not isinstance(original, str):
            raise ValueError("invalid title fields")
        source = sources[source_id]
        if (source.get("desk") or {}).get("code") != "china":
            continue
        rows.append({
            "id": rid, "date": day, "source": source["code"],
            "state": states[state_id]["code"], "title_orig": original,
            "title_en": en, "protected_trail": rid in protected,
        })
    if not protected.issubset(seen):
        raise ValueError("published source-trail id not held in index")
    return rows


def duplicate_candidates(index, day_span=2):
    """Same normalized headline in <=2-day windows: manual-review leads only.

    Fix window span to first record, not previous record. A day-1, day-3,
    day-5 chain cannot be merged into one five-day event.
    """
    if type(day_span) is not int or not 0 <= day_span <= 7:
        raise ValueError("date window must be an integer 0..7")
    china = china_rows(index)
    by_title = defaultdict(list)
    for row in china:
        k = title_key(row)
        if k:
            by_title[k].append(row)
    candidates, recurring = [], []
    for key in sorted(by_title):
        same = sorted(by_title[key], key=lambda r: (r["date"], r["id"]))
        if len(same) < 2:
            continue
        windows, current = [], []
        for row in same:
            if current and (date.fromisoformat(row["date"]) -
                            date.fromisoformat(current[0]["date"])).days > day_span:
                windows.append(current)
                current = []
            current.append(row)
        windows.append(current)
        if len(windows) > 1:
            recurring.append({
                "normalized_title": key, "event_windows": len(windows),
                "all_record_ids": [r["id"] for r in same],
                "publication_dates": sorted({r["date"] for r in same}),
                "warning": "Repeated headline may describe separate dated events",
            })
        for group in windows:
            if len(group) < 2:
                continue
            candidates.append({
                "normalized_title": key,
                "record_ids": [r["id"] for r in group],
                "dates": sorted({r["date"] for r in group}),
                "sources": sorted({r["source"] for r in group}),
                "protected_trail_ids": [r["id"] for r in group if r["protected_trail"]],
                "title_examples": list(dict.fromkeys(
                    (r["title_orig"] or r["title_en"]) for r in group))[:3],
                "status": "requires_original_text_and_issuer_review",
            })
    candidates.sort(key=lambda g: (min(g["dates"]), min(g["record_ids"])), reverse=True)
    recurring.sort(key=lambda g: (g["normalized_title"], g["all_record_ids"]))
    return {
        "version": 1, "purpose": "private_read_only_review",
        "never_a_publication_allowlist": True,
        "snapshot": index.get("snapshot"),
        "china_stored_records": len(china),
        "max_same_event_span_days": day_span,
        "candidate_group_count": len(candidates),
        "records_in_candidate_groups": sum(len(g["record_ids"]) for g in candidates),
        "possible_redundant_occurrences_not_cleared_for_removal": sum(
            len(g["record_ids"]) - 1 for g in candidates),
        "cross_outlet_group_count": sum(len(g["sources"]) > 1 for g in candidates),
        "candidate_groups": candidates,
        "recurring_headline_family_count": len(recurring),
        "recurring_headline_families": recurring,
    }


class _TextOnly(HTMLParser):
    """Read only the record's .original-text element, not navigation/footer."""
    VOID = frozenset({"br", "hr", "img", "input", "meta", "link", "source", "wbr"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "original-text" in attrs.get("class", "").split() and not self.depth:
            self.depth = 1
            self.found += 1
        elif self.depth and tag not in self.VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        # HTML void/self-closing tags must not terminate the stored-text div.
        pass

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def text_quality_warning(html):
    """Potential corruption detector; never independently verifies the source."""
    parser = _TextOnly()
    parser.feed(html)
    if parser.found != 1 or parser.depth:
        return {"status": "needs_manual_review",
                "reasons": ["missing_or_ambiguous_stored_text"]}
    body = " ".join(" ".join(parser.parts).split())
    ellipses = len(re.findall(r"(?:\.\s*){3}|…", body))
    reasons = []
    if ellipses >= 5:
        reasons.append("many_teaser_ellipses_possible_page_feed")
    if len(body) < 80:
        reasons.append("short_stored_text")
    return {
        "status": "needs_manual_review" if reasons else "no_heuristic_warning",
        "reasons": reasons, "stored_text_characters": len(body),
        "ellipsis_count": ellipses,
        "warning": "This is not proof of completeness, authenticity or extraction error.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--max-span-days", type=int, default=2)
    ap.add_argument("--record-html", type=Path,
                    help="Optional existing record HTML for non-mutating text check")
    ap.add_argument("--out", type=Path,
                    help="Private JSON review file outside the repository")
    args = ap.parse_args(argv)
    if args.out:
        dest = args.out.resolve()
        if dest == ROOT or ROOT in dest.parents or dest.exists():
            ap.error("--out must not overwrite or live within the repository")
    report = duplicate_candidates(
        json.loads(args.index.read_text(encoding="utf-8")),
        day_span=args.max_span_days)
    if args.record_html:
        report["record_text_quality"] = text_quality_warning(
            args.record_html.read_text(encoding="utf-8"))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False,
                                       sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("candidate_groups", "recurring_headline_families")},
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
