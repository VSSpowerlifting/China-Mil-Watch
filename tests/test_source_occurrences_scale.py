"""Actual-size inventory and larger fictional replay, with metadata-only timing receipts."""
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path

from core.source_occurrences import canonical
from scripts.source_occurrences import ROOT, build_batch, file_digest, pinned_archive, summary
from storage.source_occurrences import commit_batch, initialize, read_batches


class ScaleReceipts(unittest.TestCase):
    def exercise(self,build):
        with tempfile.TemporaryDirectory(prefix='ipr-occurrence-scale-') as temp:
            ledger=Path(temp).resolve()/'ledger.db'; initialize(ledger)
            tracemalloc.start(); start=time.perf_counter()
            try:
                batch=build()
                self.assertTrue(commit_batch(ledger,batch))
                self.assertEqual(read_batches(ledger),[batch])
                receipt=dict(summary(batch),elapsed_seconds=round(time.perf_counter()-start,3),
                             peak_python_mib=round(tracemalloc.get_traced_memory()[1]/1048576,2))
            finally:
                tracemalloc.stop()
            print('IPR metadata-only scale receipt: '+canonical(receipt))
            return batch

    def test_actual_pinned_retained_inventory_and_native_pointer_resolution(self):
        pin=file_digest(ROOT/'pla_watch.db')
        native_ids=[]
        def build():
            with pinned_archive(ROOT/'pla_watch.db',pin) as (rows,sources):
                native_ids.extend(r['id'] for r in rows)
                return build_batch('archive_inventory','real-retained-scale-test',pin,rows,sources)
        batch=self.exercise(build)
        self.assertEqual(len(batch.observations),len(native_ids))
        self.assertEqual({o.native_ids[0] for o in batch.observations},set(native_ids))
        self.assertTrue(all(o.url_hash_reason=='historical_decision_unknown' for o in batch.observations))
        self.assertEqual(file_digest(ROOT/'pla_watch.db'),pin)
        self.assertFalse(Path(str(ROOT/'pla_watch.db')+'-wal').exists())
        self.assertFalse(Path(str(ROOT/'pla_watch.db')+'-shm').exists())

    def test_larger_fictional_fixture_indexed_memberships(self):
        docs=[dict(url='https://example.test/fictional/%d'%i,
                   title_original='Fictional recurring title %d'%(i//3),
                   text_original='Fictional body variant %d'%(i%97),
                   published_date='2026-10-%02d'%(1+i%11)) for i in range(20000)]
        batch=self.exercise(lambda:build_batch('observed_replay','fictional-scale-20000','a'*64,[],[],docs))
        self.assertEqual(len(batch.observations),20000)
        self.assertEqual(sum(o.title_reason=='title_selected' for o in batch.observations),6667)
        self.assertEqual(sum(r.kind=='same_title_group' for r in batch.relations),6667)
        self.assertEqual(sum(r.kind=='equal_normalized_text' for r in batch.relations),97)
        self.assertFalse(any(r.kind=='equal_normalized_title_text' for r in batch.relations))
