"""Measured ministry structures only; sockets are forbidden in this suite."""
import hashlib
import json
import socket
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from core.collection import status as st
from core.collection.contract import CandidateReference, CaptureResult, CollectionWindow
from core.collection.vietnam_sources import SOURCES
from scraper.sources.vn_ministries import VNMinistryAdapter
from scripts.shadow_collect_vietnam_ministry import collect, load_source
from scripts.review_vietnam_ministry_state import review
from tests.test_vn_shadow_http import Clock, FakeResponse, FakeSession

FIX = Path(__file__).parent / "fixtures/vn_ministries"
ROWS = json.loads((FIX / "requests.json").read_text())["requests"]
FILES = {r["url"]: r.get("fixture") or (r.get("derived_fixture") or {}).get("file")
         for r in ROWS if r.get("fixture") or r.get("derived_fixture")}
URLS = {f: u for u, f in FILES.items()}
MPS = "vn_mps_foreign_affairs_vi"
ENERGY = "vn_moit_energy_vi"
INDUSTRY = "vn_moit_foundational_industry_vi"
LISTINGS = {MPS: "mps-rss-34.bin", ENERGY: "derived-moit-listing-nang-luong.html",
            INDUSTRY: "derived-moit-listing-cong-nghiep-nen-tang.html"}


def response(name, status=200, headers=None):
    ctype = "application/xml" if name.endswith("rss-34.bin") else "text/html"
    if "robots" in name:
        ctype = "text/plain"
    return FakeResponse(status, (FIX / name).read_bytes(), headers or {"Content-Type": ctype})


def adapter(slug, extra=(), listing=None, robots=None):
    clock = Clock()
    session = FakeSession([response(robots or ("mps-robots.bin" if slug == MPS
                                               else "moit-robots.bin")),
                           listing or response(LISTINGS[slug])] + list(extra))
    return VNMinistryAdapter(load_source(slug), session=session, sleeper=clock.sleep,
                             clock=clock, wall=clock, max_requests=42)


def capture(slug, name, text=None):
    url = URLS[name]
    body = (FIX / name).read_text() if text is None else text
    return CaptureResult(CandidateReference(url, slug), st.OK, url, final_url=url,
                         http_status=200, content_type="text/html", body=body,
                         payload_bytes=len(body.encode()),
                         payload_sha256=hashlib.sha256(body.encode()).hexdigest())


