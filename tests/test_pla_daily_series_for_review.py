"""PLA Daily recurring headline series are review cues, not cull commands."""
import copy
import json
from pathlib import Path
import unittest
from scripts.audit_pla_daily_series_for_review import audit, family

# Frozen October 14 evidence (5,230 records, 5,144 China records).
# Live output/corpus-index.json advances with daily collection and is not
# the source of truth for exact 2026-10-14 historical audit assertions.
INDEX = Path(__file__).resolve().parent / "fixtures/china-corpus-index-2026-10-14.json"

class PlaSeriesAuditTest(unittest.TestCase):
    def test_real_series_counts_and_issuer_counterexamples(self):
        d=json.loads(INDEX.read_text(encoding="utf-8"))
        before=copy.deepcopy(d)
        r=audit(d)
        self.assertEqual(d,before)
        self.assertEqual(r["pla_daily_preserved"],4173)
        self.assertEqual(r["pla_daily_months"],{
            "2026-05":788,"2026-06":933,"2026-07":706,
            "2026-08":778,"2026-09":697,"2026-10":271,
        })
        series={x["family"]:x for x in r["repeated_families"]}
        for label,count in [
            ("强军论坛",100),("八一锐评",45),("军营观察",45),
            ("外交部",138),("国台办",26),("清风正气歌",26)
        ]:
            self.assertEqual(series[label]["count"],count)
            self.assertLessEqual(len(series[label]["sample_record_ids"]),6)
        self.assertIn("外交部",r["high_caution_prefixes"])
        self.assertFalse(r["publication_enabled"])
        self.assertEqual(r["editorial_rejection_decisions"],0)

    def test_publisher_prefixes_not_editorial_categories(self):
        self.assertEqual(family("强军论坛丨锻造强军之基"),"强军论坛")
        self.assertEqual(family("外交部：某项正式声明"),"外交部")
        self.assertEqual(family("八一锐评｜评论文章"),"八一锐评")
        self.assertIsNone(family(""))

    def test_reject_invalid_corpus_or_lost_citations(self):
        data=json.loads(INDEX.read_text(encoding="utf-8"))
        data["records"][0][0]=data["records"][1][0]
        with self.assertRaisesRegex(ValueError,"duplicate"):
            audit(data)
        data=json.loads(INDEX.read_text(encoding="utf-8"))
        data["trail_ids"].append(999999)
        with self.assertRaisesRegex(ValueError,"trails"):
            audit(data)
        data=json.loads(INDEX.read_text(encoding="utf-8"))
        data["snapshot"]["records"]=5231
        with self.assertRaisesRegex(ValueError,"snapshot drift"):
            audit(data)

    def test_threshold_only_changes_report_not_archive(self):
        data=json.loads(INDEX.read_text(encoding="utf-8"))
        first=audit(data,10)
        second=audit(data,25)
        self.assertEqual(first["pla_daily_preserved"],second["pla_daily_preserved"])
        self.assertGreater(len(first["repeated_families"]),len(second["repeated_families"]))
        self.assertEqual(second["editorial_rejection_decisions"],0)
        with self.assertRaisesRegex(ValueError,"frequency threshold"):
            audit(data,1)

if __name__=="__main__":
    unittest.main()
