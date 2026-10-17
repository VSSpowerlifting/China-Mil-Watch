"""Publication boundary and reproducible JS query/export contracts. All fixtures synthetic."""
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'site/preview'))
import generate_preview as gp
from core import archive_research as c

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'site/preview/archive-search.js'
FIXTURE = ROOT / 'tests/fixtures/archive_relevance.json'


def node(expression, payload=None):
    if not shutil.which('node'):
        raise unittest.SkipTest('Node is required for the shared browser/CLI query engine')
    script = "const E=require(process.argv[1]), input=JSON.parse(require('fs').readFileSync(0,'utf8'));\n" + expression
    result = subprocess.run(['node', '-e', script, str(ENGINE)], input=json.dumps(payload),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class CorpusBoundaryTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(exist_ok=True)
        self.con = sqlite3.connect(':memory:')
        self.addCleanup(self.con.close)
        self.con.executescript('''CREATE TABLE sources(id INTEGER,slug TEXT);
          INSERT INTO sources VALUES(1,'fixture');
          CREATE TABLE articles(id INTEGER,url TEXT,published_date TEXT,title_english TEXT,title_original TEXT,source_id INTEGER);
          INSERT INTO articles VALUES(1,'https://example.org/a','2026-01-01','Public title','Original fixture',1);
          INSERT INTO articles VALUES(2,'https://example.org/private','2026-01-01','Private needle','Private fixture',1);
          CREATE TABLE retired_article_urls(original_article_id INTEGER,url_sha256 TEXT);''')
        self.index = {'fields':['id','date','source','state','title_en','title_orig'],
            'snapshot':{'date':'2026-01-01','records':1},
            'sources':[{'code':'fixture','label':'Fixture source','desk':{'code':'fixture'},'institution':0}],
            'institutions':[{'label':'Fixture issuer'}], 'states':[{'code':'analyzed','label':'Analyzed'}],
            'records':[[1,'2026-01-01',0,0,'Public title','Original fixture']]}
        self.excluded = Counter()
        # Use the existing citation helper itself, not a mock copy of its format.
        self.gp = gp

    def project(self):
        return list(c.archive_projection(self.index, self.con, gp.record_citation, gp.CITATION_PROCESSING_NOTES, self.excluded))

    def test_only_public_projection_fields_and_never_private_row(self):
        result = self.project()
        self.assertEqual([r['id'] for r in result], ['record:1'])
        blob = json.dumps(result)
        for private in ('Private needle', 'example.org/a', 'Private fixture'):
            self.assertNotIn(private, blob)
        self.assertIsNone(result[0]['text'])
        self.assertIsNone(result[0]['summary'])
        self.assertIsNone(result[0]['source_url'])
        self.assertEqual(self.excluded['active_not_in_public_projection'], 1)
        self.assertIn('As held.', result[0]['citation'])
        self.assertIn('Record 1', result[0]['citation'])

    def test_retired_id_cannot_resurrect_at_alternate_url(self):
        self.con.execute('INSERT INTO retired_article_urls VALUES(?,?)', (1,c.url_sha256('https://example.org/old')))
        self.assertEqual(self.project(), [])
        self.assertEqual(self.excluded['retired_candidate'], 1)

    def test_retired_url_cannot_resurrect_under_different_id(self):
        self.con.execute('INSERT INTO retired_article_urls VALUES(?,?)', (99,c.url_sha256('https://example.org/a')))
        self.assertEqual(self.project(), [])

    def test_stale_index_entry_is_excluded(self):
        self.con.execute('DELETE FROM articles WHERE id=1')
        self.assertEqual(self.project(), [])
        self.assertEqual(self.excluded['stale_public_projection'], 1)

    def test_changed_public_projection_is_not_reconstructed(self):
        self.con.execute("UPDATE articles SET title_english='Restricted changed title' WHERE id=1")
        self.assertEqual(self.project(), [])
        self.assertEqual(self.excluded['changed_public_projection'], 1)

    def test_missing_titles_dates_remain_missing(self):
        self.con.execute("UPDATE articles SET title_english=NULL,title_original=NULL,published_date=NULL WHERE id=1")
        self.index['records'][0][1:] = [None,0,0,'','']
        r = self.project()[0]
        self.assertIsNone(r['title']); self.assertIsNone(r['date'])
        self.assertIn('Record 1', r['citation'])

    def test_duplicate_index_identity_fails_closed(self):
        self.index['records'] *= 2; self.index['snapshot']['records'] = 2
        with self.assertRaisesRegex(ValueError,'duplicate_public_archive_identity'):
            self.project()

    def test_missing_retirement_ledger_fails(self):
        self.con.execute('DROP TABLE retired_article_urls')
        with self.assertRaises(ValueError):
            c.verify_no_active_retired_urls(self.con)

    def test_bad_facet_index_fails_instead_of_negative_index_access(self):
        self.index['records'][0][2] = -1
        with self.assertRaises(ValueError): self.project()

    def test_official_link_cannot_acquire_private_fields(self):
        raw = {'source_identity':'fixture:x','source_url':'https://example.org/x','published_date':None,
               'neutral_label':'Fixture official reference', 'title_private':'Secret needle',
               'summary_english':'Secret needle','text_original':'Secret needle','model_draft':'Secret needle'}
        result = list(c.official([raw],'fixture','Fixture source','Fixture issuer'))[0]
        self.assertNotIn('Secret needle',json.dumps(result))
        self.assertIsNone(result['text']); self.assertIsNone(result['summary'])
        self.assertIsNone(result['original_title']); self.assertIsNone(result['date'])
        poisoned = dict(result, text='Secret needle')
        with self.assertRaisesRegex(ValueError,'official_link_text_prohibited'): c.projection(**poisoned)

    def test_exact_duplicates_collapse_distinct_documents_survive(self):
        a,b = fixture()['records'][:2]
        b = dict(b,title=a['title'])
        self.assertEqual(len(c.deduplicate([a,a,b])),2)
        with self.assertRaisesRegex(ValueError,'conflicting_canonical_artifact'):
            c.deduplicate([a,dict(a,title='Conflicting title')])

    def test_official_duplicate_urls_use_loader_priority_not_title_merging(self):
        d = fixture()['records'][3]
        other = dict(d,id='fixture:d2',title='Another permitted label')
        self.assertEqual(c.deduplicate([d,other]),[d])

    def test_retired_article_alias_is_not_an_alternate_route_back(self):
        a = dict(fixture()['records'][0],ipr_url=c.ORIGIN+'/article/1.html')
        self.assertEqual(c.deduplicate([a],retired_ids={1}),[])

    def test_unsafe_urls_and_unknown_fields_fail(self):
        for value in ('javascript:alert(1)','https://user:pass@example.org/x','https://example.org/\\evil','https://example.org/\nx'):
            with self.assertRaises(ValueError): c.public_url(value)
        with self.assertRaises(ValueError): c.projection(**dict(fixture()['records'][0],secret='secret'))

    def test_private_draft_matching_query_is_withheld_by_existing_gate(self):
        from core.brief_collection import load_collection
        from core.desk_registry import load_registry
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,'private-matching-needle.json').write_text(json.dumps({
                'editorial_status':'draft','title':'maritime private matching needle'}))
            result = load_collection([],load_registry(),briefs_dir=Path(temp))
            self.assertEqual(result.briefs,())
            self.assertEqual(result.withheld,('private-matching-needle',))


