"""Metadata-only *live* proof for the Japan Coast Guard shadow adapter.

Three recent, named publisher originals; no production writes, no shadow writes,
no captures/artifact bodies. Strict all-or-nothing success. Runs only from an
explicit PR; it is not a scheduled shadow collector or qualification clock.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from types import SimpleNamespace

from core.collection import status as st
from core.collection.contract import CollectionWindow
from scraper.sources.jp_jcg_en import JCGEnglishAdapter

EXPECTED = {
    "jcg-en:9455": "2026-10-06",
    "jcg-en:9453": "2026-10-06",
    "jcg-en:9436": "2026-09-29",
}


def run(*, adapter=None):
    adapter = adapter or JCGEnglishAdapter(SimpleNamespace(
        slug="jp_jcg_press_en", enabled=True))
    discovered = adapter.discover(CollectionWindow(date(2026, 10, 8), 9))
    report = {
        "kind": "jcg-shadow-adapter-live-metadata-smoke/1",
        "source": "Japan Coast Guard English press archive",
        "archive_method": "none", "shadow_state_written": False,
        "production_state_written": False,
        "discovery_status": discovered.status,
        "robots_status": adapter.robots_status,
        "discover_count": len(discovered.references),
        "records": [],
    }
    if not discovered.ok:
        return report, False
    got = set()
    for ref in discovered.references:
        if len(report["records"]) >= 5:
            report["error"] = "unexpectedly many recent official releases"
            return report, False
        capture = adapter.fetch(ref)
        entry = {"url": ref.url, "fetch_status": capture.status}
        report["records"].append(entry)
        if capture.status != st.OK:
            return report, False
        extracted = adapter.extract(capture)
        entry["extraction_status"] = extracted.status
        if extracted.status != st.OK or len(extracted.documents) != 1:
            return report, False
        doc = extracted.documents[0]
        identity = doc.extra["source_identity"]
        entry.update({
            "source_identity": identity, "publication_date": doc.published_date,
            "original_language": doc.language_tag,
            "original_title_sha256": hashlib.sha256(
                doc.title_original.encode("utf-8")).hexdigest(),
            "original_text_sha256": doc.extra["content_sha256"],
            "capture_sha256": capture.payload_sha256,
            "original_text_chars": len(doc.text_original),
            "html_only": doc.extra["body_scope"] == "published_html_text_only",
            "uncollected_attachment_count": len(doc.extra["attachment_urls"]),
        })
        if identity in got or doc.published_date != EXPECTED.get(identity):
            return report, False
        got.add(identity)
    report["expected_ids_observed"] = sorted(got)
    return report, got == set(EXPECTED)


def main():
    report, passed = run()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if not passed:
        print("JCG exact-week adapter smoke did not pass; no source activated.",
              file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
