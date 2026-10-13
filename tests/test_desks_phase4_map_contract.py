"""Phase 4A: public Desks map is a light, status-honest geographic index.

These are cheap source contracts. They do not replace browser geometry,
accessible interaction, and label/plate collision probes.
"""

from pathlib import Path
import unittest

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
        self.assertIn('from "_relief.html" import flag with context', self.html)
        for iso, slug in (("cn", "china"), ("sg", "singapore"), ("jp", "japan"),
                          ("vn", "vietnam"), ("us", "us-indopacific"),
                          ("kr", "korea"), ("ph", "philippines")):
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


if __name__ == "__main__":
    unittest.main()