class QueryExportTests(unittest.TestCase):
    def test_independently_described_relevance_cases(self):
        data = fixture()
        results = node("console.log(JSON.stringify(input.cases.map(c=>E.search(E.prepare(input.records),c.query).map(h=>h.record.id))));",data)
        for case, actual in zip(data['cases'],results):
            with self.subTest(case=case['why']): self.assertEqual(actual,case['ids'])

    def test_query_limits_malformed_phrases_dates_and_controls(self):
        queries = [{'q':'a'*513},{'q':'"unclosed'},{'q':'\x00'},
            {'q':' '.join('x'+str(i) for i in range(33))},
            {'from':'2026-02-30'},{'from':'2026-01-04','to':'2026-01-01'},
            {'from':'2026-1-01'},{'sort':'unknown'}]
        result = node("console.log(JSON.stringify(input.map(q=>{try{E.search([],q);return false;}catch(_){return true;}})));",queries)
        self.assertTrue(all(result))

    def test_sort_missing_dates_tie_breakers_and_input_order_independence(self):
        data = fixture()['records']
        result = node("console.log(JSON.stringify(['newest','oldest','relevance'].map(sort=>{const ids=rs=>E.search(E.prepare(rs),{sort}).map(h=>h.record.id);return [ids(input),ids([...input].reverse())];})));",data)
        for left,right in result:
            self.assertEqual(left,right); self.assertEqual(left[-2:],['fixture:c','fixture:d'])

    def test_csv_quotes_unicode_newlines_and_formula_injection(self):
        rows = []
        for n,value in enumerate(['=1+2',' +SUM(1,2)','\t@cmd','\ufeff-1','\u200b=1','Unicode café, "quoted"\nsecond line']):
            rows.append(dict(fixture()['records'][0],id='formula:'+str(n),title=value,secret='never exported'))
        result = node("console.log(JSON.stringify({csv:E.csv(input,input.map(r=>r.id)),json:E.selected(input,input.map(r=>r.id))}));",rows)
        import csv, io
        parsed = list(csv.reader(io.StringIO(result['csv'].lstrip('\ufeff'))))
        title = parsed[0].index('title')
        for row in parsed[1:6]: self.assertTrue(row[title].startswith("'"))
        self.assertEqual(parsed[6][title],rows[5]['title'])
        self.assertNotIn('secret',json.dumps(result)); self.assertNotIn('never exported',json.dumps(result))

    def test_selection_export_ignores_stale_ids_duplicates_and_input_sort(self):
        data = fixture()['records']
        result = node("const ids=['fixture:b','missing','fixture:a','fixture:b'];console.log(JSON.stringify([E.selected(input,ids),E.selected([...input].reverse(),ids)]));",data)
        self.assertEqual(result[0],result[1]); self.assertEqual([r['id'] for r in result[0]],['fixture:a','fixture:b'])

    def test_snippets_are_only_from_indexed_fields(self):
        d = dict(fixture()['records'][3],secret_body='Secret needle')
        result = node("console.log(JSON.stringify(E.snippet(input,'needle')));",d)
        self.assertEqual(result,'')



