#!/usr/bin/env python3
"""Build original decorative profiles, not geographic/elevation evidence.

Deterministic SVG compositions. No sampled coastlines, photos or data. Source
coordinates deliberately carry no scale, location or measurement labels.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site/assets/material'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    # A broad material boundary with three distinct bends. The line bundle
    # follows both sides of the edge rather than filling a rectangular field.
    profile = []
    for i in range(23):
        x = 148 + i * 11
        profile.append('<path d="M%d -40 C%d 100 %d 122 %d 227 S%d 350 %d 449 S%d 607 %d 705 S%d 827 %d 960"/>' %
                       (x, x-12, x+87, x+36, x-65, x+29, x+166, x+86, x-38, x+84))
    boundary = 'M434 -40C422 100 521 122 470 227S369 350 463 449S600 607 520 705S396 827 518 960L680 960V-40Z'
    markup = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 900">'
              '<path fill="#142e38" d="%s"/>' % boundary
              + '<g fill="none" stroke="#3f8c8f" stroke-width="1.15">'
              + ''.join(profile) + '</g>'
              + '<path fill="none" stroke="#92d5cc" stroke-width="1.6" d="%s"/>' % boundary
              + '</svg>\n')
    (OUT / 'coast-profile.svg').write_text(markup)
    (OUT / 'reading-profile.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 900">'
        '<g fill="none" stroke="#3f8c8f" stroke-width="1.15">'
        + ''.join(profile) + '</g></svg>\n')
    shelf = []
    for i in range(25):
        y = 16 + i * 9
        shelf.append('<path d="M-60 %dC180 %d 302 %d 439 %dS636 %d 777 %dS967 %d 1128 %dS1390 %d 1500 %d"/>' %
                     (y, y+4, y+141, y+92, y-105, y+36, y+126, y-4, y-48, y+38))
    (OUT / 'chart-shelf.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 400">'
        '<g fill="none" stroke="#63abae" stroke-width="1.15">' + ''.join(shelf) + '</g></svg>\n')
    receipt = {'purpose': 'Original abstract material boundaries; no geography, elevation or evidence',
               'generator': 'scripts/build_profile_material.py',
               'assets': {name: {'bytes': (OUT/name).stat().st_size,
                                'sha256': hashlib.sha256((OUT/name).read_bytes()).hexdigest()}
                          for name in ('coast-profile.svg', 'reading-profile.svg', 'chart-shelf.svg')}}
    (OUT / 'PROFILE_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
