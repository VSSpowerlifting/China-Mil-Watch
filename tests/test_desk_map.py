"""
The Desks-page map stays in step with the desk registry.

Editorial facts come from the registry and the corpus; `desks/geography.json`
only says where a desk sits. These checks keep the two from drifting: every
declared public desk is placed, nothing undeclared is, every seat falls inside
the frame and on its own country's land in the committed geometry, and every
plate's leader can be drawn without crossing its own plate.
"""

import json
import re
import unittest
from pathlib import Path

from core.desk_registry import load_registry
from scripts import desk_map

ROOT = Path(__file__).resolve().parent.parent


class DeskMapTest(unittest.TestCase):

    def setUp(self):
        self.places = json.loads(desk_map.GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
        self.public = list(load_registry().public_entries)
        self.geo = desk_map.GEO_SVG.read_text(encoding="utf-8")

    def test_every_public_desk_is_placed_and_nothing_else(self):
        slugs = {e.slug for e in self.public}
        self.assertEqual(set(self.places), slugs)

    def test_layout_places_every_desk_inside_the_frame(self):
        out = desk_map.layout(self.public)  # raises if a leader crosses its plate
        self.assertEqual((out["width"], out["height"]),
                         (desk_map.WIDTH, desk_map.HEIGHT))
        for slug, entry in out["desks"].items():
            with self.subTest(desk=slug):
                self.assertTrue(0 < float(entry["x"]) < desk_map.WIDTH)
                self.assertTrue(0 < float(entry["y"]) < desk_map.HEIGHT)
                for mode in ("wide", "mid"):
                    self.assertIn(entry[mode]["hang"], ("left", "right", "up", "down"))

    def test_projection_frame_corners(self):
        self.assertEqual(desk_map.project(desk_map.LON_W, desk_map.LAT_N), (0.0, 0.0))
        x, y = desk_map.project(desk_map.LON_E, desk_map.LAT_S)
        self.assertAlmostEqual(x, desk_map.WIDTH, delta=1)
        self.assertAlmostEqual(y, desk_map.HEIGHT, delta=1)

    def test_committed_geometry_carries_each_desk_country(self):
        for slug in self.places:
            with self.subTest(desk=slug):
                self.assertRegex(self.geo, r'<path id="dm-geo-%s" ' % re.escape(slug))
        self.assertIn("Natural Earth", self.geo)

    def _rings(self, slug):
        """The closed rings of a desk country's committed path (M/L/Z only)."""
        d = re.search(r'<path id="dm-geo-%s"[^>]* d="([^"]+)"' % re.escape(slug),
                      self.geo).group(1)
        self.assertRegex(d, r"^(M[^MZ]+Z)+$", "path uses commands beyond M/L/Z")
        return [[tuple(float(n) for n in pt.split()) for pt in ring.split("L")]
                for ring in re.findall(r"M([^MZ]+)Z", d)]

    @staticmethod
    def _contains(rings, x, y):
        """Even-odd ray cast across every ring, as `fill-rule="evenodd"` paints."""
        inside = False
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        return inside

    def test_containment_is_even_odd(self):
        square = lambda a, b: [(a, a), (b, a), (b, b), (a, b)]
        self.assertTrue(self._contains([square(0, 10)], 5, 5))
        self.assertFalse(self._contains([square(0, 10)], 15, 5))
        # A ring inside a ring is a hole; two separate islands both count.
        self.assertFalse(self._contains([square(0, 10), square(4, 6)], 5, 5))
        self.assertTrue(self._contains([square(0, 10), square(20, 30)], 25, 25))

    def test_seat_lies_within_its_country_polygon(self):
        """A seat is a point on its own desk's land, not in open sea."""
        for slug, geo in self.places.items():
            with self.subTest(desk=slug):
                self.assertTrue(self._contains(self._rings(slug),
                                               *desk_map.project(*geo["anchor"])))

    def test_points_in_the_bounding_box_but_off_the_land_are_not_contained(self):
        """The check is the polygon, not its extent: each point below lies
        inside the country's bounding box and outside the country."""
        for slug, place, lonlat in (("china", "Ulaanbaatar", (106.9, 47.9)),
                                    ("china", "Yellow Sea", (123, 35)),
                                    ("japan", "Sea of Japan", (135, 40)),
                                    ("vietnam", "Gulf of Tonkin", (107.5, 20.0)),
                                    ("vietnam", "Vientiane", (102.6, 17.97))):
            rings = self._rings(slug)
            x, y = desk_map.project(*lonlat)
            xs = [p[0] for r in rings for p in r]
            ys = [p[1] for r in rings for p in r]
            with self.subTest(place=place):
                self.assertTrue(min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys))
                self.assertFalse(self._contains(rings, x, y))

if __name__ == "__main__":
    unittest.main()
