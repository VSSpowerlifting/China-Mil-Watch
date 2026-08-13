"""
Deterministic offline end-to-end test.

Drives one saved source page through the whole chain — discovery, capture,
extraction, deduplication, storage, an analysis *stub*, and static publication
— against a temporary database and a temporary output directory.

Three properties make this suitable for CI:

  * **No network.** The adapter's listing and fetch are served from
    `tests/fixtures/html/`, and the parser is the real PLA Daily parser.
  * **No paid model calls.** Analysis is a deterministic stub. This test proves
    the plumbing, not the model.
  * **No shared state.** Temporary database, temporary output directory; the
    production `pla_watch.db` and `output/` are never touched.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.legacy import LegacyScraperAdapter                 # noqa: E402
from core.collection import status as st                         # noqa: E402
from core.collection.contract import CollectionWindow            # noqa: E402
from core.collection.health import (                             # noqa: E402
    aggregate_status, human_report, machine_report,
)
from core.manifests import load_manifest                         # noqa: E402
from migrations.runner import apply_all, connect, verify         # noqa: E402
from processing.metadata import normalize_article                # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "html" / "pla_daily_article.html"
LEGACY_SCHEMA = REPO_ROOT / "tests" / "fixtures" / "legacy_schema.sql"
ARTICLE_URL = "http://www.81.cn/yw_208727/16473227.html"
CHINA = load_manifest(REPO_ROOT / "desks" / "china" / "manifest.json")


def offline_pla_daily_class(html: str, urls):
    """Real PLA Daily parser with its network calls replaced by fixtures."""
    from scraper.sources.pla_daily import PLADailyScraper

    class OfflinePLADaily(PLADailyScraper):
        def get_article_urls(self):
            return list(urls)

        def fetch(self, url, force_refresh=False):
            return html if url in urls else None

    return OfflinePLADaily


class TestEndToEndOffline(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "e2e.db"

        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(LEGACY_SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
        conn.close()

        conn = connect(self.db_path)
        apply_all(conn)
        conn.close()

        self.html = FIXTURE.read_text(encoding="utf-8", errors="replace")
        self.window = CollectionWindow(target_date=date(2026, 5, 10))

    def tearDown(self):
        self._tmp.cleanup()

    def _adapter(self, urls=(ARTICLE_URL,)):
        return LegacyScraperAdapter(
            CHINA.source_by_slug("pla_daily"),
            scraper_class=offline_pla_daily_class(self.html, urls),
        )

    def _store(self, articles, run_id=1):
        """Minimal stand-in for storage.db.insert_article against the temp DB."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        src_id = conn.execute(
            "SELECT id FROM sources WHERE slug='pla_daily'"
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO scrape_runs (id, status) VALUES (?, 'running')",
            (run_id,),
        )
        stored = []
        for a in articles:
            try:
                cur = conn.execute(
                    "INSERT INTO articles (url, content_hash, source_id, "
                    "scrape_run_id, title_original, text_original, published_date) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (a["url"], a["content_hash"], src_id, run_id,
                     a["title_original"], a["text_original"], a["published_date"]),
                )
                stored.append(cur.lastrowid)
            except sqlite3.IntegrityError:
                pass          # duplicate URL — the dedup path
        conn.commit()
        conn.close()
        return stored

    # ── the chain ────────────────────────────────────────────────────────────

    def test_discovery_capture_extraction(self):
        adapter = self._adapter()

        discovery = adapter.discover(self.window)
        self.assertEqual(discovery.status, st.OK)
        self.assertEqual(len(discovery.references), 1)

        capture = adapter.fetch(discovery.references[0])
        self.assertTrue(capture.ok)
        self.assertEqual(capture.http_status, None)   # offline capture
        self.assertTrue(capture.payload_sha256)
        self.assertEqual(capture.payload_bytes, len(self.html.encode("utf-8")))

        extraction = adapter.extract(capture)
        self.assertEqual(extraction.status, st.OK)
        self.assertEqual(len(extraction.documents), 1)
        self.assertTrue(extraction.documents[0].title_original.strip())

    def test_capture_hash_is_deterministic(self):
        """Same input, same hash — the property Phase 3 capture storage needs."""
        a = self._adapter()
        first = a.fetch(a.discover(self.window).references[0])
        b = self._adapter()
        second = b.fetch(b.discover(self.window).references[0])
        self.assertEqual(first.payload_sha256, second.payload_sha256)

    def test_full_chain_to_storage(self):
        adapter = self._adapter()
        result, documents = adapter.collect(self.window)

        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(documents), 1)

        normalized = [normalize_article(d.as_article_dict()) for d in documents]
        self.assertTrue(normalized[0]["content_hash"])

        stored = self._store(normalized)
        self.assertEqual(len(stored), 1)

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT url, title_original, text_original, passed_relevance "
            "FROM articles WHERE id = ?", (stored[0],)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], ARTICLE_URL)
        self.assertTrue(row[1])
        self.assertGreater(len(row[2]), 200)
        self.assertIsNone(row[3], "relevance must be unset before analysis")

    def test_deduplication_on_second_run(self):
        """The same article collected twice must be stored once."""
        adapter = self._adapter()
        _, documents = adapter.collect(self.window)
        normalized = [normalize_article(d.as_article_dict()) for d in documents]

        first = self._store(normalized, run_id=1)
        second = self._store(normalized, run_id=2)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0, "duplicate URL must not be re-stored")

        conn = sqlite3.connect(str(self.db_path))
        n = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE url = ?", (ARTICLE_URL,)
        ).fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)

    def test_analysis_stub_writes_provenance(self):
        """
        Stands in for the LLM stage. Asserts that model and prompt identifiers
        are recorded — the provenance the schema already carries and which
        reanalysis must not lose.
        """
        adapter = self._adapter()
        _, documents = adapter.collect(self.window)
        normalized = [normalize_article(d.as_article_dict()) for d in documents]
        aid = self._store(normalized)[0]

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "UPDATE articles SET passed_relevance=1, relevance_score=0.9, "
            "title_english=?, text_english=?, summary_english=?, "
            "analyzed_at=datetime('now'), model_id=?, prompt_version=? "
            "WHERE id=?",
            ("[stub] title", "[stub] body", "[stub] summary",
             "stub-model-not-a-real-call", "v1", aid),
        )
        conn.commit()
        row = conn.execute(
            "SELECT model_id, prompt_version, text_original, text_english "
            "FROM articles WHERE id=?", (aid,)
        ).fetchone()
        conn.close()

        self.assertEqual(row[0], "stub-model-not-a-real-call")
        self.assertEqual(row[1], "v1")
        self.assertTrue(row[2], "original text must survive analysis")
        self.assertNotEqual(row[2], row[3],
                            "translation must never overwrite the original")

    def test_static_publication(self):
        """Renders the site from the temp DB into a temp output directory."""
        adapter = self._adapter()
        _, documents = adapter.collect(self.window)
        normalized = [normalize_article(d.as_article_dict()) for d in documents]
        aid = self._store(normalized)[0]

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "UPDATE articles SET passed_relevance=1, relevance_score=0.9, "
            "title_english='Stub title', text_english='Stub body', "
            "summary_english='Stub summary.', analyzed_at=datetime('now'), "
            "model_id='stub', prompt_version='v1' WHERE id=?", (aid,),
        )
        conn.commit()
        conn.close()

        out_dir = self.tmp / "output"
        out_dir.mkdir()

        import config
        import storage.db as dbmod

        original_db, original_out = config.DB_PATH, config.OUTPUT_DIR
        config.DB_PATH, dbmod.DB_PATH = self.db_path, self.db_path
        config.OUTPUT_DIR = out_dir
        try:
            for name in [m for m in list(sys.modules) if m.startswith("site")]:
                del sys.modules[name]
            sys.path.insert(0, str(REPO_ROOT / "site"))
            import importlib
            generator = importlib.import_module("generator")
            generator.generate_site(output_dir=out_dir)
        finally:
            config.DB_PATH, dbmod.DB_PATH = original_db, original_db
            config.OUTPUT_DIR = original_out
            if str(REPO_ROOT / "site") in sys.path:
                sys.path.remove(str(REPO_ROOT / "site"))

        index = out_dir / "index.html"
        self.assertTrue(index.exists(), "static publication produced no index")
        html = index.read_text(encoding="utf-8")
        self.assertNotIn("{{", html, "unrendered Jinja in published output")
        self.assertTrue(
            (out_dir / "article" / ("%d.html" % aid)).exists(),
            "article page was not published at its id-derived URL",
        )

    def test_health_report_for_the_run(self):
        adapter = self._adapter()
        result, _ = adapter.collect(self.window)
        results = [result]

        self.assertEqual(aggregate_status(results), "completed")
        machine = machine_report(results, run_id=1)
        self.assertEqual(machine["failed_sources"], [])
        self.assertIn("pla_daily", human_report(results, run_id=1))

    def test_migrated_temp_db_verifies_clean(self):
        conn = connect(self.db_path)
        report = verify(conn)
        conn.close()
        self.assertTrue(report["ok"])
        self.assertEqual(report["integrity_check"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
