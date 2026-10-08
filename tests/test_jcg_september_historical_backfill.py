"""Historical JCG content backfill never invents earlier shadow collecting days."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.manifests import load_manifest
from scraper.sources.jp_jcg_en import JCGEnglishAdapter, LISTING
from scripts import shadow_collect_desk as collector
from scripts import review_desk_shadow as reviewer
from tests.test_japan_jcg_manual_shadow_gate import MemorySession, Response

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://www.kaiho.mlit.go.jp"
DATES = [
    ("9455", "06 10 2026", "06 October, 2026"),
    ("9453", "06 10 2026", "06 October, 2026"),
    ("9436", "29 09 2026", "29 September, 2026"),
    ("9424", "18 09 2026", "18 September, 2026"),
    ("9399", "07 09 2026", "07 September, 2026"),
]


def session():
    s = MemorySession()
    rows = "".join(
        '<dt><p class="topics-date">' + listed + '</p></dt>'
        '<dd><a href="article' + ident + '.html" class="arrow-link">'
        'Official JCG release ' + ident + '</a></dd>'
        for ident, listed, _ in DATES
    )
    s.pages[LISTING] = Response(
        LISTING,
        ('<html><main><article class="main-article"><section class="topics has-pd">'
         '<dl class="topics-list">' + rows + '</dl></section></article></main></html>'
         ).encode())
    for ident, _, visible in DATES:
        url = HOST + "/e/topics_archive/article" + ident + ".html"
        prose = ("The Japan Coast Guard provided international maritime law "
                 "enforcement cooperation and capacity building. " * 5)
        body = (
            '<html><main><article class="main-article">'
            '<section class="topics topics-article">'
            '<h1 class="entry-title">Official JCG release ' + ident + '</h1>'
            '<time datetime="2021-3-1">' + visible + '</time>'
            '<div class="topics-article__main tich-text"><p>' + prose + '</p>'
            '<a href="upload/file.pdf">Companion PDF not imported</a>'
            '</div></section></article></main></html>'
        )
        s.pages[url] = Response(url, body.encode())
    return s


class JCGBackfillSafety(unittest.TestCase):
    def setUp(self):
        self.source = load_manifest(ROOT / "shadow/jp_jcg/manifest.json").sources[0]

    def adapter(self):
        return JCGEnglishAdapter(self.source, session=session(),
                                 sleeper=lambda _: None)

    def bootstrap(self, state):
        entry = collector.run("japan_jcg", state, date(2026, 10, 8),
                              lookback=9, cap=20, run_id="37828199188-1",
                              adapter=self.adapter())
        self.assertEqual(entry["health"], "ok")
        self.assertEqual(entry["inserted"], 3)
        self.assertEqual(entry["target_date"], "2026-10-08")
        return entry

    def test_one_time_backfill_adds_only_two_missing_sources_without_new_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            day0 = self.bootstrap(state)
            original_clock = (state / "clock.json").read_bytes()
            original_ledger = next((state / "ledger").glob("*.json"))
            original_ledger_bytes = original_ledger.read_bytes()
            outcome = collector.run(
                "japan_jcg", state, date(2026, 10, 8),
                lookback=38, cap=5, run_id="backfill-test-1",
                adapter=self.adapter(), historical_backfill=True)
            self.assertEqual(outcome["health"], "ok")
            self.assertEqual(outcome["discovered"], 5)
            self.assertEqual(outcome["inserted"], 2)
            self.assertEqual(outcome["duplicates"], 3)
            self.assertEqual(outcome["operation"], "jcg_2026_09_historical_backfill")
            self.assertFalse(outcome["counts_as_qualifying_shadow_day"])
            self.assertIsNone(outcome["shadow_day"])
            self.assertEqual(outcome["target_date"], day0["target_date"])
            self.assertEqual(outcome["day_zero_utc"], day0["day_zero_utc"])
            self.assertEqual((state / "clock.json").read_bytes(), original_clock)
            self.assertEqual(original_ledger.read_bytes(), original_ledger_bytes)
            self.assertEqual(len(list((state / "ledger").glob("*.json"))), 2)
            with sqlite3.connect(state / "shadow.db") as db:
                actual = dict(db.execute(
                    "SELECT source_identity, published_date FROM shadow_records").fetchall())
                rows = db.execute(
                    "SELECT source_identity, first_seen_run FROM shadow_records").fetchall()
            self.assertEqual(actual, {
                "jcg-en:" + ident: datevalue for ident, datevalue in [
                    ("9455","2026-10-06"),("9453","2026-10-06"),
                    ("9436","2026-09-29"),("9424","2026-09-18"),
                    ("9399","2026-09-07"),
                ]})
            initial = {k:v for k,v in rows if k in {"jcg-en:9455","jcg-en:9453","jcg-en:9436"}}
            self.assertEqual(set(initial.values()), {"37828199188-1"})
            new = {k:v for k,v in rows if k in {"jcg-en:9424","jcg-en:9399"}}
            self.assertEqual(set(new.values()), {"backfill-test-1"})
            self.assertFalse((ROOT / "desks/japan/manifest.json").exists())

    def test_formal_reviewer_excludes_historical_backfill_from_day_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            self.bootstrap(state)
            outcome = collector.run("japan_jcg", state, date(2026, 10, 8),
                                    lookback=38, cap=5, run_id="backfill-for-review",
                                    adapter=self.adapter(), historical_backfill=True)
            self.assertEqual(outcome["health"], "ok")
            report = reviewer.review(state, "japan_jcg",
                                     Path(tmp) / "review-day0",
                                     date(2026, 10, 8))
            self.assertEqual(report["records"], 5)
            self.assertEqual(report["ledgers"], 2)
            self.assertEqual(report["qualifying_ledgers"], 1)
            self.assertEqual(report["historical_backfill_run_ids"],
                             ["backfill-for-review"])
            self.assertEqual(report["missing_successful_days"], [])
            self.assertEqual(report["findings"], [])
            self.assertFalse(report["human_review_completed"])
            report_next = reviewer.review(state, "japan_jcg",
                                          Path(tmp) / "review-day1",
                                          date(2026, 10, 9))
            self.assertIn("2026-10-09", report_next["missing_successful_days"])
            self.assertTrue(any("No successful logical-day ledger" in f
                                for f in report_next["findings"]))
            self.assertEqual(report_next["qualifying_ledgers"], 1)

    def test_backfill_ledger_must_be_explicitly_nonqualifying(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            self.bootstrap(state)
            collector.run("japan_jcg", state, date(2026, 10, 8),
                          lookback=38, cap=5, run_id="backfill-for-tamper",
                          adapter=self.adapter(), historical_backfill=True)
            target = next(x for x in (state / "ledger").glob("*backfill-for-tamper.json"))
            value = json.loads(target.read_text())
            value["counts_as_qualifying_shadow_day"] = True
            target.write_text(json.dumps(value))
            report = reviewer.review(state, "japan_jcg",
                                     Path(tmp) / "review-tamper",
                                     date(2026, 10, 8))
            self.assertTrue(any("misclassified historical backfill" in f
                                for f in report["findings"]))
            self.assertEqual(report["qualifying_ledgers"], 1)

    def test_backfill_requires_day_zero_and_fixed_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            with self.assertRaisesRegex(ValueError, "cannot bootstrap"):
                collector.run("japan_jcg", state, date(2026, 10, 8),
                              lookback=38, cap=5, historical_backfill=True)
            self.bootstrap(state)
            for desk, target, lookback, cap in [
                ("korea", date(2026, 10, 8), 38, 5),
                ("japan_jcg", date(2026, 10, 7), 38, 5),
                ("japan_jcg", date(2026, 10, 8), 37, 5),
                ("japan_jcg", date(2026, 10, 8), 38, 6),
            ]:
                with self.subTest(desk=desk,target=target,lookback=lookback,cap=cap):
                    with self.assertRaises(ValueError):
                        collector.run(desk, state, target, lookback=lookback, cap=cap,
                                      historical_backfill=True)
            with self.assertRaisesRegex(ValueError, "0–30"):
                collector.run("japan_jcg", state, date(2026, 10, 8), lookback=38,
                              cap=5, historical_backfill=False)

    def test_replay_is_refused_not_duplicate_qualifying_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            self.bootstrap(state)
            collector.run("japan_jcg", state, date(2026, 10, 8),
                          lookback=38, cap=5, run_id="backfill-test-1",
                          adapter=self.adapter(), historical_backfill=True)
            before = sorted(x.name for x in (state / "ledger").glob("*.json"))
            with self.assertRaisesRegex(ValueError, "already recorded"):
                collector.run("japan_jcg", state, date(2026, 10, 8),
                              lookback=38, cap=5, run_id="backfill-test-2",
                              historical_backfill=True)
            self.assertEqual(before,
                             sorted(x.name for x in (state / "ledger").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
