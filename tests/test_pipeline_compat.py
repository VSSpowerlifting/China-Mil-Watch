"""
Pipeline compatibility and observability tests.

Covers the Phase 2 gate conditions:

  * the China collection path still resolves through the registry;
  * a simulated source failure is visible and degrades the aggregate run;
  * a zero-publication source stays distinguishable from a failed one;
  * one high-volume source cannot starve the others;
  * per-source results round-trip through the database.

Offline: no network, no model calls. Databases are temporary files.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                       # noqa: E402
from core.collection.contract import SourceRunResult           # noqa: E402
from core.collection.health import (                           # noqa: E402
    aggregate_status, human_report, machine_report, silence_verdict,
)
from core.registry import SourceRegistry, sync_desk_config     # noqa: E402
from migrations.runner import apply_all, connect               # noqa: E402
from tests.test_migrations import build_legacy_db              # noqa: E402


def result(slug, status, **kw):
    return SourceRunResult(source_slug=slug, status=status, desk_id="china", **kw)


class TestRegistryDrivesCollection(unittest.TestCase):
    def test_pipeline_imports_no_china_scraper(self):
        """
        The specific coupling Phase 2 was asked to remove: `pipeline.py` must
        not name a country-specific scraper class.
        """
        source_text = (REPO_ROOT / "pipeline.py").read_text(encoding="utf-8")
        for forbidden in ("PLADailyScraper", "MODChinaScraper",
                          "XinhuaMilScraper", "GlobalTimesMilScraper",
                          "ChinaMilOnlineScraper"):
            self.assertNotIn(
                forbidden, source_text,
                "pipeline.py still names %s — sources must come from desk "
                "manifests" % forbidden,
            )

    def test_core_imports_no_scraper_module(self):
        """
        `core/` must not import scraper modules. Checked against import
        statements specifically, not any textual occurrence — the dotted path
        appears in a docstring as an example of manifest configuration, which
        is the opposite of a coupling.
        """
        import ast

        for module in ("domain.py", "manifests.py", "registry.py"):
            path = REPO_ROOT / "core" / module
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported += [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
            offenders = [m for m in imported if m.startswith("scraper")]
            self.assertEqual(
                offenders, [],
                "core/%s imports %s — core must stay country-neutral"
                % (module, offenders),
            )

    def test_registry_exposes_the_five_existing_sources(self):
        self.assertEqual(
            SourceRegistry().slugs,
            ["china_mil_online", "global_times_mil", "mod_china",
             "pla_daily", "xinhua_mil"],
        )

    def test_compatibility_shim_still_answers_like_a_dict(self):
        """Scripts and the CLI still read `SCRAPERS`."""
        import pipeline
        self.assertIn("pla_daily", pipeline.SCRAPERS)
        self.assertNotIn("does_not_exist", pipeline.SCRAPERS)
        self.assertEqual(sorted(pipeline.SCRAPERS.keys()),
                         SourceRegistry().slugs)


class TestAggregateStatus(unittest.TestCase):
    def test_all_healthy_is_completed(self):
        results = [result("pla_daily", st.OK, new_documents=34),
                   result("mod_china", st.OK_NO_PUBLICATIONS)]
        self.assertEqual(aggregate_status(results), "completed")

    def test_one_source_failure_degrades_the_run(self):
        """
        The MOD China case. PLA Daily supplies ~87% of the corpus, so totals do
        not move when a smaller source dies — and for four weeks no run failed.
        """
        results = [result("pla_daily", st.OK, new_documents=34),
                   result("mod_china", st.LISTING_FAILURE)]
        self.assertEqual(aggregate_status(results), "degraded")

    def test_all_sources_failing_is_failed(self):
        results = [result("pla_daily", st.LISTING_FAILURE),
                   result("mod_china", st.FETCH_FAILURE)]
        self.assertEqual(aggregate_status(results), "failed")

    def test_stub_source_alone_does_not_degrade_a_healthy_run(self):
        results = [result("pla_daily", st.OK, new_documents=34),
                   result("xinhua_mil", st.NOT_IMPLEMENTED)]
        self.assertEqual(aggregate_status(results), "completed")

    def test_quiet_day_across_all_sources_is_still_completed(self):
        results = [result("pla_daily", st.OK_NO_PUBLICATIONS),
                   result("mod_china", st.OK_NO_PUBLICATIONS)]
        self.assertEqual(aggregate_status(results), "completed")

    def test_no_results_is_failed(self):
        self.assertEqual(aggregate_status([]), "failed")

    def test_aggregate_status_is_one_of_the_db_permitted_values(self):
        """It is written to scrape_runs.status, which has a CHECK constraint."""
        permitted = {"running", "completed", "degraded", "failed"}
        for results in ([], [result("a", st.OK)],
                        [result("a", st.LISTING_FAILURE)],
                        [result("a", st.OK), result("b", st.TIMEOUT)]):
            self.assertIn(aggregate_status(results), permitted)


class TestSilenceIsNotFailure(unittest.TestCase):
    def test_zero_publications_is_not_a_failure(self):
        r = result("mod_china", st.OK_NO_PUBLICATIONS)
        self.assertFalse(r.is_failure)
        self.assertTrue(r.is_success)

    def test_listing_failure_is_a_failure(self):
        r = result("mod_china", st.LISTING_FAILURE)
        self.assertTrue(r.is_failure)
        self.assertFalse(r.is_success)

    def test_reports_separate_empty_from_failed(self):
        results = [result("pla_daily", st.OK, new_documents=30),
                   result("mod_china", st.OK_NO_PUBLICATIONS),
                   result("china_mil_online", st.LISTING_FAILURE)]
        report = machine_report(results, run_id=111)
        self.assertEqual(report["failed_sources"], ["china_mil_online"])
        self.assertIn("mod_china", report["empty_sources"])
        self.assertNotIn("mod_china", report["failed_sources"])
        self.assertEqual(report["aggregate_status"], "degraded")

    def test_human_report_names_the_failing_source(self):
        results = [result("pla_daily", st.OK, new_documents=30),
                   result("mod_china", st.LISTING_FAILURE)]
        text = human_report(results, run_id=111)
        self.assertIn("mod_china", text)
        self.assertIn("DEGRADED", text)
        self.assertIn("FAIL", text)

    def test_human_report_leaks_no_multiline_detail(self):
        results = [result("pla_daily", st.ADAPTER_ERROR,
                          error_detail="boom")]
        for line in human_report(results).splitlines():
            self.assertLess(len(line), 400)


class TestSilenceThresholds(unittest.TestCase):
    """
    A source that publishes twice a month is not sick after seven quiet days
    (DECISION_LOG 2026-08-09 §8). Thresholds come from the manifest.
    """

    def setUp(self):
        self.registry = SourceRegistry()

    def test_mod_china_tolerates_a_quiet_fortnight(self):
        src = self.registry.get_source("mod_china")
        self.assertEqual(src.silence_threshold_days, 21)
        self.assertEqual(silence_verdict(14, src), "within_cadence")

    def test_mod_china_overdue_past_its_own_threshold(self):
        src = self.registry.get_source("mod_china")
        self.assertEqual(silence_verdict(33, src), "overdue")

    def test_daily_source_is_overdue_sooner(self):
        src = self.registry.get_source("pla_daily")
        self.assertEqual(silence_verdict(14, src), "overdue")

    def test_unknown_silence_is_reported_as_unknown(self):
        self.assertEqual(silence_verdict(None), "unknown")


class TestNoSourceStarvesAnother(unittest.TestCase):
    """
    One high-volume source must not consume the run and leave others
    uncollected. Collection iterates per source and each gets its own result,
    so a source that yields nothing still produces a row rather than being
    crowded out of the record.
    """

    def test_every_configured_source_produces_a_result(self):
        results = [
            result("pla_daily", st.OK, references_discovered=340,
                   fetched=340, extracted=340, new_documents=34),
            result("mod_china", st.OK_NO_PUBLICATIONS),
            result("china_mil_online", st.OK, new_documents=3),
            result("global_times_mil", st.OK, new_documents=1),
            result("xinhua_mil", st.NOT_IMPLEMENTED),
        ]
        report = machine_report(results)
        self.assertEqual(report["source_count"], 5)
        self.assertEqual(
            sorted(s["source_slug"] for s in report["sources"]),
            SourceRegistry().slugs,
        )

    def test_low_volume_source_is_visible_beside_a_dominant_one(self):
        results = [
            result("pla_daily", st.OK, new_documents=2766),
            result("mod_china", st.LISTING_FAILURE),
        ]
        report = machine_report(results)
        self.assertEqual(report["failed_sources"], ["mod_china"])
        self.assertEqual(report["aggregate_status"], "degraded")


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        build_legacy_db(self.db_path)
        conn = connect(self.db_path)
        apply_all(conn)
        conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, run_id, res):
        """Mirror storage.db.record_source_run_result against the temp DB."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, "
            "desk_id, status, is_failure, references_discovered, fetched, "
            "extracted, duplicates, new_documents, relevance_rejected, "
            "failed_fetches, error_detail) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(scrape_run_id, source_slug) DO UPDATE SET "
            "status=excluded.status, is_failure=excluded.is_failure",
            (run_id, res.source_slug, res.desk_id, res.status,
             1 if res.is_failure else 0, res.references_discovered, res.fetched,
             res.extracted, res.duplicates, res.new_documents,
             res.relevance_rejected, res.failed_fetches, res.error_detail),
        )
        conn.commit()
        conn.close()

    def test_results_round_trip(self):
        self._write(1, result("pla_daily", st.OK, new_documents=34,
                              references_discovered=40, fetched=40, extracted=40))
        self._write(1, result("mod_china", st.LISTING_FAILURE,
                              error_detail="listing unreachable"))

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM source_run_results WHERE scrape_run_id = 1 "
            "ORDER BY source_slug"
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        by_slug = {r["source_slug"]: r for r in rows}
        self.assertEqual(by_slug["pla_daily"]["new_documents"], 34)
        self.assertEqual(by_slug["pla_daily"]["is_failure"], 0)
        self.assertEqual(by_slug["mod_china"]["is_failure"], 1)
        self.assertEqual(by_slug["mod_china"]["status"], st.LISTING_FAILURE)

    def test_one_result_per_source_per_run(self):
        self._write(1, result("pla_daily", st.OK, new_documents=1))
        self._write(1, result("pla_daily", st.OK, new_documents=2))
        conn = sqlite3.connect(str(self.db_path))
        n = conn.execute(
            "SELECT COUNT(*) FROM source_run_results WHERE scrape_run_id=1"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(n, 1, "a second write for the same pair must upsert")

    def test_results_cascade_with_their_run(self):
        # Run 2 carries no articles. Run 1 does, and `articles.scrape_run_id`
        # has no ON DELETE clause, so a run with articles cannot be deleted at
        # all — which is the correct protection for published rows and is
        # asserted separately below.
        self._write(2, result("pla_daily", st.OK))
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM scrape_runs WHERE id = 2")
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM source_run_results").fetchone()[0]
        conn.close()
        self.assertEqual(n, 0, "orphaned per-source rows must not survive")

    def test_a_run_holding_articles_cannot_be_deleted(self):
        """
        Per-source results cascade; articles deliberately do not. Deleting a run
        that owns published articles must remain impossible, or article ids —
        and therefore live `output/article/<id>.html` URLs — could be orphaned.
        """
        self._write(1, result("pla_daily", st.OK))
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM scrape_runs WHERE id = 1")
        conn.close()


class TestConfigSyncIsIdempotent(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        build_legacy_db(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sync_does_not_alter_legacy_source_columns(self):
        """
        A config sync must never be able to rename a live source or re-point it
        at a different host.
        """
        conn = connect(self.db_path)
        before = conn.execute(
            "SELECT slug, display_name, base_url, language, is_active "
            "FROM sources ORDER BY slug"
        ).fetchall()
        apply_all(conn)
        sync_desk_config(conn)
        after = conn.execute(
            "SELECT slug, display_name, base_url, language, is_active "
            "FROM sources ORDER BY slug"
        ).fetchall()
        conn.close()
        self.assertEqual(before, after)

    def test_repeated_sync_inserts_no_duplicate_sources(self):
        conn = connect(self.db_path)
        apply_all(conn)
        for _ in range(3):
            sync_desk_config(conn)
        n = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        desks = conn.execute("SELECT COUNT(*) FROM desks").fetchone()[0]
        insts = conn.execute("SELECT COUNT(*) FROM institutions").fetchone()[0]
        conn.close()
        self.assertEqual(n, 5)
        self.assertEqual(desks, 1)
        self.assertEqual(insts, 4)

    def test_sync_populates_authority_and_originality(self):
        conn = connect(self.db_path)
        apply_all(conn)
        rows = dict(conn.execute(
            "SELECT slug, authority_tier FROM sources").fetchall())
        orig = dict(conn.execute(
            "SELECT slug, originality FROM sources").fetchall())
        conn.close()
        self.assertEqual(rows["mod_china"], "A")
        self.assertEqual(rows["global_times_mil"], "D")
        self.assertEqual(orig["china_mil_online"], "mirror")


if __name__ == "__main__":
    unittest.main(verbosity=2)
