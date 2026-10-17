"""Publication-aware Archive projection, adapted from reviewed PR #766.

The renderer supplies its current compact projection and already-public loader
results. This module never reads generated output or enumerates private packs.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import calendar
import hashlib
import json
import re
from urllib.parse import urlsplit

from scripts.reconcile_db import read_only
from core.retired_article_urls import url_sha256, verify_no_active_retired_urls

ORIGIN = 'https://indopacificrecord.org'
SCHEMA = 'ipr-archive-research/1'
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


def archive_projection(index, con, cite_record, processing_notes, excluded):
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
            citation = cite_record({'id': ident, 'institution': issuer,
                'title_original': original, 'source_name': source['label'],
                'published_date': day, 'url': stored[1], 'state': state['code']},
                'Indo-Pacific Record', {'date': index['snapshot']['date'],
                                      'expected_records': index['snapshot']['records']})['as_held']
        yield projection(id='record:%d' % ident, title=english or original or None,
            original_title=original or None, date=day or None, date_kind='source-stated publication',
            desks=[desk['code']] if desk.get('code') else [], source=source['label'], issuer=issuer,
            record_type='archive_record', processing=state['label'] + ' · ' + processing_notes[state['code']],
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



def published_artifacts(originals, english_publications):
    """Only public-register results supplied by the renderer, never review packs."""
    for r in originals:
        ipr = ORIGIN + '/' + r['route']
        yield projection(id='original:' + r['source_identity'], title=None,
            text=r['text_original'], date=r['publisher_posted_date'], date_kind='source-stated publication',
            desks=['korea'], source=r['publisher_label'], issuer=r['issuer_label'],
            record_type='preserved_original', processing='Published original source text; source statements are not independently verified',
            ipr_url=ipr, source_url=r['official_url'],
            citation='%s. Original source text, %s. %s. %s' % (r['issuer_label'], r['publisher_posted_date'], ipr, r['official_url']))
    for release, review, original in english_publications:
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
            yield projection(id=kind + ':' + original['source_identity'],
                title=title, summary=summary, text=text, date=issued, date_kind='IPR publication',
                desks=['korea'], source='Indo-Pacific Record', issuer=original['issuer_label'],
                record_type=kind, processing='Machine-assisted; reviewed by an editor. Source statements are not independent verification.',
                ipr_url=ipr, source_url=original['official_url'],
                citation='“%s.” Indo-Pacific Record, %s. Machine-assisted, editor-reviewed. Source published %s. %s' % (
                    title, issued, original['publisher_posted_date'], ipr))


def analysis_records(collection, catalog, historical, *, edition_citation,
                     state_labels, state_order, language_label):
    from core.brief_collection import brief_view, brief_citation
    from core.edition_identity import resolve_identity
    catalog = {ORIGIN + '/' + r['ipr_page']: r for r in catalog}
    for row in collection.rows:
        e = row['entry']
        ipr = e['url'] if e['url'].startswith('https://') else ORIGIN + '/' + e['url']
        if row['kind'] == 'brief':
            view = brief_view(e['slug'], collection.sidecars[e['slug']],
                desk_names={}, state_labels=state_labels, state_order=state_order,
                language_label=language_label)
            citation = brief_citation(view, origin=ORIGIN)
            desks = e['desks']
        else:
            citation = edition_citation(e)
            desks = ['china']
        stored = historical.get(e['slug'], {}) if row['kind'] == 'issue' else {}
        author = e.get('author_name') or (resolve_identity(stored)['author_name'] if stored else None)
        publication = catalog.pop(ipr, None)
        issued = publication['published_on'] if publication else stored.get('published_date')
        yield projection(id='analysis:' + e['slug'], title=e['title'] or None,
            summary=e['dek'] or None, date=issued,
            date_kind='IPR publication' if issued else 'Publication date unrecorded; week ending ' + e['date'],
            desks=desks, source=e.get('series_name'), issuer=author,
            record_type='human_analysis', processing='Human-controlled analytical collection',
            ipr_url=ipr, citation=citation)
    for ipr, r in catalog.items():
        yield projection(id='analysis:' + r['ipr_page'], title=r['ipr_title'],
            date=r['published_on'], date_kind='IPR publication', desks=[r['desk']],
            source='Indo-Pacific Record Briefs', record_type='human_analysis',
            processing='Human-controlled analytical collection', ipr_url=ipr,
            citation='“%s.” Indo-Pacific Record, %s. %s' % (r['ipr_title'], r['published_on'], ipr))


def build_index(db_path, compact, *, cite_record, processing_notes,
                official_groups=(), originals=(), english_publications=(), analyses=()):
    """One build's selected DB + current public projection/loaders, fail closed.

    Source URLs are read solely for retirement checks on archive rows, never
    serialized for them. Counts and digests describe public data only.
    """
    excluded = Counter()
    with read_only(str(db_path)) as con:
        count = verify_no_active_retired_urls(con)
        tombstones = con.execute('SELECT original_article_id,url_sha256 FROM retired_article_urls').fetchall()
        records = list(archive_projection(compact, con, cite_record, processing_notes, excluded))
    holds = {}
    for rows, desk, source, issuer in official_groups:
        rows = list(rows)
        group = list(official(rows, desk, source, issuer))
        records.extend(group)
        for raw, record in zip(rows, group):
            if raw.get('editorial_hold'):
                holds.setdefault(record['id'], raw['editorial_hold'])
    records.extend(published_artifacts(originals, english_publications))
    records.extend(analyses)
    records = deduplicate(records, {r[0] for r in tombstones}, {r[1] for r in tombstones}, excluded)
    # Per-type rules also bind any future caller of the public projection API.
    for r in records:
        if r['record_type'] == 'archive_record' and any(r[k] is not None for k in ('summary', 'text', 'source_url')):
            raise ValueError('archive_bulk_text_prohibited')
    return {'schema': SCHEMA, 'snapshot': compact['snapshot'],
            'archive_sha256': digest(encoded(compact)), 'digest': digest(encoded(records)),
            'records': records, 'holds': {r['id']: holds[r['id']] for r in records if r['id'] in holds}, 'display': display_records(compact, records),
            'days': {day: [int(day[8:10]), calendar.month_name[int(day[5:7])] + ' ' + day[:4],
                           calendar.day_name[date.fromisoformat(day).weekday()]]
                     for day in sorted({r['date'] for r in records if r['date']})}, 'retirement_ledger_entries': count,
            'excluded': dict(sorted(excluded.items()))}


def display_records(compact, records):
    """Reader labels and closed facets from the same six-field public projection.

    Kept outside the export records. This avoids a second set of browser-side
    metadata joins and keeps stored state/language codes out of reading labels.
    """
    by_id = {r['id']: r for r in records}
    result = {}
    for position, row in enumerate(compact['records']):
        ident, day, source_pos, state_pos, english, original = row
        r = by_id.get('record:' + str(ident))
        if r is None:
            continue
        source = compact['sources'][source_pos]
        state = compact['states'][state_pos]
        institution = source.get('institution')
        who = compact['institutions'][institution] if institution is not None else {}
        language = source.get('language')
        lang = compact['languages'][language] if language is not None else {}
        desk = source.get('desk') or {}
        result[r['id']] = dict(
            english=bool(english), source=source['code'], institution=who.get('code'), language=lang.get('code'), status=state['code'],
            focus=ident in compact['focus_ids'], trail=ident in compact['trail_ids'], order=position,
            who=who.get('label') or source['label'],
            via=' · '.join(v for v in (source['label'] if who else '', lang.get('label')) if v),
            desk_name=desk.get('label'), desk_route=desk.get('route'), lang=lang.get('code'), title_lang=lang.get('code') if not english else None,
            analyzed=state['label'] if state['code'] == 'analyzed' else None,
            state=state['label'] if state['code'] != 'analyzed' else None,
            state_class='state state--' + state['code'],
            trail_label='In an analysis source trail' if ident in compact['trail_ids'] else None)
    return result
