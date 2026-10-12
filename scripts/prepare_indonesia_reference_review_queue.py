"""Produce a metadata-only Indonesian source-review queue from a pinned Git state.

The existing private reader verifies archived original text but exports only
publisher metadata; this workflow never repackages article bodies or grants
review/rights/publication approval. The resulting queue is *not* a site input.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from core.indonesia_official_index import load as load_public_links
from scripts.private_country_desk_reader import build

ROOT = Path(__file__).resolve().parents[1]
HELD_PATH = (
    "/2026/10/02/kunker-ke-kaltara-menhan-sjafrie-tinjau-yonif-tp-880-banuanta-"
    "di-bulungan-tegaskan-kemampuan-tempur-dan-teritorial-pembangunan-"
    "untuk-kedaulatan-perbatasan.html"
)
REQUIRED_ROW_FIELDS = frozenset((
    "country", "institution", "source_slug", "identity", "url", "title",
    "published_date", "first_seen_run", "state_commit", "review_status",
))
DISPOSITIONS = ("official_link_already_public_not_reviewed",
                "hold_publisher_geography_inconsistent",
                "new_source_review_candidate")


class QueueError(ValueError):
    """Source metadata changed or review queue would misstate readiness."""


def require(ok, reason):
    if not ok:
        raise QueueError(reason)


def prepare(reader_report, public_links):
    require(isinstance(reader_report, dict) and
            reader_report.get("status") == "private_research_not_source_admitted" and
            reader_report.get("schema") == "ipr-private-shadow-desk-reader/1" and
            reader_report.get("desk_filter") == "indonesia" and
            reader_report.get("query") == "" and
            reader_report.get("truncated") is False and
            reader_report.get("source_body_text_exported") is False and
            reader_report.get("human_source_review_completed") is False and
            reader_report.get("public_release_authorized") is False,
            "private reader provenance or admission fields changed")
    sources, records = reader_report.get("sources"), reader_report.get("results")
    require(type(sources) is list and len(sources) == 1 and
            type(sources[0]) is dict and
            sources[0].get("source_slug") == "id_kemhan_news" and
            type(records) is list and len(records) == reader_report.get("matched_total") ==
            sources[0].get("stored_records"), "incomplete Indonesia shadow snapshot")
    sha = sources[0].get("state_commit")
    require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha),
            "invalid immutable source revision")
    # The private pilot began with four links; the owner has separately released
    # eight fixed Berita publisher URLs. These are navigation, never review signoff.
    # Do not silently accept a truncated four-link list or arbitrary ninth URL.
    require(type(public_links) is list and len(public_links) == 8,
            "fixed eight-link public Berita directory changed")
    require(all(type(x) is dict and
                set(x) == {"id", "source_url", "title_original",
                           "published_date", "language"} and
                x["language"] == "id" for x in public_links),
            "public link metadata unexpectedly expanded or changed")
    released = {x["source_url"]: x for x in public_links}
    require(len(released) == 8, "duplicate public source link")
    found, rows = set(), []
    for row in records:
        require(type(row) is dict and set(row) == REQUIRED_ROW_FIELDS,
                "unrecognized source fields; potential article body leak")
        url = row["url"]
        parts = urlsplit(url)
        require(parts.scheme == "https" and parts.netloc == "www.kemhan.go.id" and
                not parts.query and not parts.fragment and
                row["identity"] == "kemhan:" + parts.path and
                row["country"] == "indonesia" and
                row["source_slug"] == "id_kemhan_news" and
                row["state_commit"] == sha and
                row["review_status"] == "not_human_reviewed_for_public_use",
                "source identity or review status diverged from pinned original")
        require(url not in found, "duplicate source identity")
        found.add(url)
        if url in released:
            published = released[url]
            require(row["title"] == published["title_original"] and
                    row["published_date"] == published["published_date"],
                    "public link title/date disagrees with archived original metadata")
            status = DISPOSITIONS[0]
        elif parts.path == HELD_PATH:
            status = DISPOSITIONS[1]
        else:
            status = DISPOSITIONS[2]
        rows.append({
            "publication_date": row["published_date"],
            "title_original": row["title"],
            "official_url": url,
            "source_identity": row["identity"],
            "first_seen_run": row["first_seen_run"],
            "disposition": status,
            "independent_human_review_complete": False,
            "publisher_body_reuse_authorized": False,
            "eligible_for_public_corpus": False,
        })
    require(set(released) <= found, "a live external-source link lacks archived provenance")
    require(sum(x["disposition"] == DISPOSITIONS[1] for x in rows) == 1,
            "held geographic discrepancy missing or duplicated")
    counts = {name: sum(x["disposition"] == name for x in rows) for name in DISPOSITIONS}
    return {
        "schema": "ipr-indonesia-private-review-queue/1",
        "state_commit": sha,
        "source_family": "id_kemhan_news",
        "stored_originals": len(rows),
        "counts": counts,
        "public_renderer_consumes_queue": False,
        "independent_human_review_completed": False,
        "source_reuse_approved": False,
        "public_corpus_admitted": False,
        "rows": rows,
    }


def destination(path):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink() and
            path.resolve() != ROOT and ROOT not in path.resolve().parents and
            not path.exists(), "output must be a new absolute path outside source checkout")
    require(path.parent.is_dir() and not path.parent.is_symlink(),
            "private queue parent directory must already exist")
    return path


def spreadsheet_value(value):
    """Prevent spreadsheet formula execution in publisher-controlled titles."""
    text = str(value)
    return "'" + text if text and (text[0] in "=+-@" or text[0].isspace()) else text


def write(queue, dest):
    target = destination(dest)
    target.mkdir(mode=0o700)
    (target / "review_queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (target / "review_queue.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("status", "publication_date", "title_original", "official_url",
                         "source_identity", "first_seen_run", "human_review_completed"))
        for item in queue["rows"]:
            writer.writerow(tuple(spreadsheet_value(v) for v in
                           (item["disposition"], item["publication_date"],
                            item["title_original"], item["official_url"],
                            item["source_identity"], item["first_seen_run"], "NO")))
    receipt = {key: queue[key] for key in
               ("schema", "state_commit", "source_family", "stored_originals",
                "counts", "public_renderer_consumes_queue",
                "independent_human_review_completed", "source_reuse_approved",
                "public_corpus_admitted")}
    (target / "COUNT_ONLY_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-repo", type=Path, required=True)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = "id_kemhan_news,%s,%s" % (args.state_repo, args.state_commit)
    report = build([spec], country="indonesia", max_results=300)
    packet = prepare(report, load_public_links())
    receipt = write(packet, args.out)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
