"""Offline tests for ordinary Sunday research contributions from additional desks.

All 2026-10-17 publisher URLs in this suite are synthetic path fixtures, not
claims that these particular pages were published. No networking or mail.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import (
    EditorialEvidenceError, load_editorial_evidence, evidence_prompt,
)
from scripts.sunday_editorial_handoff import main
from scripts.validate_editorial_return import validate_return, ReturnValidationError
from tests.test_briefs_editorial_evidence import (
    packet as original_packet, scaffold, manuscript,
)

SAT = "2026-10-17"
DAY = "2026-10-12"


def item(desk):
    example = copy.deepcopy(original_packet()["items"][0])
    example.update({
        "published_date": DAY,
        "source_kind": "official-publisher-page-reviewed-for-research",
        "state_commit": None,
        "source_content_sha256": None,
        "hash_rule": None,
        "summary": (
            "An independently written test-only synopsis records the reported "
            "government action without asserting a completed operation, final "
            "policy decision, or corroboration beyond the attributed notice."
        ),
        "caveats": [
            "Check the actual original before offering this synopsis to a model.",
            "A reported or planned activity is not proof of completion.",
        ],
        "topics": ["maritime_security"],
    })
    details = {
        "philippines": (
            "PH-AFP-W42-01", "Armed Forces of the Philippines",
            "https://www.afp.mil.ph/news/synthetic-official-press-release",
            "en", "Synthetic AFP publication used only in an offline test",
        ),
        "indonesia": (
            "ID-KEMHAN-W42-01", "Indonesia Ministry of Defense",
            "https://www.kemhan.go.id/2026/10/12/synthetic-official-press-release.html",
            "id", "Contoh berita Kemhan untuk pengujian offline saja",
        ),
        "japan": (
            "JP-W42-01", "Japan Coast Guard",
            "https://www.kaiho.mlit.go.jp/e/topics_archive/article999999.html",
            "en", "Synthetic Japan Coast Guard notice used only in a test",
        ),
    }
    ident, source, url, language, title = details[desk]
    example.update({
        "id": ident, "desk": desk, "source_name": source,
        "source_url": url, "language": language, "title_original": title,
    })
    return example


def packet(*items):
    return {
        "schema": "ipr-private-drafting-evidence/1",
        "week_ending": SAT,
        "status": "unapproved-source-linked-editorial-candidate",
        "items": list(items),
    }


def load(data):
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        (directory / (SAT + ".json")).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return load_editorial_evidence(SAT, SAT, directory=directory)


class AdditionalDeskEditorialTests(unittest.TestCase):
    def test_new_families_are_ordinary_typed_research_evidence(self):
        rows = load(packet(item("philippines"), item("indonesia"),
                           item("japan")))
        self.assertEqual({r["desk"] for r in rows},
                         {"philippines", "indonesia", "japan"})
        self.assertEqual({r["source_kind"] for r in rows},
                         {"official-publisher-page-reviewed-for-research"})
        prompt = evidence_prompt(rows)
        for ident in ("PH-AFP-W42-01", "ID-KEMHAN-W42-01", "JP-W42-01"):
            self.assertIn('id="' + ident + '"', prompt)
        self.assertNotIn("text_original", prompt)

    def test_wrong_official_host_path_or_issuer_cannot_enter(self):
        cases = [
            ("philippines", "source_url",
             "https://www.afp.mil.ph.bad.test/news/article"),
            ("philippines", "source_url", "https://www.afp.mil.ph/news"),
            ("philippines", "source_name", "National Security Council"),
            ("indonesia", "source_url",
             "https://www.kemhan.go.id/2026/10/12/../press.html"),
            ("indonesia", "source_url",
             "https://www.kemhan.go.id/2026/10/13/synthetic-official-press-release.html"),
            ("japan", "source_url",
             "https://www.kaiho.mlit.go.jp.evil.test/e/topics_archive/article22.html"),
            ("japan", "source_name", "Japan Ministry of Defense"),
            ("japan", "language", "ja"),
        ]
        for desk, key, value in cases:
            with self.subTest(desk=desk, key=key, value=value):
                candidate = item(desk)
                candidate[key] = value
                with self.assertRaises(EditorialEvidenceError):
                    load(packet(candidate))

    def test_week_source_identity_and_body_controls(self):
        for desk in ("philippines", "indonesia"):
            with self.subTest(desk=desk, fail="wrong week"):
                candidate = item(desk)
                candidate["id"] = candidate["id"].replace("W42", "W41")
                with self.assertRaises(EditorialEvidenceError):
                    load(packet(candidate))
            with self.subTest(desk=desk, fail="not this week"):
                candidate = item(desk)
                candidate["published_date"] = "2026-10-10"
                with self.assertRaises(EditorialEvidenceError):
                    load(packet(candidate))
            with self.subTest(desk=desk, fail="fake original body"):
                candidate = item(desk)
                candidate["text_original"] = "unapproved copied article"
                with self.assertRaises(EditorialEvidenceError):
                    load(packet(candidate))
            with self.subTest(desk=desk, fail="unknown capture hash"):
                candidate = item(desk)
                candidate["source_kind"] = "shadow-extracted-original"
                candidate["state_commit"] = "a" * 40
                candidate["source_content_sha256"] = "a" * 64
                candidate["hash_rule"] = "sha256-text-original-utf8"
                with self.assertRaises(EditorialEvidenceError):
                    load(packet(candidate))
        with self.assertRaises(EditorialEvidenceError):
            load(packet(item("philippines"), item("philippines")))

    def test_jcg_unreviewed_shadow_hash_cannot_be_assumed(self):
        candidate = item("japan")
        candidate.update({
            "source_kind": "shadow-extracted-original",
            "state_commit": "b" * 40,
            "source_content_sha256": "b" * 64,
            "hash_rule": "sha256-text-original-utf8",
        })
        with self.assertRaises(EditorialEvidenceError):
            load(packet(candidate))

    def test_private_rehearsal_uses_existing_writer_and_never_sends(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            input_path = directory / (SAT + ".json")
            input_path.write_text(
                json.dumps(packet(item("philippines"), item("indonesia"))),
                encoding="utf-8")
            sidecar = scaffold()
            sidecar["week_start"] = "2026-10-11"
            sidecar["week_ending"] = SAT
            sidecar_path = directory / "sidecar.json"
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
            output = directory / "one-brief.txt"
            prose = manuscript()
            prose["supplemental_citations"]["cross_desk_comparison"] = [
                "PH-AFP-W42-01"
            ]
            prose["supplemental_citations"]["why_it_matters"] = [
                "ID-KEMHAN-W42-01"
            ]
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=prose) as writer, \
                 patch("scripts.sunday_editorial_handoff.send_packet") as mail:
                main([
                    "--sidecar", str(sidecar_path), "--out", str(output),
                    "--write-automatic", "--full-week", "--include-research",
                    "--research-packet", str(input_path), "--as-of", SAT,
                ])
            self.assertEqual(
                {r["desk"] for r in writer.call_args.kwargs["supplemental"]},
                {"philippines", "indonesia"})
            self.assertIn("External source PH-AFP-W42-01",
                          output.read_text(encoding="utf-8"))
            self.assertIn("External source ID-KEMHAN-W42-01",
                          output.read_text(encoding="utf-8"))
            mail.assert_not_called()
            # Dylan's ordinary return validator must accept both new typed
            # citation families without any new public article label.
            original = output.read_text(encoding="utf-8")
            edited = original.replace(
                "Official statements around a concrete development",
                "Official developments independently reviewed for editorial clarity", 1)
            receipt = validate_return(original, edited)
            self.assertEqual(receipt["external_sources"], 2)
            with self.assertRaises(ReturnValidationError):
                validate_return(original, edited.replace(
                    "External source PH-AFP-W42-01 |",
                    "External source PH-AFP-W42-99 |", 1))


if __name__ == "__main__":
    unittest.main()
