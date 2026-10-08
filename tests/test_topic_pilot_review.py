"""Review-artifact integrity and preservation; no classification or attachments."""
import copy
import hashlib
import json
import unittest

from core.topics import load_taxonomy
from scripts import topic_pilot as pilot
from tests import test_topic_pilot as production_tests

REVIEW = pilot.LEDGER.parent / 'review' / 'assessment.json'
REVIEWED_HEAD = '0f368eb3131b7cac7d6d1db9e9f00ed7d889a57f'
ORIGINAL_ARTIFACT_HASHES = {'research/topic_pilot_v1/ledger.json': '5b7e6a6d330db25395efbeea371106ebca7cd4f3684ae93e3d0670e79da2e766', 'research/topic_pilot_v1/LEDGER.md': 'bc810b7b272627b76e94cb68bfa56a1aff9eb95b415637b3f0ad8cd0bf268c6f', 'research/topic_pilot_v1/README.md': '6b0b5b1e4959721598818e523b2797a8a8c04cb03c6f2ee00e92d7f7bc254330', 'research/topic_pilot_v1/verification.json': '52e10b2341ba4b10db01f64a5a655fe5e6a4950cc101274431281438c3634f79', 'docs/REGIONAL_TOPIC_PILOT.md': '0474b6fd87a179ae6c51340c99d037506152475fecd5c4a3a33b5985ee0e5240'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_review(review):
    ledger = json.loads(pilot.LEDGER.read_text(encoding='utf-8'))
    pilot.validate(ledger)
    require(review['review_version'] == 1 and review['reviewed_head'] == REVIEWED_HEAD,
            'review target changed')
    require(review['ledger_sha256'] == hashlib.sha256(pilot.LEDGER.read_bytes()).hexdigest(),
            'original ledger changed')
    require(review['taxonomy_sha256'] == ledger['taxonomy_sha256'], 'taxonomy changed')
    require(review['human_approved'] is False and review['status'] == 'recommendations_only',
            'review must not claim approval')
    require(review['reviewer'] == 'Codex editorial-skeptic second pass' and
            bool(review['independence_limit'].strip()), 'missing model provenance or limit')
    records = review['records']
    require(len(records) == len(ledger['records']), 'incomplete review')
    taxonomy = load_taxonomy()
    for r, original in zip(records, ledger['records']):
        require(all(r[k] == original[k] for k in
                    ('pilot_id', 'record_id', 'desk_id', 'storage_layer', 'body_sha256')),
                'record identity or layer changed')
        require(r['source_url'] == original['canonical_url'] and
                r['source_date'] == original['published_date'] and
                r['origin_commit'] == ledger['origins'][original['origin']]['commit'],
                'source pin changed')
        require(r['original_flagged'] == bool(original['review_issue']), 'flag changed')
        old = [p['topic'] for p in original['proposals']]
        require(r['original_topics'] == old, 'original proposals changed')
        new = r['recommended_topics']
        require(len(new) == len(set(new)), 'duplicate review topic')
        for topic in new:
            taxonomy.topic(topic)
        require(r['classification_recommendation'] ==
                ('accept' if set(old) == set(new) else 'revise'), 'verdict inconsistent')
        require(bool(r['rationale'].strip()) and bool(r['evidence_assessment'].strip()),
                'missing assessment')
        require(r['owner_question'] is None or bool(r['owner_question'].strip()),
                'empty owner question')
        evidence = {}
        for e in r['evidence']:
            require(e['id'] not in evidence, 'duplicate evidence')
            require(e['field'] == 'text_original' and type(e['start']) is int and
                    type(e['end']) is int and
                    0 <= e['start'] < e['end'] <= original['body_chars'] and
                    len(e['quote']) == e['end'] - e['start'], 'invalid review locator')
            require(e['provenance'] in ('original-ledger excerpt',
                    'full-body second-pass locator'), 'unknown evidence provenance')
            evidence[e['id']] = e
        decisions = {}
        for decision in r['label_decisions']:
            topic = decision['topic']
            taxonomy.topic(topic)
            require(topic not in decisions, 'duplicate label decision')
            expected = ('accept' if topic in old and topic in new else
                        'reject' if topic in old else 'add')
            require(decision['recommendation'] == expected, 'label decision inconsistent')
            require(decision['evidence'] and
                    all(e in evidence for e in decision['evidence']), 'missing label evidence')
            decisions[topic] = decision
        require(set(decisions) == set(old) | set(new), 'missing or extraneous label decision')
        require(bool(evidence) == bool(original['body_chars']), 'empty-body evidence mismatch')
        if not original['body_chars']:
            require(not new, 'empty body classified')
    return review


def replay_data(review):
    """Reuse immutable source replay with separate review excerpts, never write data."""
    validate_review(review)
    ledger = json.loads(pilot.LEDGER.read_text(encoding='utf-8'))
    for record, assessment in zip(ledger['records'], review['records']):
        record['evidence'] = copy.deepcopy(assessment['evidence'])
    # verify_sources checks bodies and all excerpts directly, without interpreting labels.
    return ledger


class TopicPilotReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads(REVIEW.read_text(encoding='utf-8'))

    def refuses(self, mutate, message):
        mutate(self.review)
        with self.assertRaisesRegex(ValueError, message):
            validate_review(self.review)

    def test_all_records_flags_and_priority_cases_are_reviewed(self):
        validate_review(self.review)
        for path, digest in ORIGINAL_ARTIFACT_HASHES.items():
            self.assertEqual(hashlib.sha256((pilot.ROOT / path).read_bytes()).hexdigest(), digest, path)
        self.assertEqual(len(self.review['records']), 60)
        self.assertEqual(sum(r['original_flagged'] for r in self.review['records']), 30)
        by_id = {r['pilot_id']: r for r in self.review['records']}
        for identifier in ('P25', 'P31', 'P33', 'P38', 'P47', 'P58'):
            self.assertTrue(by_id[identifier]['owner_question'])

    def test_original_ledger_is_frozen(self):
        self.refuses(lambda d: d.update(ledger_sha256='0' * 64), 'original ledger changed')

    def test_approval_is_refused(self):
        self.refuses(lambda d: d.update(human_approved=True), 'must not claim approval')

    def test_wrong_head_is_refused(self):
        self.refuses(lambda d: d.update(reviewed_head='0' * 40), 'target changed')

    def test_partial_or_duplicate_record_review_is_refused(self):
        self.refuses(lambda d: d['records'].pop(), 'incomplete review')
        self.setUp()
        self.refuses(lambda d: d['records'].__setitem__(1, copy.deepcopy(d['records'][0])),
                     'identity or layer changed')

    def test_unknown_topic_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'unknown regional topic'):
            self.review['records'][0]['recommended_topics'].append('unregistered_hadr')
            validate_review(self.review)

    def test_duplicate_topic_is_refused(self):
        self.refuses(lambda d: d['records'][0]['recommended_topics'].append(
            d['records'][0]['recommended_topics'][0]), 'duplicate review topic')

    def test_decision_without_evidence_is_refused(self):
        self.refuses(lambda d: d['records'][0]['label_decisions'][0].update(evidence=[]),
                     'missing label evidence')

    def test_inconsistent_verdict_or_delta_is_refused(self):
        self.refuses(lambda d: d['records'][0].update(classification_recommendation='accept'),
                     'verdict inconsistent')
        self.setUp()
        self.refuses(lambda d: d['records'][0]['label_decisions'].pop(),
                     'missing or extraneous label decision')

    def test_shadow_identity_and_source_pin_are_preserved(self):
        self.refuses(lambda d: d['records'][36].update(storage_layer='production'),
                     'identity or layer changed')
        self.setUp()
        self.refuses(lambda d: d['records'][36].update(origin_commit='0' * 40),
                     'source pin changed')

    def production_replay(self, data):
        return production_tests.TopicPilotTests().production_replay(data)

    def test_production_review_excerpts_replay_offline(self):
        self.assertEqual(self.production_replay(replay_data(self.review)), 36)

    def test_same_length_fabricated_quote_is_refused_by_replay(self):
        data = replay_data(self.review)
        quote = data['records'][0]['evidence'][0]
        quote['quote'] = 'x' * len(quote['quote'])
        with self.assertRaisesRegex(ValueError, 'excerpt differs from source'):
            self.production_replay(data)

    def test_replay_preserves_original_artifacts_and_protected_tree(self):
        def snapshot():
            paths = [pilot.LEDGER, pilot.LEDGER.parent / 'LEDGER.md',
                     pilot.LEDGER.parent / 'README.md', pilot.ROOT / 'pla_watch.db']
            for directory in ('output', 'taxonomy', 'desks', 'shadow', 'storage', 'core'):
                paths.extend(p for p in (pilot.ROOT / directory).rglob('*')
                             if p.is_file() and '__pycache__' not in p.parts)
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        before = snapshot()
        self.production_replay(replay_data(self.review))
        self.assertEqual(before, snapshot())
        for suffix in ('-wal', '-shm'):
            self.assertFalse((pilot.ROOT / ('pla_watch.db' + suffix)).exists())


if __name__ == '__main__':
    unittest.main()