class MinistryCase(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_each_measured_surface_selects_its_complete_window(self):
        for slug, day, count in [(MPS, date(2026, 10, 5), 2),
                                 (ENERGY, date(2026, 9, 30), 2),
                                 (INDUSTRY, date(2026, 9, 30), 1)]:
            with self.subTest(slug=slug):
                a = adapter(slug)
                result = a.discover(CollectionWindow(day))
                self.assertEqual(result.status, st.OK, result.error_detail)
                self.assertEqual(len(result.references), count)
                self.assertEqual(a.listing_report["coverage"], "proven")
                self.assertEqual(len(a.request_log), 2)

    def test_quiet_window_is_distinct_from_unprovable_history(self):
        for slug in SOURCES:
            a = adapter(slug)
            self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 6))).status,
                             st.OK_NO_PUBLICATIONS)
            a = adapter(slug)
            result = a.discover(CollectionWindow(date(2020, 1, 1)))
            self.assertEqual(result.status, st.LISTING_FAILURE)
            self.assertFalse(result.references)
            self.assertEqual(len(a.request_log), 2)

    def test_published_first_page_cannot_be_silently_truncated(self):
        soup = BeautifulSoup((FIX / LISTINGS[ENERGY]).read_text(), "html.parser")
        soup.select_one('[modulerootid="5238390"] article').decompose()
        a = adapter(ENERGY, listing=FakeResponse(200, str(soup).encode(),
                                              {"Content-Type": "text/html"}))
        self.assertEqual(a.discover(CollectionWindow(date(2026, 9, 30))).status,
                         st.LISTING_FAILURE)

    def test_rss_identity_and_declared_offset_are_required(self):
        original = (FIX / LISTINGS[MPS]).read_text()
        for text in [original.replace("</guid>", "bad</guid>", 1),
                     original.replace(" UTC", ""),
                     original.replace("<rss ", "<!DOCTYPE rss><rss ", 1)]:
            a = adapter(MPS, listing=FakeResponse(200, text.encode(),
                                                 {"Content-Type": "application/xml"}))
            self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 5))).status,
                             st.LISTING_FAILURE)

    def test_challenge_and_app_shell_stop_at_robots(self):
        for name in ["derived-mond-robots-challenge.html", "mof-robots-app-shell.bin"]:
            a = adapter(MPS, robots=name)
            self.assertFalse(a.discover(CollectionWindow(date(2026, 10, 5))).ok)
            self.assertEqual(len(a.request_log), 1)

    def test_every_saved_article_extracts_with_publisher_and_visible_date(self):
        for name in URLS:
            if "article" not in name:
                continue
            slug = MPS if name.startswith("mps-") else ENERGY if any(
                s in name for s in ("thue", "nghi-dinh")) else INDUSTRY
            with self.subTest(name=name):
                a = adapter(slug)
                result = a.extract(capture(slug, name))
                self.assertEqual(result.status, st.OK, result.error_detail)
                doc = result.documents[0]
                self.assertEqual(doc.language_tag, "vi")
                self.assertIsNone(doc.extra["published_at_utc"])
                metadata = doc.extra["source_metadata"]
                self.assertEqual(metadata["publisher"], SOURCES[slug].publisher)
                self.assertIsNone(metadata["issuer"])
                self.assertIsNone(metadata["legal_effective_date"])
                self.assertEqual(doc.extra["publication_kind"], "ministry portal report")

    def test_meta_date_does_not_replace_printed_publication_date(self):
        a = adapter(INDUSTRY)
        doc = a.extract(capture(INDUSTRY, "derived-moit-article-date-discrepancy.html")).documents[0]
        self.assertEqual(doc.published_date, "2022-01-12")
        self.assertTrue(doc.extra["source_metadata"]["article_published_time"].startswith("2022-08-25"))
        self.assertTrue(any(s.startswith("metadata_date_differs") for s in doc.extra["anomalies"]))

    def test_nonarticle_and_foreign_identity_are_refused_before_transport(self):
        a = adapter(MPS)
        for url in ["https://example.com/bai-viet/foo-1791199677",
                    URLS["mps-article-concordia.bin"] + "?id=1"]:
            self.assertEqual(a.fetch(CandidateReference(url, MPS)).status, st.FETCH_FAILURE)
        self.assertEqual(len(a.request_log), 0)

    def test_short_unicode_and_table_are_preserved_on_structure(self):
        name = "derived-moit-article-thue-xang-dau.html"
        soup = BeautifulSoup((FIX / name).read_text(), "html.parser")
        body = soup.select_one("div.article-content.common-content")
        body.clear()
        fragment = BeautifulSoup("<p>Việt Nam\u00a0e\u0301</p><table><tr><td>A</td><td>B</td></tr></table>",
                                 "html.parser")
        for child in list(fragment.contents):
            body.append(child)
        result = adapter(ENERGY).extract(capture(ENERGY, name, str(soup)))
        self.assertEqual(result.status, st.OK, result.error_detail)
        self.assertIn("Việt Nam\u00a0e\u0301", result.documents[0].text_original)
        self.assertTrue(any(k == "tr" for k, _ in result.documents[0].extra["blocks"]))

    def test_missing_body_wrong_canonical_and_truncated_html_fail(self):
        name = "mps-article-concordia.bin"
        text = (FIX / name).read_text()
        soup = BeautifulSoup(text, "html.parser")
        soup.select_one(".tinymce-content").decompose()
        for bad in [str(soup), text.replace(URLS[name], "https://example.com/article"),
                    text.replace("</html>", "")]:
            result = adapter(MPS).extract(capture(MPS, name, bad))
            self.assertEqual(result.status, st.EXTRACTION_FAILURE)
            self.assertFalse(result.documents)


