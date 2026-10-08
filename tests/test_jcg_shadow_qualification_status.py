"""JCG qualification-day evidence must never be inferred from publication dates."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.jcg_shadow_qualification_status import (
    BACKFILL, DAY_ZERO_RUN, EvidenceError, _summarize, main,
)
from scripts.shadow_collect_desk import SCHEMA

COMMIT = "a" * 40


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    state = root / "state"
    (state / "ledger").mkdir(parents=True)
    (state / "captures").mkdir()
    (state / "clock.json").write_text(json.dumps({
        "desk": "japan_jcg",
        "day_zero_utc": "2026-10-08T18:57:32+00:00",
        "day_zero_run_id": DAY_ZERO_RUN,
    }))
    with sqlite3.connect(state / "shadow.db") as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO shadow_meta VALUES ('japan_jcg')")
        for number in (9455, 9453, 9436):
            ident = "jcg-en:" + str(number)
            db.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (ident, "https://www.kaiho.mlit.go.jp/e/topics_archive/article" +
                        str(number) + ".html", "jp_jcg_press_en",
                        "Official article", "Official original paragraph",
                        "2026-10-06", "en", "{}", "c" * 64, "d" * 64,
                        DAY_ZERO_RUN))
        db.commit()
    evidence = b"<html>exact original publisher capture</html>"
    h = hashlib.sha256(evidence).hexdigest()
    (state / "captures" / (h + ".bin")).write_bytes(evidence)
    item = ledger(
        run=DAY_ZERO_RUN, when="2026-10-08T18:57:32+00:00",
        target="2026-10-08", before=None, after=digest(state / "shadow.db"))
    item["requests"] = [{"capture_sha256": h}]
    item["shadow_day"] = 0
    put_ledger(state, "20261008T185732.000000+0000", item)
    return state


def ledger(run, when, target, before, after, health="ok", result="ok"):
    return {
        "desk": "japan_jcg", "run_id": run,
        "started_utc": when, "finished_utc": when,
        "target_date": target, "target_date_source": "explicit",
        "state_sha256_before": before, "state_sha256_after": after,
        "health": health, "result": result,
        "robots_status": "absent", "listing_status": "ok",
        "requests": [], "selected": 0, "retrieved": 0, "extracted": 0,
        "fetch_failures": 0, "extraction_failures": 0, "access_failures": 0,
        "shadow_day": None,
    }


def put_ledger(state, stamp, entry):
    (state / "ledger" / (stamp + "-" + entry["run_id"] + ".json")
     ).write_text(json.dumps(entry, sort_keys=True) + "\n")


class QualificationEvidence(unittest.TestCase):
    def test_actual_day_zero_shape_has_no_claim_of_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            r = _summarize(state, date(2026, 10, 8), COMMIT)
            self.assertEqual(r["archived_records"], 3)
            self.assertEqual(r["collected_days_from_day_zero"], 1)
            self.assertEqual(r["consecutive_collected_days_from_day_zero"], 1)
            self.assertEqual(r["missing_days"], [])
            self.assertEqual(r["ledger_count"], 1)
            self.assertEqual(r["nonqualifying_historical_backfill_runs"], [])
            self.assertEqual(r["checkpoints"][0]["due_utc_date"], "2026-10-15")
            self.assertEqual(r["checkpoints"][0]["machine_readiness"], "not_due")
            for k in ("human_checkpoint_reviews_completed", "production_eligible",
                      "weekly_writer_eligible", "owner_promotion_authorized",
                      "source_pdf_completeness_human_review_completed"):
                self.assertIs(r[k], False)
            self.assertNotIn("Official original paragraph", json.dumps(r))

    def test_missing_day_is_not_an_implicit_success(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            r = _summarize(state, date(2026, 10, 9), COMMIT)
            self.assertEqual(r["missing_days"], ["2026-10-09"])
            self.assertEqual(r["consecutive_collected_days_from_day_zero"], 1)
            self.assertEqual(r["days"][1]["status"], "missing")

    def test_healthy_zero_publication_day_counts_as_collection(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            h = digest(state / "shadow.db")
            put_ledger(state, "20261009T190000.000000+0000",
                       ledger("run-day1", "2026-10-09T19:00:00+00:00",
                              "2026-10-09", h, h, result="ok_no_publications"))
            r = _summarize(state, date(2026, 10, 9), COMMIT)
            self.assertEqual(r["collected_days_from_day_zero"], 2)
            self.assertEqual(r["consecutive_collected_days_from_day_zero"], 2)
            self.assertEqual(r["missing_days"], [])

    def test_backfill_adds_no_collection_day_and_no_checkpoint_credit(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            h = digest(state / "shadow.db")
            value = ledger("backfill1", "2026-10-08T20:00:00+00:00",
                           "2026-10-08", h, h)
            value.update(operation=BACKFILL, counts_as_qualifying_shadow_day=False,
                         backfill_anchor_day_zero_run_id=DAY_ZERO_RUN,
                         lookback_days=38, cap=5)
            put_ledger(state, "20261008T200000.000000+0000", value)
            r = _summarize(state, date(2026, 10, 15), COMMIT)
            self.assertEqual(r["ledger_count"], 2)
            self.assertEqual(r["qualifying_collection_attempts"], 1)
            self.assertEqual(r["nonqualifying_historical_backfill_runs"], ["backfill1"])
            self.assertEqual(r["collected_days_from_day_zero"], 1)
            self.assertEqual(r["missing_days"][0], "2026-10-09")
            self.assertEqual(r["checkpoints"][0]["machine_readiness"],
                             "evidence_gaps_or_anomalies_require_disposition")

    def test_fake_qualifying_backfill_is_structural_error(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            h = digest(state / "shadow.db")
            value = ledger("backfill2", "2026-10-08T20:00:00+00:00",
                           "2026-10-08", h, h)
            value.update(operation=BACKFILL, counts_as_qualifying_shadow_day=True,
                         backfill_anchor_day_zero_run_id=DAY_ZERO_RUN,
                         lookback_days=38, cap=5)
            put_ledger(state, "20261008T200000.000000+0000", value)
            with self.assertRaisesRegex(EvidenceError, "backfill marked"):
                _summarize(state, date(2026, 10, 9), COMMIT)

    def test_failed_day_and_later_repair_still_need_anomaly_disposition(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            h = digest(state / "shadow.db")
            put_ledger(state, "20261009T190000.000000+0000",
                       ledger("failed", "2026-10-09T19:00:00+00:00",
                              "2026-10-09", h, h, health="fail",
                              result="fetch_failure"))
            put_ledger(state, "20261009T201000.000000+0000",
                       ledger("repair", "2026-10-09T20:10:00+00:00",
                              "2026-10-09", h, h))
            r = _summarize(state, date(2026, 10, 9), COMMIT)
            self.assertEqual(r["missing_days"], [])
            self.assertEqual(r["unhealthy_attempts"], 1)
            self.assertEqual(r["collected_days_from_day_zero"], 2)
            self.assertTrue(any(x["kind"] == "multiple_collection_attempts_same_day"
                                for x in r["anomalies_require_disposition"]))

    def test_detects_state_chain_and_original_capture_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            capture = next((state / "captures").iterdir())
            capture.write_bytes(b"not the official capture")
            with self.assertRaisesRegex(EvidenceError, "capture altered"):
                _summarize(state, date(2026, 10, 8), COMMIT)
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            db = state / "shadow.db"
            with sqlite3.connect(db) as conn:
                conn.execute("DELETE FROM shadow_records WHERE source_identity='jcg-en:9455'")
                conn.commit()
            with self.assertRaisesRegex(EvidenceError, "last ledger hash"):
                _summarize(state, date(2026, 10, 8), COMMIT)

    def test_cli_writes_only_metadata_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            state = fixture(root)
            out = root / "qualification.json"
            args = ["--state-dir", str(state), "--state-commit", COMMIT,
                    "--as-of", "2026-10-08", "--output", str(out)]
            self.assertEqual(main(args), 0)
            self.assertIn('"archived_records": 3', out.read_text())
            with self.assertRaises(SystemExit):
                main(args)

    def test_rejects_pre_dayzero_and_synthetic_commit(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            with self.assertRaises(EvidenceError):
                _summarize(state, date(2026, 10, 7), COMMIT)
            with self.assertRaises(EvidenceError):
                _summarize(state, date(2026, 10, 8), "not-a-git-sha")

    def test_future_exhausted_checkpoint_is_not_autoapproved(self):
        with tempfile.TemporaryDirectory() as d:
            state = fixture(Path(d))
            last = digest(state / "shadow.db")
            for day in range(1, 31):
                target = (date(2026, 10, 8) +
                          __import__("datetime").timedelta(days=day)).isoformat()
                when = target + "T19:13:00+00:00"
                put_ledger(state, target.replace("-", "") + "T191300.000000+0000",
                           ledger("run-" + str(day), when, target, last, last,
                                  result="ok_all_duplicates"))
            r = _summarize(state, date(2026, 11, 7), COMMIT)
            self.assertEqual(r["consecutive_collected_days_from_day_zero"], 31)
            self.assertEqual(r["checkpoints"][-1]["machine_readiness"],
                             "human_checkpoint_required_not_approved")
            self.assertFalse(r["production_eligible"])


if __name__ == "__main__":
    unittest.main()
