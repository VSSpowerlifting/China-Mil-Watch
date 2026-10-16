"""Adversarial standing Korea text autopublication contracts.

Only fake Korean bodies used, no live source downloads and no site writes.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.korea_published_originals import SCHEMA, read_release_index
from core.standing_source_rights import StandingLicenseHold, POLICIES
from scripts import admit_korea_standing_original_texts as sut

OLD_ID = "korea-policy:156784297"
NEW = "korea-policy:156990001"
SECOND = "korea-policy:156990002"
HELD = "korea-policy:156990003"
RAW = ("국방부의 공식 자료 원문입니다. 이 문서는 테스트 자료입니다.\n" * 12).encode()
BASE_IDS = {OLD_ID} | {"korea-policy:" + str(160000000 + i) for i in range(13)}
FROZEN_SHA = "0595f0fd29b769cbab5dd57c2ef57af174237a67"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def entry(identity, *, git=FROZEN_SHA, body=RAW, capture="c"*64, date="2026-10-16"):
    return {
        "source_identity": identity,
        "official_url": ("https://www.korea.kr/briefing/pressReleaseView.do?newsId="
                         + identity.split(":")[1]),
        "publisher_posted_date": date,
        "source_git_commit": git,
        "original_text_sha256": sha(body),
        "source_html_sha256": capture,
        "policy_sha256": "b"*64,
        "release_decision_sha256": "d"*64,
        "released_at_utc": "2026-10-16T02:15:00Z",
    }


class Adapter:
    def __init__(self, checkout, identity):
        self.source = {
            "desk": "korea", "source_family": "kr_policy_mnd_releases",
            "source_identity": identity,
            "official_url": entry(identity)["official_url"],
            "source_git_commit": "e"*40,
            "source_capture_sha256": "c"*64,
            "publisher_posted_date": "2026-10-06" if identity == OLD_ID else "2026-10-16",
            "language": "ko",
        }

    def read_original_text_private(self):
        return RAW

    def source_replay(self, source):
        return {
            "source_git_commit": source["source_git_commit"],
            "source_capture_sha256": source["source_capture_sha256"],
            "entire_clean_original_text_sha256": sha(RAW),
            "source_text_complete": True, "original_custody_authenticated": True,
        }

    def item_license_replay(self, source, license_kind):
        return license_kind == "KOGL_TYPE_1_TEXT"


class Exceptions:
    def __init__(self, adapter):
        self.adapter = adapter
        self.last_screen = None

    def __call__(self, source, policy):
        self.last_screen = {"third_party_indicators_present": source["source_identity"] == HELD}
        return {
            "first_party_official_text": True,
            "third_party_text_present": source["source_identity"] == HELD,
            "separate_terms_apply": False,
            "privacy_or_secrecy_exception": False,
            "released_artifact_embeds_media": False,
            "entire_source_text_version_sha256": sha(RAW),
        }


def policy(_):
    return {
        "publisher_policy_sha256": "b"*64,
        "observed_at_utc": "2026-10-16T02:15:00Z",
    }


def qualify(source, **kwargs):
    item = kwargs["exception_replay"](source, POLICIES["kr_policy_mnd_releases"])
    if item["third_party_text_present"]:
        raise StandingLicenseHold("source_item_excluded_by_rights_or_scope")
    if kwargs["proposed_sha256"] != sha(RAW):
        raise StandingLicenseHold("proposed_original_text_does_not_match_source")
    return {"original_text_matches_authenticated_capture": True}


class KoreaStandingAutoTextsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.index = self.root / "published.json"
        self.texts = self.root / "published"
        self.texts.mkdir()
        existing = entry(OLD_ID, date="2026-10-06")
        (self.texts / "156784297.txt").write_bytes(RAW)
        self.index.write_text(json.dumps({"schema": SCHEMA, "records": [existing]}))
        self.context = {"scope": sut.SCOPE, "run_id": "38830631398"}
        self.packet = {
            "source_git_commit": "e"*40,
            "source_original_count": 14,
            "records": [{"source_identity": ident, "publisher_posted_date": "2026-10-06",
                         "original_text_sha256": sha(RAW),
                         "editorial_exception": None} for ident in sorted(BASE_IDS)]
        }

    def run_admit(self, max_new=4):
        with patch.object(sut, "qualify_standing_text", side_effect=qualify):
            return sut.admit_eligible(
                self.root, index=self.index, original_dir=self.texts,
                context=self.context, max_new=max_new,
                adapter_type=Adapter, exception_type=Exceptions,
                policy_replay=policy, packet=self.packet,
                historical_ids=BASE_IDS, ancestor=lambda *_: True)

    def add(self, identity, hold=False):
        self.packet["records"].append({
            "source_identity": identity,
            "publisher_posted_date": "2026-10-16",
            "original_text_sha256": sha(RAW),
            "editorial_exception": "requires_editor" if hold else None})
        self.packet["source_original_count"] = len(self.packet["records"])

    def read(self):
        return read_release_index(self.index, self.texts)

    def test_frozen_fourteen_are_not_retroactively_published(self):
        result = self.run_admit()
        self.assertEqual(result["status"], "NO_NEW_FUTURE_KOREA_ORIGINALS")
        self.assertEqual(len(self.read()), 1)
        self.assertFalse((self.texts / "160000000.txt").exists())

    def test_first_future_record_auto_added_and_retry_idempotent(self):
        self.add(NEW)
        result = self.run_admit()
        self.assertEqual(result["new_original_texts"], 1)
        self.assertEqual({x["source_identity"] for x in self.read()}, {OLD_ID, NEW})
        self.assertEqual((self.texts / "156990001.txt").read_bytes(), RAW)
        again = self.run_admit()
        self.assertEqual(again["new_original_texts"], 0)
        self.assertEqual(len(self.read()), 2)
        self.assertFalse((self.root / "pla_watch.db").exists())

    def test_specific_editorial_hold_skips_without_stopping_other_new_source(self):
        self.add(SECOND, hold=True)
        self.add(NEW)
        result = self.run_admit()
        self.assertEqual(result["new_original_texts"], 1)
        self.assertEqual(result["held_candidates"], 1)
        self.assertFalse((self.texts / "156990002.txt").exists())

    def test_third_party_flag_blocks_one_record_only(self):
        self.add(HELD)
        self.add(NEW)
        result = self.run_admit()
        self.assertEqual(result["new_original_texts"], 1)
        self.assertEqual(result["held_candidates"], 1)
        self.assertFalse((self.texts / "156990003.txt").exists())

    def test_moving_previously_published_original_blocks_everything(self):
        self.add(NEW)
        with self.assertRaisesRegex(sut.AutoTextHold,
                                    "previously_published_korea_original_changed"):
            sut.admit_eligible(
                self.root, index=self.index, original_dir=self.texts,
                context=self.context, historical_ids=BASE_IDS,
                adapter_type=Adapter, packet=self.packet,
                ancestor=lambda *_: False)
        self.assertFalse((self.texts / "156990001.txt").exists())

    def test_source_archive_missing_frozen_baseline_fails_closed(self):
        self.packet["records"] = self.packet["records"][:-1]
        self.packet["source_original_count"] = 13
        with self.assertRaises(sut.AutoTextHold):
            self.run_admit()
        self.assertEqual(len(self.read()), 1)

    def test_missing_license_policy_blocks_new_source(self):
        self.add(NEW)
        with self.assertRaisesRegex(sut.AutoTextHold, "korea_current_policy_unverified"):
            sut.admit_eligible(
                self.root, index=self.index, original_dir=self.texts,
                context=self.context, adapter_type=Adapter,
                packet=self.packet, historical_ids=BASE_IDS,
                ancestor=lambda *_: True,
                policy_replay=lambda _: {})
        self.assertEqual(len(self.read()), 1)

    def test_batch_maximum_and_scope_enforced(self):
        self.add(NEW)
        self.add(SECOND)
        with self.assertRaisesRegex(sut.AutoTextHold,
                                    "automatic_korea_standing_context_invalid"):
            sut.admit_eligible(self.root, index=self.index, original_dir=self.texts,
                               context={"scope": "all_contents", "run_id": "123"},
                               packet=self.packet, historical_ids=BASE_IDS)
        result = self.run_admit(max_new=1)
        self.assertEqual(result["new_original_texts"], 1)
        self.assertEqual(len(self.read()), 2)

    def test_untrusted_context_not_authorized(self):
        env = {"GITHUB_REPOSITORY": "VSSpowerlifting/IndoPacificRecord",
               "GITHUB_REF": "refs/heads/main",
               "GITHUB_EVENT_NAME": "pull_request", "GITHUB_RUN_ID": "38830631398"}
        with self.assertRaisesRegex(sut.AutoTextHold, "automatic_korea_release_context_invalid"):
            sut.validate_standing_context(env)
        env["GITHUB_EVENT_NAME"] = "schedule"
        self.assertEqual(sut.validate_standing_context(env)["scope"], sut.SCOPE)


if __name__ == "__main__":
    unittest.main()
