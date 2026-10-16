"""Korea reviewed English translation / analytical source-trail security."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.korea_full_content_rehearsal import original_paragraphs
from core.korea_english_publication import (
    SCHEMA, REGISTER, KoreaEnglishHold, verify_review, public_registry,
    render_translation, render_analysis,
)
from scripts import draft_korea_english_analysis as draft

ID="korea-policy:156784297"
TEXT=("국방부는 올해 연합훈련 일정을 발표했다. 군은 세부 내용을 추후 공개할 예정이다.\n"
      "정부는 이번 발표가 일정에 관한 설명이라고 밝혔다. 관련 국가는 따로 확인하지 않았다.")
SHA=hashlib.sha256(TEXT.encode()).hexdigest()


def make_source():
    return {
        "source_identity":ID,
        "original_text_sha256":SHA,
        "official_url":"https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297",
        "text_original":TEXT,
    }


def make_review():
    source=make_source()
    ko=original_paragraphs(TEXT)
    return {
        "schema":SCHEMA, "source_identity":ID, "source_sha256":SHA,
        "model_id":"claude-sonnet-4-6",
        "translations":[
            {"index":1,"original_sha256":hashlib.sha256(ko[0].encode()).hexdigest(),
             "text_en":"The ministry reported a schedule for combined military exercises."},
            {"index":2,"original_sha256":hashlib.sha256(ko[1].encode()).hexdigest(),
             "text_en":"The government described the notice as a schedule announcement."},
        ],
        "analysis":{
            "heading_en":"Limits of the ministry's exercise announcement",
            "thesis_en":"The statement establishes an official announcement but not whether activities occurred.",
            "claims":[
                {"heading_en":"An announcement, not evidence of execution",
                 "analysis_en":"The ministry describes scheduling. The text does not prove training occurred.",
                 "source_indices":[1],
                 "source_quotes_ko":["연합훈련 일정을 발표했다"],
                 "assessment_type":"bounded_analytical_inference"},
                {"heading_en":"Verification remains source-dependent",
                 "analysis_en":"The government explicitly frames the release as a statement about the timetable.",
                 "source_indices":[2],
                 "source_quotes_ko":["일정에 관한 설명이라고 밝혔다"],
                 "assessment_type":"attributed_source_interpretation"},
            ],
            "limitations_en":"No independently corroborating operational record was provided in this single release."
        },
        "review":{
            "status":"editor_approved","reviewer":"VSSpowerlifting",
            "reviewed_at_utc":"2026-10-16T02:00:00Z",
            "translation_semantics_checked":True,
            "analysis_fact_checked":True,
            "attribution_checked":True,
            "source_limitations_checked":True,
        }
    }


class ReviewTests(unittest.TestCase):
    def test_fully_source_pinned_structure_can_be_rendered(self):
        review=make_review()
        attestation=verify_review(review,make_source())
        self.assertEqual(attestation["paragraphs"],2)
        self.assertEqual(attestation["claims"],2)
        self.assertFalse(attestation["editorial_meaning_verified_by_code"])
        a=render_translation({},review,make_source())
        b=render_analysis({},review,make_source())
        self.assertIn("Korean original",a)
        self.assertIn("claims attributed",b.lower())
        self.assertIn("연합훈련",b)
        self.assertIn("Limits of the evidence",b)

    def test_editor_approved_pages_have_ipr_shell_and_public_canonical(self):
        review, source = make_review(), make_source()
        for kind, renderer, route in (
            ("translation", render_translation,
             "korea-translations/156784297.html"),
            ("analysis", render_analysis,
             "korea-analysis/156784297.html"),
        ):
            with self.subTest(page=kind):
                html = renderer({}, review, source)
                url = "https://indopacificrecord.org/" + route
                self.assertIn('class="masthead', html)
                self.assertIn('<footer class="site">', html)
                self.assertIn('href="#main"', html)
                self.assertIn('id="main"', html)
                self.assertIn('<meta name="description" content="Official defense and security texts, preserved as published and analyzed in context.">', html)
                self.assertIn('<link rel="canonical" href="' + url + '">', html)
                self.assertIn('<meta property="og:url" content="' + url + '">', html)
                self.assertNotIn('content="noindex, nofollow"', html)
                self.assertIn(source["original_text_sha256"], html)
                self.assertNotIn("<iframe", html)
                self.assertNotIn(".hwpx", html)

    def test_private_english_pages_remain_noindex_and_source_escaped(self):
        review, source = make_review(), make_source()
        review["translations"][0]["text_en"] = '<script>bad()</script>'
        for renderer in (render_translation, render_analysis):
            with self.subTest(renderer=renderer.__name__):
                html = renderer({}, review, source, site_origin=None)
                self.assertIn('content="noindex, nofollow"', html)
                self.assertNotIn('rel="canonical"', html)
                self.assertNotIn('property="og:url"', html)
                self.assertNotIn("<script>", html)
                self.assertNotIn(".hwpx", html)
        self.assertIn("&lt;script&gt;", render_translation({}, review, source,
                                                          site_origin=None))

    def test_reviewed_page_cannot_be_indexed_at_unapproved_origin(self):
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "korea_english_page_origin_unrecognized"):
            render_translation({}, make_review(), make_source(),
                               site_origin="https://example.invalid")
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "korea_english_page_origin_unrecognized"):
            render_analysis({}, make_review(), make_source(),
                            site_origin="https://example.invalid")

    def test_editor_review_required_for_public(self):
        r=make_review()
        r["review"]["status"]="machine_unreviewed"
        r["review"]["reviewer"]="unreviewed_machine_draft"
        for key in ("translation_semantics_checked","analysis_fact_checked",
                    "attribution_checked","source_limitations_checked"):
            r["review"][key]=False
        with self.assertRaisesRegex(KoreaEnglishHold,"editorial_attestation_missing"):
            verify_review(r,make_source())
        self.assertTrue(verify_review(r,make_source(),allow_machine=True)["machine_only"])

    def test_missing_second_paragraph_translation_blocks_publication(self):
        r=make_review()
        r["translations"].pop()
        with self.assertRaisesRegex(KoreaEnglishHold,"paragraph_count_mismatch"):
            verify_review(r,make_source())

    def test_reordered_paragraph_cannot_pass_exact_hash(self):
        r=make_review()
        r["translations"][0],r["translations"][1]=r["translations"][1],r["translations"][0]
        with self.assertRaisesRegex(KoreaEnglishHold,"translation_alignment_invalid"):
            verify_review(r,make_source())

    def test_changed_original_hash_blocks_both_outputs(self):
        r=make_review()
        with self.assertRaisesRegex(KoreaEnglishHold,"source_version_mismatch"):
            verify_review(r,{**make_source(),"original_text_sha256":"a"*64})

    def test_citation_quote_must_exist_in_its_exact_source_paragraph(self):
        r=make_review()
        r["analysis"]["claims"][0]["source_quotes_ko"]=["전혀 존재하지 않는 출처 인용"]
        with self.assertRaisesRegex(KoreaEnglishHold,"quote_not_exact_source"):
            verify_review(r,make_source())

    def test_unknown_claim_evidence_indices_rejected(self):
        r=make_review()
        r["analysis"]["claims"][0]["source_indices"]=[3]
        with self.assertRaisesRegex(KoreaEnglishHold,"claim_indices_invalid"):
            verify_review(r,make_source())

    def test_unattributed_claims_or_invalid_status_are_held(self):
        r=make_review()
        r["analysis"]["claims"][0]["assessment_type"]="independently_confirmed"
        with self.assertRaisesRegex(KoreaEnglishHold,"unsupported_analysis_type"):
            verify_review(r,make_source())

    def test_malicious_html_is_escaped_both_pages(self):
        r=make_review()
        r["translations"][0]["text_en"]="<script>evil()</script> official claim"
        r["analysis"]["claims"][0]["analysis_en"]="<img src=x onerror=alert(1)> No independent proof."
        verify_review(r,make_source())
        tr=render_translation({},r,make_source())
        an=render_analysis({},r,make_source())
        self.assertNotIn("<script>",tr)
        self.assertNotIn("<img ",an)
        self.assertIn("&lt;script&gt;",tr)
        self.assertIn("&lt;img ",an)

    def test_approved_registry_empty_is_inert(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            index=base/"index.json"
            index.write_text(json.dumps({"schema":REGISTER,"releases":[]}))
            self.assertEqual(public_registry(index,base),[])

    def test_nonregistered_machine_draft_cannot_be_promoted_by_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            index=base/"english_index.json"
            number=ID.split(":")[1]
            review=make_review()
            p=base/(number+".json")
            p.write_text(json.dumps(review,ensure_ascii=False))
            index.write_text(json.dumps({"schema":REGISTER,"releases":[{
                "source_identity":ID,"source_sha256":SHA,
                "review_sha256":"0"*64,"owner_run_id":"38839142468",
                "released_at_utc":"2026-10-16T02:15:00Z",
            }]}))
            # Source index is deliberately empty: a fake reviewed file cannot
            # bootstrap a source original that isn't separately published.
            original_index=base/"original_index.json"
            original_index.write_text('{"schema":"ipr-korea-public-original-text-index/1","records":[]}')
            with self.assertRaisesRegex(KoreaEnglishHold,
                                        "publication_source_not_published"):
                public_registry(index,base,source_index=original_index,
                                source_dir=base)

    def test_model_json_accepts_only_complete_object_or_single_fence(self):
        self.assertEqual(draft._exact_model_json('{"translations":[]}'),
                         {"translations":[]})
        self.assertEqual(draft._exact_model_json(
            '```json\n{"translations":[]}\n```'),
            {"translations":[]})
        for raw in (
            'Here is JSON: {"translations":[]}',
            '{"translations":[]}\nExtra prose',
            '{"translations":[]}{"claims":[]}',
            '[1,2]', '{"translations":[],}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(KoreaEnglishHold,
                                            "korea_model_response_not_exact_json"):
                    draft._exact_model_json(raw)

    def test_model_json_retries_format_at_most_once_without_echoing_response(self):
        from types import SimpleNamespace as NS
        from unittest.mock import Mock
        client=NS(messages=NS(create=Mock(side_effect=[
            NS(stop_reason="end_turn",content=[NS(type="text",text="PRIVATE_BAD_DRAFT")]),
            NS(stop_reason="end_turn",content=[NS(type="text",text='{"ok":true}')]),
        ])))
        got=draft.response_json(client,system="source-only",prompt="ORIGINAL SOURCE")
        self.assertEqual(got,{"ok":True})
        self.assertEqual(client.messages.create.call_count,2)
        calls=client.messages.create.call_args_list
        self.assertEqual(calls[0].kwargs["max_tokens"],6500)
        self.assertEqual(calls[1].kwargs["max_tokens"],6500)
        self.assertIn("ORIGINAL SOURCE",calls[1].kwargs["messages"][0]["content"])
        self.assertNotIn("PRIVATE_BAD_DRAFT",
                         str(calls[1].kwargs["messages"]))
        self.assertIn("FORMAT RETRY",calls[1].kwargs["messages"][0]["content"])

    def test_model_json_two_malformed_responses_fail_closed(self):
        from types import SimpleNamespace as NS
        from unittest.mock import Mock
        client=NS(messages=NS(create=Mock(return_value=NS(
            stop_reason="end_turn",content=[NS(type="text",text="NOT JSON")]))))
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "^korea_model_response_not_exact_json$"):
            draft.response_json(client,system="strict",prompt="original")
        self.assertEqual(client.messages.create.call_count,2)

    def test_model_incomplete_response_never_retried_or_admitted(self):
        from types import SimpleNamespace as NS
        from unittest.mock import Mock
        client=NS(messages=NS(create=Mock(return_value=NS(
            stop_reason="max_tokens",content=[NS(type="text",text='{"ok":true}')]))))
        with self.assertRaisesRegex(KoreaEnglishHold,
                                    "korea_model_response_incomplete_or_nontext"):
            draft.response_json(client,system="strict",prompt="original")
        self.assertEqual(client.messages.create.call_count,1)

    def test_model_draft_generation_is_private_and_unreviewed(self):
        source=make_source()
        original=original_paragraphs(TEXT)
        review=make_review()
        response_calls=[]
        def fake_response(client,*,system,prompt,max_tokens=6500):
            response_calls.append(system)
            if len(response_calls)==1:
                return {"translations":review["translations"]}
            return review["analysis"]
        with patch.object(draft,"response_json",side_effect=fake_response):
            machine,receipt=draft.draft(source,client=object())
        self.assertEqual(len(response_calls),2)
        self.assertEqual(machine["review"]["status"],"machine_unreviewed")
        self.assertTrue(receipt["machine_only"])
        self.assertFalse(machine["review"]["analysis_fact_checked"])

    def test_model_draft_bogus_alignment_does_not_reach_analyst_call(self):
        r=make_review()
        r["translations"][0]["original_sha256"]="a"*64
        calls=[]
        def fake(client,*,system,prompt,max_tokens=6500):
            calls.append(True)
            return {"translations":r["translations"]}
        with patch.object(draft,"response_json",side_effect=fake):
            with self.assertRaisesRegex(KoreaEnglishHold,"machine_translation_alignment_invalid"):
                draft.draft(make_source(),client=object())
        self.assertEqual(len(calls),1)


if __name__=="__main__":
    unittest.main()
