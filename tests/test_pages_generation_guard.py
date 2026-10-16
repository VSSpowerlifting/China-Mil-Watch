"""Offline integration tests for the opt-in generation guard; never access GitHub."""
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.pages_generation_guard import Hold, MANIFEST, digest, prepare


def run(cwd, *args):
    p = subprocess.run(['git', '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                        *args], cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(f"git {args[0]} failed: {p.stderr}")
    return p.stdout.strip()

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.remote = self.root / 'origin.git'
        run(self.root, 'init', '--bare', '-b', 'main', str(self.remote))
        self.main = self.root / 'main'
        run(self.root, 'clone', str(self.remote), str(self.main))
        run(self.main, 'checkout', '-b', 'main')
        self.write('index.html', b'<h1>one</h1>')
        self.write('korea.html', b'Korea one')
        self.write('CNAME', b'not allowed', local_only=True)
        run(self.main, 'add', 'output')
        run(self.main, 'commit', '-m', 'initial')
        run(self.main, 'push', '-u', 'origin', 'main')
        self.pages = self.root / 'pages-seed'
        run(self.root, 'clone', '--no-checkout', str(self.remote), str(self.pages))
        run(self.pages, 'checkout', '--orphan', 'gh-pages')
        run(self.pages, 'rm', '-rf', '--cached', '.')
        shutil.rmtree(self.pages / 'output', ignore_errors=True)
        for name in ('index.html', 'korea.html'):
            (self.pages / name).write_bytes((self.main / 'output' / name).read_bytes())
        (self.pages / 'CNAME').write_text('indopacificrecord.org\n')
        run(self.pages, 'add', '-A')
        run(self.pages, 'commit', '-m', 'bootstrap pages')
        run(self.pages, 'push', 'origin', 'gh-pages')

    def write(self, name, content, local_only=False):
        f = self.main / 'output' / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
        if local_only:
            f.unlink()

    def update_main(self, name, content):
        self.write(name, content)
        run(self.main, 'add', 'output')
        run(self.main, 'commit', '-m', f'Update {name}')
        run(self.main, 'push', 'origin', 'main')

    def view(self):
        run(self.pages, 'fetch', 'origin', 'gh-pages')
        return run(self.pages, 'show-ref', '--hash', 'refs/remotes/origin/gh-pages')

    def page_bytes(self, name):
        p = subprocess.run(['git', 'show', 'origin/gh-pages:' + name], cwd=self.pages, capture_output=True)
        return p.stdout if p.returncode == 0 else None

    def publish(self, **kwargs):
        kwargs.setdefault('writer', 'unit-test')
        kwargs.setdefault('mode', 'full-tree')
        kwargs.setdefault('push', True)
        return prepare(self.main, **kwargs)

    def boot(self):
        return self.publish(bootstrap=True)

    def test_bootstrap_is_manifest_in_same_commit_and_preserves_dns(self):
        before = self.view()
        self.assertIsNone(self.page_bytes(MANIFEST))
        report = self.boot()
        self.assertTrue(report['published'])
        self.assertEqual(report['generation'], 1)
        self.assertNotEqual(before, self.view())
        self.assertEqual(self.page_bytes('CNAME'), b'indopacificrecord.org\n')
        doc = json.loads(self.page_bytes(MANIFEST))
        self.assertEqual(doc['generation'], 1)
        self.assertEqual(doc['source_sha'], run(self.main, 'rev-parse', 'HEAD'))
        self.assertEqual(doc['tree_sha256'], digest({'CNAME': b'indopacificrecord.org\n',
                                                         'index.html': b'<h1>one</h1>',
                                                         'korea.html': b'Korea one'}))

    def test_no_mutation_in_preflight(self):
        before = self.view()
        result = self.publish(bootstrap=True, push=False)
        self.assertFalse(result['published'])
        self.assertEqual(self.view(), before)

    def test_bootstrap_requires_exact_current_public_parity(self):
        self.out_of_band('rogue.html', b'unknown')
        with self.assertRaisesRegex(Hold, 'cannot bootstrap'):
            self.publish(bootstrap=True)

    def out_of_band(self, name, content):
        # Only used in disposable bare origin.
        clone = self.root / ('actor-' + str(len(list(self.root.iterdir()))))
        run(self.root, 'clone', '--branch', 'gh-pages', str(self.remote), str(clone))
        f = clone / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
        run(clone, 'add', '-A')
        run(clone, 'commit', '-m', 'unattested outsider')
        run(clone, 'push', 'origin', 'gh-pages')

    def test_unmanifested_pages_change_holds_everything(self):
        self.boot()
        self.out_of_band('rogue.html', b'unknown')
        with self.assertRaisesRegex(Hold, 'diverged'):
            self.publish(mode='file-only', paths=('korea.html',))

    def test_stale_head_refused(self):
        self.boot()
        self.update_main('korea.html', b'Korea two')
        stale = self.root / 'stale'
        run(self.root, 'clone', str(self.remote), str(stale))
        self.update_main('index.html', b'<h1>three</h1>')
        with self.assertRaisesRegex(Hold, 'not current origin/main'):
            prepare(stale, mode='file-only', writer='stale', paths=('korea.html',), push=True)
        self.view()
        self.assertEqual(json.loads(self.page_bytes(MANIFEST))['generation'], 1)

    def test_file_only_rewrites_only_its_declared_page(self):
        self.boot()
        self.update_main('korea.html', b'Korea two')
        self.update_main('index.html', b'<h1>two</h1>')
        report = self.publish(mode='file-only', paths=('korea.html',))
        self.assertEqual(report['generation'], 2)
        self.view()
        self.assertEqual(self.page_bytes('korea.html'), b'Korea two')
        self.assertEqual(self.page_bytes('index.html'), b'<h1>one</h1>')

    def test_full_tree_is_blocked_if_new_pages_only_record_would_be_lost(self):
        self.boot()
        # A separately reviewed Pages-only file-only publication can exist,
        # but only if it is itself attested; for the fixture, add it via direct
        # Pages commit with an updated manifest to mimic a cooperating writer.
        self.add_attested_pages_only('korea-originals/one.html', b'government work')
        self.update_main('index.html', b'<h1>two</h1>')
        with self.assertRaisesRegex(Hold, 'erase'):
            self.publish(mode='full-tree')
        self.view()
        self.assertEqual(self.page_bytes('korea-originals/one.html'), b'government work')

    def add_attested_pages_only(self, name, content):
        clone = self.root / 'publisher'
        run(self.root, 'clone', '--branch', 'gh-pages', str(self.remote), str(clone))
        f = clone / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
        current = json.loads((clone / MANIFEST).read_text())
        # Current source remains a valid main SHA; update digest and generation.
        current['generation'] += 1
        from scripts.pages_generation_guard import tree_files
        current['tree_sha256'] = digest(tree_files(clone))
        (clone / MANIFEST).write_text(json.dumps(current, sort_keys=True, separators=(',', ':'))+'\n')
        run(clone, 'add', '-A')
        run(clone, 'commit', '-m', 'attested pages-only evidence')
        run(clone, 'push', 'origin', 'gh-pages')

    def test_full_tree_preserve_requires_exact_allowlist(self):
        self.boot()
        self.add_attested_pages_only('korea-originals/one.html', b'preserved')
        self.update_main('index.html', b'<h1>two</h1>')
        report = self.publish(mode='full-tree', preserve=('korea-originals/one.html',))
        self.assertEqual(report['generation'], 3)
        self.view()
        self.assertEqual(self.page_bytes('korea-originals/one.html'), b'preserved')
        self.assertEqual(self.page_bytes('index.html'), b'<h1>two</h1>')

    def test_full_tree_detects_same_filename_pages_only_override(self):
        self.boot()
        self.add_attested_pages_only('korea.html', b'new Korea without main output')
        self.update_main('index.html', b'<h1>two</h1>')
        with self.assertRaisesRegex(Hold, 'overwrite a Pages-only changed file'):
            self.publish(mode='full-tree')
        self.view()
        self.assertEqual(self.page_bytes('korea.html'), b'new Korea without main output')

    def test_full_tree_respects_committed_cname(self):
        self.boot()
        self.write('CNAME', b'indopacificrecord.org\n')
        run(self.main, 'add', 'output/CNAME')
        run(self.main, 'commit', '-m', 'Commit matching CNAME')
        run(self.main, 'push', 'origin', 'main')
        self.publish()
        self.view()
        self.assertEqual(self.page_bytes('CNAME'), b'indopacificrecord.org\n')
        self.write('CNAME', b'wrong.invalid\n')
        run(self.main, 'add', 'output/CNAME')
        run(self.main, 'commit', '-m', 'Misconfigured CNAME')
        run(self.main, 'push', 'origin', 'main')
        with self.assertRaisesRegex(Hold, 'infrastructure mismatch'):
            self.publish()

    def test_file_only_refuses_conflicting_committed_cname(self):
        self.boot()
        self.write('CNAME', b'wrong.invalid\n')
        run(self.main, 'add', 'output/CNAME')
        run(self.main, 'commit', '-m', 'Misconfigured DNS while publishing desk')
        run(self.main, 'push', 'origin', 'main')
        before = self.view()
        with self.assertRaisesRegex(Hold, 'infrastructure mismatch'):
            self.publish(mode='file-only', paths=('korea.html',))
        self.assertEqual(self.view(), before)

    def test_file_only_bootstrap_refuses_conflicting_committed_cname(self):
        self.write('CNAME', b'wrong.invalid\n')
        run(self.main, 'add', 'output/CNAME')
        run(self.main, 'commit', '-m', 'Misconfigured DNS before bootstrap')
        run(self.main, 'push', 'origin', 'main')
        before = self.view()
        with self.assertRaisesRegex(Hold, 'infrastructure mismatch'):
            self.publish(mode='file-only', paths=('korea.html',), bootstrap=True)
        self.assertEqual(self.view(), before)

    def test_committed_git_metadata_filename_is_refused(self):
        from scripts.pages_generation_guard import path_ok
        self.assertFalse(path_ok('.git'))
        self.assertFalse(path_ok('.git/config'))
        self.assertFalse(path_ok('.ipr-release.json'))

    def test_pages_cas_refuses_race_after_candidate_built(self):
        self.boot()
        self.update_main('korea.html', b'Korea two')
        import scripts.pages_generation_guard as mod
        orig_git = mod.git
        raced = [False]

        def hooked_git(cwd, *args, **kwargs):
            if not raced[0] and len(args) >= 4 and args[:4] == ('fetch', '-q', 'origin', 'gh-pages') and cwd.name == 'pages':
                raced[0] = True
                self.out_of_band('other.html', b'extra')
            return orig_git(cwd, *args, **kwargs)

        with patch.object(mod, 'git', side_effect=hooked_git):
            with self.assertRaisesRegex(Hold, 'Pages changed during candidate'):
                self.publish(mode='file-only', paths=('korea.html',))
        self.assertTrue(raced[0])
        self.view()
        self.assertEqual(self.page_bytes('korea.html'), b'Korea one')

    def test_rollback_flag_not_implemented(self):
        self.boot()
        with self.assertRaisesRegex(Hold, 'rollback publication is not implemented'):
            self.publish(rollback={'expected_current': '0'*40, 'target': '1'*40})

    def test_refuse_undeclared_file_only(self):
        self.boot()
        with self.assertRaisesRegex(Hold, 'absent'):
            self.publish(mode='file-only', paths=('unknown.html',))

    def test_invalid_path_holds(self):
        self.boot()
        for name in ('../shadow', '/root', '.ipr-release.json', 'a//b'):
            with self.subTest(name=name):
                with self.assertRaises(Hold):
                    self.publish(mode='file-only', paths=(name,))

    def test_normal_rollback_needs_explicit_receipt(self):
        self.boot()
        self.update_main('index.html', b'<h1>two</h1>')
        self.publish()
        # Re-point main to the old commit as a real new commit (revert), which
        # is monotonic; a raw old source cannot be current main and is held.
        run(self.main, 'checkout', 'HEAD~1', '--', 'output/index.html')
        run(self.main, 'commit', '-am', 'Revert main site')
        run(self.main, 'push', 'origin', 'main')
        self.publish()
        self.view()
        self.assertEqual(self.page_bytes('index.html'), b'<h1>one</h1>')
        self.assertEqual(json.loads(self.page_bytes(MANIFEST))['generation'], 3)

if __name__ == '__main__':
    unittest.main()
