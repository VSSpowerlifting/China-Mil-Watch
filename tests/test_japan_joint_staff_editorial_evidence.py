"""Offline evidence contracts for the Japan Joint Staff PDF research-note lane.

The single public URL in the positive fixture is a first-party publisher original
independently inspected on 2026-10-13; format validation is not source approval.
No network, source-body fetch, model call, database change or email.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import (
    EditorialEvidenceError, evidence_prompt, load_editorial_evidence,
)


SAT = "2026-10-17"
URL = "https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf"


def source():
    return {
        "id": "JP-W42-07",
        "desk": "japan",
        "source_name": "Japan Joint Staff",
        "source_url": URL,
        "published_date": "2026-10-13",
        "language": "ja",
        "title_original": "中国軍機の動向について",
        "source_kind": "official-publisher-page-reviewed-for-research",
        "state_commit": None,
        "source_content_sha256": None,
        "hash_rule": None,
        "summary": (
            "On October 13, Japan's Joint Staff reported that a single Chinese "
            "military Y-9 intelligence-collection aircraft flew over the East "
            "China Sea and that Japanese Air Self-Defense Force fighters scrambled."
        ),
        "caveats": [
            "This is a single institutional report, not an independent flight confirmation.",
            "No airspace violation, completed interception, or hostile encounter is established.",
        ],
        "topics": ["maritime_security"],
        "status": "unapproved-source-linked-editorial-candidate",
        "copy_scope": "private-model-drafting-only-no-source-body",
    }


def load(*items):
    with tempfile.TemporaryDirectory() as d:
        folder = Path(d)
        (folder / (SAT + ".json")).write_text(json.dumps({
            "schema": "ipr-private-drafting-evidence/1",
            "week_ending": SAT,
            "status": "unapproved-source-linked-editorial-candidate",
            "items": list(items),
        }, ensure_ascii=False), encoding="utf-8")
        return load_editorial_evidence(SAT, SAT, directory=folder)


class JapanJointStaffEditorialTests(unittest.TestCase):
    def test_real_dated_publisher_url_can_be_private_research_only(self):
        checked = load(source())
        self.assertEqual(len(checked), 1)
        self.assertEqual(checked[0]["source_url"], URL)
        self.assertEqual(checked[0]["state_commit"], None)
        prompt = evidence_prompt(checked)
        self.assertIn('id="JP-W42-07" desk="japan"', prompt)
        self.assertIn(URL, prompt)
        self.assertNotIn("text_original", prompt)

    def test_publisher_identity_and_pdf_path_are_exact(self):
        invalid = (
            "https://www.mod.go.jp.evil.test/js/pdf/2026/p20261013_01.pdf",
            "http://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf",
            "https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf?download=1",
            "https://www.mod.go.jp/j/press/news/2026/10/13a.pdf",
            "https://www.mod.go.jp/js/pdf/2026/p20261013_01.html",
            "https://www.mod.go.jp/js/pdf/2026/../press/a.pdf",
            "https://www.mod.go.jp/js/pdf/2025/p20261013_01.pdf",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(EditorialEvidenceError):
                entry = source()
                entry["source_url"] = url
                load(entry)

    def test_source_date_is_bound_to_filename_and_reporting_week(self):
        for changed in (
            {"published_date": "2026-10-12"},
            {"source_url": "https://www.mod.go.jp/js/pdf/2026/p20261012_01.pdf"},
            {"id": "JP-W41-07"},
            {"published_date": "2026-10-18",
             "source_url": "https://www.mod.go.jp/js/pdf/2026/p20261018_01.pdf"},
        ):
            with self.subTest(changed=changed), self.assertRaises(EditorialEvidenceError):
                entry = source()
                entry.update(changed)
                load(entry)

    def test_japanese_joint_staff_identity_not_conflated_with_mod_or_jcg(self):
        for changed in (
            {"source_name": "Japan Ministry of Defense"},
            {"source_name": "Japan Coast Guard"},
            {"language": "en"},
            {"desk": "china"},
        ):
            with self.subTest(changed=changed), self.assertRaises(EditorialEvidenceError):
                entry = source()
                entry.update(changed)
                load(entry)

    def test_not_a_verified_shadow_capture_or_approved_source(self):
        for changed in (
            {"source_kind": "shadow-extracted-original",
             "state_commit": "a" * 40,
             "source_content_sha256": "b" * 64,
             "hash_rule": "sha256-text-original-utf8"},
            {"state_commit": "a" * 40},
            {"source_content_sha256": "b" * 64},
            {"status": "approved"},
            {"copy_scope": "approved-for-publication"},
            {"text_original": "A copied publisher body should never be in a private note."},
        ):
            with self.subTest(changed=changed), self.assertRaises(EditorialEvidenceError):
                entry = source()
                entry.update(changed)
                load(entry)

    def test_duplicate_source_identity_or_url_is_rejected(self):
        duplicate = copy.deepcopy(source())
        with self.assertRaises(EditorialEvidenceError):
            load(source(), duplicate)
        duplicate["id"] = "JP-W42-08"
        with self.assertRaises(EditorialEvidenceError):
            load(source(), duplicate)

    def test_joint_staff_note_reaches_existing_private_no_send_handoff(self):
        # Test the *shape* of the source-linked handoff, not a model call,
        # publication or publisher rights approval. The writer is mocked.
        from scripts.sunday_editorial_handoff import main
        from tests.test_briefs_editorial_evidence import scaffold, valid_manuscript

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            packet = folder / (SAT + ".json")
            packet.write_text(json.dumps({
                "schema": "ipr-private-drafting-evidence/1",
                "week_ending": SAT,
                "status": "unapproved-source-linked-editorial-candidate",
                "items": [source()],
            }, ensure_ascii=False), encoding="utf-8")
            sidecar = scaffold()
            sidecar["week_start"] = "2026-10-11"
            sidecar["week_ending"] = SAT
            sidecar_path = folder / "scaffold.json"
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
            preview = folder / "no-send-preview.txt"
            proposed = valid_manuscript()
            proposed["editorial_focus"] = (
                "Distinguish what the Japanese government reported from independently "
                "established flight behavior, without asserting a territorial violation."
            )
            proposed["supplemental_citations"] = {
                field: [] for field in proposed["citations"]
            }
            proposed["supplemental_citations"]["cross_desk_comparison"] = [
                "JP-W42-07"
            ]
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=proposed) as writer, \
                 patch("scripts.sunday_editorial_handoff.send_packet") as send:
                main([
                    "--sidecar", str(sidecar_path),
                    "--out", str(preview),
                    "--write-automatic", "--full-week", "--include-research",
                    "--research-packet", str(packet), "--as-of", SAT,
                ])
            writer.assert_called_once()
            self.assertEqual(
                writer.call_args.kwargs["supplemental"][0]["source_url"], URL)
            self.assertIn("External source JP-W42-07",
                          preview.read_text(encoding="utf-8"))
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
