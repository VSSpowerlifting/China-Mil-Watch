"""Phase 4A: public Desks map is a light, status-honest geographic index.

These are cheap source contracts. They do not replace browser geometry,
accessible interaction, and label/plate collision probes.
"""

from pathlib import Path
import unittest

from core.desk_registry import load_registry
from scripts import desk_map

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site/preview/templates/desks.html"
STYLE = ROOT / "site/preview/desk-map.css"
FLAGS = ROOT / "site/assets/flags"
RELIEF = ROOT / "site/preview/templates/_relief.html"


class DesksPhase4MapContract(unittest.TestCase):
    def setUp(self):
        self.html = TEMPLATE.read_text(encoding="utf-8")
        self.css = STYLE.read_text(encoding="utf-8")
        self.relief = RELIEF.read_text(encoding="utf-8")

    def test_template_compiles_as_jinja(self):
        from jinja2 import Environment
        Environment().parse(self.html)

    def test_no_us_sovereign_fill(self):
        self.assertIn("d.slug != 'us-indopacific'", self.html)
        self.assertIn('href="#dm-geo-{{ d.slug }}"', self.html)
        self.assertIn('class="dm-anchor', self.html)
        self.assertIn("Seat only: regional reference, not a country fill", self.html)

    def test_registry_drives_status_not_geography(self):
        self.assertIn("d.status_label", self.html)
        self.assertIn("d.status_explanation", self.html)
        self.assertIn("d.record_count", self.html)
        self.assertIn("d.last_successful_run", self.html)
        self.assertIn("Not admitted", self.html)
        self.assertIn("if d.slug not in placed", self.html)
        self.assertNotIn("private_originals", self.html)

    def test_flags_are_licensed_local_assets(self):
        self.assertIn('from "_relief.html" import flag, emblem, glyph_for with context', self.html)
        for iso, slug in (("cn", "china"), ("sg", "singapore"), ("jp", "japan"),
                          ("vn", "vietnam"), ("us", "us-indopacific"),
                          ("kr", "korea"), ("ph", "philippines"),
                          ("id", "indonesia")):
            with self.subTest(slug=slug):
                self.assertTrue((FLAGS / (iso + ".svg")).is_file())
                self.assertIn("'" + slug + "': '" + iso + "'", self.relief)
        self.assertTrue((FLAGS / "LICENSE").is_file())
        self.assertIn('aria-hidden="true">{{ flag(d.slug) }}', self.html)

    def test_seat_map_keeps_no_js_register_and_context(self):
        self.assertEqual(self.html.count('<div class="deskmap-register">'), 1)
        self.assertLess(self.html.index('<div class="deskmap-chart">'),
                        self.html.index('<div class="deskmap-register">'))
        self.assertLess(self.html.index('<div class="deskmap-register">'),
                        self.html.index('<div class="deskmap-context"'))
        self.assertIn('href="#desk-{{ d.slug }}"', self.html)
        self.assertIn('id="desk-{{ d.slug }}"', self.html)
        self.assertIn('src="desk-map.js"', self.html)
        self.assertIn('rel="stylesheet" href="relief.css"', self.html)

    def test_light_chart_fallback_and_accessibility(self):
        self.assertIn("--dm-sea:#e2ebe9", self.css)
        self.assertIn("dm-country.is-shadow use", self.css)
        self.assertIn("dm-leader.is-quiet", self.css)
        self.assertIn("min-width:1480px", self.css)
        self.assertIn("max-width:899px", self.css)
        self.assertIn("prefers-reduced-motion:no-preference", self.css)
        self.assertIn("forced-colors:active", self.css)
        self.assertIn("@media print", self.css)

    def test_wide_plate_projection_has_no_obvious_pairwise_overlap(self):
        """Conservative box preflight; does NOT certify real-browser labels.

        Real browser B10 probe is still required before publication. Use a
        deliberately generous paper-plate bounding box (232 x 265 px) at the
        shell's max map width, 1280 px, rather than a five-desk mockup.
        """
        map_width = 1280.0
        map_height = map_width * desk_map.HEIGHT / desk_map.WIDTH
        width, height = 232.0, 265.0
        bounds = {}
        for slug, place in desk_map.layout(load_registry().public_entries)["desks"].items():
            card = place["wide"]
            x = float(card["left"].rstrip("%")) * map_width / 100
            y = float(card["top"].rstrip("%")) * map_height / 100
            x += float(card["tx"].rstrip("%")) * width / 100
            y += float(card["ty"].rstrip("%")) * height / 100
            bounds[slug] = (x, y, x + width, y + height)
            self.assertGreaterEqual(x, 0, slug)
            self.assertLessEqual(x + width, map_width, slug)
        slugs = sorted(bounds)
        for i, left_slug in enumerate(slugs):
            a = bounds[left_slug]
            for right_slug in slugs[i + 1:]:
                b = bounds[right_slug]
                overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                self.assertFalse(overlap, "%s overlaps %s" % (left_slug, right_slug))


if __name__ == "__main__":
    unittest.main()
