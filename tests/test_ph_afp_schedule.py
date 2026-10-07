"""Exercise the AFP workflow's actual shell and collector modes, offline."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import check_ph_afp_state as checker, shadow_collect_ph as runner
from tests import ph_afp_support as S
from tests.test_ph_afp_readiness import CapturedSession

WORKFLOW = S.REPO_ROOT / '.github/workflows/ph_afp_shadow.yml'


class BeforeCron(datetime):
    @classmethod
    def now(cls, tz=None):
        # A delayed slot crosses UTC midnight but belongs to September 26.
        return cls(2026, 9, 27, 2, 0, tzinfo=timezone.utc)


class TestScheduledWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.text = WORKFLOW.read_text()
        self.remote = self.root / 'remote.git'
        self.collector = self.root / 'workspace/repo'
        self.collector.mkdir(parents=True)
        self.git('init', '--bare', self.remote)
        self.git('init', self.collector)
        (self.collector / 'proof.txt').write_text('offline collector fixture\n')
        self.git('-C', self.collector, 'add', 'proof.txt')
        self.git('-C', self.collector, '-c', 'user.name=Fixture', '-c',
                 'user.email=fixture@example.test', 'commit', '-m', 'fixture')
        self.commit = self.git('-C', self.collector, 'rev-parse', 'HEAD')
        self.state = self.root / 'shadow-state/state'
        self.env = dict(os.environ, RUNNER_TEMP=str(self.root),
                        GITHUB_WORKSPACE=str(self.root / 'workspace'),
                        GITHUB_RUN_ID='fixture', GITHUB_RUN_ATTEMPT='1',
                        STATE_REMOTE=str(self.remote))

    def git(self, *args):
        return subprocess.check_output(['git', *map(str, args)], text=True,
                                       stderr=subprocess.STDOUT).strip()

    def section(self, name):
        return self.text.split('      - name: ' + name + '\n', 1)[1].split(
            '\n      - name:', 1)[0]

    def block(self, name):
        return textwrap.dedent(self.section(name).split('        run: |\n', 1)[1])

    def shell(self, name, env=None):
        return subprocess.run(['bash', '-c', self.block(name)], cwd=self.collector,
                              env=env or self.env, capture_output=True, text=True)

    def expression(self, expression, event, publish=False, outcome='success', success=True):
        # Evaluate the literal workflow guard, not a separately copied policy.
        expression = expression.replace('success()', str(success)).replace(
            'steps.collect.outcome', repr(outcome)).replace(
            'github.event_name', repr(event)).replace('inputs.publish_state', str(publish))
        return eval(expression.replace('&&', ' and ').replace('||', ' or '),
                    {'__builtins__': {}}, {})

    def bootstrap(self, event, publish=False):
        expression = re.search(r'PUBLISH_STATE: \$\{\{ (.+) \}\}', self.text).group(1)
        selected = self.expression(expression, event, publish)
        self.env['PUBLISH_STATE'] = str(selected).lower()
        result = self.shell('Check out isolated shadow state')
        self.assertEqual(result.returncode, 0, result.stderr)
        return selected

    def invoke(self, event, sess=None, run_id='fixture', clock=BeforeCron):
        # Record argv from the exact YAML shell; run those args through the real
        # CLI with original-payload fixtures, never a network fallback.
        bin_dir = self.root / 'bin'
        bin_dir.mkdir(exist_ok=True)
        recorder = bin_dir / 'python'
        recorder.write_text('#!' + sys.executable + '\nimport json,os,sys\n'
                            'open(os.environ["AFP_ARGS"],"w").write(json.dumps(sys.argv[2:]))\n'
                            'sys.exit(int(os.environ.get("AFP_EXIT", "0")))\n')
        recorder.chmod(0o755)
        self.env.update(PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        AFP_ARGS=str(self.root / 'argv.json'), GITHUB_EVENT_NAME=event,
                        GITHUB_RUN_ID=run_id, GITHUB_RUN_ATTEMPT='1',
                        TARGET_DATE='2026-09-26' if event == 'workflow_dispatch' else '')
        result = self.shell('Run shadow collection or bounded rehearsal')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / 'argv.json').read_text())
        before = checker.snapshot(self.state)
        adapter = S.adapter(sess or S.session_for(details_ids=(1384, 1378, 1365)), cap=100)
        with mock.patch.object(runner, 'PHAfpAdapter', return_value=adapter), \
                mock.patch.object(runner, 'datetime', clock), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = runner.main(args)
        entry = checker.verify(self.state, before, run_id + '-1', self.commit)
        return args, rc, entry

    def publish_allowed(self, event, publish=False, outcome='success', success=True):
        condition = re.search(r'^        if: (.+)$',
                              self.section('Preserve completed shadow attempt'), re.M).group(1)
        return self.expression(condition, event, publish, outcome, success)

    def test_schedule_collects_full_window_with_cron_date_and_publishes_only_state(self):
        self.assertTrue(self.bootstrap('schedule'))
        args, rc, entry = self.invoke('schedule')
        self.assertEqual(rc, 0)
        self.assertIn('--cron-utc', args)
        self.assertEqual(args[args.index('--cron-utc') + 1], '06:40')
        self.assertNotIn('--rehearsal', args)
        self.assertEqual(entry['target_date'], '2026-09-26')
        self.assertEqual(entry['target_date_source'], 'schedule-slot')
        self.assertEqual((entry['lookback_days'], entry['cap']), (14, 100))
        self.assertEqual((entry['selected'], entry['retrieved']), (2, 2))
        self.assertFalse(entry['rehearsal'])
        self.assertTrue((self.state / 'clock.json').exists())
        self.assertTrue(self.publish_allowed('schedule'))
        result = self.shell('Preserve completed shadow attempt')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('--git-dir', self.remote, 'for-each-ref',
                                  '--format=%(refname)', 'refs/heads'), 'refs/heads/shadow/ph-afp')
        self.assertEqual(self.git('--git-dir', self.remote, 'ls-tree', '--name-only',
                                  'shadow/ph-afp'), 'state')
        self.assertEqual(self.git('-C', self.collector, 'status', '--porcelain'), '')

    def test_manual_default_is_two_samples_without_state_publication_or_clock(self):
        self.assertFalse(self.bootstrap('workflow_dispatch'))
        self.assertFalse((self.state.parent / '.git').exists())
        args, rc, entry = self.invoke('workflow_dispatch')
        self.assertEqual(rc, 0)
        self.assertIn('--rehearsal', args)
        self.assertNotIn('--cron-utc', args)
        self.assertEqual((entry['selected'], entry['retrieved'], entry['sample_unselected']), (2, 2, 0))
        self.assertIsNone(entry['shadow_day'])
        self.assertFalse((self.state / 'clock.json').exists())
        self.assertFalse(self.publish_allowed('workflow_dispatch'))
        self.assertEqual(self.git('--git-dir', self.remote, 'for-each-ref',
                                  '--format=%(refname)', 'refs/heads'), '')

    def test_explicit_manual_publication_stays_rehearsal_and_isolated(self):
        self.assertTrue(self.bootstrap('workflow_dispatch', publish=True))
        _, rc, entry = self.invoke('workflow_dispatch')
        self.assertEqual(rc, 0)
        self.assertTrue(entry['rehearsal'])
        self.assertFalse((self.state / 'clock.json').exists())
        self.assertTrue(self.publish_allowed('workflow_dispatch', publish=True))
        result = self.shell('Preserve completed shadow attempt')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('--git-dir', self.remote, 'for-each-ref',
                                  '--format=%(refname)', 'refs/heads'), 'refs/heads/shadow/ph-afp')

    def test_partial_schedule_is_nonzero_has_no_clock_and_cannot_publish(self):
        self.bootstrap('schedule')
        sess = S.session_for(details_ids=(1384, 1378, 1365))
        sess.details[S.detail_obj(1378)['slug']] = S.FakeResponse('unavailable', 500)
        _, rc, entry = self.invoke('schedule', sess)
        self.assertNotEqual(rc, 0)
        self.assertEqual(entry['health'], 'partial')
        self.assertIsNone(entry['shadow_day'])
        self.assertFalse((self.state / 'clock.json').exists())
        self.assertFalse(self.publish_allowed('schedule', outcome='failure'))
        self.assertEqual(self.git('--git-dir', self.remote, 'for-each-ref',
                                  '--format=%(refname)', 'refs/heads'), '')
        self.assertTrue((self.state / entry['request_evidence']['path']).exists())

    def test_schedule_selects_whole_recent_window_and_preserves_failure_guard(self):
        class OctoberSlot(BeforeCron):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 7, 2, 0, tzinfo=timezone.utc)
        self.bootstrap('schedule')
        sess = CapturedSession()
        original = sess.get
        def get(url, **kwargs):
            if url not in sess.routes:
                sess.calls.append(url)
                return S.FakeResponse('unavailable', 404, url=url, headers={
                    'Content-Type': 'text/plain', 'X-Robots-Tag': 'noindex, nofollow'})
            return original(url, **kwargs)
        sess.get = get
        _, rc, entry = self.invoke('schedule', sess, clock=OctoberSlot)
        self.assertEqual(entry['target_date'], '2026-10-06')
        self.assertEqual((entry['discovered'], entry['selected'], entry['retrieved']), (11, 11, 2))
        self.assertEqual(entry['sample_unselected'], 0)
        self.assertEqual(entry['health'], 'fail')
        self.assertEqual(entry['aborted'], 'consecutive_failures')
        self.assertEqual(entry['fetch_failures'], runner.MAX_CONSECUTIVE_FAILURES)
        self.assertNotEqual(rc, 0)
        self.assertFalse((self.state / 'clock.json').exists())
        self.assertFalse(self.publish_allowed('schedule', outcome='failure'))
        self.assertEqual(len([url for url in sess.calls if '/articles/' in url
                              and '?' not in url]), 2 + runner.MAX_CONSECUTIVE_FAILURES)

    def test_failed_schedule_keeps_existing_clock_and_durable_head(self):
        self.bootstrap('schedule')
        self.invoke('schedule')
        self.assertEqual(self.shell('Preserve completed shadow attempt').returncode, 0)
        head = self.git('--git-dir', self.remote, 'rev-parse', 'shadow/ph-afp')
        clock = (self.state / 'clock.json').read_bytes()
        _, rc, entry = self.invoke('schedule', S.FakeSession(), run_id='next')
        self.assertNotEqual(rc, 0)
        self.assertEqual(entry['health'], 'fail')
        self.assertIsNone(entry['shadow_day'])
        self.assertEqual((self.state / 'clock.json').read_bytes(), clock)
        self.assertFalse(self.publish_allowed('schedule', outcome='failure'))
        self.assertEqual(self.git('--git-dir', self.remote, 'rev-parse', 'shadow/ph-afp'), head)

    def test_failed_manual_or_verification_never_publishes_and_artifacts_are_unconditional(self):
        for event in ('schedule', 'workflow_dispatch'):
            for publish in (False, True):
                self.assertFalse(self.publish_allowed(event, publish, outcome='failure'))
                self.assertFalse(self.publish_allowed(event, publish, success=False))
        self.assertIn('        if: always()', self.section('Preserve run evidence'))
        self.assertIn("steps.collect.outcome == 'failure'", self.section(
            'Report incomplete collection after preserving evidence'))
        self.env.update(GITHUB_EVENT_NAME='schedule', AFP_EXIT='0')
        # tee must not swallow a collector failure: run the actual pipeline.
        self.invoke('schedule')
        self.env['AFP_EXIT'] = '1'
        self.assertNotEqual(self.shell('Run shadow collection or bounded rehearsal').returncode, 0)

    def test_only_the_authorized_cron_and_event_gate_exist(self):
        self.assertEqual(re.findall(r'(?m)^\s+- cron: (.+)$', self.text), ["'40 6 * * *'"])
        self.assertIn("if: github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'", self.text)
        self.assertNotIn('--force', self.text)
        self.assertNotIn('HEAD:refs/heads/main', self.text)
