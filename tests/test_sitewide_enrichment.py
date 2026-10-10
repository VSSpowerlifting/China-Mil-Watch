"""Publication parity must reject meaning changes and cover every route family."""
from pathlib import Path
from html.parser import HTMLParser
import tempfile
import unittest

from scripts.verify_enrichment_frontend import compare_publication, read_body, representative_routes,historical_routes


class PublicationParity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / 'baseline'; self.baseline.mkdir()
        self.candidate = self.root / 'candidate'; self.candidate.mkdir()
        self.source = '<html><head></head><body><main id="main"><h1>Published title</h1><p>Source text.</p><a href="record/42.html#source">Original record</a></main></body></html>'

    def put(self, root, route, contents):
        path = root / route; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(contents)

    def test_decorative_subtrees_and_script_changes_preserve_contract(self):
        self.put(self.baseline,'index.html',self.source)
        art = '<div aria-hidden="true"><span id="decorative">Not publication</span><a href="art.svg">Shape</a></div><script>window.newMotion=true</script><style>body{color:black}</style>'
        self.put(self.candidate,'index.html',self.source.replace('<main',art+'<main'))
        result = compare_publication(self.candidate,self.baseline,require_enrichment=False)
        self.assertEqual(result['failures'],[])
        self.assertEqual(read_body(self.candidate/'index.html').contract(),read_body(self.baseline/'index.html').contract())

    def test_text_links_and_anchor_tampering_are_reported_independently(self):
        self.put(self.baseline,'index.html',self.source)
        for old,new,field in [('Source text.','Altered claim.','text'),('record/42.html#source','record/99.html','links'),('id="main"','id="missing"','ids')]:
            with self.subTest(field=field):
                self.put(self.candidate,'index.html',self.source.replace(old,new))
                result=compare_publication(self.candidate,self.baseline,require_enrichment=False)
                self.assertIn(field,result['failures'][0]['changed'])

    def test_missing_routes_redirect_changes_and_exposed_timeline_fail(self):
        redirect='<html><head><meta http-equiv="refresh" content="0; url=../record/42.html"></head><body><a href="../record/42.html">Record</a></body></html>'
        self.put(self.baseline,'article/42.html',redirect)
        self.put(self.baseline,'about.html',self.source)
        self.put(self.candidate,'article/42.html',redirect.replace('url=../record/42.html','url=../record/99.html'))
        self.put(self.candidate,'timeline/draft.html',self.source)
        result=compare_publication(self.candidate,self.baseline,require_enrichment=False)
        self.assertTrue(any(item.get('missing_routes') == ['about.html'] for item in result['failures']))
        self.assertTrue(any(item.get('changed') == ['redirect'] for item in result['failures']))
        self.assertTrue(any(item.get('changed') == ['unpublished timeline exposed'] for item in result['failures']))

    def test_script_free_weeks_and_shared_delivery_are_checked(self):
        self.put(self.baseline,'week-2026-10-05.html',self.source)
        self.put(self.candidate,'week-2026-10-05.html',self.source.replace('</body>','<script src="optional.js"></script></body>'))
        result=compare_publication(self.candidate,self.baseline)
        changed=[item['changed'] for item in result['failures']]
        self.assertIn(['script-free week'],changed)
        self.assertIn(['missing enrichment stylesheet'],changed)

    def test_historical_routes_require_their_bounded_stylesheet(self):
        for route,required in [('the-pla-watch/posts/fixture.html','enrichment.css'),('the-pla-watch/index.html','historical-enrichment.css'),('the-pla-watch/archive.html','historical-enrichment.css'),('the-pla-watch/terms.html','historical-enrichment.css')]:
            self.put(self.baseline,route,self.source)
            for sheet in ('historical-enrichment.css','enrichment.css'):
                with self.subTest(route=route,sheet=sheet):
                    linked=self.source.replace('</head>','<link rel="stylesheet" href="../../'+sheet+'"></head>')
                    self.put(self.candidate,route,linked)
                    result=compare_publication(self.candidate,self.baseline)
                    self.assertEqual(not result['failures'],sheet==required)
            self.put(self.candidate,route,self.source.replace('</head>','<link rel="stylesheet" href="../../'+required+'"></head>'))


class RepresentativeCoverage(unittest.TestCase):
    def test_historical_replacement_discovers_every_post_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            routes=['the-pla-watch/posts/fixture-'+str(n)+'.html' for n in range(14)]
            routes+=['the-pla-watch/'+name+'.html' for name in ('index','archive','terms')]
            for route in routes:
                path=root/route;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('<h1>Fixture</h1>')
            selected=historical_routes(root)
            self.assertEqual(set(selected.values()),set(routes))
            self.assertEqual(len(selected),17)
            self.assertIn('historical-largest',selected)
    def test_discovers_real_briefs_historical_sources_and_largest_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            routes=['index.html','archive.html','analysis.html','desks.html','about.html','corpus.html','china.html','us-indopacific.html','vietnam.html','source/pla_daily.html','source/jp_mod_news_ja.html','briefs/real-slug.html','record/42.html','record/99.html','week-2026-10-05.html','week-2026-10-05-2.html','the-pla-watch/index.html','the-pla-watch/archive.html','the-pla-watch/terms.html','the-pla-watch/posts/2026-05-09.html','article/42.html','signals.html']
            for route in routes:
                path=root/route;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('<body><h1>Stored title</h1></body>')
            (root/'record/99.html').write_text('<body><h1 lang="en">Stored original fixture</h1>'+'x'*200+'</body>')
            actual=representative_routes(root)
            for label in ('home','archive','catalog','desks-map','about','corpus','desk-china','desk-held','desk-research','source-live','source-shadow','brief-real-slug','record-paired','record-largest','record-original-only','week','week-pagination','historical-oldest','historical-index','historical-archive','historical-terms','redirect-article','redirect-signals'):
                self.assertIn(label,actual)
            self.assertEqual(actual['record-largest'],'record/99.html')
            self.assertEqual(actual['record-original-only'],'record/99.html')
            self.assertTrue(all((root/route).is_file() for route in actual.values()))


class SharedShellRendering(unittest.TestCase):
    def test_actual_base_preserves_private_timeline_shell_and_script_free_weeks(self):
        from jinja2 import Environment, FileSystemLoader
        templates=Path(__file__).resolve().parents[1]/'site/preview/templates'
        environment=Environment(loader=FileSystemLoader(str(templates)),autoescape=True)
        environment.filters.update(count=lambda value:value,reader_date=lambda value:value)
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__();self.sources=[]
            def handle_starttag(self,tag,attrs):
                if tag=='script':
                    self.sources.append(dict(attrs).get('src',''))
        context=dict(title='Fixture publication',tagline='Fixture',mode='test',
                     desks=[],timelines=[],maintainer={'name':'Fixture','email':'fixture@example.invalid'},
                     collection_name='Fixture collection',live_base='https://example.invalid')
        cases=[('analysis.html',{},0),('analysis.html',{'timeline_surface':True},1),
               ('analysis.html',{'brief':{'route':'briefs/fixture.html'}},1),
               ('week-fixture.html',{'week':{'path':'week-fixture.html'}},0),
               ('index.html',{},1),('about.html',{},1)]
        for page,extra,expected in cases:
            with self.subTest(page=page,context=extra):
                rendered=environment.get_template('base.html').render(**context,page=page,**extra)
                scripts=Scripts();scripts.feed(rendered)
                self.assertEqual(sum(src.endswith('shell.js') for src in scripts.sources),expected)
                if 'week' in extra:
                    self.assertEqual(scripts.sources,[])


if __name__ == '__main__':
    unittest.main()
