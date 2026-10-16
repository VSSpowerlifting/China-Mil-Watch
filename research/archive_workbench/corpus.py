"""Publication-aware adapters. The bulk archive contract is intentionally title-only."""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from scripts.reconcile_db import read_only
from core.retired_article_urls import url_sha256, verify_no_active_retired_urls

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'https://indopacificrecord.org'
SCHEMA = 'ipr-archive-workbench/1'
FIELDS = ('id', 'title', 'original_title', 'summary', 'text', 'date', 'date_kind', 'desks',
          'source', 'issuer', 'record_type', 'processing', 'ipr_url', 'source_url', 'citation')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def public_url(value, *, ipr=False):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError('unsafe_public_url')
    try:
        u = urlsplit(value)
        safe = (u.scheme in ('https', 'http') and u.hostname and not u.username
                and not u.password and u.port in (None, 80, 443) and '\\' not in value)
    except ValueError:
        safe = False
    if not safe or (ipr and (u.scheme != 'https' or u.netloc != 'indopacificrecord.org')):
        raise ValueError('unsafe_public_url')
    return value


def projection(**values):
    """Never pass arbitrary dictionaries or row serialization across this boundary."""
    if set(values) - set(FIELDS):
        raise ValueError('unknown_public_field')
    result = {key: values.get(key) for key in FIELDS}
    if not isinstance(result['id'], str) or not result['id']:
        raise ValueError('missing_public_identity')
    for key in ('title', 'original_title', 'summary', 'text', 'source', 'issuer', 'processing', 'citation', 'date_kind'):
        if result[key] is not None and not isinstance(result[key], str):
            raise ValueError('invalid_public_text')
    if result['date'] is not None:
        day = result['date']
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or date.fromisoformat(day).isoformat() != day:
            raise ValueError('invalid_publication_date')
    if not isinstance(result['desks'], list) or not all(isinstance(s, str) for s in result['desks']):
        raise ValueError('invalid_public_desk')
    result['desks'] = sorted(set(result['desks']))
    public_url(result['ipr_url'], ipr=True)
    public_url(result['source_url'])
    if result['record_type'] == 'official_link':
        # Title may be copied ONLY by a loader that explicitly permits it. No body,
        # summary, model draft or private capture fields can cross this boundary.
        if result['summary'] is not None or result['text'] is not None:
            raise ValueError('official_link_text_prohibited')
    return result


