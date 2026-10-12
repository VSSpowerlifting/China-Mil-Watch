"""Private ledger/snapshot/replay contracts; fictional inputs never imply real events."""
import contextlib
import copy
import io
import json
import multiprocessing
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from core.source_occurrences import OccurrenceError, canonical, digest
from scripts.source_occurrences import (
    ROOT, build_batch, file_digest, main, pinned_archive, saved_mindef, summary,
)
from scripts.source_occurrences_view import render
from storage.source_occurrences import commit_batch, initialize, private_path, read_batches, write_report
from processing.metadata import compute_content_hash


TITLE='RAW_TITLE_SENTINEL_67e49c'
BODY='RAW_BODY_SENTINEL_a55d2c'
SUMMARY='RAW_SUMMARY_SENTINEL_8d6192'
EXTRA='RAW_EXTRA_SENTINEL_71cd42'


def document(url='https://example.test/a', title=TITLE, text=BODY, date='2026-10-10', **extra):
    return dict(url=url,title_original=title,text_original=text,published_date=date,**extra)


def native_row(i, raw, stored=None):
    r=dict(raw,id=i,desk_id=None,institution_id=None,scraped_at='2026-10-11 10:00:00')
    r['content_hash']=compute_content_hash(raw.get('title_original'),raw.get('text_original')) if stored is None else stored
    return r


def race_commit(path,batch,barrier,queue):
    barrier.wait()
    try:
        queue.put(('ok',commit_batch(path,batch)))
    except OccurrenceError as exc:
        queue.put(('refused',str(exc)))


class OccurrenceContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ipr-occurrence-test-')
        self.root=Path(self.tmp.name).resolve()
        self.ledger=self.root/'ledger.db'
        initialize(self.ledger)
        self.pin='a'*64

    def tearDown(self):
        self.tmp.cleanup()

    def batch(self,docs=None,rows=None,key='fictional-batch',mode='observed_replay',sources=None):
        return build_batch(mode,key,self.pin,rows or [],sources or [],docs or [])

    def test_redaction_ledger_export_html_and_safe_diagnostics(self):
        d=document(summary_english=SUMMARY,extra={'provider_prompt':EXTRA},source_slug=EXTRA)
        b=self.batch([d])
        self.assertTrue(commit_batch(self.ledger,b))
        reopened=read_batches(self.ledger)
        export=canonical([x.as_dict() for x in reopened])
        html=render(reopened)
        json_path=self.root/'metadata.json'; write_report(json_path,export)
        with sqlite3.connect(str(self.ledger)) as c:
            fields=canonical(c.execute('SELECT * FROM batches').fetchall())
        for secret in [TITLE,BODY,SUMMARY,EXTRA]:
            for artifact in [fields,export,html,json_path.read_text()]:
                self.assertNotIn(secret,artifact)
        self.assertEqual(reopened[0].observations[0].metadata.identity_state,'unknown_identity')
        bad=self.root/'bad.json'; bad.write_text(canonical([dict(d,url='bad:'+BODY)]))
        out=io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result=main(['replay','--ledger',str(self.ledger),'--archive',str(self.root/'missing'),
                         '--snapshot-sha256',self.pin,'--batch','x','--documents',str(bad)])
        self.assertEqual(result,2)
        for secret in [TITLE,BODY,SUMMARY,EXTRA]: self.assertNotIn(secret,out.getvalue())

    def test_every_position_body_variants_missing_and_recurrence(self):
        d=document()
        docs=[d,d,document(url='https://example.test/b',text='Fictional different body',date='2026-10-11'),
              document(url='https://example.test/c',title=None,text=None,date=None),
              document(url='https://example.test/d',title='',text='  ',date='invalid')]
        before=copy.deepcopy(docs)
        b=self.batch(docs)
        self.assertEqual(docs,before)
        self.assertEqual(len(b.observations),5)
        self.assertEqual(len({o.observation_id for o in b.observations}),5)
        self.assertEqual(sum(o.title_reason=='title_suppressed' for o in b.observations),2)
        self.assertEqual([o.metadata.body_state for o in b.observations],['extracted_text']*3+['missing','blank'])
        self.assertEqual([o.metadata.title_state for o in b.observations][-2:],['missing','blank'])
        self.assertIsNone(b.observations[3].metadata.extracted_title_sha256)
        self.assertEqual([o.metadata.published_date for o in b.observations][-2:],[None,None])
        groups=[r for r in b.relations if r.kind=='same_title_group']
        self.assertEqual(len(groups),1); self.assertEqual(len(groups[0].members),3)
        self.assertFalse(any('o:'+b.observations[3].observation_id in r.members
                             for r in b.relations if 'equal_' in r.kind))
        later=self.batch([document(date='2026-10-12')],key='later')
        self.assertEqual(later.observations[0].url_hash_reason,'prospective_survivor')
        self.assertNotEqual(b.execution_sha256,later.execution_sha256)

    def test_same_title_different_body_only_candidate_signal(self):
        b=self.batch([document(url='https://example.test/a'),document(url='https://example.test/b',text='Fictional different')])
        self.assertEqual({r.kind for r in b.relations},{'same_title_group'})
        self.assertEqual([o.url_hash_reason for o in b.observations],['not_reached','prospective_survivor'])
        self.assertIn('Differing extracted versions; unresolved',render([b]))

    def test_different_titles_same_normalized_text_and_cross_batch_reader(self):
        a=document(title='Fictional first',text='Fictional body  spaced')
        b=document(url='https://example.test/b',title='Fictional second',text='Fictional body spaced')
        batch=self.batch([a,b])
        self.assertEqual({r.kind for r in batch.relations},{'equal_normalized_text'})
        self.assertTrue(all(o.url_hash_reason=='prospective_survivor' for o in batch.observations))
        later=self.batch([dict(a,published_date='2026-10-11')],key='later')
        html=render([batch,later],{'group':batch.observations[0].metadata.title_group_sha1})
        self.assertEqual(html.count('<article id="observation-'),2)

    def test_supplied_producer_capture_and_media_only_metadata(self):
        raw=document(text='',capture_sha256='b'*64,retrieved_at='2026-10-11T12:00:00Z',content_verdict='media_only')
        m=self.batch([raw]).observations[0].metadata
        self.assertEqual(m.producer_capture_sha256,'b'*64)
        self.assertEqual(m.body_kind,'media_only')
        self.assertIsNone(m.normalized_text_sha256)

    def test_saved_fixture_byte_changes_refuse_existing_identity_and_exact_locator_survives(self):
        folder=self.root/'fixtures';folder.mkdir(mode=0o700)
        index=json.loads((ROOT/'tests/fixtures/sg_mindef/items.json').read_text())[:1]
        index[0]['url'] += '?local-fixture=1'
        source=ROOT/'tests/fixtures/sg_mindef'/index[0]['file']
        target=folder/index[0]['file'];target.write_bytes(source.read_bytes())
        path=folder/'items.json';path.write_text(json.dumps(index))
        docs=saved_mindef(path)
        first=self.batch(docs)
        self.assertEqual(first.observations[0].metadata.supplied_url,index[0]['url'])
        self.assertNotEqual(first.observations[0].metadata.url,index[0]['url'])
        commit_batch(self.ledger,first)
        target.write_bytes(target.read_bytes()+b'<!-- local fictional byte change -->')
        changed=self.batch(saved_mindef(path))
        self.assertNotEqual(changed.input_sha256,first.input_sha256)
        with self.assertRaisesRegex(OccurrenceError,'batch_revision_conflict'):
            commit_batch(self.ledger,changed)

    def test_hash_equality_requires_nonblank_body_and_recomputed_retained_hash(self):
        row=native_row(1,document(),stored='b'*64)
        b=self.batch([document(url='https://example.test/new')],[row])
        self.assertEqual(b.observations[0].url_hash_reason,'prospective_survivor')
        self.assertIn('equal_normalized_title_text',{r.kind for r in b.relations})
        self.assertEqual(b.records[0].metadata.stored_hash_state,'disagrees')
        empty=self.batch([document(title='',text='')],[native_row(1,document(url='https://example.test/empty',title='',text=''))])
        self.assertEqual(empty.observations[0].url_hash_reason,'stored_legacy_hash_match')
        self.assertFalse(any('equal_' in r.kind for r in empty.relations))

    def test_url_hash_precedence_ambiguous_ids_and_prospective_pointer(self):
        rows=[native_row(1,document(),stored='b'*64),native_row(2,document(text='Other'))]
        b=self.batch([document()],rows)
        o=b.observations[0]
        self.assertEqual(o.url_hash_reason,'stored_url_match')
        self.assertEqual(o.decision_native_ids,(1,2))
        self.assertEqual(o.native_ids,(1,2))
        self.assertIn('Ambiguous matches',render([b]))
        self.assertEqual({r.native_id for r in b.records},{1,2})
        b=self.batch([document(url='https://example.test/new')],[native_row(4,document()),native_row(5,document(url='https://example.test/b'))])
        self.assertEqual(b.observations[0].decision_native_ids,(4,5))
        self.assertEqual(b.observations[0].url_hash_reason,'stored_legacy_hash_match')
        fresh=self.batch([document()])
        self.assertEqual(fresh.observations[0].native_ids,())

    def test_batch_hash_and_url_matches_after_title_stage(self):
        docs=[document(title=''),document(url='https://example.test/b',title=''),
              document(title='',text='Other')]
        b=self.batch(docs)
        self.assertEqual([o.url_hash_reason for o in b.observations],
                         ['prospective_survivor','batch_legacy_hash_match','batch_url_match'])
        self.assertEqual(b.observations[1].url_hash_representative,b.observations[0].observation_id)

    def test_archive_inventory_labels_unknown_history_and_resolves_pointers(self):
        rows=[native_row(1,document()),native_row(2,document(url='https://example.test/b',date='2026-10-11'))]
        b=self.batch(rows=rows,mode='archive_inventory')
        self.assertEqual([o.origin for o in b.observations],['existing_archive_row']*2)
        self.assertTrue(all(o.url_hash_reason=='historical_decision_unknown' for o in b.observations))
        self.assertEqual(summary(b)['cohorts_differing_dates'],1)
        self.assertEqual({n for o in b.observations for n in o.native_ids},{r.native_id for r in b.records})
        self.assertIn('Differing publication dates',render([b]))

    def test_identity_source_and_host_mismatch_fail_closed(self):
        src={'slug':'sg_mindef_releases','desk_id':'singapore','institution_id':'sg_mindef'}
        good=document(url='https://www.mindef.gov.sg/news-and-events/latest-releases/10oct26-nr/',source_slug=src['slug'])
        b=self.batch([good],sources=[src])
        self.assertEqual(b.observations[0].metadata.institution_id,'sg_mindef')
        with self.assertRaisesRegex(OccurrenceError,'source_identity_mismatch'):
            self.batch([good],sources=[dict(src,desk_id='china')])
        with self.assertRaisesRegex(OccurrenceError,'source_locator_mismatch'):
            self.batch([dict(good,url='https://example.test/a')],sources=[src])

    def test_transaction_idempotency_revision_rollback_and_determinism(self):
        b=self.batch([document()])
        self.assertEqual(canonical(b.as_dict()),canonical(self.batch([document()]).as_dict()))
        self.assertTrue(commit_batch(self.ledger,b)); self.assertFalse(commit_batch(self.ledger,b))
        before=self.ledger.read_bytes()
        with self.assertRaisesRegex(OccurrenceError,'batch_revision_conflict'):
            commit_batch(self.ledger,self.batch([document(text='Changed')]))
        self.assertEqual(before,self.ledger.read_bytes())
        with sqlite3.connect(str(self.ledger)) as c:
            c.execute("CREATE TRIGGER refuse BEFORE INSERT ON batches BEGIN SELECT RAISE(ABORT,'fixture rollback'); END")
        with self.assertRaises(OccurrenceError): commit_batch(self.ledger,self.batch([document()],key='new'))
        self.assertEqual(len(read_batches(self.ledger)),1)
        self.assertEqual(len(read_batches(self.ledger)[0].observations),1)

    def test_same_code_at_another_git_head_is_noop_but_changed_code_refuses(self):
        b=self.batch([document()]);commit_batch(self.ledger,b)
        self.assertFalse(commit_batch(self.ledger,replace(b,code_git_head='b'*40)))
        self.assertEqual(read_batches(self.ledger)[0].code_git_head,b.code_git_head)
        with patch('scripts.source_occurrences.code_binding',return_value=('c'*64,'b'*40)):
            changed=self.batch([document()])
        with self.assertRaisesRegex(OccurrenceError,'batch_revision_conflict'):
            commit_batch(self.ledger,changed)

    def test_real_cross_process_same_and_conflicting_writers(self):
        ctx=multiprocessing.get_context('spawn')
        for conflict in [False,True]:
            ledger=self.root/('race-%s.db'%conflict); initialize(ledger)
            b=self.batch([document()])
            other=self.batch([document(text='Fictional changed')]) if conflict else b
            barrier=ctx.Barrier(2); queue=ctx.Queue()
            workers=[ctx.Process(target=race_commit,args=(ledger,x,barrier,queue)) for x in [b,other]]
            for p in workers: p.start()
            for p in workers:
                p.join(30); self.assertEqual(p.exitcode,0)
            results=sorted([queue.get(timeout=5),queue.get(timeout=5)])
            self.assertEqual(results,[('ok',True),('refused','batch_revision_conflict')] if conflict else [('ok',False),('ok',True)])
            self.assertEqual(len(read_batches(ledger)),1)

    def test_unsafe_destinations_permissions_links_and_overwrite(self):
        for path in [ROOT/'ledger.db',ROOT/'output'/'metadata.json',self.ledger]:
            with self.assertRaises(OccurrenceError): private_path(path)
        link=self.root/'link.db'; link.symlink_to(self.ledger)
        with self.assertRaises(OccurrenceError): read_batches(link)
        outside=self.root/'directory'; outside.mkdir(mode=0o700)
        alias=self.root/'alias'; alias.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OccurrenceError): initialize(alias/'ledger.db')
        hard=self.root/'hard'; os.link(self.ledger,hard)
        with self.assertRaises(OccurrenceError): read_batches(hard)
        hard.unlink()
        os.chmod(outside,0o755)
        with self.assertRaises(OccurrenceError): initialize(outside/'ledger.db')
        report=self.root/'report.json'; write_report(report,'{}')
        with self.assertRaises(OccurrenceError): write_report(report,'changed')
        side=Path(str(self.ledger)+'-journal'); side.symlink_to(report)
        with self.assertRaises(OccurrenceError): read_batches(self.ledger)
        self.assertEqual(report.read_text(),'{}')

    def test_corruption_schema_missing_snapshot_and_digest_mismatch(self):
        bad=self.root/'bad.db'; bad.write_bytes(b'not sqlite'); os.chmod(bad,0o600)
        with self.assertRaises(OccurrenceError): read_batches(bad)
        with self.assertRaises(OccurrenceError):
            with pinned_archive(self.root/'missing',self.pin): pass
        with self.assertRaises(OccurrenceError):
            with pinned_archive(self.ledger,self.pin): pass
        with self.assertRaises(OccurrenceError):
            with pinned_archive(self.ledger,file_digest(self.ledger)): pass
        commit_batch(self.ledger,self.batch([document()]))
        with sqlite3.connect(str(self.ledger)) as c: c.execute("UPDATE batches SET metadata_json='{}'")
        with self.assertRaises(OccurrenceError): read_batches(self.ledger)

    def test_snapshot_wal_changed_bytes_and_source_guard(self):
        snapshot=self.root/'snapshot.db'
        with sqlite3.connect(str(snapshot)) as c:
            c.executescript('CREATE TABLE articles(id INTEGER,url TEXT,source_id INTEGER,content_hash TEXT,title_original TEXT,text_original TEXT,published_date TEXT); CREATE TABLE sources(id INTEGER,slug TEXT,desk_id TEXT,institution_id TEXT); CREATE TABLE institutions(institution_id TEXT,desk_id TEXT); CREATE TABLE desks(desk_id TEXT);')
        pin=file_digest(snapshot)
        side=Path(str(snapshot)+'-wal'); side.write_bytes(b'fictional')
        with self.assertRaisesRegex(OccurrenceError,'snapshot_not_quiescent'):
            with pinned_archive(snapshot,pin): pass
        side.unlink()
        with self.assertRaises(OccurrenceError):
            with pinned_archive(snapshot,pin):
                snapshot.write_bytes(snapshot.read_bytes()+b'changed')

    def test_malformed_inputs_no_partial_acceptance_or_secret_echo(self):
        for bad in [None,[],document(text={BODY:BODY}),document(url='javascript:'+BODY),
                    document(url='https://user:secret@example.test/a'),
                    document(url='https://example.test/a?token='+BODY),document(extra=float('nan')),
                    document(title=TITLE+'\ud800')]:
            with self.assertRaises(OccurrenceError) as error: self.batch([document(),bad])
            self.assertNotIn(BODY,str(error.exception))
            self.assertEqual(read_batches(self.ledger),[])
        # Non-contract arbitrary payload cannot be committed or read as metadata.
        b=self.batch([document()]); o=b.observations[0]
        with self.assertRaises(OccurrenceError):
            commit_batch(self.ledger,replace(b,observations=(replace(o,metadata=replace(o.metadata,extracted_title_sha256=TITLE)),)))

    def test_actual_saved_html_adapter_normalize_engines_selected_archive_reopen(self):
        fixture=ROOT/'tests/fixtures/sg_mindef/items.json'
        documents=saved_mindef(fixture)
        self.assertEqual(len(documents),9)
        pin=file_digest(ROOT/'pla_watch.db')
        with pinned_archive(ROOT/'pla_watch.db',pin) as (rows,sources):
            b=build_batch('observed_replay','saved-fixture-integration',pin,rows,sources,documents)
        self.assertEqual(len(b.observations),len(documents))
        self.assertTrue(all(o.metadata.source_slug=='sg_mindef_releases' for o in b.observations))
        self.assertTrue(all(o.metadata.producer_capture_sha256 is None for o in b.observations))
        self.assertTrue(commit_batch(self.ledger,b))
        self.assertEqual(read_batches(self.ledger)[0],b)
        self.assertIn('Observed replay',render(read_batches(self.ledger)))
        self.assertEqual(file_digest(ROOT/'pla_watch.db'),pin)
        self.assertFalse(Path(str(ROOT/'pla_watch.db')+'-wal').exists())
        self.assertTrue(all(n in {r['id'] for r in rows} for o in b.observations for n in o.native_ids))
