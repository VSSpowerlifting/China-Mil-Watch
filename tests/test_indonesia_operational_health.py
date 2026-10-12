"""Synthetic read-only tests for Indonesia's daily operational canary."""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scripts.indonesia_operational_health import (
    HealthError, check_public_page, evaluate, monitor_day,
)
from core.indonesia_official_index import load as load_index


def ledger(run, target, start, end, before, after, count, source):
    return {
        "desk": "indonesia",
        "run_id": run,
        "target_date": target,
        "target_date_source": source,
        "started_utc": start,
        "finished_utc": end,
        "state_sha256_before": before,
        "state_sha256_after": after,
        "health": "ok", "result": "ok",
        "stored_total": count,
        "fetch_failures": 0, "extraction_failures": 0, "access_failures": 0,
    }


class OperationalCanaryTests(unittest.TestCase):
    def setUp(self):
        self.clock = {
            "desk": "indonesia", "day_zero_run_id": "local-native-20261006-indonesia",
            "day_zero_utc": "2026-10-06T16:53:00+00:00",
        }
        self.rows = [
            ledger("local-native-20261006-indonesia", "2026-10-06",
                   "2026-10-06T16:52:00Z", "2026-10-06T16:53:00Z",
                   None, "a" * 64, 14, "manual-utc-date"),
            ledger("37533271730-1", "2026-10-06",
                   "2026-10-06T21:21:00Z", "2026-10-06T21:22:00Z",
                   "a" * 64, "a" * 64, 14, "manual-utc-date"),
            ledger("37693074726-1", "2026-10-07",
                   "2026-10-07T21:58:00Z", "2026-10-07T21:59:00Z",
                   "a" * 64, "b" * 64, 16, "schedule-slot"),
        ]
        self.sha = "c" * 40

    def assess(self, expected=date(2026, 10, 7), rows=None, digest=None):
        return evaluate(self.clock, rows if rows is not None else self.rows,
                        digest or "b" * 64, expected, self.sha)

    def test_current_first_scheduled_day_with_manual_and_day_zero(self):
        result = self.assess()
        self.assertEqual(result["collection_status"], "LEDGERS_CURRENT")
        self.assertEqual(result["stored_private_originals"], 16)
        self.assertEqual(result["successful_scheduled_dates"], 1)
        self.assertEqual(result["missing_scheduled_dates"], [])
        self.assertFalse(result["production_admitted"])
        self.assertFalse(result["all_actions_attempts_independently_audited"])

    def test_missed_scheduled_date_is_an_actionable_hold(self):
        r = self.assess(date(2026, 10, 8))
        self.assertEqual(r["collection_status"], "HOLD_MISSING_SCHEDULED_SLOT")
        self.assertEqual(r["missing_scheduled_dates"], ["2026-10-08"])
        self.assertEqual(r["days_lagging"], 1)

    def test_bad_hash_chain_and_failed_collection_fail_closed(self):
        changes = [
            lambda rows: rows[2].update(state_sha256_before="f" * 64),
            lambda rows: rows[2].update(fetch_failures=1),
            lambda rows: rows[2].update(health="error"),
            lambda rows: rows[2].update(stored_total=10),
            lambda rows: rows[2].update(target_date="2026-10-08"),
            lambda rows: rows[2].update(run_id="forged-run"),
            lambda rows: rows[2].update(finished_utc="2026-10-07T21:00:00Z"),
        ]
        for change in changes:
            rows = copy.deepcopy(self.rows)
            change(rows)
            with self.subTest(change=change), self.assertRaises(HealthError):
                self.assess(rows=rows)
        with self.assertRaises(HealthError):
            self.assess(digest="f" * 64)

    def test_monitor_uses_nominal_slot_across_midnight(self):
        before = datetime(2026, 10, 9, 2, 15, tzinfo=timezone.utc)
        after = datetime(2026, 10, 9, 4, 15, tzinfo=timezone.utc)
        self.assertEqual(monitor_day(before), date(2026, 10, 7))
        self.assertEqual(monitor_day(after), date(2026, 10, 8))

    def test_actual_published_index_contract_in_disposable_html(self):
        approved = load_index()
        self.assertEqual(len(approved), 4)
        with tempfile.TemporaryDirectory(prefix="ipr-id-canary-") as tmp:
            page = Path(tmp) / "indonesia.html"
            def document(refs, good=True):
                links = "".join(
                    '<li><a href="%s" lang="id">%s</a></li>' %
                    (row["source_url"], row["title_original"]) for row in refs
                )
                return (
                    "<h2>Shadow evaluation — no public corpus records</h2>"
                    "<p>No individual source references have completed</p>"
                    "<h2>Explore official Indonesian defense publications</h2>"
                    '<ol aria-label="Four external ministry news links">' + links + "</ol>"
                ) if good else "<h1>Wrong site</h1>" + links
            page.write_text(document(approved), encoding="utf-8")
            self.assertEqual(check_public_page(page), 4)
            page.write_text(document(approved[:-1]), encoding="utf-8")
            with self.assertRaises(HealthError):
                check_public_page(page)
            page.write_text(document(approved, good=False), encoding="utf-8")
            with self.assertRaises(HealthError):
                check_public_page(page)
            page.write_text(document(approved) + "text_original", encoding="utf-8")
            with self.assertRaises(HealthError):
                check_public_page(page)


if __name__ == "__main__":
    unittest.main()
