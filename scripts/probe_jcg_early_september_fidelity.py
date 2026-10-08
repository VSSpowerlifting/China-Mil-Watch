"""Two missing early-September JCG publisher releases: read-only original proof.

The first *persistent* JCG shadow run (2026-10-08) archived only three
Sept29/Oct6 releases, because its 9-day window did not reach Sept7/Sept18.
This script checks the two earlier items from the same first-party English
source index, at the SAME fixed logical source cutoff, without:
 - touching the shadow SQLite database, captures, ledger or Day 0 clock
 - spoofing a historical collection day or changing the normal 30-day cap
 - feeding the weekly writer, production, or public output.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.manifests import load_manifest
from scraper.sources.jp_jcg_en import JCGEnglishAdapter

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = date(2026, 10, 8)
HISTORICAL_WINDOW = 38
EXPECTED_ALL = {
    "jcg-en:9455": "2026-10-06",
    "jcg-en:9453": "2026-10-06",
    "jcg-en:9436": "2026-09-29",
    "jcg-en:9424": "2026-09-18",
    "jcg-en:9399": "2026-09-07",
}
TO_CHECK = {"jcg-en:9424", "jcg-en:9399"}


def inspect(*, adapter=None):
    if adapter is None:
        config = load_manifest(ROOT / "shadow/jp_jcg/manifest.json")
        adapter = JCGEnglishAdapter(config.sources[0])
    discovery = adapter.discover(CollectionWindow(CUTOFF, HISTORICAL_WINDOW))
    result = {
        "schema": "jcg-early-september-source-fidelity/1",
        "purpose": "read_only_pre_backfill_source_original_validation",
        "index_cutoff": CUTOFF.isoformat(),
        "normal_collector_lookback_modified": False,
        "shadow_state_written": False, "production_state_written": False,
        "publishing_or_editorial_approval": False,
        "discovery_status": discovery.status,
        "discovered": len(discovery.references),
        "records": [],
    }
    if not discovery.ok:
        result["failure"] = "official_listing_unavailable"
        return result, False
    found = {}
    for ref in discovery.references:
        parts = ref.url.split("/")
        key = "jcg-en:" + parts[-1].removeprefix("article").removesuffix(".html")
        if key in found or key not in EXPECTED_ALL or str(ref.hint_published_date) != EXPECTED_ALL[key]:
            result["failure"] = "unexpected_listing_identity_or_date"
            return result, False
        found[key] = ref
    result["discovered_ids"] = sorted(found)
    if set(found) != set(EXPECTED_ALL):
        result["failure"] = "unexpected_publisher_index_scope"
        return result, False
    for identity in sorted(TO_CHECK):
        ref = found[identity]
        capture = adapter.fetch(ref)
        item = {"identity": identity, "source_url": ref.url,
                "fetch_status": capture.status}
        result["records"].append(item)
        if capture.status != st.OK:
            result["failure"] = "original_http_not_collected"
            return result, False
        extraction = adapter.extract(capture)
        item["extraction_status"] = extraction.status
        if extraction.status != st.OK or len(extraction.documents) != 1:
            result["failure"] = "original_body_extraction_failed"
            return result, False
        doc = extraction.documents[0]
        meta = doc.extra
        if (meta.get("source_identity") != identity or
                doc.published_date != EXPECTED_ALL[identity] or
                doc.language_tag != "en" or
                doc.source_slug != "jp_jcg_press_en" or
                meta.get("issuer") != "Japan Coast Guard" or
                meta.get("body_scope") != "published_html_text_only" or
                meta.get("attachments_collected") is not False or
                len(doc.text_original) < 180):
            result["failure"] = "publisher_identity_date_or_scope_mismatch"
            return result, False
        content_digest = hashlib.sha256(doc.text_original.encode("utf-8")).hexdigest()
        if content_digest != meta.get("content_sha256"):
            result["failure"] = "original_text_digest_mismatch"
            return result, False
        item.update({
            "published_date": doc.published_date,
            "original_text_chars": len(doc.text_original),
            "original_text_sha256": content_digest,
            "capture_sha256": capture.payload_sha256,
            "publisher_machine_date_verdict": meta.get("html_datetime_verdict"),
            "linked_pdf_count_not_collected": len(meta.get("attachment_urls", [])),
            "source_body_scope": meta["body_scope"],
        })
    return result, True


def main():
    report, passed = inspect()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("No shadow records, source bodies or PDFs were persisted.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