def gp_module():
    spec = importlib.util.spec_from_file_location('ipr_workbench_existing_preview', ROOT / 'site/preview/generate_preview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive_projection(index, con, gp, excluded):
    """Intersection of existing public metadata, exact current rows and tombstones.

    Original URLs are used ONLY for retirement checks, never serialized. The
    existing bulk-index contract explicitly excludes bodies, summaries and URLs.
    """
    if index.get('fields') != ['id', 'date', 'source', 'state', 'title_en', 'title_orig']:
        raise ValueError('unknown_public_archive_projection')
    if len(index.get('records', [])) != index['snapshot']['records']:
        raise ValueError('public_archive_count_drift')
    retired = con.execute('SELECT original_article_id, url_sha256 FROM retired_article_urls').fetchall()
    retired_ids, retired_urls = {r[0] for r in retired}, {r[1] for r in retired}
    # Explicit metadata select; never SELECT *, source bodies or model summaries.
    current = {r[0]: r for r in con.execute(
        'SELECT a.id, a.url, a.published_date, a.title_english, a.title_original, '
        's.slug FROM articles a JOIN sources s ON s.id=a.source_id')}
    seen = set()
    for row in index['records']:
        if not isinstance(row, list) or len(row) != 6 or type(row[0]) is not int:
            raise ValueError('invalid_public_archive_row')
        ident, day, source_pos, state_pos, english, original = row
        if type(source_pos) is not int or type(state_pos) is not int or not (0 <= source_pos < len(index['sources'])) or not (0 <= state_pos < len(index['states'])):
            raise ValueError('invalid_public_archive_facet')
        if ident in seen:
            raise ValueError('duplicate_public_archive_identity')
        seen.add(ident)
        if ident in retired_ids or (ident in current and url_sha256(current[ident][1]) in retired_urls):
            excluded['retired_candidate'] += 1
            continue
        if ident not in current:
            excluded['stale_public_projection'] += 1
            continue
        source, state = index['sources'][source_pos], index['states'][state_pos]
        stored = current[ident]
        if (day, english or '', original or '', source['code']) != (stored[2], stored[3] or '', stored[4] or '', stored[5]):
            excluded['changed_public_projection'] += 1
            continue
        desk = source.get('desk') or {}
        institution_pos = source.get('institution')
        issuer = (index['institutions'][institution_pos]['label'] if institution_pos is not None else None)
        ipr = ORIGIN + '/record/%d.html' % ident
        # Reuse only the helper's As-held block; its source-text block is NOT a
        # permitted bulk export. Sparse records retain a precise record locator.
        citation = 'As held. Indo-Pacific Record, Research Atlas corpus, Record %d, Snapshot — %s (%s records).' % (
            ident, index['snapshot']['date'], format(index['snapshot']['records'], ','))
        if original and day and issuer and source.get('label'):
            citation = gp.record_citation({'id': ident, 'institution': issuer,
                'title_original': original, 'source_name': source['label'],
                'published_date': day, 'url': stored[1], 'state': state['code']},
                'Indo-Pacific Record', {'date': index['snapshot']['date'],
                                      'expected_records': index['snapshot']['records']})['as_held']
        yield projection(id='record:%d' % ident, title=english or original or None,
            original_title=original or None, date=day or None, date_kind='source-stated publication',
            desks=[desk['code']] if desk.get('code') else [], source=source['label'], issuer=issuer,
            record_type='archive_record', processing=state['label'] + ' · ' + gp.CITATION_PROCESSING_NOTES[state['code']],
            ipr_url=ipr, citation=citation + ' ' + ipr)
    excluded['active_not_in_public_projection'] += len(set(current) - seen)


def official(rows, desk, source, issuer):
    for r in rows:
        url = public_url(r['source_url'])
        title = r.get('title_original')
        neutral = r.get('neutral_label')
        ident = str(r.get('source_identity') or r.get('id') or digest(url.encode()))
        display = title or neutral  # No invented substitute publisher headline.
        hold = r.get('editorial_hold') or ''
        record_issuer = issuer or r.get('issuer_label') or r.get('source_name')
        citation = '. '.join(s for s in [record_issuer, ('“%s”' % title) if title else neutral,
                              r.get('published_date'), url, hold] if s) + '.'
        yield projection(id='official:' + ident, title=display, original_title=title,
            date=r.get('published_date'), date_kind='source-stated publication',
            desks=[desk], source=r.get('source_name') or source, issuer=record_issuer,
            record_type='official_link', processing='Official-link metadata only; this reference includes no source text or independent verification' + ('. ' + hold if hold else ''),
            source_url=url, citation=citation)


def deduplicate(records, retired_ids=(), retired_urls=(), excluded=None):
    """Exact canonical artifact identity only. No fuzzy title/URL/event matching."""
    excluded = excluded if excluded is not None else Counter()
    by_key, by_id = {}, {}
    for record in records:
        r = projection(**record)
        url = r['ipr_url']
        match = re.search(r'/(?:record|article)/(\d+)\.html$', url or '')
        if ((match and int(match.group(1)) in retired_ids) or
                (r['source_url'] and url_sha256(r['source_url']) in retired_urls)):
            excluded['retired_candidate'] += 1
            continue
        key = url or r['source_url']
        if not key:
            raise ValueError('missing_canonical_identity')
        if key in by_key:
            prior = by_key[key]
            if prior != r:
                # Different approved registers can name the same outbound
                # document. Earliest loader is production's explicit priority;
                # do not combine text/claims from duplicate manifestations.
                if prior['record_type'] != 'official_link' or r['record_type'] != 'official_link':
                    raise ValueError('conflicting_canonical_artifact')
            excluded['duplicate_canonical_identity'] += 1
            continue
        if r['id'] in by_id:
            raise ValueError('conflicting_stable_identity')
        by_key[key], by_id[r['id']] = r, key
    return sorted(by_key.values(), key=lambda r: r['id'])


def build_corpus(db=ROOT / 'pla_watch.db'):
    from core.desk_registry import load_registry
    from core.brief_collection import load_collection, brief_view, brief_citation
    from core.reviewed_source_links import load_public_desk_references
    from core.public_editorial_research import load_catalog
    from core.edition_identity import resolve_identity
    from core.indonesia_official_index import load as indonesia_news
    from core.indonesia_press_index import load as indonesia_press
    from core.us_pacom_official_links import load_us_pacom_official_links
    from core import uscc_official_metadata as uscc, us_treasury_official_metadata as treasury
    from core import us_bis_authenticated_metadata as bis

    gp = gp_module()
    excluded = Counter({reason: 0 for reason in ('retired_candidate', 'stale_public_projection',
        'changed_public_projection', 'active_not_in_public_projection',
        'private_brief_draft', 'duplicate_canonical_identity')})
    records = []
    raw = (ROOT / 'output/corpus-index.json').read_bytes()
    index = json.loads(raw)
    with read_only(str(db)) as con:
        # A malformed/missing ledger fails the build. A retired ID cannot be
        # revived under an alternate URL or through a stale compact index.
        retirement_count = verify_no_active_retired_urls(con)
        tombstones = con.execute('SELECT original_article_id,url_sha256 FROM retired_article_urls').fetchall()
        records.extend(archive_projection(index, con, gp, excluded))
    registry = load_registry()
    for desk in ('japan', 'vietnam', 'philippines', 'indonesia'):
        records.extend(official(load_public_desk_references(desk), desk, None, None))
    records.extend(official(indonesia_news(), 'indonesia', 'Kemhan Berita', 'Kementerian Pertahanan Republik Indonesia'))
    records.extend(official(indonesia_press(), 'indonesia', 'Kemhan Siaran Pers', 'Kementerian Pertahanan Republik Indonesia'))
    records.extend(official(load_us_pacom_official_links(), 'us-indopacific', 'U.S. Indo-Pacific Command official site', 'U.S. Indo-Pacific Command'))
    for loader, label, issuer in (
        (uscc, 'USCC press releases', 'U.S.-China Economic and Security Review Commission'),
        (treasury, 'Treasury press releases', 'U.S. Department of the Treasury'),
        (bis, 'BIS press releases', 'U.S. Department of Commerce · Bureau of Industry and Security')):
        records.extend(official(loader.load_public_links(db), 'us-indopacific', label, issuer))
    korea = registry.get('korea')
    if korea and korea.public:
        from core.korea_public_bibliography import load_public_korea_links
        from core.korea_additional_public_links import load_additional_korea_official_links
        from core.korea_official_live_links import load_live_korea_official_links
        from core.korea_published_originals import read_release_index
        fixed = load_public_korea_links() + load_additional_korea_official_links()
        links = fixed + load_live_korea_official_links(db, exclude={r['source_identity'] for r in fixed})
        records.extend(official(links, 'korea', 'Republic of Korea Policy Briefing', 'Republic of Korea Ministry of National Defense'))
        # Only the public release register can enable original text. A private
        # capture, KOGL mark or draft pack alone cannot enter this adapter.
        for r in read_release_index():
            ipr = ORIGIN + '/' + r['route']
            records.append(projection(id='original:' + r['source_identity'], title=None,
                text=r['text_original'], date=r['publisher_posted_date'], date_kind='source-stated publication',
                desks=['korea'], source=r['publisher_label'], issuer=r['issuer_label'],
                record_type='preserved_original', processing='Published original source text; source statements are not independently verified',
                ipr_url=ipr, source_url=r['official_url'],
                citation='%s. Original source text, %s. %s. %s' % (r['issuer_label'], r['publisher_posted_date'], ipr, r['official_url'])))
        from core.korea_english_publication import public_registry
        for release, review, original in public_registry():
            number = original['news_id']
            for kind, route, title, summary, text in (
                ('reviewed_translation', 'korea-translations/',
                 'English translation — Korean MND release ' + number, None,
                 '\n\n'.join(p['text_en'] for p in review['translations'])),
                ('reviewed_analysis', 'korea-analysis/', review['analysis']['heading_en'],
                 review['analysis']['thesis_en'], '\n\n'.join(
                     c['heading_en'] + '\n' + c['analysis_en'] for c in review['analysis']['claims'])
                     + '\n\n' + review['analysis']['limitations_en'])):
                ipr = ORIGIN + '/' + route + number + '.html'
                issued = release['released_at_utc'][:10]
                records.append(projection(id=kind + ':' + original['source_identity'],
                    title=title, summary=summary, text=text, date=issued, date_kind='IPR publication',
                    desks=['korea'], source='Indo-Pacific Record', issuer=original['issuer_label'],
                    record_type=kind, processing='Machine-assisted; reviewed by an editor. Source statements are not independent verification.',
                    ipr_url=ipr, source_url=original['official_url'],
                    citation='“%s.” Indo-Pacific Record, %s. Machine-assisted, editor-reviewed. Source published %s. %s' % (
                        title, issued, original['publisher_posted_date'], ipr)))
    editions = gp.load_editions(ROOT)
    collection = load_collection(editions, registry, briefs_dir=ROOT / 'briefs')
    excluded['private_brief_draft'] += len(collection.withheld)
    catalog = {ORIGIN + '/' + r['ipr_page']: r for r in load_catalog()}
    for row in collection.rows:
        e = row['entry']
        ipr = e['url'] if e['url'].startswith('https://') else ORIGIN + '/' + e['url']
        if row['kind'] == 'brief':
            view = brief_view(e['slug'], collection.sidecars[e['slug']],
                desk_names={}, state_labels=gp.STATE_LABELS, state_order=gp.STATE_ORDER,
                language_label=gp.language_label)
            citation = brief_citation(view, origin=ORIGIN)
            desks = e['desks']
        else:
            citation = gp.edition_citation(e)
            desks = ['china']  # Existing editions are the China Desk weekly series.
        # load_editions deliberately omits two stored historical publication
        # dates and its author fields. Resolve them from the same canonical
        # edition, never substitute the coverage week or a current masthead.
        historical = {}
        if row['kind'] == 'issue':
            historical = json.loads((ROOT / 'output/the-pla-watch/posts' / (e['slug'] + '.json')).read_text(encoding='utf-8'))
        author = e.get('author_name') or (resolve_identity(historical)['author_name'] if historical else None)
        publication = catalog.get(ipr)
        issued = publication['published_on'] if publication else historical.get('published_date')
        records.append(projection(id='analysis:' + e['slug'], title=e['title'] or None,
            summary=e['dek'] or None, date=issued,
            date_kind='IPR publication' if issued else 'Publication date unrecorded; week ending ' + e['date'],
            desks=desks, source=e.get('series_name'), issuer=author,
            record_type='human_analysis', processing='Human-controlled analytical collection',
            ipr_url=ipr, citation=citation))
        catalog.pop(ipr, None)
    for ipr, r in catalog.items():
        records.append(projection(id='analysis:' + r['ipr_page'], title=r['ipr_title'],
            date=r['published_on'], date_kind='IPR publication', desks=[r['desk']],
            source='Indo-Pacific Record Briefs', record_type='human_analysis',
            processing='Separately approved published IPR writing', ipr_url=ipr,
            citation='“%s.” Indo-Pacific Record Briefs, %s. %s' % (r['ipr_title'], r['published_on'], ipr)))
    final = deduplicate(records, {r[0] for r in tombstones}, {r[1] for r in tombstones}, excluded)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'schema': SCHEMA, 'source_revision': revision,
        'database_sha256': digest(Path(db).read_bytes()), 'public_projection_sha256': digest(raw),
        'public_snapshot': index['snapshot'], 'retirement_ledger_entries': retirement_count,
        'included': len(final), 'included_by_type': dict(sorted(Counter(r['record_type'] for r in final).items())),
        'excluded_candidates_by_reason': dict(sorted(excluded.items())),
        'not_enumerated': ['private source archives', 'shadow captures', 'unpublished timelines/dossiers',
                           'held editorial packs outside public loaders'],
        'records_sha256': digest(encoded(final))}
    return {'schema': SCHEMA, 'records': final}, manifest
