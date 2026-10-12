"""Trace compatibility tests with explicit survivor/precedence expectations."""
import copy
import itertools
import unittest
from unittest.mock import patch

from processing.dedup import dedup_articles, dedup_articles_detailed
from processing.deduplicator import deduplicate, deduplicate_detailed


class TraceCompatibility(unittest.TestCase):
    def test_authority_and_identity_preserved_under_every_permutation(self):
        a = {"url":"https://www.mod.gov.cn/gfbw/release", "source_slug":"mod_china", "title_original":"Fictional repeated bulletin", "text_original":"A"}
        b = {"url":"https://www.81.cn/yw_208727/release", "source_slug":"pla_daily", "title_original":a["title_original"], "text_original":"Different"}
        blank = {"url":"https://example.test/blank", "title_original":""}
        c = {"url":"https://example.test/other", "title_original":"Fictional separate bulletin"}
        for order in itertools.permutations([a,b,blank,c]):
            batch = list(order)
            expected = sorted([a,c],key=lambda x:batch.index(x)) + [blank]
            before = copy.deepcopy(batch)
            detail = dedup_articles_detailed(batch)
            self.assertEqual(detail.articles,expected)
            self.assertEqual(dedup_articles(batch),expected)
            self.assertTrue(all(x is batch[i] for x,i in zip(detail.articles,detail.positions)))
            self.assertEqual(batch,before)
            self.assertEqual(detail.decisions[batch.index(b)].reason,"title_suppressed")
            self.assertEqual(detail.decisions[batch.index(b)].representative,batch.index(a))

    def test_repeated_object_passthrough_and_legacy_last_identity_order(self):
        a={"url":"https://example.test/a","title_original":"Fictional A"}
        b={"url":"https://example.test/b","title_original":"Fictional B"}
        p={"url":"https://example.test/p","title_original":None}
        q={"url":"https://example.test/q","title_original":""}
        batch=[a,p,b,q,a,p]
        d=dedup_articles_detailed(batch)
        self.assertEqual(d.positions,[2,0,3,1,5])
        self.assertEqual(d.articles,[b,a,q,p,p])
        self.assertEqual(d.decisions[4].representative,0)
        self.assertEqual(d.decisions[4].reason,'title_suppressed')
        self.assertIs(dedup_articles(batch)[1],a)

    def test_spec_title_precedence_and_empty_batch(self):
        a={"url":"https://example.test/a","title_zh":"Fictional spec", "title_original":"Different"}
        b={"url":"https://example.test/b","title_original":"Fictional spec"}
        self.assertEqual(len(dedup_articles_detailed([a,b]).articles),1)
        self.assertEqual(dedup_articles_detailed([]).decisions,[])

    def test_singleton_never_reads_canonical_ranking_fields(self):
        a={'title_original':'Fictional singleton','source_slug':17,'url':object()}
        with patch('processing.dedup.select_canonical',side_effect=AssertionError):
            self.assertIs(dedup_articles([a])[0],a)
            self.assertIs(dedup_articles_detailed([a]).articles[0],a)

    def test_lookup_precedence_and_asymmetric_seen_sets(self):
        # A stored URL only adds its URL; a stored hash only adds its hash.
        # This batch deliberately revisits both with different counterparts.
        batch=[dict(url=u,content_hash=h) for u,h in [
            ('stored-url','shared'), ('new-url','shared'), ('stored-hash-url','stored-hash'),
            ('stored-hash-url','fresh'), ('new-url','another'), ('different','fresh'),
            ('stored-url','freshest'), ('tail','tailhash')]]
        expected_calls=[('url','stored-url'),('url','new-url'),('hash','shared'),
                        ('url','stored-hash-url'),('hash','stored-hash'),
                        ('url','stored-hash-url'),('hash','fresh'),
                        ('url','tail'),('hash','tailhash')]
        expected_reasons=['stored_url_match','prospective_survivor','stored_legacy_hash_match',
                          'prospective_survivor','batch_url_match','batch_legacy_hash_match',
                          'batch_url_match','prospective_survivor']
        for detailed in [False,True]:
            calls=[]
            def url(u):
                calls.append(('url',u)); return u=='stored-url'
            def sha(h):
                calls.append(('hash',h)); return h=='stored-hash'
            with patch('processing.deduplicator.db.url_exists',side_effect=url), patch('processing.deduplicator.db.hash_exists',side_effect=sha):
                result=deduplicate_detailed(batch) if detailed else deduplicate(batch)
            self.assertEqual(calls,expected_calls)
            self.assertEqual(result.articles if detailed else result,[batch[i] for i in [1,3,7]])
            if detailed:
                self.assertEqual([x.reason for x in result.decisions],expected_reasons)
                self.assertEqual([x.representative for x in result.decisions],[None,None,None,None,1,3,0,None])
                self.assertEqual(result.positions,[1,3,7])

    def test_injected_lookup_does_not_open_default_db(self):
        a={'url':'https://example.test/a','content_hash':'x'}
        with patch('processing.deduplicator.db.url_exists',side_effect=AssertionError), patch('processing.deduplicator.db.hash_exists',side_effect=AssertionError):
            d=deduplicate_detailed([a,a],url_lookup=lambda _:False,hash_lookup=lambda _:False)
        self.assertIs(d.articles[0],a)
        self.assertEqual(d.decisions[1].reason,'batch_url_match')

    def test_wrappers_delegate_to_the_same_engine(self):
        sentinel=object()
        class R:
            articles=sentinel
        with patch('processing.dedup.dedup_articles_detailed',return_value=R()) as engine:
            self.assertIs(dedup_articles([]),sentinel); engine.assert_called_once_with([])
        with patch('processing.deduplicator.deduplicate_detailed',return_value=R()) as engine:
            self.assertIs(deduplicate([]),sentinel); engine.assert_called_once_with([])