class SnapshotRefreshTests(unittest.TestCase):
    def test_same_build_tracks_selected_database_retirement_and_public_register(self):
        from unittest import mock
        from scripts.reconcile_db import read_only
        with tempfile.TemporaryDirectory(prefix='ipr-archive-snapshot-') as temp:
            temp = Path(temp)
            db = temp / 'fixture.db'
            with read_only(str(ROOT / 'pla_watch.db')) as source:
                dest = sqlite3.connect(str(db))
                source.backup(dest)
                dest.close()
            con = sqlite3.connect(str(db))
            columns = [r[1] for r in con.execute('PRAGMA table_info(articles)')]
            latest = dict(zip(columns, con.execute('SELECT * FROM articles ORDER BY id DESC LIMIT 1').fetchone()))
            ident = max(con.execute('SELECT MAX(id) FROM articles').fetchone()[0],
                        con.execute('SELECT MAX(original_article_id) FROM retired_article_urls').fetchone()[0]) + 1
            latest.update(id=ident, url='https://example.org/synthetic-archive-integration',
                          title_english='Synthetic newly eligible fixture', title_original='Synthetic original title',
                          text_original='Synthetic body excluded from bulk search', summary_english='Synthetic summary excluded')
            con.execute('INSERT INTO articles (%s) VALUES (%s)' % (','.join(columns), ','.join('?' for _ in columns)), list(latest.values()))
            con.commit()

            def build(name):
                path = temp / name
                gp.build(path, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db), legacy_routes=True)
                return json.loads((path / 'archive-research-index.json').read_text()), json.loads((path / 'corpus-index.json').read_text())

            before, compact = build('newly-eligible')
            item = next(r for r in before['records'] if r['id'] == 'record:' + str(ident))
            self.assertEqual(item['title'], 'Synthetic newly eligible fixture')
            self.assertIsNone(item['text']); self.assertIsNone(item['summary']); self.assertIsNone(item['source_url'])
            self.assertEqual(before['archive_sha256'], c.digest(c.encoded(compact)))
            self.assertNotIn('Synthetic body excluded', json.dumps(before))
            self.assertTrue(any(r['record_type'] == 'reviewed_translation' for r in before['records']))
            con.execute('DELETE FROM articles WHERE id=?', (ident,))
            con.execute('INSERT INTO retired_article_urls VALUES(?,?,?,?,?)',
                        (c.url_sha256(latest['url']),ident,'synthetic','2026-01-01','0'*64))
            con.commit(); con.close()
            # The renderer consumes the changed register result, never stale
            # generated pages or the merely staged Korea review packages.
            with mock.patch('core.korea_english_publication.public_registry', return_value=[]):
                after, after_compact = build('retired-and-withheld')
            ids = {r['id'] for r in after['records']}
            self.assertNotIn(item['id'], ids)
            self.assertNotIn(item['id'], after['display'])
            self.assertFalse(any(r['record_type'] in ('reviewed_translation','reviewed_analysis') for r in after['records']))
            self.assertNotEqual(before['digest'], after['digest'])
            self.assertEqual(after['archive_sha256'], c.digest(c.encoded(after_compact)))
            self.assertNotEqual(compact['snapshot']['records'],after_compact['snapshot']['records'])

    def test_renderer_has_no_generated_search_input_or_dynamic_import(self):
        source = (ROOT / 'core/archive_research.py').read_text()
        self.assertNotIn('importlib', source)
        self.assertNotIn('output/', source)
        self.assertNotIn('read_release_index(', source)
        self.assertNotIn('public_registry(', source)
