"""Offline manual-only JCG pilot: contract, isolation, first run and idempotence."""
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core.manifests import load_all_desks, load_manifest
from scraper.sources.jp_jcg_en import JCGEnglishAdapter, LISTING
from scripts import shadow_collect_desk as runner

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://www.kaiho.mlit.go.jp"
URL = HOST + "/e/topics_archive/article9455.html"


class Response:
    def __init__(self, url, data, status=200, kind="text/html"):
        self.url, self.data, self.status_code = url, data, status
        self.headers = {"Content-Type": kind}

    def iter_content(self, _):
        yield self.data

    def close(self):
        pass


class MemorySession:
    def __init__(self):
        self.calls = []
        self.pages = {
            HOST + "/robots.txt": Response(HOST + "/robots.txt", b"", 404, "text/plain"),
            LISTING: Response(LISTING, (
                '<html><main><article class="main-article">'
                '<section class="topics has-pd"><dl class="topics-list">'
                '<dt><p class="topics-date">06 10 2026</p></dt>'
                '<dd><a class="arrow-link" href="/e/topics_archive/article9455.html">'
                'PCG Training</a></dd>'
                '<dt><p class="topics-date">01 07 2025</p></dt>'
                '<dd><a class="arrow-link" href="https://www.kaiho.mlit.go.jp/e/old.pdf">'
                'Historic format</a></dd>'
                '</dl></section></article></main></html>'
            ).encode()),
            URL: Response(URL, (
                '<html><main><article class="main-article">'
                '<section class="topics topics-article"><h1 class="entry-title">'
                'PCG Training</h1><time datetime="2021-3-1">'
                '06 October, 2026</time>'
                '<div class="topics-article__main tich-text"><p>' +
                ('JCG instructors provided maritime law enforcement training '
                 'for the Philippine Coast Guard. ' * 5) +
                '</p><p><a href="upload/original.pdf">Official attachment</a>'
                '</p></div></section></article></main></html>'
            ).encode()),
        }

    def request(self, method, url, data, headers, **kwargs):
        self.calls.append(url)
        if method != "GET" or kwargs.get("allow_redirects") is not False:
            raise AssertionError("unexpected request method or redirect")
        if url not in self.pages:
            raise AssertionError("attempted undeclared official route: " + url)
        return self.pages[url]


class JapanJCGManualShadow(unittest.TestCase):
    def test_source_registered_only_for_explicit_shadow_runner(self):
        self.assertIn("japan_jcg", runner.DESKS)
        self.assertEqual(runner.DESKS["japan_jcg"][0], "jp_jcg")
        self.assertIs(runner.DESKS["japan_jcg"][1], JCGEnglishAdapter)
        source = load_manifest(ROOT / "shadow/jp_jcg/manifest.json").sources[0]
        self.assertTrue(source.enabled)
        self.assertEqual(source.desk_id, "japan_jcg")
        self.assertEqual(source.language_tag, "en")
        self.assertNotIn("japan_jcg", load_all_desks())
        self.assertNotIn("japan", load_all_desks())
        self.assertFalse((ROOT / "desks/japan/manifest.json").exists())

    def test_workflow_manual_only_and_no_production_or_artifact_bodies(self):
        text = (ROOT / ".github/workflows/japan_jcg_shadow_manual.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("shadow/japan-jcg", text)
        self.assertIn("--desk japan_jcg", text)
        self.assertIn("git push origin", text)
        self.assertNotIn("--force", text)
        self.assertNotIn("output/", text)
        self.assertNotIn("pla_watch.db", text)
        self.assertNotIn("/jcg-state/state/", text.split("path:", 1)[-1])

    def test_mock_one_run_stores_shadow_only_and_replay_is_idempotent(self):
        config = load_manifest(ROOT / "shadow/jp_jcg/manifest.json")
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state"
            initial = MemorySession()
            a = JCGEnglishAdapter(config.sources[0], session=initial,
                                  sleeper=lambda _: None)
            first = runner.run("japan_jcg", state, date(2026, 10, 8),
                               lookback=9, cap=20, adapter=a, run_id="jcg-test-1")
            self.assertEqual(first["health"], "ok")
            self.assertEqual(first["inserted"], 1)
            self.assertEqual(first["robots_status"], "absent")
            self.assertEqual(first["discovered"], 1)
            self.assertEqual(first["selected"], 1)
            self.assertEqual(a.listing_report["outside_declared_pilot_scope"], 1)
            with sqlite3.connect(state / "shadow.db") as db:
                rows = db.execute("SELECT source_identity, published_date, language_tag,"
                                  " metadata_json FROM shadow_records").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][:3], ("jcg-en:9455", "2026-10-06", "en"))
            metadata = json.loads(rows[0][3])
            self.assertEqual(metadata["html_datetime_verdict"],
                             "observed_stale_template_2021-3-1")
            self.assertFalse(metadata["attachments_collected"])
            self.assertEqual(len(list((state / "captures").glob("*.bin"))), 3)
            self.assertEqual(len(list((state / "ledger").glob("*.json"))), 1)
            self.assertTrue((state / "clock.json").is_file())

            replay = JCGEnglishAdapter(config.sources[0], session=MemorySession(),
                                       sleeper=lambda _: None)
            second = runner.run("japan_jcg", state, date(2026, 10, 9),
                                lookback=9, cap=20, adapter=replay, run_id="jcg-test-2")
            self.assertEqual(second["inserted"], 0)
            self.assertEqual(second["duplicates"], 1)
            self.assertEqual(second["health"], "ok")
            self.assertEqual(len(list((state / "ledger").glob("*.json"))), 2)

    def test_refuses_to_write_inside_source_checkout(self):
        with self.assertRaises(ValueError):
            runner.assert_isolated(ROOT / "shadow" / "jcg-forbidden")


if __name__ == "__main__":
    unittest.main()
