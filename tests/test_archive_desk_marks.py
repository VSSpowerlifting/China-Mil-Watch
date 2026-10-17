"""
Phase 2b: the Archive's finder lift and desk markers stay what the ruling allows.

The lift is the approved finder token (DECISION_LOG 2026-10-10 B1) reached
through `rl-finder`, never a new shadow. The marker is a CSS mask over one
small static outline per country desk, delivered by an explicit allowlist, drawn
on the link both row renderers already share, so `browse.js` is untouched.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for entry in (REPO_ROOT, REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
import build_desk_marks as marks  # noqa: E402
import build_geo_assets as geo  # noqa: E402

PREVIEW = REPO_ROOT / "site" / "preview"
ARCHIVE_CSS = (PREVIEW / "archive.css").read_text(encoding="utf-8")
ARCHIVE_HTML = (PREVIEW / "templates" / "archive.html").read_text(encoding="utf-8")
MARKS = REPO_ROOT / "site" / "assets" / "desk-marks"
TRACKED_DB = REPO_ROOT / "pla_watch.db"
ARCHIVE_JS_CAP = 10_000


class MarkAssetTests(unittest.TestCase):
    def test_eligible_desks_are_the_country_outlines_and_no_others(self):
        self.assertEqual(marks.SLUGS, ("china", "japan", "singapore", "vietnam"))
        self.assertEqual(sorted(p.stem for p in MARKS.glob("*.svg")), list(marks.SLUGS))
        registry = json.loads((REPO_ROOT / "desks" / "registry.json").read_text(encoding="utf-8"))
        slugs = {d.get("slug") or d.get("code")
                 for d in (registry["desks"] if isinstance(registry, dict) else registry)}
        self.assertTrue(set(marks.SLUGS) <= slugs)
        # The US desk is drawn as Hawaii (a seat, not a country) and the
        # Philippines desk has no geometry: neither gets a marker.
        self.assertFalse({"us-indopacific", "philippines"} & set(marks.SLUGS))

    def test_committed_files_are_what_the_generator_builds(self):
        tmp = Path(tempfile.mkdtemp(prefix="desk-marks-"))
        try:
            marks.build(tmp)
            self.assertEqual(sorted(p.name for p in tmp.iterdir()),
                             sorted([s + ".svg" for s in marks.SLUGS] + [marks.RECEIPT]))
            for path in sorted(tmp.iterdir()):
                self.assertEqual(path.read_bytes(), (MARKS / path.name).read_bytes(), path.name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_each_outline_is_the_emblem_outline_byte_for_byte(self):
        emblems = marks.SOURCE.read_text(encoding="utf-8")
        for slug in marks.SLUGS:
            raw = (MARKS / (slug + ".svg")).read_text(encoding="utf-8")
            doc = xml.dom.minidom.parseString(raw)
            paths = doc.getElementsByTagName("path")
            self.assertEqual(len(paths), 1, slug)
            self.assertEqual(paths[0].getAttribute("d"), marks.outline(emblems, slug), slug)
            # A standalone image, line-free decoration: no script, raster or text.
            self.assertNotRegex(raw, r"<(image|text|use|script|foreignObject)\b|href=")
            self.assertRegex(raw, r'viewBox="[-\d. ]+"')
            self.assertLess(len(raw.encode("utf-8")), 4_100, slug)

    def test_receipt_records_input_and_output_hashes(self):
        receipt = json.loads((MARKS / marks.RECEIPT).read_text(encoding="utf-8"))
        import hashlib
        self.assertEqual(receipt["input"]["sha256"],
                         hashlib.sha256(marks.SOURCE.read_bytes()).hexdigest())
        for name, entry in receipt["outputs"].items():
            data = (MARKS / name).read_bytes()
            self.assertEqual((entry["bytes"], entry["sha256"]),
                             (len(data), hashlib.sha256(data).hexdigest()), name)
        self.assertNotRegex(json.dumps(receipt), r"20\d\d-\d\d-\d\d")


class ArchiveStyleTests(unittest.TestCase):
    def test_the_finder_takes_the_approved_lift_through_rl_finder(self):
        self.assertRegex(ARCHIVE_HTML, r'id="controls" class="finder rl-finder"')
        head = re.search(r"\{% block head_scripts %\}(.*?)\{% endblock %\}", ARCHIVE_HTML).group(1)
        self.assertLess(head.index('href="relief.css"'), head.index('href="archive.css"'))
        # archive.css casts and names no shadow of its own.
        self.assertNotRegex(ARCHIVE_CSS, r"box-shadow\s*:(?!\s*none)|--lift-|drop-shadow|text-shadow")

    def test_one_rule_per_eligible_desk_and_nothing_generic(self):
        used = re.findall(r'\.archive-page \.row-side a\[href="([a-z-]+)\.html"\]::before'
                          r"\{-webkit-mask-image:url\(assets/desk-marks/([a-z-]+)\.svg\);"
                          r"mask-image:url\(assets/desk-marks/\2\.svg\)\}", ARCHIVE_CSS)
        self.assertEqual(sorted(slug for slug, _ in used), list(marks.SLUGS))
        self.assertTrue(all(a == b for a, b in used))
        # Every url() the stylesheet adds under desk-marks is an allowlisted file.
        self.assertEqual(sorted(set(re.findall(r"assets/desk-marks/([a-z-]+)\.svg", ARCHIVE_CSS))),
                         list(marks.SLUGS))
        # The shared box applies only to the mapped hrefs, so an unmapped desk
        # draws nothing rather than a filled rectangle.
        base = re.search(r"a:is\(([^)]*)\)::before\{content:\"\"", ARCHIVE_CSS).group(1)
        self.assertEqual(sorted(re.findall(r'href="([a-z-]+)\.html"', base)), list(marks.SLUGS))

    def test_marker_is_decorative_and_withdrawn_in_forced_colours_and_print(self):
        self.assertIn('content:""', ARCHIVE_CSS)
        for query in ("@media(forced-colors:active)", "@media print"):
            block = ARCHIVE_CSS[ARCHIVE_CSS.index(query + "{.archive-page .row-side a::before"):]
            self.assertIn("display:none", block[:block.index("}}") + 2], query)

    def test_archive_javascript_is_untouched_and_inside_its_cap(self):
        self.assertLessEqual((PREVIEW / "browse.js").stat().st_size, ARCHIVE_JS_CAP)
        self.assertNotIn("desk-marks", (PREVIEW / "browse.js").read_text(encoding="utf-8"))


class ProductionDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        sys.path.insert(0, str(PREVIEW))
        import generate_preview as gp
        cls.gp = gp
        cls.tmp = Path(tempfile.mkdtemp(prefix="archive-marks-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB), legacy_routes=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_exactly_the_allowlisted_marks_are_published_byte_identical(self):
        self.assertEqual(self.gp.ARCHIVE_MARK_ASSETS,
                         tuple("assets/desk-marks/%s.svg" % s for s in marks.SLUGS))
        published = sorted(p.name for p in (self.out / "assets/desk-marks").iterdir())
        self.assertEqual(published, [s + ".svg" for s in marks.SLUGS])
        for route in self.gp.ARCHIVE_MARK_ASSETS:
            self.assertEqual((self.out / route).read_bytes(),
                             (REPO_ROOT / "site" / route).read_bytes(), route)

    def test_only_archive_css_references_the_marks_and_only_archive_links_it(self):
        self.assertEqual((self.out / "archive.css").read_bytes(), (PREVIEW / "archive.css").read_bytes())
        html = (self.out / "archive.html").read_text(encoding="utf-8")
        self.assertIn("rl-finder", html)
        for sheet in sorted(self.out.glob("*.css")):
            if sheet.name != "archive.css":
                self.assertNotIn("desk-marks", sheet.read_text(encoding="utf-8"), sheet.name)
        for page in sorted(self.out.rglob("*.html")):
            if page.parent != self.out or page.name != "archive.html":
                self.assertNotIn('href="archive.css"', page.read_text(encoding="utf-8"), page.name)

    def test_initial_rows_keep_declared_desk_routes_without_requiring_art(self):
        html = (self.out / "archive.html").read_text(encoding="utf-8")
        # Inert client templates are not server-rendered initial records.
        content = re.sub(r'<template\b[^>]*>.*?</template>', '', html, flags=re.S)
        rows = re.findall(r'<li class="record-row">.*?</li>', content, re.S)
        self.assertEqual(len(rows), 50)
        registry = json.loads((REPO_ROOT / "desks" / "registry.json").read_text(encoding="utf-8"))
        declared_routes = {desk["route"] for desk in registry["desks"] if desk.get("route")}
        marked_routes = {slug + ".html" for slug in marks.SLUGS}
        for row in rows:
            href = re.search(r'<p class="row-side">.*?<a href="([^"]+)"', row, re.S)
            if href is None:
                # An unassigned record must not acquire an invented desk link.
                continue
            route = href.group(1)
            self.assertIn(route, declared_routes)
            if route in marked_routes:
                # The same CSS covers both server and browse.js row markup.
                self.assertIn('a[href="%s"]::before' % route, ARCHIVE_CSS)
            # Declared desks without permitted country artwork stay linkable.


if __name__ == "__main__":
    unittest.main()
