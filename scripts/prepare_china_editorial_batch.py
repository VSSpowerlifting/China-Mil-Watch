#!/usr/bin/env python3
"""Generate a PRIVATE 25-record China editorial intake packet without approvals.

Reads only the published compact index, existing record HTML and a frozen
diagnostic manifest. Never queries publishers, modifies canonical records,
assumes source veracity, writes output/, or chooses public archive records.
"""
import argparse
from collections import Counter
from datetime import date
from html import escape, unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "output" / "corpus-index.json"
MANIFEST = ROOT / "research/china/editorial-batch-01-2026-10-15.json"
RECORDS = ROOT / "output" / "record"
FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
LANES = {
    "screened_out_primary_source", "historical_capture_quality",
    "republication_comparison", "source_fidelity_unknown",
    "primary_source_significance", "brief_trail_review",
    "media_and_rights_review", "keyword_false_positive_control",
    "strong_military_forum_commentary", "august_first_commentary",
    "military_camp_observation", "foreign_ministry_primary_issuer",
    "taiwan_affairs_office_primary_issuer",
}


def _day(value, name):
    try:
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError("%s must be an ISO date" % name) from None


def _url(value, name):
    if not isinstance(value, str):
        raise ValueError(name + " not a URL")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError(name + " URL malformed") from None
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError(name + " must be an HTTP(S) publisher URL")


