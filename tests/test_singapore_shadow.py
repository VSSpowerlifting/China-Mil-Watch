"""
Singapore shadow desk: isolation, extraction discipline, and the clock.

The collector's job in this phase is to prove it can retrieve and identify
official documents reliably. The tests' job is to prove it cannot reach
production while doing so, and that it never reports a failure as silence.

Everything runs from saved bounded fixtures. No network, no tracked-database
access, no writes outside a temporary directory.
"""

from __future__ import annotations

import json
import re
import sqlite3
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import (                          # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow)
from scraper.sources import sg_mindef as sg                     # noqa: E402
import scripts.shadow_collect as runner                         # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "sg_mindef"
MANIFEST = REPO_ROOT / "shadow" / "singapore_mindef" / "manifest.json"
TRACKED_DB = REPO_ROOT / "pla_watch.db"
PRODUCTION_OUT = REPO_ROOT / "output"

ROBOTS_ALLOW = "User-Agent: *\nAllow: /\nDisallow: /search\n"
ROBOTS_DENY = "User-Agent: *\nDisallow: /\n"


def items():
    return json.loads((FIX / "items.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None, url=""):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self.url = url


class FakeSession:
    """Serves the saved fixtures. Records every URL it was asked for."""

    def __init__(self, robots=ROBOTS_ALLOW, item_status=200, sitemap_status=200,
                 sitemap_text=None):
        self.robots = robots
        self.item_status = item_status
        self.sitemap_status = sitemap_status
        self.sitemap_text = sitemap_text
        self.calls = []
        self._by_url = {}
        for rec in items():
            self._by_url[rec["url"]] = (FIX / rec["file"]).read_text(encoding="utf-8")

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        if url == sg.ROBOTS:
            return FakeResponse(self.robots, 200)
        if url == sg.SITEMAP:
            text = (self.sitemap_text if self.sitemap_text is not None
                    else (FIX / "sitemap_fixtures.xml").read_text(encoding="utf-8"))
            return FakeResponse(text, self.sitemap_status)
        if self.item_status != 200:
            return FakeResponse("", self.item_status)
        body = self._by_url.get(url)
        if body is None:
            return FakeResponse("", 404)
        return FakeResponse(body, 200, url=url)


def adapter(session=None, cap=40):
    src = runner.load_source()
    return sg.SGMindefAdapter(src, session=session or FakeSession(), cap=cap,
                              sleeper=lambda _s: None)


def window():
    """Covers the whole fixture set deterministically."""
    return CollectionWindow(target_date=date(2026, 8, 31), lookback_days=365)


# ── Isolation ────────────────────────────────────────────────────────────────

class TestIsolationFromProduction(unittest.TestCase):

    def test_the_shadow_manifest_is_not_under_the_discovered_desks_path(self):
        """
        `load_all_desks()` globs desks/*/manifest.json. A Singapore manifest
        there would be synced into pla_watch.db by the next migration run.
        """
        self.assertTrue(MANIFEST.is_file())
        self.assertNotIn("desks", MANIFEST.relative_to(REPO_ROOT).parts[:1])
        discovered = {p.parent.name for p in (REPO_ROOT / "desks").glob("*/manifest.json")}
        self.assertEqual(discovered, {"china"})

    def test_production_discovery_does_not_find_singapore(self):
        from core.manifests import load_all_desks
        configs = load_all_desks()
        self.assertEqual(sorted(configs), ["china"])
        slugs = {s.slug for cfg in configs.values() for s in cfg.sources}
        self.assertNotIn("sg_mindef_releases", slugs)

    def test_the_shadow_source_is_disabled_in_its_own_manifest(self):
        cfg = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertFalse(cfg["desk"]["active"])
        for source in cfg["sources"]:
            with self.subTest(source=source["slug"]):
                self.assertFalse(source["enabled"])

    def test_singapore_is_absent_from_the_tracked_database(self):
        from scripts.reconcile_db import _read_only
        with _read_only(str(TRACKED_DB)) as con:
            desks = [r[0] for r in con.execute("SELECT desk_id FROM desks")]
            slugs = [r[0] for r in con.execute("SELECT slug FROM sources")]
        self.assertEqual(sorted(desks), ["china"])
        self.assertNotIn("sg_mindef_releases", slugs)

    def test_the_runner_refuses_to_write_inside_the_repository(self):
        for bad in (REPO_ROOT, REPO_ROOT / "state", REPO_ROOT / "output" / "s"):
            with self.subTest(path=str(bad)):
                with self.assertRaises(SystemExit):
                    runner.assert_isolated(bad)

    def test_the_runner_never_names_the_production_database(self):
        def code_only(path):
            """Strip docstrings and comments — prose may name the file it
            promises never to touch; executable code may not."""
            src = (REPO_ROOT / path).read_text(encoding="utf-8")
            src = re.sub(r'(?s)""".*?"""', " ", src)
            return re.sub(r"(?m)#.*$", " ", src)
        for path in ("scripts/shadow_collect.py", "scraper/sources/sg_mindef.py"):
            with self.subTest(module=path):
                code = code_only(path)
                self.assertNotIn("pla_watch.db", code)
                self.assertNotIn("sqlite3.connect(str(PRODUCTION_DB))", code)

    def test_singapore_does_not_appear_in_the_public_renderer(self):
        gp = (REPO_ROOT / "site" / "preview"
              / "generate_preview.py").read_text(encoding="utf-8")
        for token in ("singapore", "mindef", "sg_mindef"):
            with self.subTest(token=token):
                self.assertNotIn(token, gp.lower())

    def test_no_workflow_makes_the_shadow_run_write_to_main(self):
        wf = (REPO_ROOT / ".github" / "workflows"
              / "singapore_shadow.yml").read_text(encoding="utf-8")
        # Checking out main is fine and necessary — that is where the collector
        # lives. What must never happen is a push to it.
        pushes = re.findall(r"git push\s+\S+\s+(\S+)", wf)
        self.assertTrue(pushes, "no push found to check")
        for ref in pushes:
            with self.subTest(ref=ref):
                self.assertEqual(ref, "shadow/singapore-mindef")
        self.assertNotIn("--force", wf)
        self.assertNotIn("actions/deploy-pages", wf)
        self.assertNotIn("pipeline.py", wf)
        self.assertIn("permissions:\n  contents: write", wf)


# ── Extraction discipline ────────────────────────────────────────────────────

class TestExtractionFailsClosed(unittest.TestCase):

    def _capture(self, body, url=None):
        url = url or items()[0]["url"]
        ref = CandidateReference(url=url, source_slug="sg_mindef_releases")
        return CaptureResult(ref, st.OK, url, http_status=200, body=body)

    def test_a_real_document_extracts(self):
        rec = items()[0]
        body = (FIX / rec["file"]).read_text(encoding="utf-8")
        res = adapter().extract(self._capture(body, rec["url"]))
        self.assertEqual(res.status, st.OK)
        doc = res.documents[0]
        self.assertTrue(doc.title_original)
        self.assertRegex(doc.published_date, r"^\d{4}-\d{2}-\d{2}$")
        self.assertGreaterEqual(len(doc.text_original), sg.MIN_BODY_CHARS)
        self.assertEqual(doc.language_tag, "en")
        self.assertIn(doc.extra["publication_kind"], set(sg.KINDS.values()) | {"other"})

    def test_an_empty_body_is_refused(self):
        res = adapter().extract(self._capture(""))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)

    def test_a_stub_body_is_refused(self):
        res = adapter().extract(self._capture("<h1>A release</h1><p>short</p>"))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("too short", res.error_detail)

    def test_a_missing_title_is_refused(self):
        res = adapter().extract(self._capture("<p>" + "x" * 500 + "</p>"))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("no title", res.error_detail)

    def test_a_url_without_a_date_is_refused(self):
        bad = "https://www.mindef.gov.sg/news-and-events/latest-releases/about/"
        res = adapter().extract(self._capture("<h1>T</h1><p>" + "x" * 500 + "</p>", bad))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("publication date", res.error_detail)

    def test_a_non_canonical_url_is_refused(self):
        bad = "https://example.com/news-and-events/latest-releases/1jan26-nr/"
        res = adapter().extract(self._capture("<h1>T</h1><p>" + "x" * 500 + "</p>", bad))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)

    def test_the_publication_date_comes_from_the_slug_not_lastmod(self):
        self.assertEqual(
            sg.slug_published_date(
                "https://www.mindef.gov.sg/news-and-events/latest-releases/5aug26-pq2/"),
            "2026-08-05")

    def test_query_strings_and_fragments_never_change_identity(self):
        base = "https://www.mindef.gov.sg/news-and-events/latest-releases/15aug26-speech/"
        for variant in (base, base + "?utm_source=x", base + "#top"):
            with self.subTest(variant=variant):
                self.assertEqual(sg.canonical_url(variant), base)


# ── Result taxonomy ──────────────────────────────────────────────────────────

class TestFailuresAreNotSilence(unittest.TestCase):

    def test_robots_disallow_fails_closed_before_any_fetch(self):
        s = FakeSession(robots=ROBOTS_DENY)
        res = adapter(s).discover(window())
        self.assertEqual(res.status, st.AUTH_FAILURE)
        self.assertEqual([c for c in s.calls if "latest-releases" in c], [])

    def test_a_sitemap_failure_is_not_reported_as_no_publications(self):
        res = adapter(FakeSession(sitemap_status=500)).discover(window())
        self.assertEqual(res.status, st.LISTING_FAILURE)
        self.assertNotEqual(res.status, st.OK_NO_PUBLICATIONS)

    def test_a_sitemap_403_is_an_access_failure(self):
        res = adapter(FakeSession(sitemap_status=403)).discover(window())
        self.assertEqual(res.status, st.AUTH_FAILURE)

    def test_an_empty_sitemap_parse_is_a_listing_failure(self):
        empty = '<?xml version="1.0"?><urlset></urlset>'
        res = adapter(FakeSession(sitemap_text=empty)).discover(window())
        self.assertEqual(res.status, st.LISTING_FAILURE)
        self.assertIn("zero release URLs", res.error_detail)

    def test_an_item_403_is_an_access_failure_not_a_missing_document(self):
        a = adapter(FakeSession(item_status=403))
        ref = CandidateReference(url=items()[0]["url"],
                                 source_slug="sg_mindef_releases")
        cap = a.fetch(ref)
        self.assertEqual(cap.status, st.AUTH_FAILURE)

    def test_a_window_with_no_publications_is_a_success(self):
        far = CollectionWindow(target_date=date(2019, 1, 1), lookback_days=1)
        res = adapter().discover(far)
        self.assertEqual(res.status, st.OK_NO_PUBLICATIONS)
        self.assertTrue(st.is_success(res.status))


# ── The run, state, and the clock ────────────────────────────────────────────

class ShadowRunCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sg-shadow-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "state"

    def go(self, session=None, run_id="test-1", target=date(2026, 8, 31),
           lookback=365, cap=40):
        return runner.run(self.state, target, lookback, cap, run_id, "testsha",
                          adapter=adapter(session or FakeSession(), cap=cap))


class TestShadowRun(ShadowRunCase):

    def test_a_first_run_inserts_and_records_a_ledger_entry(self):
        e = self.go()
        self.assertEqual(e["result"], st.OK)
        self.assertEqual(e["health"], "ok")
        self.assertGreater(e["inserted"], 0)
        self.assertEqual(e["duplicates"], 0)
        self.assertEqual(e["extraction_failures"], 0)
        self.assertEqual(e["access_failures"], 0)
        led = list((self.state / "ledger").glob("*.json"))
        self.assertEqual(len(led), 1)
        stored = json.loads(led[0].read_text(encoding="utf-8"))
        for field in ("run_id", "collector_commit", "started_utc",
                      "finished_utc", "robots_status", "listing_status",
                      "discovered", "selected", "retrieved", "inserted",
                      "duplicates", "fetch_failures",
                      "extraction_failures", "access_failures",
                      "state_sha256_before", "state_sha256_after", "result",
                      "health"):
                with self.subTest(field=field):
                    self.assertIn(field, stored)

    def test_a_second_run_inserts_nothing_and_deduplicates(self):
        first = self.go(run_id="r1")
        second = self.go(run_id="r2")
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["duplicates"], first["inserted"])
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["stored_total"], first["stored_total"])

    def test_the_stored_corpus_is_identical_across_two_fresh_runs(self):
        a = self.go(run_id="a")
        other = Path(tempfile.mkdtemp(prefix="sg-shadow-b-"))
        self.addCleanup(shutil.rmtree, other, True)
        runner.run(other / "state", date(2026, 8, 31), 365, 40, "b", "testsha",
                   adapter=adapter(FakeSession(), cap=40))
        def rows(p):
            con = sqlite3.connect(str(p))
            r = con.execute("SELECT url, content_sha256, published_date, "
                            "publication_kind FROM shadow_records "
                            "ORDER BY url").fetchall()
            con.close()
            return r
        self.assertEqual(rows(self.state / "shadow.db"),
                         rows(other / "state" / "shadow.db"))
        self.assertGreater(a["inserted"], 0)

    def test_two_documents_sharing_a_title_stay_distinct(self):
        e = self.go()
        con = sqlite3.connect(str(self.state / "shadow.db"))
        con.execute("INSERT INTO shadow_records (url, source_slug,"
                    " title_original, text_original, published_date,"
                    " language_tag, publication_kind, content_sha256)"
                    " SELECT url || 'x2/', source_slug, title_original,"
                    " text_original, published_date, language_tag,"
                    " publication_kind, content_sha256 FROM shadow_records"
                    " LIMIT 1")
        con.commit()
        titles = con.execute("SELECT title_original, COUNT(*) FROM"
                             " shadow_records GROUP BY title_original"
                             " HAVING COUNT(*) > 1").fetchall()
        total = con.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
        con.close()
        self.assertTrue(titles, "fixture did not produce a shared title")
        self.assertEqual(total, e["inserted"] + 1,
                         "a shared title collapsed two distinct records")

    def test_an_interrupted_run_does_not_corrupt_prior_state(self):
        first = self.go(run_id="r1")
        before = (self.state / "shadow.db").read_bytes()
        broken = FakeSession(sitemap_status=500)
        second = self.go(session=broken, run_id="r2")
        self.assertEqual(second["health"], "fail")
        self.assertEqual((self.state / "shadow.db").read_bytes(), before)
        con = sqlite3.connect(str(self.state / "shadow.db"))
        self.assertEqual(
            con.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0],
            first["inserted"])
        con.close()

    def test_the_run_writes_nothing_outside_its_state_directory(self):
        db_before = TRACKED_DB.stat().st_size
        out_before = sorted(p.name for p in PRODUCTION_OUT.iterdir())
        self.go()
        self.assertEqual(TRACKED_DB.stat().st_size, db_before)
        self.assertEqual(sorted(p.name for p in PRODUCTION_OUT.iterdir()),
                         out_before)
        for ext in ("-wal", "-shm"):
            self.assertFalse(Path(str(TRACKED_DB) + ext).exists())

    def test_the_selection_is_bounded_and_deterministic(self):
        a = self.go(run_id="a", cap=3)
        self.assertLessEqual(a["selected"], 3)
        other = Path(tempfile.mkdtemp(prefix="sg-cap-"))
        self.addCleanup(shutil.rmtree, other, True)
        b = runner.run(other / "s", date(2026, 8, 31), 365, 3, "b", "sha",
                       adapter=adapter(FakeSession(), cap=3))
        self.assertEqual(a["content_hashes"], b["content_hashes"])


