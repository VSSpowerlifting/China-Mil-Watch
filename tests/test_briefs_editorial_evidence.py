"""No-network regression checks for unified Japan/Vietnam model evidence.

Real weekly data is compared to its original source packets, while actual model
responses, SMTP, production database access and source fetches are mocked.
Nothing in this suite counts as human approval of a source.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.brief_editorial_evidence import (
    EditorialEvidenceError, load_editorial_evidence, evidence_prompt,
)
from scripts.weekly_briefs_auto_writer import (
    compose, validate_manuscript, writing_schema,
)
from scripts.weekly_editorial_handoff import main, render_packet
from scripts.validate_editorial_return import (
    ReturnValidationError, validate_return,
)
from tests.test_weekly_briefs_auto_writer import evidence, valid_manuscript
from tests.test_weekly_editorial_handoff import draft as friday_fixture

SAT = "2026-10-10"
FRI = "2026-10-09"
ROOT = Path(__file__).resolve().parents[1]


def packet():
    return json.loads((ROOT / "research/briefs_editorial_evidence" /
                       (SAT + ".json")).read_text(encoding="utf-8"))


def manuscript():
    m = valid_manuscript()
    m["editorial_focus"] = (
        "Official accounts of regional security cooperation and capacity")
    m["supplemental_citations"] = {
        name: [] for name in m["citations"]
    }
    m["citations"]["cross_desk_comparison"] = [1]
    m["supplemental_citations"]["cross_desk_comparison"] = ["JP-W41-01"]
    m["supplemental_citations"]["why_it_matters"] = ["VN-MPS-1791199100"]
    m["citations"]["why_it_matters"] = []
    return m


def scaffold():
    x = friday_fixture()
    x["week_start"] = "2026-10-04"
    x["week_ending"] = SAT
    return x


class RealResearchEvidenceTests(unittest.TestCase):
    def test_exact_october_ten_packet_has_japan_and_vietnam(self):
        rows = load_editorial_evidence(SAT, SAT)
        self.assertEqual(len(rows), 5)
        self.assertEqual({x["desk"] for x in rows}, {"japan", "vietnam"})
        self.assertEqual(load_editorial_evidence(SAT, FRI), rows)
        self.assertEqual(load_editorial_evidence("2026-10-17", "2026-10-17"), [])
        self.assertEqual({x["status"] for x in rows},
                         {"unapproved-source-linked-editorial-candidate"})
        self.assertTrue(all("text_original" not in x for x in rows))
        self.assertTrue(all(x["copy_scope"].startswith("private-") for x in rows))

    def test_source_pins_reconcile_with_existing_country_review_packets(self):
        data = packet()["items"]
        vn = json.loads((ROOT / "research/vietnam_briefs_candidates" /
                         (SAT + ".json")).read_text(encoding="utf-8"))
        jp = json.loads((ROOT / "research/japan/friday_2026-10-09" /
                         "official_source_candidates.json").read_text(encoding="utf-8"))
        for item in data:
            if item["desk"] == "vietnam":
                matching = [x for x in vn["candidates"]
                            if item["id"].endswith(x["source_identity"].split(":")[1])]
                self.assertEqual(len(matching), 1)
                record = matching[0]
                self.assertEqual(item["source_url"], record["canonical_url"])
                self.assertEqual(item["published_date"], record["published_date"])
                self.assertEqual(item["title_original"], record["original_title"])
                self.assertEqual(item["body_sha256"], record["content_sha256"])
                self.assertEqual(item["state_commit"], vn["state_commit"])
            elif item["source_kind"] == "shadow-extracted-original":
                original = jp["shadow_current_week_original"]
                self.assertEqual(item["source_url"], original["source_url"])
                self.assertEqual(item["title_original"], original["title_original"])
                self.assertEqual(item["state_commit"],
                                 original["historical_state_commit"])
                self.assertEqual(item["body_sha256"],
                                 original["extracted_body_sha256"])
            else:
                matching = [x for x in jp["source_candidates"]
                            if x["candidate_id"] == item["id"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(item["source_url"],
                                 matching[0]["public_source_url"])
                self.assertEqual(item["published_date"],
                                 matching[0]["publisher_date"])

    def test_provenance_prompt_contains_no_copied_source_body(self):
        prompt = evidence_prompt(load_editorial_evidence(SAT, SAT))
        self.assertIn('id="JP-W41-01"', prompt)
        self.assertIn('id="VN-MPS-1791199100"', prompt)
        self.assertIn("Short, unapproved, source-attributed research synopsis", prompt)
        self.assertNotIn("<source_record id=", prompt)

    def test_wrong_cutoffs_fail_and_future_weeks_not_backfilled(self):
        for saturday, cutoff in [(SAT, "2026-10-08"),
                                 (SAT, "2026-10-11"),
                                 ("2026-10-09", FRI)]:
            with self.subTest(saturday=saturday, cutoff=cutoff):
                with self.assertRaises(EditorialEvidenceError):
                    load_editorial_evidence(saturday, cutoff)

    def test_source_packet_rejects_injected_body_fake_approval_and_bad_url(self):
        cases = [
            ("article_body", "copied original source text"),
            ("human_review", {"approved": True}),
        ]
        for field, value in cases:
            data = packet()
            data["items"][0][field] = value
            with self.subTest(field=field), self.assertRaises(EditorialEvidenceError):
                self.load_data(data)
        for url in ("https://www.mod.go.jp.evil.example/j/a.html",
                    "http://www.mod.go.jp/en/article/a.html",
                    "https://www.mod.go.jp:bad/en/article/a.html",
                    "https://www.mod.go.jp/en/article/a.html#fragment"):
            data = packet()
            data["items"][0]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(EditorialEvidenceError):
                self.load_data(data)

    def test_invalid_hash_duplicate_identity_and_out_of_window(self):
        for field, value in (("body_sha256", "b" * 63),
                             ("state_commit", "f" * 39),
                             ("published_date", "2026-10-03"),
                             ("status", "approved")):
            data = packet()
            item = next(x for x in data["items"]
                        if x["id"] == "VN-MPS-1791199100")
            item[field] = value
            with self.subTest(field=field), self.assertRaises(EditorialEvidenceError):
                self.load_data(data)
        data = packet()
        data["items"].append(copy.deepcopy(data["items"][0]))
        with self.assertRaises(EditorialEvidenceError):
            self.load_data(data)

    def load_data(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / (SAT + ".json")).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return load_editorial_evidence(SAT, SAT, directory=d)


class UnifiedWriterTests(unittest.TestCase):
    def setUp(self):
        self.research = load_editorial_evidence(SAT, SAT)

    def test_supplemental_schema_never_uses_numeric_pseudo_records(self):
        schema = writing_schema([1, 2], supplemental_ids=[
            item["id"] for item in self.research])
        props = schema["properties"]
        self.assertEqual(props["citations"]["properties"]["opening_note"]["minItems"], 0)
        self.assertEqual(props["supplemental_citations"]["properties"]
                         ["opening_note"]["items"]["type"], "string")
        self.assertIn("editorial_focus", schema["required"])
        with self.assertRaises(ValueError):
            writing_schema([1, 2], supplemental_ids=["42"])

    def test_two_desks_can_be_one_production_one_research_in_private_draft(self):
        result = manuscript()
        self.assertIs(validate_manuscript(
            result, evidence(), supplemental=self.research), result)
        result = manuscript()
        result["supplemental_citations"]["cross_desk_comparison"] = []
        with self.assertRaisesRegex(ValueError, "both desks"):
            validate_manuscript(result, evidence(), supplemental=self.research)

    def test_unverified_external_and_empty_section_citations_rejected(self):
        result = manuscript()
        result["supplemental_citations"]["why_it_matters"] = ["JP-FAKE-2026"]
        with self.assertRaisesRegex(ValueError, "external source ids"):
            validate_manuscript(result, evidence(), supplemental=self.research)
        result = manuscript()
        result["supplemental_citations"]["why_it_matters"] = []
        with self.assertRaisesRegex(ValueError, "neither production nor external"):
            validate_manuscript(result, evidence(), supplemental=self.research)

    def test_unified_model_prompt_and_schema_offer_evidence_once(self):
        response = SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", name="compose_editorial_draft",
                            input=manuscript())])
        params = []
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: (
            params.append(kw), nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]))
        x = scaffold()
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence",
                   return_value=evidence()):
            result = compose(x, SAT, client=fake, supplemental=self.research)
        self.assertEqual(result["editorial_focus"], manuscript()["editorial_focus"])
        self.assertEqual(len(params), 1)
        sent = params[0]["messages"][0]["content"]
        self.assertIn("ONE cohesive article", sent)
        self.assertIn("SUPPLEMENTAL OFFICIAL-SOURCE RESEARCH", sent)
        self.assertIn("VN-MPS-1791199100", sent)
        self.assertIn("JP-W41-01", sent)
        self.assertIn("do NOT shoehorn", sent.replace("Do NOT shoehorn", "do NOT shoehorn"))

    def test_packet_is_one_editable_article_and_immutable_source_trail(self):
        r = manuscript()
        packet_text = render_packet(
            scaffold(), manuscript=r, as_of=SAT,
            research_evidence=self.research)
        self.assertEqual(packet_text.count("=== EDITABLE MANUSCRIPT ==="), 1)
        self.assertIn("## EDITORIAL FOCUS", packet_text)
        self.assertIn("EXTERNAL SOURCE IDS: JP-W41-01", packet_text)
        self.assertIn("EXTERNAL SOURCE IDS: VN-MPS-1791199100", packet_text)
        self.assertIn("External source JP-W41-01 | japan", packet_text)
        self.assertNotIn("=== VIETNAM SHADOW CANDIDATES", packet_text)
        edit = packet_text.replace(
            "Official statements around a concrete development",
            "Official accounts of regional cooperation reviewed for clarity", 1)
        valid = validate_return(packet_text, edit)
        self.assertEqual(valid["external_sources"], 5)
        self.assertEqual(valid["source_records"], 2)
        for altered in (
            edit.replace("EXTERNAL SOURCE IDS: JP-W41-01",
                         "EXTERNAL SOURCE IDS: JP-FAKE-01", 1),
            edit.replace("External source JP-W41-01 |",
                         "External source JP-W41-99 |", 1),
        ):
            with self.subTest(altered=altered[:80]):
                with self.assertRaises(ReturnValidationError):
                    validate_return(packet_text, altered)

    def test_main_sunday_dry_run_writes_one_packet_and_no_email(self):
        sidecar = scaffold()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sidecar.json"
            dest = Path(tmp) / "one-article.txt"
            p.write_text(json.dumps(sidecar), encoding="utf-8")
            with patch("scripts.weekly_briefs_auto_writer.compose",
                       return_value=manuscript()) as writer, \
                 patch("scripts.weekly_editorial_handoff.send_packet") as mail:
                main(["--sidecar", str(p), "--out", str(dest),
                      "--write-automatic", "--full-week",
                      "--include-research", "--as-of", SAT])
            self.assertTrue(dest.is_file())
            self.assertIn("## EDITORIAL FOCUS", dest.read_text(encoding="utf-8"))
            self.assertIn("EXTERNAL SOURCE IDS:", dest.read_text(encoding="utf-8"))
            self.assertEqual(writer.call_args.kwargs["supplemental"],
                             self.research)
            mail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
