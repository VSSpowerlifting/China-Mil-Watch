"""Publication boundary and reproducible JS query/export contracts. All fixtures synthetic."""
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from research.archive_workbench import corpus as c
from research.archive_workbench.build import destination

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'research/archive_workbench/web/search.js'
FIXTURE = ROOT / 'research/archive_workbench/fixtures/relevance.json'


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
        self.gp = c.gp_module()

    def project(self):
        return list(c.archive_projection(self.index, self.con, self.gp, self.excluded))

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

    def test_build_cannot_target_production_or_arbitrary_directory(self):
        for target in (ROOT/'output',ROOT/'output/research',ROOT/'research/archive_workbench',Path('/tmp/workbench')):
            with self.assertRaises(ValueError): destination(target)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            path = Path(temp)/'safe'
            self.assertEqual(destination(path),path)
            path.mkdir(); (path/'unrelated').write_text('preserve')
            with self.assertRaises(ValueError): destination(path)
            link = Path(temp)/'link'; link.symlink_to(ROOT/'output',target_is_directory=True)
            with self.assertRaises(ValueError): destination(link/'research')

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

    def test_cli_uses_identical_engine(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp,'index.json'); path.write_bytes(c.encoded({'schema':c.SCHEMA,'records':fixture()['records']}))
            cli = subprocess.run(['node',str(ROOT/'research/archive_workbench/query.cjs'),str(path),'--q','maritime'],text=True,capture_output=True,check=True)
            self.assertEqual([r['id'] for r in json.loads(cli.stdout)['results']],['fixture:a','fixture:b'])
            bad = subprocess.run(['node',str(ROOT/'research/archive_workbench/query.cjs'),str(path),'--from','2026-02-30'],text=True,capture_output=True)
            self.assertEqual(bad.returncode,2)

    def test_snippets_are_only_from_indexed_fields(self):
        d = dict(fixture()['records'][3],secret_body='Secret needle')
        result = node("console.log(JSON.stringify(E.snippet(input,'needle')));",d)
        self.assertEqual(result,'')


class CurrentPublicBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.manifest = c.build_corpus()

    def test_manifest_matches_projection_without_private_rows(self):
        self.assertEqual(self.manifest['included'],len(self.data['records']))
        self.assertEqual(self.manifest['records_sha256'],c.digest(c.encoded(self.data['records'])))
        for r in self.data['records']:
            self.assertEqual(set(r),set(c.FIELDS))
            if r['record_type'] in ('archive_record','official_link'):
                self.assertIsNone(r['text']);self.assertIsNone(r['summary'])
            if r['record_type']=='archive_record':self.assertIsNone(r['source_url'])
        self.assertEqual(sum(self.manifest['included_by_type'].values()),self.manifest['included'])

    def test_real_public_loader_editorial_hold_survives_search_and_export(self):
        r = next(r for r in self.data['records'] if r['id']=='official:korea-policy:156785161')
        for field in ('processing','citation'):
            self.assertIn('unresolved excavation-year discrepancy',r[field])
        exported = node("console.log(JSON.stringify(E.selected(input,[input[0].id])));",[r])
        self.assertEqual(exported,[r])

    def test_issuer_names_and_historical_authors_not_internal_keys(self):
        by_id = {r['id']:r for r in self.data['records']}
        self.assertEqual(by_id['analysis:2026-05-09']['date'],'2026-05-10')
        self.assertEqual(by_id['analysis:2026-05-09']['issuer'],'Benjamin Yang')
        self.assertIsNone(by_id['analysis:2026-05-23']['date'])
        for r in self.data['records']:
            self.assertNotIn(r['issuer'],('us_department_treasury','us_china_economic_security_review_commission','us_bureau_of_industry_and_security'))

    def test_only_registered_originals_and_reviewed_english_artifacts(self):
        from core.korea_published_originals import read_release_index
        from core.korea_english_publication import public_registry
        ids = {r['id'] for r in self.data['records']}
        originals = read_release_index()
        for r in originals:self.assertIn('original:'+r['source_identity'],ids)
        for release,review,r in public_registry():
            self.assertIn('reviewed_translation:'+r['source_identity'],ids)
            self.assertIn('reviewed_analysis:'+r['source_identity'],ids)
        self.assertEqual(sum(r['record_type']=='preserved_original' for r in self.data['records']),len(originals))

    def test_core_text_and_focus_colors_pass_ordinary_text_contrast(self):
        def luminance(value):
            rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
            linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
        for foreground,background in (('#1D2D31','#F3F2EC'),('#405456','#F3F2EC'),
            ('#176C6C','#F3F2EC'),('#23665B','#F3F2EC'),('#446C79','#F3F2EC'),
            ('#FAFBF7','#176C6C'),('#92D5CC','#142E38')):
            a,b=sorted((luminance(foreground),luminance(background)))
            self.assertGreaterEqual((b+.05)/(a+.05),4.5,(foreground,background))
