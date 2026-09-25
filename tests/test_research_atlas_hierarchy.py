"""Rendered Atlas hierarchy and provenance, without touching production state."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402
from core.desk_registry import load_registry  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ResearchAtlasHierarchy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="research-atlas-"))
        cls.out = cls.tmp / "site"
        cls.db_before = digest(gp.TRACKED_DB)
        cls.registry_before = digest(ROOT / "desks" / "registry.json")
        cls.output_before = digest(ROOT / "output" / "index.html")
        gp.build(cls.out, gp.PUBLIC_TITLE, gp.TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                 legacy_routes=True)
        cls.index = json.loads((cls.out / "corpus-index.json").read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def html(self, route):
        return (self.out / route).read_text(encoding="utf-8")

    def test_shared_navigation_and_breadcrumbs(self):
        for route in ("index.html", "archive.html", "analysis.html",
                      "coverage.html", "desks.html", "sources.html"):
            with self.subTest(route=route):
                self.assertIn('href="archive.html"', self.html(route))
                self.assertIn('>Atlas</a>', self.html(route))
        record_id = self.index["records"][0][0]
        record = self.html("record/%d.html" % record_id)
        self.assertIn('aria-label="Breadcrumb"', record)
        self.assertLess(record.index('>Atlas</a>'),
                        record.index('>Record %d</span>' % record_id))
        source = next(s for s in self.index["sources"] if s["desk"])
        source_page = self.html("source/%s.html" % source["code"])
        self.assertIn(source["desk"]["route"], source_page)
        self.assertIn('aria-current="page"', source_page)

    def test_atlas_spine_uses_declared_states_and_snapshot(self):
        snapshot = gp.snapshot_from_corpus(gp.TRACKED_DB)
        for route in ("index.html", "archive.html", "coverage.html",
                      "analysis.html", "desks.html"):
            page = self.html(route)
            with self.subTest(route=route):
                self.assertIn('aria-label="Atlas status and provenance"', page)
                self.assertIn(snapshot["date"], page)
                for desk in load_registry().public_entries:
                    self.assertIn(desk.status_label, page)
        self.assertIn("Paused — collection stopped", self.html("desks.html"))
        self.assertIn("Planned — nothing collected", self.html("desks.html"))

    def test_listing_and_search_resolve_desk_through_source(self):
        self.assertEqual(self.index["fields"],
                         ["id", "date", "source", "state", "title_en", "title_orig"])
        for source in self.index["sources"]:
            self.assertIsNotNone(source["desk"])
            self.assertTrue((self.out / source["desk"]["route"]).is_file())
        self.assertIn('src.desk.route', (self.out / "browse.js").read_text())
        self.assertTrue(any('href="china.html"' in p.read_text(encoding="utf-8")
                            for p in self.out.glob("week-*.html")))

    def test_analysis_separates_draft_published_and_historical(self):
        page = self.html("analysis.html")
        headings = [page.index(label) for label in
                    ("Briefs in development", "Published Briefs",
                     "Historical The PLA Watch archive")]
        self.assertEqual(headings, sorted(headings))
        self.assertIn("Draft Briefs are withheld", page)
        self.assertIn('href="pla-watch.html"', page)

    def test_accessibility_and_local_table_scrolling(self):
        css = (self.out / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".table-scroll { max-width: 100%;", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("focus-visible", css)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("min-height: 44px", css)
        for route in ("index.html", "archive.html", "analysis.html",
                      "coverage.html", "desks.html", "sources.html"):
            page = self.html(route)
            with self.subTest(route=route):
                self.assertEqual(len(re.findall(r"<h1\b", page)), 1)
                self.assertIn('<main id="main"', page)
                self.assertIn('aria-label="Primary"', page)

    def test_deterministic_render_and_no_state_mutation(self):
        second = self.tmp / "second"
        gp.build(second, gp.PUBLIC_TITLE, gp.TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB),
                 legacy_routes=True)
        for route in ("index.html", "archive.html", "analysis.html",
                      "record/%d.html" % self.index["records"][0][0],
                      "corpus-index.json"):
            with self.subTest(route=route):
                self.assertEqual(digest(self.out / route), digest(second / route))
        self.assertEqual(self.db_before, digest(gp.TRACKED_DB))
        self.assertEqual(self.registry_before,
                         digest(ROOT / "desks" / "registry.json"))
        self.assertEqual(self.output_before, digest(ROOT / "output" / "index.html"))


if __name__ == "__main__":
    unittest.main()
