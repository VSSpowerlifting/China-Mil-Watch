"""Private export, replay and desktop/mobile Operations Center contracts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.analysis_plan import Policy, build_plan, digest
from core.desk_registry import load_registry
from scripts import operations_center as ops
from scripts.analysis_capacity import (PrivateRunJournal, read_packet, replay,
                                      stored_plan, validate_packet, validate_replay)
from scripts.source_health_report import build_report
from tests.test_analysis_planning import candidate


def packet():
    plan = build_plan([candidate(1, source_slug="<img src=x onerror=alert(1)>"),
                       candidate(2, body="\u2003")], Policy("2026-10-11T00:00:00Z", cap=1),
                      code_identity="code", pricing_identity="prices")
    return {"plan": plan, "run": None}


def base_snapshot(tmp):
    from config import DB_PATH
    (tmp / "shadow").mkdir(exist_ok=True)
    return ops.assemble(load_registry(), build_report(DB_PATH), tmp / "shadow", tmp / "marker", date(2026, 10, 11))


class ReportTests(unittest.TestCase):
    def test_replay_is_deterministic_equal_envelope_and_explicitly_modeled(self):
        r = replay()
        self.assertEqual(r, replay())
        validate_replay(r)
        self.assertFalse(r["historical_per_record_spend_available"])
        self.assertEqual(r["evidence_class"], "modeled")
        changed = copy.deepcopy(r)
        changed["results"][0]["days"][0]["packet"]["plan"]["policy"]["cap"] += 1
        with self.assertRaises(ValueError): validate_replay(changed)

    def test_nested_body_exports_and_false_lifecycle_claims_refused(self):
        p = packet()
        validate_packet(p)
        p["plan"]["records"][0]["body"] = "SECRET_SOURCE_BODY"
        p["plan"]["plan_id"] = digest({k: v for k, v in p["plan"].items() if k != "plan_id"})
        with self.assertRaises(ValueError): validate_packet(p)
        p = packet()
        p["plan"]["snapshot_identity"] = {"db": "a" * 64, "body": "SECRET_SOURCE_BODY"}
        p["plan"]["plan_id"] = digest({k: v for k, v in p["plan"].items() if k != "plan_id"})
        with self.assertRaises(ValueError): validate_packet(p)
        r = replay()["results"][0]["days"][0]["packet"]
        r["run"]["known_cost_usd"] = "0"
        with self.assertRaises(ValueError): validate_packet(r)

    def test_private_journal_refuses_protected_existing_and_symlink_paths(self):
        with self.assertRaises(ops.SnapshotError): PrivateRunJournal(ops.ROOT / "output" / "private.jsonl")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.jsonl"
            journal = PrivateRunJournal(path)
            try:
                journal(packet())
                self.assertEqual(read_packet(path), packet())
                with self.assertRaises(ops.SnapshotError): PrivateRunJournal(path)
                link = Path(tmp) / "link.jsonl"
                link.symlink_to(path)
                with self.assertRaises(ops.SnapshotError): PrivateRunJournal(link)
                with path.open("a") as f: f.write('{"interrupted":')
                with self.assertRaises(ValueError): read_packet(path)
            finally: journal.close()

    def test_pinned_stored_plan_never_fabricates_new_arrivals(self):
        from config import DB_PATH
        p = stored_plan(DB_PATH, Policy("2026-10-11T00:00:00Z"))
        self.assertEqual(p["snapshot_kind"], "stored snapshot")
        self.assertEqual(p["counts"]["new_planned"], 0)
        self.assertNotIn("body", p["records"][0])
        self.assertFalse(p["origin_authenticated"])
        self.assertEqual(len(p["snapshot_identity"]["db"]), 64)

    def test_html_escapes_metadata_keeps_noindex_and_unknown_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = base_snapshot(Path(tmp))
            s["analysis_capacity"] = packet()
            html = ops.render_html(s)
            self.assertIn("&lt;img", html)
            self.assertNotIn("<img src=x", html)
            self.assertIn("noindex,nofollow", html)
            self.assertIn("attempted, fully analyzed and cost are unknown", html)
            self.assertIn("scope='col'", html)
            self.assertIn("tabindex='0'", html)
            self.assertNotIn("FICTIONAL source text", html)


class OperationsBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        try: cls.browser = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop()
            raise unittest.SkipTest("chromium not available: %s" % type(exc).__name__)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def test_desktop_mobile_keyboard_semantics_and_private_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = base_snapshot(Path(tmp))
            s["analysis_capacity"] = packet()
            s["analysis_replay"] = replay()
            html = ops.render_html(s)
            for width in (1280, 375):
                page = self.browser.new_page(viewport={"width": width, "height": 900})
                try:
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.set_content(html)
                    page.locator("#analysis-capacity").scroll_into_view_if_needed()
                    self.assertEqual(page.locator("meta[name=robots]").get_attribute("content"), "noindex,nofollow")
                    self.assertEqual(page.locator("h1").inner_text(), "Operations Center")
                    self.assertEqual(page.locator("#analysis-capacity h3").all_text_contents(), ["Overview", "Allocation and queue", "Execution evidence"])
                    self.assertEqual(page.locator("#analysis-capacity img").count(), 0)
                    scroll = page.locator("#analysis-capacity .table-scroll").first
                    scroll.focus()
                    self.assertTrue(scroll.evaluate("el=>el===document.activeElement"))
                    page.keyboard.press("ArrowRight")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    self.assertEqual(errors, [])
                    self.assertNotIn("FICTIONAL source text", page.locator("body").inner_text())
                finally: page.close()
