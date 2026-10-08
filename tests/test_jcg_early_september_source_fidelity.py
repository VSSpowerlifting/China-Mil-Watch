"""No-state backfill feasibility contracts for exactly two publisher originals."""
import hashlib
import unittest
from types import SimpleNamespace

from core.collection import status as st
from core.collection.contract import CandidateReference
from scripts.probe_jcg_early_september_fidelity import (
    CUTOFF, EXPECTED_ALL, HISTORICAL_WINDOW, TO_CHECK, inspect,
)

BASE = "https://www.kaiho.mlit.go.jp/e/topics_archive/article"


class FakeAdapter:
    def __init__(self, mutate=None):
        self.mutate = mutate
        self.fetched = []
        self.extracted = []

    def discover(self, window):
        self.window = window
        refs = [CandidateReference(BASE + ident.split(":")[-1] + ".html",
                                   "jp_jcg_press_en", "publisher-index", day)
                for ident, day in EXPECTED_ALL.items()]
        if self.mutate == "missing":
            refs = refs[:-1]
        if self.mutate == "wrong_date":
            refs[0] = CandidateReference(refs[0].url, "jp_jcg_press_en",
                                         "publisher-index", "2000-01-01")
        return SimpleNamespace(ok=True, status=st.OK, references=refs)

    def fetch(self, reference):
        self.fetched.append(reference.url)
        if self.mutate == "fetch_fail":
            return SimpleNamespace(status=st.FETCH_FAILURE)
        return SimpleNamespace(status=st.OK, payload_sha256="a" * 64,
                               reference=reference)

    def extract(self, capture):
        self.extracted.append(capture.reference.url)
        if self.mutate == "extract_fail":
            return SimpleNamespace(status=st.EXTRACTION_FAILURE, documents=[])
        identity = "jcg-en:" + capture.reference.url.split("article")[-1].replace(".html", "")
        original = "Japan Coast Guard officially reported capacity building and maritime safety. " * 5
        digest = hashlib.sha256(original.encode()).hexdigest()
        meta = {
            "source_identity": identity,
            "content_sha256": digest if self.mutate != "hash_mismatch" else "bad",
            "issuer": "Japan Coast Guard",
            "body_scope": "published_html_text_only",
            "attachments_collected": False,
            "attachment_urls": ["https://www.kaiho.mlit.go.jp/e/topics_archive/upload/sample.pdf"],
            "html_datetime_verdict": "observed_stale_template_2021-3-1",
        }
        date_value = capture.reference.hint_published_date
        if self.mutate == "body_date_mismatch":
            date_value = "2001-01-01"
        doc = SimpleNamespace(
            source_slug="jp_jcg_press_en", published_date=date_value,
            language_tag="en", text_original=original, extra=meta)
        return SimpleNamespace(status=st.OK, documents=[doc])


class JCGSeptemberSourceProof(unittest.TestCase):
    def test_five_listed_only_two_fetched_and_no_state(self):
        fake = FakeAdapter()
        report, ok = inspect(adapter=fake)
        self.assertTrue(ok)
        self.assertEqual(report["discovered"], 5)
        self.assertEqual({v["identity"] for v in report["records"]}, TO_CHECK)
        self.assertEqual(len(fake.fetched), 2)
        self.assertTrue(all(any(str(k).split(":")[-1] in u for u in fake.fetched)
                            for k in TO_CHECK))
        self.assertEqual(len(fake.extracted), 2)
        self.assertEqual(report["index_cutoff"], CUTOFF.isoformat())
        self.assertTrue(report["shadow_state_written"] is False)
        self.assertTrue(report["production_state_written"] is False)
        self.assertFalse(report["publishing_or_editorial_approval"])
        self.assertTrue(all(len(x["original_text_sha256"]) == 64 for x in report["records"]))
        self.assertNotIn("Japan Coast Guard officially reported", str(report))

    def test_fails_closed_on_publisher_index_missing_or_changed(self):
        for mode in ("missing", "wrong_date"):
            with self.subTest(mode=mode):
                fake = FakeAdapter(mode)
                report, ok = inspect(adapter=fake)
                self.assertFalse(ok)
                self.assertEqual(len(fake.fetched), 0)
                self.assertTrue(report["failure"].startswith("unexpected_"))

    def test_refuses_bad_body_and_transport(self):
        for mode in ("fetch_fail", "extract_fail", "hash_mismatch", "body_date_mismatch"):
            with self.subTest(mode=mode):
                report, ok = inspect(adapter=FakeAdapter(mode))
                self.assertFalse(ok)
                self.assertIn("failure", report)
                self.assertFalse(report["shadow_state_written"])

    def test_declared_scope_does_not_override_normal_collection_limit(self):
        from scripts import shadow_collect_desk
        self.assertIn("japan_jcg", shadow_collect_desk.DESKS)
        self.assertGreater(HISTORICAL_WINDOW, 30)
        self.assertEqual(HISTORICAL_WINDOW, 38)
        self.assertTrue(all(day >= "2026-09-01" for day in EXPECTED_ALL.values()))
        # Do not run the 38-day lookback through the persistent collector
        # or invent an early September shadow day; this PR is research only.
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/probe_jcg_early_september_fidelity.py").read_text()
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("git push", source)


if __name__ == "__main__":
    unittest.main()
