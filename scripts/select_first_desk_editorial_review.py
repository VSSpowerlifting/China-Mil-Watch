"""Select *unsigned*, source-pinned review priorities from real AFP/Indonesia dockets.

Inputs are locally downloaded metadata-only GitHub Actions artifacts; this
script does not fetch anything, contact publishers, copy originals, decide
rights, record human approvals, or feed the public renderer. It deliberately
fails closed if a docket cannot be reconciled with its frozen source version.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AFP_PACKET = ROOT / "research/philippines/sanlakas_2026/source_event_candidates.json"
AFP_PIN = "492001f34ba6176169b6acc96a237f05592a3395"
ID_PIN = "0595c6677be24f8f0f33aecb28eec0050e36e8f9"
AFP_IDS = ("afp:1390", "afp:1391", "afp:1393", "afp:1394")
ID_URLS = (
    "https://www.kemhan.go.id/2026/10/14/kemhan-dorong-penguatan-kerja-sama-teknik-militer-dan-industri-pertahanan-pada-mtc-ke-17-ri-rusia.html",
    "https://www.kemhan.go.id/2026/10/14/sekjen-kemhan-resmi-tutup-mtc-ke-17-ri-rusia-dorong-penguatan-kerja-sama-teknik-militer-dan-industri-pertahanan.html",
    "https://www.kemhan.go.id/2026/10/14/menhan-ri-terima-kunjungan-wakil-direktur-fsmtc-federasi-rusia.html",
)
EXPECTED_AFP_BATCHES = (
    ("2026-10-07", "37631681338-1", AFP_PIN, 13),
    ("2026-10-08", "37788547061-1", "c668790ce3be88b08b3300b945bad58589b3a5b1", 5),
    ("2026-10-14", "38562843186-1", "4dd40b9655ec53fe4fae829eb12ba21032946b25", 4),
)
ID_COUNTS = {
    "official_link_already_public_not_reviewed": 15,
    "hold_publisher_geography_inconsistent": 1,
    "new_source_review_candidate": 15,
}
AFP_ROW_KEYS = frozenset((
    "source_identity", "title_original", "source_url", "published_date",
    "text_sha256", "capture_sha256", "review_status", "body_status",
    "extraction_review_priority", "human_review_authenticated",
))
ID_ROW_KEYS = frozenset((
    "publication_date", "title_original", "official_url", "source_identity",
    "first_seen_run", "disposition", "independent_human_review_complete",
    "publisher_body_reuse_authorized", "eligible_for_public_corpus",
))


class ReviewHold(ValueError):
    """Review input is not an authenticated exact-cohort unsigned docket."""


def require(condition, message):
    if not condition:
        raise ReviewHold(message)


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size < 3_000_000, "invalid docket file")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ReviewHold("invalid JSON docket") from exc


def select(afp, indonesia, packet):
    """Return seven *pending* reference cards; no human or rights decisions."""
    require(type(afp) is dict and
            afp.get("protocol") == "ipr_ph_afp_metadata_review_docket_v1" and
            afp.get("total_source_records") == 22 and
            afp.get("body_unavailable_records") == 0 and
            afp.get("source") == "philippines_afp_shadow" and
            afp.get("source_bodies_or_raw_api_responses_included") is False and
            afp.get("human_review_completed") is False and
            afp.get("source_reuse_approved") is False and
            afp.get("production_eligible") is False and
            afp.get("weekly_ai_writer_eligible") is False and
            afp.get("automated_review_decisions") == 0,
            "AFP review docket cannot be considered unsigned and intact")
    require(type(packet) is dict and
            packet.get("status") == "unsigned_research_candidate_requires_human_review" and
            packet.get("archive", {}).get("state_commit") == AFP_PIN and
            all(value is False for value in packet.get("permissions", {}).values()) and
            type(packet.get("records")) is list and
            len(packet["records"]) == 4,
            "existing AFP research packet does not match frozen source scope")
    pinned = {r.get("id"): r for r in packet["records"]}
    require(set(pinned) == set(AFP_IDS), "AFP editorial citation identities changed")
    batches = afp.get("batches")
    require(type(batches) is list and len(batches) == 3,
            "AFP review roster must contain exactly three known batches")
    seen, indexed = set(), {}
    for batch, (day, run, sha, count) in zip(batches, EXPECTED_AFP_BATCHES):
        require(type(batch) is dict and
                (batch.get("target_date"), batch.get("run_id"),
                 batch.get("historical_state_commit"), batch.get("new_records")) ==
                (day, run, sha, count) and
                type(batch.get("records")) is list and
                len(batch["records"]) == count,
                "AFP batch chronology, state commit or total changed")
        for row in batch["records"]:
            require(type(row) is dict and set(row) == AFP_ROW_KEYS and
                    type(row["source_identity"]) is str and
                    row["source_identity"] not in seen and
                    row["review_status"] == "not_started" and
                    row["human_review_authenticated"] is False,
                    "AFP original missing, duplicated or falsely signed")
            seen.add(row["source_identity"])
            indexed[row["source_identity"]] = (row, day, sha)
    require(len(seen) == 22, "AFP full roster is not 22 unique originals")
    afp_cards = []
    for source_id in AFP_IDS:
        require(source_id in indexed, "AFP cited original absent from actual docket")
        row, day, sha = indexed[source_id]
        ref = pinned[source_id]
        require(sha == AFP_PIN and day == "2026-10-07" and
                row["source_url"] == ref["source_url"] and
                row["title_original"] == ref["title"] and
                row["text_sha256"] == ref["content_sha256"] and
                row["capture_sha256"] == ref["capture_sha256"] and
                row["body_status"] == "text",
                "AFP article has wrong URL/title/hash or is not in Day 0")
        afp_cards.append({
            "source_id": source_id,
            "publisher_url": row["source_url"],
            "title_original": row["title_original"],
            "published_on": row["published_date"],
            "state_commit": sha,
            "body_sha256_reference": row["text_sha256"],
            "capture_sha256_reference": row["capture_sha256"],
            "review_state": "pending_named_original_version_review",
        })

    require(type(indonesia) is dict and
            indonesia.get("schema") == "ipr-indonesia-private-review-queue/1" and
            indonesia.get("state_commit") == ID_PIN and
            indonesia.get("source_family") == "id_kemhan_news" and
            indonesia.get("stored_originals") == 31 and
            indonesia.get("counts") == ID_COUNTS and
            indonesia.get("public_renderer_consumes_queue") is False and
            indonesia.get("independent_human_review_completed") is False and
            indonesia.get("source_reuse_approved") is False and
            indonesia.get("public_corpus_admitted") is False,
            "Indonesia queue is not the unsigned Oct 14 31-original cohort")
    rows = indonesia.get("rows")
    require(type(rows) is list and len(rows) == 31,
            "Indonesia review cohort incomplete")
    all_urls, selected = set(), {}
    for row in rows:
        require(type(row) is dict and set(row) == ID_ROW_KEYS and
                type(row["official_url"]) is str and
                row["official_url"] not in all_urls and
                row["independent_human_review_complete"] is False and
                row["publisher_body_reuse_authorized"] is False and
                row["eligible_for_public_corpus"] is False and
                row["disposition"] in ID_COUNTS,
                "Indonesia review row unrecognized or falsely approved")
        all_urls.add(row["official_url"])
        selected[row["official_url"]] = row
    require(len(all_urls) == 31 and
            {status: sum(x["disposition"] == status for x in rows)
             for status in ID_COUNTS} == ID_COUNTS,
            "Indonesia docket disposition counts contradict rows")
    id_cards = []
    for url in ID_URLS:
        require(url in selected, "cited Kemhan original absent from real review queue")
        row = selected[url]
        require(row["publication_date"] == "2026-10-14" and
                row["disposition"] == "new_source_review_candidate" and
                row["source_identity"] == "kemhan:" + url.split("www.kemhan.go.id", 1)[1],
                "Kemhan publication metadata/identity/disposition does not match")
        id_cards.append({
            "source_id": row["source_identity"],
            "publisher_url": url,
            "title_original": row["title_original"],
            "published_on": row["publication_date"],
            "state_commit": ID_PIN,
            # The queue does not expose original-byte hashes; do not invent one.
            "capture_sha256_reference": None,
            "review_state": "pending_named_original_version_review",
        })
    return {
        "schema": "ipr-first-editorial-seven-unsigned-review-priorities/1",
        "source": "two_completed_metadata_dockets_required",
        "approved_for_publication": False,
        "source_text_or_media_exported": False,
        "original_version_parity_verified_by_this_script": False,
        "human_review_complete": False,
        "reuse_rights_cleared": False,
        "production_source_admitted": False,
        "philippines": {"draft_pr": 661, "records": afp_cards},
        "indonesia": {"draft_pr": 652, "records": id_cards},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--afp-docket", required=True, type=Path)
    parser.add_argument("--indonesia-queue", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = select(read_json(args.afp_docket),
                        read_json(args.indonesia_queue),
                        read_json(AFP_PACKET))
    except (ReviewHold, OSError, TypeError, KeyError) as exc:
        parser.exit(1, "Editorial review subset held: %s\n" % exc)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