class TestTheClock(ShadowRunCase):

    def test_the_first_successful_run_starts_the_clock_once(self):
        first = self.go(run_id="r1")
        clock = json.loads((self.state / "clock.json").read_text(encoding="utf-8"))
        self.assertEqual(clock["day_zero_run_id"], "r1")
        self.assertEqual(first["shadow_day"], 0)
        second = self.go(run_id="r2")
        clock2 = json.loads((self.state / "clock.json").read_text(encoding="utf-8"))
        self.assertEqual(clock2, clock, "day zero was rewritten")

    def test_a_failed_run_neither_starts_nor_advances_the_clock(self):
        failed = self.go(session=FakeSession(sitemap_status=500), run_id="bad")
        self.assertEqual(failed["health"], "fail")
        self.assertIsNone(failed["shadow_day"])
        self.assertFalse((self.state / "clock.json").exists(),
                         "a failed run started the clock")

    def test_an_expected_empty_day_is_a_success_that_records_history(self):
        far = date(2019, 1, 1)
        e = self.go(run_id="quiet", target=far, lookback=1)
        self.assertEqual(e["result"], st.OK_NO_PUBLICATIONS)
        self.assertEqual(e["health"], "ok")
        self.assertEqual(e["inserted"], 0)
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 1)
        self.assertTrue((self.state / "clock.json").exists())

    def test_the_day_number_is_derived_not_hard_coded(self):
        src = (REPO_ROOT / "scripts" / "shadow_collect.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r'shadow_day"?\]?\s*=\s*\d+')
        self.assertIn("day_zero_utc", src)


