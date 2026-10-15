"""Offline Korea MND regression: portal HTML drift must not revise HWPX originals.

Real Oct 13/14 Korea-ledger metadata showed five changed HTML response hashes
but identical original HWPX hashes.  Synthetic replay protects that boundary
without copying those nine new documents or contacting any publisher.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from tests.test_indonesia_korea_shadow import (
    Case, Response, ROWS, TARGET, adapter, fixture, kr_url, runner,
)


class KoreaMNDPortalWrapperDriftTests(Case):
    def test_changed_publisher_html_does_not_revise_unchanged_hwpx_original(self):
        article_row = next(
            x for x in ROWS if x.get("capture") == "korea-article-1.bin"
        )
        url = kr_url(article_row["url"])
        original_html = fixture("korea-article-1.bin")
        changed_html = original_html + (
            b"\n<!-- synthetic publisher page chrome changed; "
            b"not original government release content -->\n"
        )
        self.assertNotEqual(hashlib.sha256(original_html).hexdigest(),
                            hashlib.sha256(changed_html).hexdigest())

        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "isolated-korea-only"
            first_adapter, first_session = adapter("korea")
            first = runner.run(
                "korea", state, TARGET, 0, 40,
                "original-capture", "synthetic-collector-sha",
                adapter=first_adapter,
            )
            self.assertEqual(first["health"], "ok")
            self.assertEqual(first["inserted"], 1)
            self.assertEqual(first["stored_total"], 1)

            with sqlite3.connect(state / "shadow.db") as db:
                original_record = db.execute(
                    "SELECT source_identity, url, title_original, text_original, "
                    "published_date, metadata_json, content_sha256, capture_sha256 "
                    "FROM shadow_records"
                ).fetchall()
            self.assertEqual(len(original_record), 1)

            replay_adapter, replay_session = adapter(
                "korea", {url: Response(url, changed_html)}
            )
            replay = runner.run(
                "korea", state, TARGET, 0, 40,
                "new-page-chrome", "synthetic-collector-sha",
                adapter=replay_adapter,
            )
            self.assertEqual(replay["health"], "ok")
            self.assertEqual(replay["inserted"], 0)
            self.assertEqual(replay["updated"], 0)
            self.assertEqual(replay["duplicates"], 1)
            self.assertEqual(replay["stored_total"], 1)
            self.assertEqual(replay["fetch_failures"], 0)
            self.assertEqual(replay["extraction_failures"], 0)
            self.assertEqual(replay["access_failures"], 0)
            self.assertEqual(replay["state_sha256_before"],
                             replay["state_sha256_after"])
            with sqlite3.connect(state / "shadow.db") as db:
                updated_record = db.execute(
                    "SELECT source_identity, url, title_original, text_original, "
                    "published_date, metadata_json, content_sha256, capture_sha256 "
                    "FROM shadow_records"
                ).fetchall()
            self.assertEqual(original_record, updated_record)

            original_request = next(
                r for r in first["requests"] if r["requested_url"] == url
            )
            wrapper_request = next(
                r for r in replay["requests"] if r["requested_url"] == url
            )
            self.assertNotEqual(
                original_request["capture_sha256"],
                wrapper_request["capture_sha256"],
            )
            self.assertEqual(
                original_request["capture_sha256"],
                hashlib.sha256(original_html).hexdigest(),
            )
            self.assertEqual(
                wrapper_request["capture_sha256"],
                hashlib.sha256(changed_html).hexdigest(),
            )

            first_documents = [
                r for r in first["requests"]
                if "/common/download.do" in r["requested_url"]
            ]
            replay_documents = [
                r for r in replay["requests"]
                if "/common/download.do" in r["requested_url"]
            ]
            self.assertEqual(len(first_documents), 1)
            self.assertEqual(len(replay_documents), 1)
            self.assertEqual(
                first_documents[0]["capture_sha256"],
                replay_documents[0]["capture_sha256"],
            )
            self.assertEqual(
                first_documents[0]["requested_url"],
                replay_documents[0]["requested_url"],
            )

            # Neither this machine-only test nor any replay is a source-rights
            # determination, human Korean-language original review, or release.
            self.assertEqual(
                json.loads(updated_record[0][5])["body_scope"],
                "published_hwpx_text",
            )
            self.assertEqual(len(first_session.calls), len(replay_session.calls))


if __name__ == "__main__":
    import unittest
    unittest.main()
