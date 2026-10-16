"""Source-bound, bounded Korea government-text exception screening.

Only the privately verified Korea HWPX adapter may call this. A machine
screen cannot make a legal/quality judgment, but it can stop automatic
staging when explicitly third-party, sensitive or contradictory terms occur.
"""
from __future__ import annotations

import hashlib
import re

from core.korea_archived_kogl_replay import KoreaArchivedMarkAdapter
from core.standing_source_rights import POLICIES

SCREEN_VERSION = "ipr-ko-text-only-exception-screen/1"
THIRD_PARTY = (
    re.compile(r"(?:©|ⓒ|All rights reserved)", re.I),
    re.compile(r"(?i)\b(?:Yonhap|Reuters|Associated Press|Agence France-Presse)\b"),
    re.compile(r"연합뉴스|뉴스1|저작권자|무단\s*(?:전재|복제|배포)"),
)
ADDITIONAL_TERMS = (
    re.compile(r"별도\s*(?:저작권|이용\s*허락|라이선스)"),
    re.compile(r"(?i)\b(?:copyright notice|all rights reserved)\b"),
)
SENSITIVE = (
    re.compile(r"\b\d{6}[-\s]?[1-4]\d{6}\b"),
    re.compile(r"주민등록번호|군사기밀\s*(?:등급|문서)|대외비\s*(?:문건|문서)"),
)


class ExceptionHold(ValueError):
    """Safe fixed error codes only, no private text in exception strings."""


def inspect_text_only(raw):
    if type(raw) is not bytes or not 80 <= len(raw) <= 200000:
        raise ExceptionHold("korea_original_text_size_or_type_invalid")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise ExceptionHold("korea_original_text_not_utf8") from None
    if len(text.strip()) < 70 or any(ord(c) < 32 and c not in "\r\t\n" for c in text):
        raise ExceptionHold("korea_original_text_not_clean")
    return {
        "schema": SCREEN_VERSION,
        "original_text_sha256": hashlib.sha256(raw).hexdigest(),
        "third_party_indicators_present": any(x.search(text) for x in THIRD_PARTY),
        "alternate_license_indicators_present": any(x.search(text) for x in ADDITIONAL_TERMS),
        "sensitive_personal_or_restricted_indicators_present": any(
            x.search(text) for x in SENSITIVE),
        "nontext_artifacts_included": False,
        "screen_is_legal_clearance": False,
        "screen_is_editorial_approval": False,
    }


class KoreaTextOnlyExceptionReplay:
    """Pass publisher-scoped text checks, holding explicit exception signals.

    A qualifying license mark is a publisher's grant for text, not a grant
    for embedded images, HWPX binary, or third-party protected expression.
    """

    def __init__(self, adapter):
        if type(adapter) is not KoreaArchivedMarkAdapter:
            raise ExceptionHold("trusted_korea_capture_adapter_required")
        self.adapter = adapter
        self.last_screen = None

    def __call__(self, source, policy):
        if source != self.adapter.source or policy != POLICIES["kr_policy_mnd_releases"]:
            raise ExceptionHold("korea_source_or_family_drift")
        proof = self.adapter.source_replay(source)
        text = self.adapter.read_original_text_private()
        screen = inspect_text_only(text)
        if screen["original_text_sha256"] != proof["entire_clean_original_text_sha256"]:
            raise ExceptionHold("korea_original_text_drift_in_exception_scan")
        self.adapter.item_license_replay(source, "KOGL_TYPE_1_TEXT")
        self.last_screen = screen
        return {
            "first_party_official_text": True,
            "third_party_text_present": screen["third_party_indicators_present"],
            "separate_terms_apply": screen["alternate_license_indicators_present"],
            "privacy_or_secrecy_exception":
                screen["sensitive_personal_or_restricted_indicators_present"],
            "released_artifact_embeds_media": False,
            "entire_source_text_version_sha256": screen["original_text_sha256"],
        }