class MinistryRunnerCase(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("network"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state"

    def go(self, run_id="first", responses=None, day=date(2026, 10, 5), cap=40):
        responses = responses if responses is not None else [response("mps-article-concordia.bin"),
                                                            response("mps-article-tho-nhi-ky.bin")]
        return collect(self.state, MPS, day, 0, cap, run_id, "test",
                       adapter=adapter(MPS, responses))

    def test_new_duplicate_quiet_and_metadata_are_source_bound(self):
        self.assertEqual(self.go()["new_records"], 2)
        self.assertEqual(self.go("repeat")["unchanged"], 2)
        self.assertEqual(self.go("quiet", [], date(2026, 10, 6))["result"], st.OK_NO_PUBLICATIONS)
        with sqlite3.connect(str(self.state / "shadow.db")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0], 2)
            metadata = json.loads(db.execute("SELECT metadata_json FROM shadow_metadata LIMIT 1").fetchone()[0])
            self.assertTrue(metadata["rss_instant_utc"].endswith("+00:00"))
        clock = json.loads((self.state / "clock.json").read_text())
        self.assertEqual(clock["day_zero_run_id"], "first")
        with self.assertRaises(ValueError):
            collect(self.state, ENERGY, date(2026, 9, 30), adapter=adapter(ENERGY))

    def test_partial_fetch_and_host_stop_never_establish_day_zero(self):
        for status, headers in [(429, {}), (503, {}), (200, {"Retry-After": "20"})]:
            with self.subTest(status=status):
                a = adapter(MPS, [FakeResponse(status, b"", headers)])
                entry = collect(self.state, MPS, date(2026, 10, 5), 0, 40,
                                "stop-%s-%s" % (status, len(headers)), "test", adapter=a)
                self.assertEqual(entry["health"], "fail")
                self.assertEqual(len(a.request_log), 3)
                self.assertEqual(len(entry["deferred_urls"]), 1)
                self.assertFalse((self.state / "clock.json").exists())

    def test_window_above_cap_fails_without_fetch_or_clock(self):
        entry = self.go(cap=1)
        self.assertEqual(entry["health"], "fail")
        self.assertEqual(entry["retrieved"], 0)
        self.assertFalse((self.state / "clock.json").exists())

    def test_review_is_deterministic_readonly_and_checks_every_capture(self):
        self.go()
        self.go("repeat")
        before = {p: p.read_bytes() for p in self.state.rglob("*") if p.is_file()}
        first = review(self.state, MPS)
        self.assertEqual(first, review(self.state, MPS))
        self.assertTrue(first["rehearsal_only"])
        self.assertIsNone(first["owner_signoff"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        with self.assertRaises(ValueError):
            review(self.state, ENERGY)
        capture_file = next((self.state / "captures").glob("*.bin"))
        capture_file.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            review(self.state, MPS)

    def test_review_refuses_forged_metadata_even_with_rehashed_database(self):
        self.go()
        db = self.state / "shadow.db"
        with sqlite3.connect(str(db)) as conn:
            conn.execute("UPDATE shadow_metadata SET metadata_json = '{}' ")
        ledger = next((self.state / "ledger").glob("*.json"))
        entry = json.loads(ledger.read_text())
        entry["state_sha256_after"] = hashlib.sha256(db.read_bytes()).hexdigest()
        ledger.write_text(json.dumps(entry))
        with self.assertRaises((ValueError, KeyError)):
            review(self.state, MPS)


if __name__ == "__main__":
    unittest.main()
