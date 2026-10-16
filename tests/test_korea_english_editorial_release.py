"""Authenticated English/editorial release: source, review and retry guard."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.korea_english_publication import (
    KoreaEnglishHold, REGISTER, public_registry,
)
from scripts import admit_korea_reviewed_english as pub
from tests.test_korea_english_publication import ID, TEXT, SHA, make_review


class OwnerEnglishAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.index=self.root/"english.json"
        self.index.write_text(json.dumps({"schema":REGISTER,"releases":[]}))
        self.review_dir=self.root/"reviewed"
        self.review_dir.mkdir()
        self.original_dir=self.root/"originals"
        self.original_dir.mkdir()
        self.origin_index=self.root/"original_index.json"
        rid=ID.split(":")[1]
        (self.original_dir/(rid+".txt")).write_text(TEXT,encoding="utf-8")
        self.origin_index.write_text(json.dumps({
            "schema":"ipr-korea-public-original-text-index/1",
            "records":[{
                "source_identity":ID,
                "official_url":"https://www.korea.kr/briefing/pressReleaseView.do?newsId="+rid,
                "publisher_posted_date":"2026-10-06",
                "source_git_commit":"a"*40,
                "original_text_sha256":SHA,
                "policy_sha256":"b"*64,
                "source_html_sha256":"c"*64,
                "release_decision_sha256":"d"*64,
                "released_at_utc":"2026-10-16T02:00:00Z",
            }]
        }))
        self.review=make_review()
        self.review_file=self.review_dir/(rid+".json")
        self.write()
        self.digest=self.canonical_hash(self.review)

    def write(self):
        self.review_file.write_text(json.dumps(self.review,ensure_ascii=False,indent=2),
                                    encoding="utf-8")

    @staticmethod
    def canonical_hash(data):
        return hashlib.sha256(
            json.dumps(data,ensure_ascii=False,sort_keys=True,
                       separators=(",",":")).encode("utf-8")).hexdigest()

    def admit(self, digest=None):
        return pub.admit(ID,digest if digest is not None else self.digest,
                         "38839142468",index=self.index,directory=self.review_dir,
                         source_index=self.origin_index,source_dir=self.original_dir)

    def loaded(self):
        return public_registry(self.index,self.review_dir,
                               source_index=self.origin_index,source_dir=self.original_dir)

    def test_owner_only_review_is_admitted_exactly_once(self):
        first=self.admit()
        self.assertEqual(first["new_english_releases"],1)
        self.assertEqual(first["approved_paragraphs"],2)
        self.assertEqual(first["approved_cited_analysis_claims"],2)
        rows=self.loaded()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][0]["review_sha256"],self.digest)
        self.assertEqual(rows[0][0]["source_sha256"],SHA)
        again=self.admit()
        self.assertEqual(again["new_english_releases"],0)
        self.assertEqual(len(self.loaded()),1)
        self.assertFalse((self.root/"pla_watch.db").exists())

    def test_edited_pack_after_review_hash_is_not_automatically_published(self):
        self.review["analysis"]["claims"][0]["analysis_en"]="Edited after owner's approval."
        self.write()
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "owner_approved_review_sha_mismatch"):
            self.admit()
        self.assertEqual(self.loaded(),[])

    def test_explicitly_unreviewed_machine_packet_cannot_be_owner_promoted(self):
        self.review["review"]["status"]="machine_unreviewed"
        self.review["review"]["reviewer"]="unreviewed_machine_draft"
        for key in ("translation_semantics_checked","analysis_fact_checked",
                    "attribution_checked","source_limitations_checked"):
            self.review["review"][key]=False
        self.write()
        self.digest=self.canonical_hash(self.review)
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "editorial_attestation_missing"):
            self.admit()
        self.assertEqual(self.loaded(),[])

    def test_nonowner_review_json_fails_even_with_correct_packet_hash(self):
        self.review["review"]["reviewer"]="model_claiming_editor_authorization"
        self.write()
        self.digest=self.canonical_hash(self.review)
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "editorial_attestation_missing"):
            self.admit()

    def test_changed_published_translation_blocks_new_releases(self):
        self.admit()
        self.review["translations"][0]["text_en"]+=" (changed later)"
        self.write()
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "reviewed_pack_modified"):
            self.loaded()
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "reviewed_pack_modified"):
            self.admit()

    def test_manual_owner_dispatch_cannot_be_faked_by_pr(self):
        env={
            "GITHUB_EVENT_NAME":"pull_request",
            "GITHUB_REPOSITORY":"VSSpowerlifting/IndoPacificRecord",
            "GITHUB_REF":"refs/heads/main",
            "GITHUB_ACTOR":"VSSpowerlifting",
            "GITHUB_RUN_ID":"38839142468",
        }
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "owner_authenticated_dispatch_required"):
            pub.owner_event(env)
        env["GITHUB_EVENT_NAME"]="workflow_dispatch"
        env["GITHUB_ACTOR"]="untrusted-collaborator"
        with self.assertRaises(KoreaEnglishHold):
            pub.owner_event(env)
        env["GITHUB_ACTOR"]="VSSpowerlifting"
        self.assertEqual(pub.owner_event(env),"38839142468")


if __name__=="__main__":
    unittest.main()
