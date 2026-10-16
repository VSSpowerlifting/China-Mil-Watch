"""Fail-closed text-only exception scan contracts; no real source exposed."""
import unittest
from core.korea_text_only_exception_replay import (
    inspect_text_only, ExceptionHold, KoreaTextOnlyExceptionReplay,
)

CLEAN = ("국방부는 공식 보도자료를 통해 훈련 계획을 설명하였다. "
         "이번 발표는 정부 공식 입장을 소개한다. " * 10).encode("utf-8")


class KoreaOriginalExceptionTests(unittest.TestCase):
    def test_bounded_first_party_text_clean_has_no_explicit_red_flags(self):
        receipt = inspect_text_only(CLEAN)
        self.assertFalse(receipt["third_party_indicators_present"])
        self.assertFalse(receipt["alternate_license_indicators_present"])
        self.assertFalse(receipt["sensitive_personal_or_restricted_indicators_present"])
        self.assertFalse(receipt["screen_is_legal_clearance"])
        self.assertFalse(receipt["screen_is_editorial_approval"])
        self.assertNotIn("text_original", str(receipt))
        self.assertNotIn("국방부", str(receipt))

    def test_embedded_ap_wire_notice_is_held(self):
        flagged = inspect_text_only(CLEAN + " Reuters".encode("utf-8"))
        self.assertTrue(flagged["third_party_indicators_present"])

    def test_korean_third_party_wire_notice_is_held(self):
        flagged = inspect_text_only(CLEAN + " 연합뉴스 제공".encode("utf-8"))
        self.assertTrue(flagged["third_party_indicators_present"])

    def test_contradictory_per_item_license_is_held(self):
        flagged = inspect_text_only(CLEAN + " 별도 저작권".encode("utf-8"))
        self.assertTrue(flagged["alternate_license_indicators_present"])

    def test_personal_identification_number_is_held(self):
        flagged = inspect_text_only(CLEAN + b" 990101-1234567")
        self.assertTrue(flagged["sensitive_personal_or_restricted_indicators_present"])

    def test_restricted_document_stamp_is_held(self):
        flagged = inspect_text_only(CLEAN + " 대외비 문서".encode("utf-8"))
        self.assertTrue(flagged["sensitive_personal_or_restricted_indicators_present"])

    def test_non_utf8_and_control_characters_refused(self):
        with self.assertRaisesRegex(ExceptionHold, "korea_original_text_not_utf8"):
            inspect_text_only(CLEAN + b"\xff")
        with self.assertRaisesRegex(ExceptionHold, "korea_original_text_not_clean"):
            inspect_text_only(CLEAN + b"\x00")

    def test_short_or_non_bytes_refused(self):
        with self.assertRaisesRegex(ExceptionHold, "korea_original_text_size_or_type_invalid"):
            inspect_text_only(b"short")
        with self.assertRaisesRegex(ExceptionHold, "korea_original_text_size_or_type_invalid"):
            inspect_text_only(CLEAN.decode("utf-8"))

    def test_untrusted_callback_adapter_refused(self):
        with self.assertRaisesRegex(ExceptionHold, "trusted_korea_capture_adapter_required"):
            KoreaTextOnlyExceptionReplay(object())


if __name__ == "__main__":
    unittest.main()
