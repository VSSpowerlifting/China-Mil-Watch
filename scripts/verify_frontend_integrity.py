#!/usr/bin/env python3
"""Read-only full-corpus parity and complete route budgets for a built candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'site/preview'))
from core.frontend_budget import measure_page
import generate_preview as gp


def normalized(value):
    return re.sub(r'\s+', '', value or '')


def verify(public, private, destination):
    public, private = Path(public), Path(private) if private else None
    data = gp.load_corpus(ROOT / 'pla_watch.db')
    corpus = data['corpus']
    snapshot = gp.snapshot_from_corpus(ROOT / 'pla_watch.db')
    failures = []
    for record in corpus:
        path = public / 'record' / ('%s.html' % record['id'])
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        fields = [('h1', record['title_english'] or record['title_original']),
                  ('.record-title-pair .original', record['title_original'] if record['title_english'] else ''),
                  ('.original-text', record.get('text_original')),
                  ('#record-summary .interpretation', record.get('summary_english'))]
        cite = gp.record_citation(record, gp.PUBLIC_TITLE, snapshot)
        fields += [('#cite-source-text', cite['source_text']), ('#cite-as-held', cite['as_held'])]
        for selector, expected in fields:
            if not expected: continue
            element = soup.select_one(selector)
            if not element or normalized(expected) != normalized(element.get_text()):
                failures.append({'id': record['id'], 'field': selector})
        date = soup.select_one('.record-source-line time')
        if not date or date.get('datetime') != record['published_date']:
            failures.append({'id': record['id'], 'field': 'published_date'})
        if not any(a.get('href') == record['url'] for a in soup.select('.record-actions a')):
            failures.append({'id': record['id'], 'field': 'original_url'})
        provenance = {row.th.get_text(strip=True): row.td.get_text(' ', strip=True)
                      for row in soup.select('.provenance tbody tr')}
        for label, field in [('Publishing institution', 'institution'), ('Source outlet', 'source_name'),
                             ('Source language', 'language_tag'), ('Source-stated publication date', 'published_date'),
                             ('Original URL', 'url'), ('Collected at', 'scraped_at'), ('Content fingerprint', 'content_hash'),
                             ('Collection run', 'scrape_run_id'), ('Analysis model', 'model_id'), ('Prompt version', 'prompt_version')]:
            value = record.get(field)
            if value is not None and str(value) and normalized(str(value)) not in normalized(provenance.get(label, '')):
                failures.append({'id': record['id'], 'field': label})
        if len(soup.find_all('h1')) != 1:
            failures.append({'id': record['id'], 'field': 'h1_count'})
        if (ROOT / 'output/article' / ('%s.html' % record['id'])).is_file() and not (public / 'article' / ('%s.html' % record['id'])).is_file():
            failures.append({'id': record['id'], 'field': 'legacy_route'})
    index = json.loads((public / 'corpus-index.json').read_text())
    expected_index = gp.corpus_index(corpus, data['sources'], snapshot)
    assert index['records'] == expected_index['records']
    assert index['fields'] == expected_index['fields']
    # The archive's approved source-trail membership and each native backlink
    # must refer to the same exact stored URLs and native trail anchors.
    by_id = {r['id']: r for r in corpus}
    native_relations = 0
    for source in sorted((ROOT / 'briefs').glob('*.json')):
        sidecar = json.loads(source.read_text())
        if sidecar.get('editorial_status') != 'approved': continue
        for entry in sidecar.get('source_trail', []):
            record = by_id.get(entry['record_id'])
            if not record or record['url'] != entry['url']: continue
            assert record['id'] in index['trail_ids']
            html = (public / 'record' / ('%s.html' % record['id'])).read_text()
            assert '../briefs/%s.html#r-%s' % (source.stem, record['id']) in html
            native_relations += 1
    assert not (public / 'timeline').exists()
    assert not (public / 'timelines.html').exists()
    for path in private.glob('timeline/*.html') if private else ():
        text = path.read_text()
        assert 'noindex, nofollow' in text and 'rel="canonical"' not in text
    budgets = []
    limits = {'index.html': 120000, 'archive.html': 300000, 'analysis.html': 300000, 'record/3924.html': 120000,
              'briefs/maritime-cooperation-2026.html': 120000, 'timelines.html': 120000,
              'timeline/maritime-cooperation-2026.html': 120000}
    for route, cap in limits.items():
        if route.startswith('timeline') and private is None:
            continue
        root = private if route.startswith('timeline') else public
        measure = measure_page(root / route, root)
        assert measure['html_css_bytes'] <= cap, (route, measure)
        # The already governed optional home arrival intro has its own 12 KB
        # limit. All other route scripts retain the 10 KB budget.
        assert measure['js_bytes'] <= (12000 if route == 'index.html' else 10000)
        assert not measure['external'], (route, measure['external'])
        budgets.append(dict(route=route, html_css_limit=cap, **measure))
    assert not failures, failures[:20]
    receipt = {'records_checked': len(corpus), 'approved_native_relations': native_relations, 'failures': failures, 'budgets': budgets,
               'database_sha256': hashlib.sha256((ROOT / 'pla_watch.db').read_bytes()).hexdigest(),
               'timeline_sha256': hashlib.sha256((ROOT / 'timelines/maritime-cooperation-2026.json').read_bytes()).hexdigest()}
    Path(destination).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('Verified all %s record bodies, titles, source URLs, dates and compatibility routes' % len(corpus))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', required=True);parser.add_argument('--private');parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    verify(args.public, args.private, args.receipt)
