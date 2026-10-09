#!/usr/bin/env python3
"""Persistent complete-route HTML/CSS/JS gate and conservative asset inventory.

Runs against a governed render; never renders or modifies production itself.
Fonts/image variants are counted once per route. Browser delivery receipts
measure the smaller actually requested subset. Historical images/fonts retain
their provenance and are reported rather than silently recompressed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.frontend_budget import measure_page


def verify(root):
    root = Path(root).resolve()
    routes, failures = [], []
    for page in sorted(root.rglob('*.html')):
        route = page.relative_to(root).as_posix()
        # Index/archive hubs have the governed 300 KB allowance. Individual
        # records, Briefs and week shards retain the stricter 120 KB cap.
        index = page.name in ('index.html', 'archive.html', 'analysis.html', 'corpus.html', 'pla-watch.html', 'desks.html')
        html_cap = 300000 if index else 120000
        js_cap = 12000 if route == 'index.html' else 10000
        values = measure_page(page, root)
        item = dict(route=route, html_css_limit=html_cap, js_limit=js_cap, **values)
        item['local_delivery_bytes'] = values['html_css_bytes'] + values['js_bytes'] + values['asset_bytes']
        routes.append(item)
        if values['html_css_bytes'] > html_cap or values['js_bytes'] > js_cap:
            failures.append(item)
    if not routes:
        raise ValueError('No HTML routes found')
    return {'routes_checked': len(routes), 'failures': failures,
            'largest_html_css': max(routes, key=lambda r: r['html_css_bytes']),
            'largest_local_delivery': max(routes, key=lambda r: r['local_delivery_bytes']),
            'routes': routes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', required=True); parser.add_argument('--receipt', required=True)
    args = parser.parse_args(); result = verify(args.root)
    Path(args.receipt).write_text(json.dumps(result, indent=2) + '\n')
    print('Checked %s routes: %s delivery budget failures' % (result['routes_checked'], len(result['failures'])))
    if result['failures']:
        print([(v['route'], v['html_css_bytes'], v['js_bytes']) for v in result['failures']])
        sys.exit(1)
