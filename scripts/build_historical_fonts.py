#!/usr/bin/env python3
"""Prepare exact historical Google WOFF2 faces as local, licensed assets.

Default rebuilds are offline and verify committed source digests. --refresh
captures the existing official CSS with ordinary Chromium, then downloads its
original faces and official OFL licenses. Review all hashes after a refresh.
Preparation requires Playwright plus fontTools==4.60.2 and brotli==1.2.0.
The latter two were installed in /tmp/ipr-font-prep-deps for this build; use
PYTHONPATH=/tmp/ipr-font-prep-deps with the existing repository Python runtime.
Production needs none of these preparation dependencies.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site/assets/fonts/historical'
CSS = ROOT / 'site/preview/historical-fonts.css'
GOOGLE_CSS = ('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
              '&family=Source+Serif+4:ital,opsz,wght@0,8..60,400..800;1,8..60,400..700'
              '&family=IBM+Plex+Mono:wght@400;500;600&display=swap')
FAMILIES = {'IBM Plex Mono': 'ibmplexmono', 'Inter': 'inter', 'Source Serif 4': 'sourceserif4'}
SUBSETS = ('latin', 'latin-ext', 'vietnamese')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unicode_values(ranges):
    result = set()
    for item in ranges.split(','):
        endpoints = item.strip().removeprefix('U+').split('-')
        low, high = int(endpoints[0], 16), int(endpoints[-1], 16)
        result.update(range(low, high + 1))
    return result


def compact_ranges(ranges):
    """Remove whitespace/leading zeroes without changing subset assignment."""
    result = []
    for item in ranges.split(','):
        ends = item.strip().removeprefix('U+').split('-')
        result.append('U+' + '-'.join('%X' % int(value, 16) for value in ends))
    return ','.join(result)


def capture_css():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as play:
        browser = play.chromium.launch()
        try:
            response = browser.new_page().goto(GOOGLE_CSS)
            if response.status != 200:
                raise ValueError('Official Google CSS request failed')
            return response.body(), browser.version
        finally:
            browser.close()


def faces(raw):
    groups = {}
    for label, block in re.findall(r'/\* ([^*]+) \*/\s*(@font-face\s*\{.*?\})', raw, re.S):
        label = label.strip()
        if label not in SUBSETS:
            continue
        family = re.search(r"font-family: '([^']+)'", block)[1]
        style = re.search(r'font-style: ([^;]+)', block)[1]
        weight = re.search(r'font-weight: ([^;]+)', block)[1]
        source = re.search(r'url\(([^)]+)\)', block)[1]
        if not source.startswith('https://fonts.gstatic.com/') or not source.endswith('.woff2'):
            raise ValueError('Expected official original WOFF2 sources')
        key = family, style, label, source
        face = groups.setdefault(key, {'family': family, 'style': style, 'subset': label,
                                      'source': source, 'weights': [],
                                      'original_unicode_range': re.search(r'unicode-range: ([^;]+)', block)[1]})
        face['weights'].append(weight)
    if len(groups) != 18:
        raise ValueError('Historical family/subset structure changed; review required')
    return list(groups.values())


def build(refresh=False):
    previous = json.loads((OUT / 'RECEIPT.json').read_text()) if (OUT / 'RECEIPT.json').exists() else None
    if refresh or not previous:
        raw, browser = capture_css()
    else:
        raw = (OUT / 'GOOGLE_SOURCE.css').read_bytes()
        browser = previous['css_source']['capture_browser']
        if sha(raw) != previous['css_source']['sha256']:
            raise ValueError('Committed source CSS digest changed')
    previous_assets = {entry['file']: entry for entry in previous['fonts']} if previous else {}
    entries, blobs, rules, coverage = [], {}, [], {}
    for face in faces(raw.decode()):
        family, style, label = face['family'], face['style'], face['subset']
        prefix = ('m' + face['weights'][0][0] if family == 'IBM Plex Mono'
                  else 'i' if family == 'Inter' else 'si' if style == 'italic' else 'sr')
        name = prefix + {'latin': 'l', 'latin-ext': 'x', 'vietnamese': 'v'}[label] + '.woff2'
        data = urlopen(face['source'], timeout=30).read() if refresh or name not in previous_assets else (OUT / name).read_bytes()
        if not refresh and name in previous_assets and sha(data) != previous_assets[name]['sha256']:
            raise ValueError('Committed font digest changed: ' + name)
        with TTFont(io.BytesIO(data), recalcTimestamp=False) as font:
            axes = {axis.axisTag: [axis.minValue, axis.defaultValue, axis.maxValue]
                    for axis in font['fvar'].axes} if 'fvar' in font else {}
            if family == 'Inter':
                if 'wght' not in axes or axes['wght'][0] > 400 or axes['wght'][2] < 700:
                    raise ValueError('Cannot group Inter weights without matching variable source')
                weight = '400 700'
            elif family == 'Source Serif 4':
                weight = '400 700' if style == 'italic' else '400 800'
                if (axes.get('opsz', [None, None, None])[0::2] != [8, 60]
                        or 'wght' not in axes or axes['wght'][0] > 400
                        or axes['wght'][2] < int(weight.split()[-1])):
                    raise ValueError('Source Serif optical/weight axes changed')
            else:
                if axes:
                    raise ValueError('Expected original static IBM Plex Mono faces')
                weight = face['weights'][0]
            cmap = set(font.getBestCmap())
        key = family, style, weight
        original, prepared = coverage.setdefault(key, (set(), set()))
        ranges = compact_ranges(face['original_unicode_range'])
        if unicode_values(ranges) != unicode_values(face['original_unicode_range']):
            raise ValueError('Original subset assignment changed')
        original.update(cmap & unicode_values(face['original_unicode_range']))
        prepared.update(cmap & unicode_values(ranges))
        entry = {**face, 'weight': weight, 'axes': axes, 'file': name,
                 'unicode_range': ranges, 'bytes': len(data), 'sha256': sha(data),
                 'binary_treatment': 'Original Google WOFF2 bytes, unchanged'}
        entries.append(entry)
        blobs[name] = data
        rules.append("@font-face{font-family:'%s';%sfont-weight:%s;src:url(assets/fonts/historical/%s);font-display:swap;unicode-range:%s}"
                     % (family, 'font-style:italic;' if style == 'italic' else '', weight, name, ranges))
    for key, (original, prepared) in coverage.items():
        if original - prepared:
            raise ValueError('Prepared ranges lose original glyph coverage: %s %s' %
                             (key, [hex(value) for value in sorted(original - prepared)]))
    css = ('\n'.join(rules) + '\n').encode()
    if len(css) > 6000:
        raise ValueError('Historical font CSS exceeds 6,000 bytes')
    licenses = []
    for family, slug in FAMILIES.items():
        url = 'https://raw.githubusercontent.com/google/fonts/main/ofl/%s/OFL.txt' % slug
        name = slug + '-OFL.txt'
        data = urlopen(url, timeout=30).read() if refresh or not previous else (OUT / name).read_bytes()
        if not refresh and previous:
            recorded = next(item for item in previous['licenses'] if item['file'] == name)
            if sha(data) != recorded['sha256']:
                raise ValueError('Committed license digest changed')
        if b'SIL OPEN FONT LICENSE' not in data:
            raise ValueError('Expected official SIL Open Font License')
        licenses.append({'family': family, 'file': name, 'source': url, 'bytes': len(data), 'sha256': sha(data)})
        blobs[name] = data
    receipt = {
        'builder': 'scripts/build_historical_fonts.py',
        'preparation_dependencies': {'fontTools': '4.60.2', 'Brotli': '1.2.0', 'Playwright': 'existing development runtime'},
        'purpose': 'Local delivery of unchanged historical font families and original WOFF2 faces',
        'css_source': {'url': GOOGLE_CSS, 'file': 'GOOGLE_SOURCE.css', 'bytes': len(raw),
                       'sha256': sha(raw), 'capture_browser': browser},
        'coverage': 'Latin, Latin Extended, Vietnamese and punctuation; original-language CJK retains system stacks',
        'subset_assignment': 'Original Google unicode ranges unchanged; only whitespace and leading hexadecimal zeroes removed',
        'weights': {'Inter': 'normal 400, 500, 600, 700 (shared variable source)',
                    'Source Serif 4': 'normal 400..800 and italic 400..700; opsz 8..60 preserved',
                    'IBM Plex Mono': 'normal static 400, 500, 600'},
        'total_font_bytes': sum(entry['bytes'] for entry in entries),
        'css': {'path': 'site/preview/historical-fonts.css', 'bytes': len(css), 'sha256': sha(css)},
        'fonts': entries, 'licenses': licenses,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in blobs.items():
        (OUT / name).write_bytes(data)
    (OUT / 'GOOGLE_SOURCE.css').write_bytes(raw)
    (OUT / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    CSS.write_bytes(css)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    receipt = build(parser.parse_args().refresh)
    print(json.dumps({'font_files': len(receipt['fonts']), 'font_bytes': receipt['total_font_bytes'],
                      'css_bytes': receipt['css']['bytes']}, indent=2))
