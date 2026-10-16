"""Korea owner-only unreviewed machine draft private email contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import send_korea_english_owner_drafts as sut

SOURCE = {
    "source_identity":"korea-policy:156784297",
    "original_text_sha256":"a"*64,
    "official_url":"https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297",
    "publisher_posted_date":"2026-10-06",
}


class OwnerDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"receipts.json"
        self.path.write_text(json.dumps({"schema":sut.SCHEMA,"delivered":[]}))
        self.sent=[]
        self.generated=0

    def fake_draft(self,row,*,client):
        self.generated+=1
        return ({
            "model_id":"claude-sonnet-4-6",
            "review":{"status":"machine_unreviewed"}
        },{"machine_only":True,"review_sha256":"b"*64})

    def run_delivery(self):
        with patch.object(sut,"read_release_index",return_value=[SOURCE]), \
             patch.object(sut,"public_registry",return_value=[]), \
             patch.object(sut,"draft",side_effect=self.fake_draft), \
             patch.object(sut,"send_owner",side_effect=lambda *a,**k:self.sent.append(a)):
            return sut.run(ledger=self.path,client=object(),
                           sender="ipr@gmail.com",recipient="owner@gmail.com",
                           password="notused")

    def test_successful_owner_send_commits_only_source_hash_receipt(self):
        result=self.run_delivery()
        self.assertEqual(result["count"],1)
        self.assertEqual(self.generated,1)
        self.assertEqual(len(self.sent),1)
        d=json.loads(self.path.read_text())
        self.assertEqual(len(d["delivered"]),1)
        entry=d["delivered"][0]
        self.assertEqual(entry["source_sha256"],"a"*64)
        self.assertEqual(entry["draft_sha256"],"b"*64)
        self.assertEqual(set(entry),{"source_identity","source_sha256",
                                    "draft_sha256","model_id","delivered_at_utc"})
        self.assertNotIn("analysis",str(d))
        self.assertNotIn("translations",str(d))

    def test_repeated_scheduled_run_does_not_repeat_email_or_model_call(self):
        self.run_delivery()
        again=self.run_delivery()
        self.assertEqual(again["status"],"NO_NEW_ENGLISH_DRAFTS")
        self.assertEqual(again["count"],0)
        self.assertEqual(self.generated,1)
        self.assertEqual(len(self.sent),1)

    def test_failed_delivery_never_marks_packet_as_sent(self):
        with patch.object(sut,"read_release_index",return_value=[SOURCE]), \
             patch.object(sut,"public_registry",return_value=[]), \
             patch.object(sut,"draft",side_effect=self.fake_draft), \
             patch.object(sut,"send_owner",side_effect=ValueError("SMTP unavailable")):
            with self.assertRaisesRegex(ValueError,"SMTP unavailable"):
                sut.run(ledger=self.path,client=object(),
                        sender="ipr@gmail.com",recipient="owner@gmail.com",
                        password="notused")
        self.assertEqual(json.loads(self.path.read_text())["delivered"],[])

    def test_already_editor_approved_source_not_re_drafted(self):
        with patch.object(sut,"read_release_index",return_value=[SOURCE]), \
             patch.object(sut,"public_registry",return_value=[
                 ({"source_identity":SOURCE["source_identity"]},{},SOURCE)]):
            pending,_=sut.pending(self.path)
        self.assertEqual(pending,[])

    def test_delivery_ledger_requires_exact_sha_and_no_duplicate(self):
        x={"source_identity":SOURCE["source_identity"],
           "source_sha256":"a"*64,"draft_sha256":"b"*64,
           "model_id":"claude-sonnet-4-6","delivered_at_utc":"2026-10-16T02:30:00Z"}
        self.path.write_text(json.dumps({"schema":sut.SCHEMA,"delivered":[x,x]}))
        with self.assertRaisesRegex(Exception,"duplicate_or_digest_invalid"):
            sut.read_receipts(self.path)
        x["source_sha256"]="unsafe"
        self.path.write_text(json.dumps({"schema":sut.SCHEMA,"delivered":[x]}))
        with self.assertRaisesRegex(Exception,"duplicate_or_digest_invalid"):
            sut.read_receipts(self.path)

    def test_missing_editor_recipient_and_secrets_prevents_send(self):
        self.assertRaises(Exception,sut.address,"bad\nmail@example.com")
        self.assertRaises(Exception,sut.address,"noemail")

    def test_daily_budget_is_two_source_records(self):
        many=[{**SOURCE,"source_identity":"korea-policy:"+str(156990000+n),
               "original_text_sha256":str(n+1).zfill(64)} for n in range(6)]
        with patch.object(sut,"read_release_index",return_value=many), \
             patch.object(sut,"public_registry",return_value=[]):
            pending,_=sut.pending(self.path)
        self.assertEqual(len(pending),2)
        self.assertEqual([r["source_identity"] for r in pending],
                         ["korea-policy:156990000","korea-policy:156990001"])


if __name__=="__main__":
    unittest.main()
