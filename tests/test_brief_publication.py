"""Publication commands and private review, using disposable sources only."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from core import brief_contract as contract
from core import brief_collection as collection
from core.desk_registry import load_registry
from scripts import author_brief
from scripts import validate_output

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'briefs/maritime-cooperation-2026.json'


class PublicationChecks(unittest.TestCase):
    def setUp(self):
        self.pending = json.loads(SOURCE.read_text())
        self.pending['title'] = 'Approval command fixture; never published'
        self.pending['author_name'] = 'Owner (test fixture)'
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.briefs = self.root / 'briefs'
        self.briefs.mkdir()
        self.posts = self.root / 'posts'
        self.posts.mkdir()
        (self.posts / 'historical.json').write_text(json.dumps({'issue_number': 14}))
        self.path = self.briefs / 'fixture.json'
        self.write(self.path, self.pending)
        self.registry = load_registry()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def run_command(self, *args):
        with mock.patch.object(author_brief, 'BRIEFS_DIR', self.briefs), \
             mock.patch.object(author_brief, 'POSTS_DIR', self.posts), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            return author_brief.main(list(args))

    def approve(self, path=None, reference='human approval (simulated test)'):
        return self.run_command('approve', str(path or self.path), '--approved-by', 'Fixture owner',
                                '--approved-on', '2026-10-04', '--approval-reference', reference)

    def test_empty_schema_valid_draft_is_not_release_ready(self):
        self.pending['opening_note'] = ''
        self.assertEqual(contract.validate_brief(self.pending, self.registry), [])
        self.assertIn('opening_note is empty', ' '.join(
            contract.validate_readiness(self.pending, self.registry)))

    def test_missing_prose_citation_and_conflicting_source_state_are_refused(self):
        self.pending['opening_note'] += ' [Records 999999]'
        self.pending['source_trail'][0]['screening'] = 'awaiting_screening'
        issues = [{'issue_number': 14}]
        errors = author_brief.readiness_problems(self.pending, issues, ROOT / 'pla_watch.db')
        self.assertIn('absent from the trail', ' '.join(errors))
        self.assertIn('conflicts with stored source state', ' '.join(errors))
        self.write(self.path, self.pending)
        before = self.path.read_bytes()
        self.assertEqual(self.approve(), 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_approval_uses_the_whole_collection_and_repeat_is_unchanged(self):
        self.assertEqual(self.approve(), 0)
        first = self.path.read_bytes()
        self.assertEqual(json.loads(first)['issue_number'], 15)
        self.assertEqual(self.approve(), 0)
        self.assertEqual(self.path.read_bytes(), first)
        self.assertEqual(self.approve(reference='different evidence'), 2)
        self.assertEqual(self.path.read_bytes(), first)
        second = self.briefs / 'second-fixture.json'
        self.write(second, self.pending)
        self.assertEqual(self.approve(second), 0)
        self.assertEqual(json.loads(second.read_text())['issue_number'], 16)
        self.assertEqual(json.loads(self.path.read_text())['issue_number'], 15)
        conflicting = copy.deepcopy(json.loads(second.read_text()))
        conflicting['issue_number'] = 15
        self.write(second, conflicting)
        self.assertEqual(self.run_command('check', str(second)), 2)

    def test_development_and_comparison_prose_citations_cannot_make_dead_links(self):
        self.pending['development']['summary'] += ' [Record 999999]'
        self.pending['cross_desk_claims'][0]['claim'] += ' [Records 999998]'
        errors = contract.validate_readiness(self.pending, self.registry)
        self.assertIn('development.summary cites a record absent', ' '.join(errors))
        self.assertIn('cross_desk_claims[0] cites a record absent', ' '.join(errors))

    def test_approval_never_writes_outside_canonical_sources(self):
        elsewhere = self.root / 'elsewhere.json'
        self.write(elsewhere, self.pending)
        before = elsewhere.read_bytes()
        self.assertEqual(self.approve(elsewhere), 2)
        self.assertEqual(elsewhere.read_bytes(), before)

    def test_feed_uses_coverage_chronology_even_after_retrospective_approval(self):
        entries = [dict(slug='older', date='2026-08-15', issue=16, approved_on='2026-10-04',
                        url='briefs/older.html', title='Older fixture', author_name='Fixture', dek=''),
                   dict(slug='newer', date='2026-09-19', issue=15, approved_on='2026-10-03',
                        url='briefs/newer.html', title='Newer fixture', author_name='Fixture', dek='')]
        feed = collection.build_briefs_feed(entries, origin='https://fixture.test')
        self.assertLess(feed.index('<title>Newer fixture'), feed.index('<title>Older fixture'))
        self.assertIn('<updated>2026-10-04T00:00:00Z</updated>', feed)

    def test_citation_markup_escapes_prose_and_exposes_only_numeric_links(self):
        prose = collection.linked_prose('<script>x</script> [Records 4164, 4466]')
        self.assertNotIn('<script>', prose)
        self.assertIn('&lt;script&gt;', prose)
        self.assertIn('href="#r-4164"', prose)
        self.assertIn('href="#r-4466"', prose)

    def test_deploy_gate_refuses_draft_routes_and_feed(self):
        out = self.root / 'output'
        (out / 'briefs').mkdir(parents=True)
        (out / 'briefs/fixture.html').write_text('Unapproved draft')
        (out / 'briefs/feed.xml').write_text('Unapproved feed')
        errors = []
        with mock.patch.object(validate_output, 'REPO_ROOT', self.root):
            validate_output._validate_briefs(out, errors)
        self.assertIn('no approved source', ' '.join(errors))
        self.assertIn('without approved Briefs', ' '.join(errors))

    def test_private_review_cannot_target_production_or_use_legacy(self):
        spec = importlib.util.spec_from_file_location('review_renderer', ROOT / 'site/render.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        for mode in ('legacy', 'indo-pacific-record'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                renderer.render_site(mode, renderer.OUTPUT_DIR, review_brief=SOURCE)

    def test_deploy_gate_requires_approved_page_home_catalog_feed_and_sitemap(self):
        self.assertEqual(self.approve(), 0)
        sc = json.loads(self.path.read_text())
        out = self.root / 'output'
        (out / 'briefs').mkdir(parents=True)
        (out / 'the-pla-watch/posts').mkdir(parents=True)
        self.write(out / 'the-pla-watch/posts/2026-08-15.json', {'issue_number': 14})
        route = 'briefs/fixture.html'
        url = 'https://fixture.test/' + route
        (out / route).write_text('<link rel="canonical" href="%s"><h1>%s</h1>No. 15' % (url, sc['title']))
        for page in ('index.html', 'analysis.html'):
            (out / page).write_text('<a href="%s">Brief</a>' % route)
        (out / 'sitemap.xml').write_text('<urlset><url><loc>%s</loc></url></urlset>' % url)
        entry = collection.brief_entry('fixture', sc)
        (out / 'briefs/feed.xml').write_text(collection.build_briefs_feed([entry], origin='https://fixture.test'))
        with mock.patch.object(validate_output, 'REPO_ROOT', self.root):
            errors = []
            validate_output._validate_briefs(out, errors)
            self.assertEqual(errors, [])
            (out / 'index.html').write_text('Missing the newest Brief')
            (out / route).write_text('<meta name="robots" content="noindex">Wrong title/number')
            (out / 'briefs/feed.xml').unlink()
            errors = []
            validate_output._validate_briefs(out, errors)
        for message in ('homepage', 'title/number', 'indexable', 'feed.xml'):
            self.assertIn(message, ' '.join(errors))

    def test_private_builder_has_no_public_artifacts_or_invented_approval(self):
        import sys
        sys.path.insert(0, str(ROOT / 'site/preview'))
        import generate_preview as gp
        out = self.root / 'private-review'
        before = self.path.read_bytes()
        gp.build(out, gp.PUBLIC_TITLE, ROOT / 'pla_watch.db',
                 snapshot=gp.snapshot_from_corpus(ROOT / 'pla_watch.db'),
                 briefs_dir=self.briefs, review_brief=self.path)
        article = (out / 'briefs/fixture.html').read_text()
        self.assertIn('unapproved, unnumbered and unpublished', article)
        self.assertIn('noindex', article)
        self.assertNotIn('rel="canonical"', article)
        self.assertNotIn('Approved ', article)
        self.assertIn(sc_title := self.pending['title'], (out / 'analysis.html').read_text())
        self.assertIn(sc_title, (out / 'index.html').read_text())
        self.assertFalse((out / 'sitemap.xml').exists())
        self.assertFalse((out / 'briefs/feed.xml').exists())
        self.assertEqual(self.path.read_bytes(), before)

    def test_ordinary_public_build_preserves_approved_source_and_all_surfaces(self):
        import sys
        sys.path.insert(0, str(ROOT / 'site/preview'))
        import generate_preview as gp
        self.assertEqual(self.approve(), 0)
        before = self.path.read_bytes()
        routes = ('briefs/fixture.html', 'analysis.html', 'index.html',
                  'briefs/feed.xml', 'sitemap.xml')
        outputs = [self.root / name for name in ('first-public', 'ordinary-repeat')]
        for out in outputs:
            gp.build(out, gp.PUBLIC_TITLE, ROOT / 'pla_watch.db',
                     snapshot=gp.snapshot_from_corpus(ROOT / 'pla_watch.db'),
                     briefs_dir=self.briefs, site_origin='https://fixture.test',
                     allow_test_origin=True)
            article = (out / routes[0]).read_text()
            self.assertIn(self.pending['title'], article)
            self.assertIn('No. 15', article)
            self.assertIn('rel="canonical"', article)
            self.assertNotIn('content="noindex', article)
            for route in routes[1:]:
                self.assertIn('briefs/fixture.html', (out / route).read_text())
        for route in routes:
            self.assertEqual((outputs[0] / route).read_bytes(),
                             (outputs[1] / route).read_bytes())
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
