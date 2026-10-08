#!/usr/bin/env python3
"""Validate/replay the frozen topic pilot; never classify or attach topics.

Default checks are offline. --verify-sources reads pinned Git blobs into
immutable temporary SQLite copies. It fetches nothing and writes no database.
--report prints Markdown to stdout; the caller chooses any destination.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.topics import RecordRef, load_taxonomy  # noqa: E402

LEDGER = ROOT / 'research/topic_pilot_v1/ledger.json'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(data):
    taxonomy = load_taxonomy()
    require(data['pilot_version'] == 1 and type(data['pilot_version']) is int,
            'unsupported pilot version')
    require(data['taxonomy_id'] == taxonomy.taxonomy_id and
            type(data['taxonomy_version']) is int and
            data['taxonomy_version'] == taxonomy.taxonomy_version,
            'taxonomy mismatch')
    require(data['taxonomy_sha256'] == hashlib.sha256(
        (ROOT / 'taxonomy/regional_topics.v1.json').read_bytes()).hexdigest(),
        'taxonomy bytes changed; pilot needs explicit review')
    records = data['records']
    require(len(records) == data['sample_size'] and 50 <= len(records) <= 100,
            'sample size mismatch/outside pilot bounds')
    seen = set()
    for name, origin in data['origins'].items():
        require(re.fullmatch('[0-9a-f]{40}', origin['commit']) and
                re.fullmatch('[0-9a-f]{40}', origin['blob']), 'un-pinned origin')
        require(origin['path'] == ('pla_watch.db' if name == 'production'
                                   else 'state/shadow.db'), 'unexpected database path')
    for position, record in enumerate(records, 1):
        loc = record['pilot_id']
        require(loc == 'P%02d' % position, 'pilot order/identifier mismatch')
        identity = [record[k] for k in ('desk_id', 'source_slug', 'canonical_url')]
        RecordRef(*identity).validate()
        require(record['desk_id'] != 'us_indopacom', 'excluded US desk')
        digest = sha(json.dumps(identity, ensure_ascii=False, separators=(',', ':')))
        require(record['record_id'] == digest and digest not in seen,
                loc + ': duplicate or unstable record identity')
        seen.add(digest)
        origin = record['origin']
        require(origin in data['origins'], loc + ': missing origin')
        require(record['storage_layer'] == ('production' if origin == 'production'
                                           else 'shadow'), loc + ': layer mismatch')
        require(record['row_locator']['table'] == ('articles' if origin == 'production'
                                                 else 'shadow_records'), loc + ': table mismatch')
        require(record['status'] == 'provisional' and record['review_state'] == 'pending'
                and record['proposer'] == 'Codex source-text review; not human-approved',
                loc + ': proposal must remain provisional')
        require(re.fullmatch('[0-9a-f]{64}', record['body_sha256']), loc + ': bad body hash')
        require(type(record['body_chars']) is int and record['body_chars'] >= 0,
                loc + ': invalid body length')
        require(bool(record['title_original']) and bool(record['published_date']),
                loc + ': missing source metadata')
        evidence = {}
        for item in record['evidence']:
            require(item['id'] not in evidence, loc + ': duplicate evidence')
            require(item['field'] == 'text_original' and
                    type(item['start']) is int and type(item['end']) is int and
                    0 <= item['start'] < item['end'] <= record['body_chars'] and
                    item['end'] - item['start'] == len(item['quote']),
                    loc + ': invalid evidence locator')
            evidence[item['id']] = item
        topics = set()
        for proposal in record['proposals']:
            taxonomy.topic(proposal['topic'])
            require(proposal['topic'] not in topics, loc + ': duplicate topic')
            topics.add(proposal['topic'])
            require(bool(proposal['rationale'].strip()) and proposal['evidence'] and
                    all(e in evidence for e in proposal['evidence']),
                    loc + ': unsupported proposal')
        require(bool(topics) != bool(record['unclassified_reason']),
                loc + ': classified/abstention inconsistency')
        if record['body_chars'] == 0:
            require(not topics and not evidence, loc + ': empty-body assignment')
        require(origin == 'production' or not record['local_categories'],
                loc + ': shadow records must not inherit China categories')
    return data


def summarize(data):
    records = data['records']
    topics = Counter(p['topic'] for r in records for p in r['proposals'])
    return {
        'records': len(records),
        'desks': dict(sorted(Counter(r['desk_id'] for r in records).items())),
        'layers': dict(sorted(Counter(r['storage_layer'] for r in records).items())),
        'topics': {t: topics[t] for t in load_taxonomy().topic_slugs},
        'covered_topics': len(topics),
        'unclassified': [r['pilot_id'] for r in records if not r['proposals']],
        'review_cases': [r['pilot_id'] for r in records if r['review_issue']],
        'multi_label': sum(len(r['proposals']) > 1 for r in records),
    }


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise ValueError('Pinned Git evidence unavailable: %s. Fetch the ledger origins explicitly.'
                         % ' '.join(args))
    return result.stdout


def verify_sources(data):
    """Replay exact selected rows, including Vietnam's versioned body storage."""
    verified = 0
    for name, origin in data['origins'].items():
        spec = origin['commit'] + ':' + origin['path']
        require(git('rev-parse', spec).decode().strip() == origin['blob'],
                'source blob differs: ' + name)
        raw = git('show', spec)
        before = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix='ipr-topic-replay-') as tmp:
            path = Path(tmp) / 'snapshot.db'
            path.write_bytes(raw)
            with sqlite3.connect(path.as_uri() + '?immutable=1', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                for record in data['records']:
                    if record['origin'] != name:
                        continue
                    url = record['row_locator']['url']
                    if name == 'production':
                        row = conn.execute(
                            'SELECT a.*,s.slug source_slug,s.desk_id FROM articles a '
                            'JOIN sources s ON s.id=a.source_id WHERE a.url=?', (url,)).fetchone()
                    elif name.startswith('vietnam-'):
                        row = conn.execute(
                            'SELECT r.*,v.title_original,v.text_original FROM shadow_records r '
                            'JOIN shadow_versions v ON v.source_identity=r.source_identity '
                            'AND v.content_sha256=r.current_content_sha256 WHERE r.url=?',
                            (url,)).fetchone()
                    else:
                        row = conn.execute('SELECT * FROM shadow_records WHERE url=?', (url,)).fetchone()
                    require(row is not None, record['pilot_id'] + ': record absent')
                    for key in ('source_slug', 'title_original', 'published_date'):
                        require(record[key] == row[key], record['pilot_id'] + ': metadata mismatch ' + key)
                    canonical = row['canonical_url'] if 'canonical_url' in row.keys() else row['url']
                    require(canonical == record['canonical_url'], 'canonical URL mismatch')
                    if name == 'production':
                        require(record['desk_id'] == row['desk_id'], 'production desk mismatch')
                        cats = sorted(r[0] for r in conn.execute(
                            'SELECT c.slug FROM article_categories ac JOIN categories c '
                            'ON c.id=ac.category_id WHERE ac.article_id=?', (row['id'],)))
                        require(cats == sorted(record['local_categories']), 'local categories changed')
                    else:
                        manifest = {'jp-mod':'shadow/jp_mod/manifest.json',
                                    'ph-afp':'shadow/ph_afp/manifest.json',
                                    'indonesia-kemhan':'shadow/id_kemhan/manifest.json',
                                    'korea-policy-briefing':'shadow/kr_policy_briefing/manifest.json'}
                        mp = manifest.get(name, 'shadow/vietnam_ministries/manifest.json')
                        cfg = json.loads((ROOT / mp).read_text())
                        require(record['desk_id'] == cfg['desk']['desk_id'], 'shadow desk mismatch')
                        require(record['source_slug'] in {s['slug'] for s in cfg['sources']},
                                'shadow source mismatch')
                    content_key = 'content_hash' if name == 'production' else (
                        'current_content_sha256' if name.startswith('vietnam-') else 'content_sha256')
                    require(record['stored_content_hash'] == row[content_key], 'stored hash mismatch')
                    body = row['text_original']
                    require(sha(body) == record['body_sha256'] and len(body) == record['body_chars'],
                            record['pilot_id'] + ': source body mismatch')
                    for item in record['evidence']:
                        require(body[item['start']:item['end']] == item['quote'],
                                record['pilot_id'] + ': excerpt differs from source')
                    verified += 1
            require(hashlib.sha256(path.read_bytes()).hexdigest() == before,
                    'temporary input changed')
            require(not Path(str(path) + '-wal').exists() and
                    not Path(str(path) + '-shm').exists(), 'SQLite sidecar residue')
        require(hashlib.sha256(git('show', spec)).hexdigest() == before, 'Git source changed')
    return verified


def markdown(data):
    stats = summarize(data)
    lines = ['# Regional Topic Taxonomy v1 — provisional review ledger', '',
             'Generated from `ledger.json` by `python3 scripts/topic_pilot.py --report`.', '',
             '**All labels are Codex proposals pending human review. No assignments are applied.**', '',
             '## Sample', '', '| Desk | Records |', '|---|---:|']
    lines += ['| %s | %d |' % item for item in stats['desks'].items()]
    lines += ['', '%d production / %d shadow; %d topics proposed; %d unclassified; '
              '%d multi-label; %d cases flagged for review.' % (
                  stats['layers']['production'], stats['layers']['shadow'],
                  stats['covered_topics'], len(stats['unclassified']),
                  stats['multi_label'], len(stats['review_cases'])), '',
              '## Topic distribution (record counts; topics overlap)', '',
              '| Topic | Proposed records |', '|---|---:|']
    lines += ['| `%s` | %d |' % item for item in stats['topics'].items()]
    for r in data['records']:
        origin = data['origins'][r['origin']]
        lines += ['', '## %s · %s · %s' % (r['pilot_id'], r['desk_id'], r['storage_layer']), '',
                  r['title_original'], '', '[Source](%s) · source-stated date `%s`' %
                  (r['canonical_url'], r['published_date']), '',
                  'Record identity: `%s` / `%s` / exact source URL above.' %
                  (r['desk_id'], r['source_slug']), '',
                  'Pinned store: `%s:%s`; `%s.url` = `%s`.' %
                  (origin['commit'], origin['path'], r['row_locator']['table'], r['row_locator']['url']), '',
                  'Body SHA-256: `%s` (%d characters).' % (r['body_sha256'], r['body_chars']), '',
                  'Existing desk labels: %s.' % (', '.join('`%s`' % c for c in r['local_categories']) or 'none recorded')]
        for p in r['proposals']:
            lines += ['', '- Propose `%s` [%s]: %s' % (p['topic'], ', '.join(p['evidence']), p['rationale'])]
        if r['unclassified_reason']:
            lines += ['', 'Unclassified: ' + r['unclassified_reason']]
        for e in r['evidence']:
            lines += ['', '%s · `text_original[%d:%d]` (Unicode characters, end exclusive):' %
                      (e['id'], e['start'], e['end']), '', '\n'.join(('> ' + line).rstrip() for line in e['quote'].split('\n'))]
        if r['review_issue']:
            lines += ['', 'Review question/limitation: ' + r['review_issue']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-sources', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    data = validate(json.loads(LEDGER.read_text(encoding='utf-8')))
    if args.verify_sources:
        print('Verified %d pinned source rows; no database writes.' % verify_sources(data))
    elif args.report:
        print(markdown(data), end='')
    else:
        print(json.dumps(summarize(data), indent=2))


if __name__ == '__main__':
    main()
