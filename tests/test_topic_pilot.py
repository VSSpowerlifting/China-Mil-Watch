"""Frozen pilot integrity, reproducibility and preservation; no classification."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import topic_pilot as pilot
from core.topics import TopicTaxonomyError


class TopicPilotTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(pilot.LEDGER.read_text(encoding='utf-8'))

    def rejects(self, change, fragment, error=ValueError):
        change(self.data)
        with self.assertRaisesRegex(error, fragment):
            pilot.validate(self.data)

    def test_sample_is_valid_and_multi_desk(self):
        pilot.validate(self.data)
        stats = pilot.summarize(self.data)
        self.assertEqual(stats['desks'], {'china':24, 'singapore':12, 'japan':5,
            'vietnam':6, 'philippines':7, 'indonesia':3, 'korea':3})
        self.assertEqual(stats['layers'], {'production':36, 'shadow':24})
        self.assertEqual(stats['covered_topics'], 16)
        self.assertEqual(len(stats['unclassified']), 15)
        self.assertGreater(stats['multi_label'], 0)

    def test_unknown_topic_is_refused(self):
        self.rejects(lambda d: d['records'][0]['proposals'][0].update(topic='unknown'),
                     'unknown regional topic', TopicTaxonomyError)

    def test_duplicate_topic_is_refused(self):
        self.rejects(lambda d: d['records'][0]['proposals'].append(
            copy.deepcopy(d['records'][0]['proposals'][0])), 'duplicate topic')

    def test_duplicate_identity_is_refused(self):
        def change(d):
            d['records'][1] = copy.deepcopy(d['records'][0])
            d['records'][1]['pilot_id'] = 'P02'
        self.rejects(change, 'duplicate or unstable')

    def test_changed_url_invalidates_stable_identity(self):
        self.rejects(lambda d: d['records'][0].update(canonical_url='https://example.invalid/'),
                     'unstable record identity')

    def test_shadow_cannot_be_presented_as_production(self):
        self.rejects(lambda d: d['records'][36].update(storage_layer='production'),
                     'layer mismatch')

    def test_approved_status_is_refused(self):
        self.rejects(lambda d: d['records'][0].update(status='approved'), 'provisional')

    def test_missing_evidence_is_refused(self):
        self.rejects(lambda d: d['records'][0]['proposals'][0].update(evidence=['absent']),
                     'unsupported proposal')

    def test_invalid_excerpt_bounds_are_refused(self):
        self.rejects(lambda d: d['records'][0]['evidence'][0].update(start=-1),
                     'invalid evidence locator')

    def test_empty_body_cannot_be_classified(self):
        self.rejects(lambda d: d['records'][35]['proposals'].append(
            copy.deepcopy(d['records'][0]['proposals'][0])), 'unsupported proposal')

    def test_taxonomy_changes_require_explicit_review(self):
        self.rejects(lambda d: d.update(taxonomy_sha256='0'*64), 'taxonomy bytes changed')

    def test_report_reproduces_checked_in_bytes(self):
        report = pilot.markdown(pilot.validate(self.data))
        self.assertEqual(report, (pilot.LEDGER.parent/'LEDGER.md').read_text(encoding='utf-8'))
        self.assertEqual(report, pilot.markdown(self.data))

    def production_replay(self, data):
        # CI shallow checkouts need no shadow branches or network. Real pinned
        # production bytes are available unchanged in the checkout. The all-desk
        # replay is a separate explicit CLI check against fetched Git objects.
        data = copy.deepcopy(data)
        data['records'] = [r for r in data['records'] if r['origin']=='production']
        data['origins'] = {'production':data['origins']['production']}
        raw = (pilot.ROOT/'pla_watch.db').read_bytes()
        blob = hashlib.sha1(('blob %d\0'%len(raw)).encode()+raw).hexdigest()
        if blob != data['origins']['production']['blob']:
            try:
                raw = pilot.git('show', data['origins']['production']['commit']+':pla_watch.db')
            except ValueError:
                self.skipTest('Frozen production Git blob absent from this shallow checkout; run explicit source replay after fetching pins')
            blob = hashlib.sha1(('blob %d\0'%len(raw)).encode()+raw).hexdigest()
            self.assertEqual(blob, data['origins']['production']['blob'])
        def pinned_git(*args):
            self.assertEqual(args[-1], data['origins']['production']['commit']+':pla_watch.db')
            return (blob+'\n').encode() if args[0]=='rev-parse' else raw
        with patch.object(pilot, 'git', side_effect=pinned_git):
            return pilot.verify_sources(data)

    def test_preserved_production_rows_and_desk_labels_replay(self):
        self.assertEqual(self.production_replay(self.data), 36)

    def test_same_length_invented_excerpt_is_refused_by_source_replay(self):
        e = self.data['records'][0]['evidence'][0]
        e['quote'] = 'x'*len(e['quote'])
        with self.assertRaisesRegex(ValueError, 'excerpt differs from source'):
            self.production_replay(self.data)

    def test_changed_body_hash_is_refused_by_source_replay(self):
        self.data['records'][0]['body_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'source body mismatch'):
            self.production_replay(self.data)

    def test_changed_local_labels_are_refused_by_source_replay(self):
        self.data['records'][0]['local_categories'] = []
        with self.assertRaisesRegex(ValueError, 'local categories changed'):
            self.production_replay(self.data)

    def test_validation_report_and_replay_preserve_production_tree(self):
        def snapshot():
            files = [pilot.ROOT/'pla_watch.db'] + sorted(
                p for p in (pilot.ROOT/'output').rglob('*') if p.is_file())
            return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        before = snapshot()
        pilot.validate(self.data)
        pilot.markdown(self.data)
        self.production_replay(self.data)
        self.assertEqual(before, snapshot())
        for suffix in ('-wal', '-shm'):
            self.assertFalse(Path(str(pilot.ROOT/'pla_watch.db')+suffix).exists())


if __name__ == '__main__':
    unittest.main()