class Body(HTMLParser):
    """Identify stored original-text only; never infer missing source prose."""
    VOID = frozenset(("br", "hr", "img", "input", "meta", "link", "wbr", "source"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.hits = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "original-text" in attrs.get("class", "").split() and not self.depth:
            self.hits += 1
            self.depth = 1
        elif self.depth and tag not in self.VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def record_custody(html):
    """Get provenance and diagnostic text length from immutable rendered HTML."""
    source = re.search(
        r'<th scope="row">Original URL</th>\s*<td class="prov-value">\s*<a href="([^"]+)"',
        html)
    collected = re.search(
        r'<th scope="row">Collected at</th>\s*<td class="prov-value">'
        r'\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})', html)
    if source is None or collected is None:
        raise ValueError("record is missing original URL or collected-at provenance")
    original = unescape(source.group(1))
    _url(original, "captured original")
    _day(collected.group(1), "capture date")
    parser = Body()
    parser.feed(html)
    if parser.hits > 1 or parser.depth:
        raise ValueError("ambiguous captured original-text block")
    stored = " ".join(" ".join(parser.parts).split()) if parser.hits else ""
    if not parser.hits:
        body_status = "no_readable_original_text_block"
    elif not stored:
        body_status = "empty_original_text_block"
    else:
        body_status = "stored_text_present_not_verified"
    return {
        "original_url": original,
        "collected_at": collected.group(1) + " " + collected.group(2),
        "stored_text_status": body_status,
        "stored_characters": len(stored),
        "teaser_ellipsis_count": len(re.findall(r"(?:\.\s*){3}|…", stored)),
    }


def validate_batch(index, batch, pages):
    if index.get("fields") != FIELDS:
        raise ValueError("compact corpus field schema changed")
    trail = index.get("trail_ids")
    if not isinstance(trail, list) or len(trail) != len(set(trail)):
        raise ValueError("published source-trail protections missing or invalid")
    if not isinstance(batch, dict) or set(batch) != {
        "version", "scope", "purpose", "publication_enabled", "owner_approved",
        "baseline_snapshot", "batch_id", "created_on", "entries",
        "protected_source_trail_ids",
    }:
        raise ValueError("diagnostic intake schema changed")
    if (batch["version"] != 1 or batch["scope"] != "china"
            or batch["purpose"] != "diagnostic_editorial_intake_not_selection"
            or batch["publication_enabled"] is not False
            or batch["owner_approved"] is not False):
        raise ValueError("diagnostic batch may never be a publication approval")
    baseline, current = batch["baseline_snapshot"], index.get("snapshot")
    if (not isinstance(baseline, dict) or not isinstance(current, dict)
            or type(baseline.get("records")) is not int
            or type(current.get("records")) is not int):
        raise ValueError("missing or invalid corpus snapshot counts")
    _day(baseline.get("date"), "intake baseline date")
    _day(current.get("date"), "current index date")
    if (current["date"] < baseline["date"]
            or current["records"] < baseline["records"]):
        raise ValueError("index snapshot drift backwards; re-review before intake")
    frozen_trails = batch["protected_source_trail_ids"]
    if (not isinstance(frozen_trails, list)
            or len(frozen_trails) != len(set(frozen_trails))
            or any(type(ident) is not int for ident in frozen_trails)
            or not set(frozen_trails).issubset(trail)):
        raise ValueError("protected historic Brief citations missing or malformed")
    if batch["batch_id"] not in (
            "china-2026-10-15-01", "china-2026-10-15-02"):
        raise ValueError("unexpected batch ID")
    _day(batch["created_on"], "batch date")
    if not isinstance(batch["entries"], list) or len(batch["entries"]) != 25:
        raise ValueError("batch 01 requires exactly 25 explicit editorial research cases")

    sources, states = index["sources"], index["states"]
    catalog = {}
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("malformed corpus record")
        rid, pub, source_i, state_i, en, original = row
        if (type(rid) is not int or rid <= 0 or rid in catalog
                or type(source_i) is not int or type(state_i) is not int
                or not 0 <= source_i < len(sources)
                or not 0 <= state_i < len(states)):
            raise ValueError("duplicate record ID or source/state index corrupted")
        _day(pub, "record publication date")
        if not isinstance(en, str) or not isinstance(original, str):
            raise ValueError("record title not a string")
        catalog[rid] = row
    if not set(trail).issubset(catalog):
        raise ValueError("a published Brief source-trail ID has disappeared")
    if current["records"] != len(catalog):
        raise ValueError("index snapshot record count does not match corpus records")
    if not set(frozen_trails).issubset(catalog):
        raise ValueError("protected intake source trail no longer exists")
    decisions, rendered, seen = [], [], set()
    for proposal in batch["entries"]:
        required = {
            "id", "source", "published_date", "source_title", "review_lane",
            "review_question", "compare_ids", "editorial_decision",
            "reviewer", "reviewed_on",
        }
        if not isinstance(proposal, dict) or set(proposal) != required:
            raise ValueError("intake item fields missing or unrecognized")
        rid = proposal["id"]
        if type(rid) is not int or rid in seen or rid not in catalog:
            raise ValueError("unknown or duplicate intake record ID")
        seen.add(rid)
        row = catalog[rid]
        src = sources[row[2]]
        if (src.get("desk") or {}).get("code") != "china":
            raise ValueError("batch cannot include a non-China desk")
        if (proposal["source"] != src["code"]
                or proposal["published_date"] != row[1]
                or proposal["source_title"] != (row[5] or row[4])):
            raise ValueError("title/date/source identity drift since intake proposal")
        if proposal["review_lane"] not in LANES:
            raise ValueError("unknown research lane")
        question = proposal["review_question"]
        if not isinstance(question, str) or len(question.strip()) < 65:
            raise ValueError("source-specific review question too vague")
        if any(proposal[k] is not None for k in (
                "editorial_decision", "reviewer", "reviewed_on")):
            raise ValueError("intake cannot contain reviewer or approval decisions")
        related = proposal["compare_ids"]
        if (not isinstance(related, list) or len(related) != len(set(related))
                or any(type(x) is not int or x == rid for x in related)):
            raise ValueError("invalid cross-record comparison references")
        if rid not in pages:
            raise ValueError("missing preserved record HTML")
        original = record_custody(pages[rid])
        rendered.append({
            "id": rid, "date": row[1], "title": row[5] or row[4],
            "english": row[4] if row[5] and row[4] != row[5] else "",
            "source": src["code"], "processing_state": states[row[3]]["code"],
            "protected_brief_trail": rid in trail, "review_lane": proposal["review_lane"],
            "review_question": question, "compare_ids": related, **original,
            "editorial_decision": None, "human_original_review": "pending",
        })
    actual_protected = {row["id"] for row in rendered
                        if row["protected_brief_trail"]}
    if actual_protected != set(frozen_trails):
        raise ValueError("intake's exact protected Brief-trail set has changed")
    for proposal in batch["entries"]:
        for other in proposal["compare_ids"]:
            if other not in seen:
                raise ValueError("related record must be in same batch")
            reciprocal = next(p for p in batch["entries"] if p["id"] == other)
            if proposal["id"] not in reciprocal["compare_ids"]:
                raise ValueError("compare references must be reciprocal")
    return {
        "version": 1, "batch_id": batch["batch_id"], "purpose": "private_diagnostic_only",
        "publication_enabled": False, "owner_approved": False,
        "source_snapshot": index["snapshot"],
        "baseline_snapshot": baseline,
        "snapshot_advanced": current != baseline,
        "preserved_records": len(catalog),
        "batch_records": len(rendered), "protected_brief_trail": sum(
            x["protected_brief_trail"] for x in rendered),
        "review_lane_counts": dict(sorted(Counter(
            r["review_lane"] for r in rendered).items())),
        "source_counts": dict(sorted(Counter(r["source"] for r in rendered).items())),
        "missing_or_empty_stored_text": sum(
            r["stored_text_status"] != "stored_text_present_not_verified"
            for r in rendered),
        "source_review_status": "all_pending",
        "entries": rendered,
    }


def _h(x):
    return escape(str(x), quote=True)


def private_html(report):
    cards = []
    for e in report["entries"]:
        secondary = ("<p class='detail' lang='en'>English title: %s</p>" %
                     _h(e["english"])) if e["english"] else ""
        refs = (", ".join("<a href='https://indopacificrecord.org/record/%d.html'>#%d</a>" %
                          (rid, rid) for rid in e["compare_ids"])) if e["compare_ids"] else "None"
        cards.append(
            "<li class='case'><h2>#%d — %s</h2>%s"
            "<p class='detail'>%s · %s · %s</p>"
            "<p><strong>Review lane:</strong> %s · <strong>Published Brief citation:</strong> %s</p>"
            "<p><strong>Stored article:</strong> <a href='https://indopacificrecord.org/record/%d.html'>Record #%d</a>"
            " · <strong>Publisher URL:</strong> <a rel='noopener noreferrer nofollow' href='%s'>Original link</a></p>"
            "<p><strong>Collected:</strong> %s · <strong>Historical text:</strong> %s (%d chars; %d ellipses)</p>"
            "<p><strong>Related records to compare:</strong> %s</p>"
            "<p class='question'><strong>Editorial research question:</strong> %s</p>"
            "<p class='pending'>Human original-language verification pending · No editorial decision · Not public</p></li>" %
            (e["id"], _h(e["title"]), secondary,
             _h(e["date"]), _h(e["source"]), _h(e["processing_state"]),
             _h(e["review_lane"].replace("_", " ")),
             "Yes" if e["protected_brief_trail"] else "No",
             e["id"], e["id"], _h(e["original_url"]), _h(e["collected_at"]),
             _h(e["stored_text_status"].replace("_", " ")),
             e["stored_characters"], e["teaser_ellipsis_count"],
             refs, _h(e["review_question"])))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline';base-uri 'none';form-action 'none'\">"
        "<title>IPR PRIVATE China editorial intake batch</title>"
        "<style>body{margin:0;background:#f7f6f1;color:#193140;font-family:system-ui,sans-serif}"
        "main,header{max-width:920px;margin:auto;padding:20px}h1{font-size:2.2rem}"
        "a{color:#126078}a:focus-visible{outline:3px solid #bb793f}"
        ".warn{padding:18px;border-left:5px solid #8e4e38;background:#ede7dd}"
        ".case{padding:25px 0;border-bottom:1px solid #bbcbd0;list-style:none}"
        ".detail{color:#52626a;font-size:.9rem}.question{line-height:1.55}"
        ".pending{font-size:.85rem;font-weight:700;color:#753d35}"
        "ol{padding:0}.stats{font-weight:650}</style></head><body>"
        "<header><p>Indo-Pacific Record · Private editorial research</p>"
        "<h1>China research batch 01 — 25 cases</h1>"
        "<p class='warn'><strong>PRIVATE DRAFT. NOT A SELECTION OR PUBLICATION.</strong> "
        "These records were chosen to investigate false negatives, extraction fidelity, "
        "source custody and republications. They are not a statistically representative "
        "sample, and their inclusion here says nothing about editorial acceptance.</p>"
        "<p class='stats'>%d case records · %d preserved source records · %d protected Brief citations</p>"
        "<p>All historical source/record URLs are preserved; no approval has been entered. "
        "This offline page contains no article prose and is readable without JavaScript.</p>"
        "</header><main><ol>%s</ol></main></body></html>" %
        (report["batch_records"], report["preserved_records"],
         report["protected_brief_trail"], "".join(cards))
    )


def write_private(directory, report):
    out = Path(directory).expanduser()
    if not out.is_absolute():
        raise ValueError("private review output directory must be absolute")
    root = ROOT.resolve()
    resolved = out.resolve()
    if (out.exists() or out.is_symlink() or resolved == root or root in resolved.parents
            or resolved in root.parents or not out.parent.is_dir()
            or out.parent.is_symlink()):
        raise ValueError("private review output requires a fresh external directory")
    out.mkdir(mode=0o700)
    for name, contents in (
        ("review.html", private_html(report)),
        ("summary.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
    ):
        flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
        fd = os.open(out / name, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(contents)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=INDEX)
    ap.add_argument("--batch", type=Path, default=MANIFEST)
    ap.add_argument("--records-dir", type=Path, default=RECORDS)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    pages = {}
    for e in batch.get("entries", []):
        rid = e.get("id")
        if type(rid) is not int:
            raise ValueError("invalid batch record ID")
        pages[rid] = (args.records_dir / ("%d.html" % rid)).read_text(encoding="utf-8")
    report = validate_batch(index, batch, pages)
    output = write_private(args.output_dir, report)
    print(json.dumps({
        "batch": report["batch_id"], "cases": report["batch_records"],
        "source_snapshot": report["source_snapshot"],
        "proposed_editorial_selection": False,
        "all_human_reviews_pending": True,
        "private_review_page": str(output / "review.html"),
        "preserved_corpus_unchanged": True,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
