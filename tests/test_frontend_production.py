"""Reviewed October frontend: dependency gates and governed relationships."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

from core.frontend_budget import measure_page
from core import brief_collection
from scripts import validate_output

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp


class DependencyBudget(unittest.TestCase):
    def test_all_stylesheets_nested_imports_and_scripts_are_counted_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {'index.html': '<link rel="stylesheet" href="base.css?v=1"><link rel="stylesheet" href="override.css"><style>@import "base.css";</style><script src="main.js"></script><script>import("extra.js")</script>',
                     'base.css': '@import url("nested.css"); body{color:black}',
                     'nested.css': '@import "base.css";h1{color:black}',
                     'override.css': 'h1{font-size:50px}',
                     'main.js': 'import "extra.js";', 'extra.js': 'export const value=1;'}
            for name, contents in files.items(): (root / name).write_text(contents)
            actual = measure_page(root / 'index.html', root)
            self.assertEqual(actual['html_css_bytes'], sum(len(files[n]) for n in ('index.html', 'base.css', 'nested.css', 'override.css')))
            self.assertEqual(actual['js_bytes'], len(files['main.js']) + len(files['extra.js']) + len('import("extra.js")'))
            self.assertEqual(actual['external'], [])

    def test_missing_dependency_and_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for url in ('missing.css', '../outside.css'):
                (root / 'index.html').write_text('<link rel="stylesheet" href="' + url + '">')
                with self.assertRaises(ValueError): measure_page(root / 'index.html', root)

    def test_external_dependencies_remain_visible_to_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('<link rel="stylesheet" href="https://fixture.test/fonts.css">')
            self.assertEqual(measure_page(root / 'index.html', root)['external'], ['https://fixture.test/fonts.css'])


class NativeRelations(unittest.TestCase):
    def test_exact_urls_native_anchors_and_review_draft_exclusion(self):
        brief = dict(slug='approved-fixture', issue=15, date='2026-09-19', title='Fixture',
                     url='briefs/approved-fixture.html', series_name='IPR Briefs', publication='IPR')
        review = dict(brief, slug='review-fixture', is_review=True)
        collection = SimpleNamespace(briefs=[brief, review], sidecars={
            'approved-fixture': {'source_trail': [{'url': 'https://fixture.test/exact', 'record_id': 42}]},
            'review-fixture': {'source_trail': [{'url': 'https://fixture.test/private', 'record_id': 43}]}})
        with tempfile.TemporaryDirectory() as directory:
            by_url, _ = gp.trail_citations(Path(directory), [], collection)
        self.assertEqual(set(by_url), {'https://fixture.test/exact'})
        self.assertEqual(by_url['https://fixture.test/exact'][0]['anchor'], 'r-42')
        self.assertNotIn('https://fixture.test/exact/', by_url)

    def test_machine_unscreened_state_does_not_deny_human_brief_judgment(self):
        note = gp.CITATION_PROCESSING_NOTES['awaiting_screening']
        self.assertIn('machine', note)
        self.assertNotIn('of any kind', note)


class AssetExchange(unittest.TestCase):
    def test_fresh_assets_win_and_historical_assets_survive_without_nesting(self):
        spec = importlib.util.spec_from_file_location('frontend_renderer', ROOT / 'site/render.py')
        render = importlib.util.module_from_spec(spec); spec.loader.exec_module(render)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); stage = root / 'stage'; target = root / 'out'
            for tree in (stage, target): (tree / 'assets').mkdir(parents=True)
            (stage / 'assets/current.woff2').write_bytes(b'new')
            (target / 'assets/current.woff2').write_bytes(b'old')
            (target / 'assets/historical.jpg').write_bytes(b'evidence')
            render.publish(stage, target, None)
            self.assertEqual((target / 'assets/current.woff2').read_bytes(), b'new')
            self.assertEqual((target / 'assets/historical.jpg').read_bytes(), b'evidence')
            self.assertFalse((target / 'assets/assets').exists())


class PhotoDelivery(unittest.TestCase):
    def test_delivered_variant_digest_and_source_are_bound_to_approved_photo(self):
        sidecar = json.loads((ROOT / 'briefs/maritime-cooperation-2026.json').read_text())
        photo = brief_collection.brief_photo('maritime-cooperation-2026', sidecar, ROOT / 'briefs/media')
        self.assertEqual(len(photo['variants']), 2)
        self.assertNotIn('duotone', photo['alt'])
        original_read = Path.read_bytes
        victim = photo['variants'][0]['file']
        def tampered(path):
            return b'tampered' if path == victim else original_read(path)
        with mock.patch.object(Path, 'read_bytes', tampered):
            corrupt = brief_collection.brief_photo('maritime-cooperation-2026', sidecar, ROOT / 'briefs/media')
        self.assertEqual(len(corrupt['variants']), 1)
        self.assertNotIn(victim.name, corrupt['srcset'])