class TestFetchFailureIsNotExtractionFailure(ShadowRunCase):

    def test_an_unreachable_item_is_counted_as_a_fetch_failure(self):
        """
        A source going dark must not read like a parser bug. The two counters
        are separate and the result names the one that happened.
        """
        class Gone(FakeSession):
            def get(self, url, timeout=None, headers=None):
                if "latest-releases" in url and url != sg.SITEMAP:
                    self.calls.append(url)
                    return FakeResponse("", 404)
                return super().get(url, timeout=timeout, headers=headers)
        e = self.go(session=Gone(), run_id="gone")
        self.assertGreater(e["fetch_failures"], 0)
        self.assertEqual(e["extraction_failures"], 0)
        self.assertEqual(e["result"], st.FETCH_FAILURE)
        self.assertEqual(e["health"], "fail")

    def test_a_retrievable_but_unparseable_item_is_an_extraction_failure(self):
        class Stub(FakeSession):
            def get(self, url, timeout=None, headers=None):
                if "latest-releases" in url and url != sg.SITEMAP:
                    self.calls.append(url)
                    return FakeResponse("<html><h1>T</h1><p>short</p></html>", 200)
                return super().get(url, timeout=timeout, headers=headers)
        e = self.go(session=Stub(), run_id="stub")
        self.assertGreater(e["extraction_failures"], 0)
        self.assertEqual(e["fetch_failures"], 0)
        self.assertEqual(e["result"], st.EXTRACTION_FAILURE)


class TestSitemapParsing(unittest.TestCase):

    def test_the_real_sitemap_parses_to_release_urls_only(self):
        xml = (FIX / "sitemap.xml").read_text(encoding="utf-8")
        entries = sg.parse_sitemap(xml)
        self.assertGreater(len(entries), 100)
        for url, _ in entries:
            with self.subTest(url=url):
                self.assertTrue(sg.RELEASE_RE.match(url))

    def test_a_non_release_url_is_not_discovered(self):
        xml = ('<urlset><url><loc>https://www.mindef.gov.sg/about-us/</loc>'
               '<lastmod>2026-01-01T00:00:00Z</lastmod></url></urlset>')
        self.assertEqual(sg.parse_sitemap(xml), [])


if __name__ == "__main__":
    unittest.main()
