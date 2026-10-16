"""No implicit original-publication permission; exact source/retry contracts."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import admit_korea_original_text as admit
from scripts import verify_korea_original_publication as verify
from core.korea_published_originals import read_release_index, render_original_body

ID = "korea-policy:156784297"
URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297"
TEXT = ("국방부 원문 비공개 가상 테스트. 정부 발표 내용은 확인되지 않았다.\n" * 12).encode("utf-8")
SHA = hashlib.sha256(TEXT).hexdigest()
EVENT = {"actor": "VSSpowerlifting", "repository": "VSSpowerlifting/IndoPacificRecord",
         "run_id": "38830631398", "scope": "korea_kogl_type1_verbatim_text_only"}


class Tests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.index = self.root / "published.json"
        self.index.write_text(json.dumps({
            "schema": "ipr-korea-public-original-text-index/1", "records": []}))
        self.originals = self.root / "korea_published_original_texts"
        self.source = {
            "desk": "korea", "source_family": "kr_policy_mnd_releases",
            "source_identity": ID, "official_url": URL,
            "source_git_commit": "a" * 40,
            "source_capture_sha256": "c" * 64,
            "publisher_posted_date": "2026-10-15", "language": "ko",
        }

    def _fake_replays(self):
        self_ref = self
        class Adapter:
            def __init__(self, checkout, identity):
                assert identity == ID
                self.source = self_ref.source
            def read_original_text_private(self):
                return TEXT
            def source_replay(self, source):
                return {"source_git_commit": source["source_git_commit"],
                        "source_capture_sha256": source["source_capture_sha256"],
                        "entire_clean_original_text_sha256": SHA,
                        "source_text_complete": True,
                        "original_custody_authenticated": True}
            def item_license_replay(self, source, kind):
                return True
        class Exceptions:
            def __init__(self, adapter):
                self.last_screen = {"none": True}
            def __call__(self, source, policy):
                return {"first_party_official_text": True,
                        "third_party_text_present": False,
                        "separate_terms_apply": False,
                        "privacy_or_secrecy_exception": False,
                        "released_artifact_embeds_media": False,
                        "entire_source_text_version_sha256": SHA}
        class Policy:
            def __call__(self, policy):
                return {"publisher_policy_sha256": "b" * 64}
        def contract(*args, **kwargs):
            assert kwargs["proposed_sha256"] == SHA
            return {"original_text_matches_authenticated_capture": True}
        return [patch.object(admit, "KoreaArchivedMarkAdapter", Adapter),
                patch.object(admit, "KoreaTextOnlyExceptionReplay", Exceptions),
                patch.object(admit, "CurrentKoreaPolicyReplay", Policy),
                patch.object(admit, "qualify_standing_text", contract)]

    def _admit(self, expected=SHA):
        with self._fake_replays()[0], self._fake_replays()[1], \
             self._fake_replays()[2], self._fake_replays()[3]:
            return admit.admit(self.root, ID, expected, owner_event=EVENT,
                               index=self.index, originals_dir=self.originals)

    def test_no_text_approval_from_generic_user_workflow_or_pull_request(self):
        env = {
            "GITHUB_EVENT_NAME": "pull_request", "GITHUB_ACTOR": "VSSpowerlifting",
            "GITHUB_REPOSITORY": "VSSpowerlifting/IndoPacificRecord",
            "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "38830631398",
        }
        with self.assertRaisesRegex(admit.OriginalAdmissionHold,
                                    "authenticated_owner_workflow_dispatch_required"):
            admit.check_owner_dispatch(env)
        env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        env["GITHUB_ACTOR"] = "another-user"
        with self.assertRaises(admit.OriginalAdmissionHold):
            admit.check_owner_dispatch(env)
        env["GITHUB_ACTOR"] = "VSSpowerlifting"
        self.assertEqual(admit.check_owner_dispatch(env)["actor"],
                         "VSSpowerlifting")

    def test_cannot_approve_unknown_source_or_text_sha(self):
        with self.assertRaisesRegex(admit.OriginalAdmissionHold,
                                    "requested_original_identity_or_sha_invalid"):
            admit.admit(self.root, ID + "wrong", SHA, owner_event=EVENT)
        with self.assertRaisesRegex(verify.ReleaseHold,
                                    "approved_identity_and_exact_text_sha_mismatch"):
            verify.validate_intent([
                {"source_identity": ID, "original_text_sha256": SHA}], ID, "0"*64)

    def test_real_writer_contract_produces_only_one_exact_text_and_index(self):
        result = self._admit()
        self.assertEqual(result["added_public_source_records"], 1)
        self.assertEqual(result["original_sha256"], SHA)
        self.assertFalse(result["publisher_assets_included"])
        rows = read_release_index(self.index, self.originals)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text_original"].encode("utf-8"), TEXT)
        self.assertEqual(rows[0]["release_decision_sha256"],
                         result["release_decision_sha256"])
        markup = render_original_body(rows[0])
        self.assertIn(URL, markup)
        self.assertNotIn("download.do", markup)
        self.assertFalse((self.root / "pla_watch.db").exists())
        self.assertFalse((self.root / "output").exists())

    def test_repeat_exact_owner_request_preserves_original_release(self):
        before = self._admit()
        later = self._admit()
        self.assertEqual(later["status"], "EXISTING_EXACT_ORIGINAL_VERIFIED")
        self.assertEqual(later["added_public_source_records"], 0)
        rows = read_release_index(self.index, self.originals)
        self.assertEqual(rows[0]["release_decision_sha256"],
                         before["release_decision_sha256"])

    def test_wrong_exact_source_sha_fails_before_public_files(self):
        with self.assertRaisesRegex(admit.OriginalAdmissionHold,
                                    "owner_approved_original_sha_does_not_match"):
            self._admit("f" * 64)
        self.assertFalse(self.originals.exists())
        self.assertEqual([], read_release_index(self.index, self.originals))


if __name__ == "__main__":
    unittest.main()
