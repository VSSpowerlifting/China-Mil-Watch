"""
The Desks-page map stays in step with the desk registry.

Editorial facts come from the registry and the corpus; `desks/geography.json`
only says where a desk sits. These checks keep the two from drifting: every
declared public desk is placed, nothing undeclared is, every seat falls inside
the frame on the coastline the committed geometry drew, and every plate's
leader can be drawn without crossing its own plate.
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

    def test_seat_lies_within_its_country_bounds(self):
        """A seat is a point in its own desk's country, not in open sea."""
        for slug, geo in self.places.items():
            d = re.search(r'<path id="dm-geo-%s"[^>]* d="([^"]+)"' % re.escape(slug),
                          self.geo).group(1)
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
            xs, ys = nums[0::2], nums[1::2]
            ax, ay = desk_map.project(*geo["anchor"])
            with self.subTest(desk=slug):
                self.assertTrue(min(xs) - 5 <= ax <= max(xs) + 5)
                self.assertTrue(min(ys) - 5 <= ay <= max(ys) + 5)


if __name__ == "__main__":
    unittest.main()
