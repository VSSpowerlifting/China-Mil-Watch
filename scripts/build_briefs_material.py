#!/usr/bin/env python3
"""Prepare the Briefs pilot's owned decorative assets (no documentary imagery).

Usage: .venv/bin/python scripts/build_briefs_material.py --master PATH
The supplied generated review master is identified by SHA; kept outside the repo.
Contour path coordinates are recovered from the surviving source stylesheet.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MASTER_SHA = '61002883e45fd8418f5544a2fd27656cef2c656c1566c0b1def250953879c672'


def build(master):
    master = Path(master)
    if hashlib.sha256(master.read_bytes()).hexdigest() != MASTER_SHA:
        raise ValueError('Unrecognized paper master; review provenance before replacement')
    out = ROOT / 'site/assets/material'
    out.mkdir(parents=True, exist_ok=True)
    css = (ROOT / 'site/preview/topography.css').read_text()
    svg = ET.fromstring(unquote(re.search(r'url\("data:image/svg\+xml,([^"\n]+)', css)[1]))
    ns = '{http://www.w3.org/2000/svg}'
    paths = list(dict.fromkeys(p.attrib['d'] for p in svg.iter(ns + 'path')))
    # Only flowing cubic contour paths; no polygon washes or faux geography.
    paths = [p for p in paths if p.startswith('M1000 ')]
    if len(paths) != 12:
        raise ValueError('Contour source changed; inspect before generating')
    curves = ''.join('<path d="%s"/>' % p for p in paths)
    for name, color, opacity in [('hero', '#89cccb', '.48'), ('paper', '#176c6c', '.14')]:
        markup = ('<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1600" viewBox="0 0 1440 1600">'
                  '<g fill="none" stroke="%s" stroke-opacity="%s" stroke-width="1">' % (color, opacity)
                  + '<g transform="translate(440 0)">' + curves + '</g>'
                  + '<g transform="translate(1000 500) scale(-1 1)">' + curves + '</g>'
                  + '<g transform="translate(440 1010)">' + curves + '</g></g></svg>\n')
        (out / ('contours-%s.svg' % name)).write_text(markup)
    # Mirrored quadrants meet at identical edge pixels on all four tile edges.
    # Preserve fine material detail while removing the master’s large tonal field.
    grain = Image.open(master).convert('L').crop((480, 480, 736, 736)).resize((128, 128), Image.Resampling.LANCZOS)
    tile = Image.new('L', (256, 256))
    tile.paste(grain, (0, 0)); tile.paste(ImageOps.mirror(grain), (128, 0))
    tile.paste(ImageOps.flip(grain), (0, 128))
    tile.paste(ImageOps.flip(ImageOps.mirror(grain)), (128, 128))
    mean = sum(tile.getdata()) / (256 * 256)
    # 8 neutral palette steps around the existing paper token, never distressed.
    indices = tile.point(lambda v: max(0, min(7, round((v - mean) * .2) + 4)))
    paper = Image.new('P', tile.size); paper.putdata(indices.getdata())
    palette = []
    for i in range(256):
        shift = min(i, 7) - 4
        palette.extend([243 + shift, 242 + shift, 236 + shift])
    paper.putpalette(palette)
    paper.save(out / 'chart-paper.png', optimize=True)
    assets = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
              for p in sorted(out.iterdir()) if p.suffix in ('.svg', '.png')}
    receipt = {'purpose': 'Generated decorative material and original abstract IPR curves; no evidence or geography',
               'master': {'bundle': 'IPR_Visual_Enrichment_2026-10-09 (2).zip', 'path': 'assets/chart-paper.png',
                          'sha256': MASTER_SHA, 'bytes': master.stat().st_size, 'dimensions': [1254, 1254],
                          'generation': 'Supplied generated chart-paper review material; original prompt/model not supplied'},
               'contours': {'source': 'site/preview/topography.css', 'path_count': 12, 'coordinates': 'unchanged; cubic paths only'},
               'paper': {'method': '256px luminance crop resized to 128px, mirrored seamless 256px tile, 8-tone IPR paper palette',
                         'dimensions': [256, 256], 'decoded_rgba_bytes': 262144}, 'assets': assets}
    (out / 'ASSET_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(assets, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--master', required=True)
    build(parser.parse_args().master)
