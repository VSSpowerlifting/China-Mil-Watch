"""Standing publisher licenses: one policy check, many eligible text originals.

Publication rights and content/editorial accuracy are DIFFERENT questions.
This code replaces repetitive document-by-document *rights approval* ONLY for
first-party text within separately verified publisher-wide licenses.

It is an eligibility contract, NOT a collector, PDF mirroring permission,
translation quality checker, writer, authorizer or public-site deployer.
All evidence verifiers must come from trusted code outside publisher metadata.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

POLICY_SCHEMA = "ipr-standing-source-family-policy/1"
RECEIPT_SCHEMA = "ipr-standing-text-license-qualification/1"
GIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
TIME = re.compile(r"20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
MAX_POLICY_AGE = timedelta(days=7)

# The two *specific* source families for which official standing terms make
# public reuse/derivatives possible. No rights carry across desks or hosts.
# JAPAN: as of Oct 15 Japan MOD's Japanese notice cites PDL1.0, allowing text
# copying, public transmission and translation with attribution, modification
# disclosure, exceptions for third-party expression and reserved contents.
# KOREA: Korea Policy Briefing confirms only items MARKED KOGL Type 1 have
# an affirmative text-reuse/derivative permission. Images/attachments excluded.
POLICIES = {
    "jp_mod_news_ja": {
        "schema": POLICY_SCHEMA,
        "desk": "japan",
        "official_host": "www.mod.go.jp",
        "official_path_prefix": "/j/",
        "policy_url": "https://www.mod.go.jp/j/info/contents.html",
        "policy_id": "jp-mod-public-data-terms-pdl1",
        "item_license_mark_required": False,
        "permitted_scopes": frozenset(("original_text", "translation_en")),
        "excluded_scopes": frozenset(("original_pdf", "original_media", "embedded_assets")),
        "requires_attribution": True,
        "requires_change_notice_for_translation": True,
    },
    "kr_policy_mnd_releases": {
        "schema": POLICY_SCHEMA,
        "desk": "korea",
        "official_host": "www.korea.kr",
        "official_path_prefix": "/briefing/pressReleaseView.do",
        "policy_url": "https://www.korea.kr/guide/copyRight.do",
        "policy_id": "korea-policy-briefing-kogl-type1-text",
        "item_license_mark_required": True,
        "permitted_scopes": frozenset(("original_text", "translation_en")),
        "excluded_scopes": frozenset(("original_pdf", "original_media", "embedded_assets")),
        "requires_attribution": True,
        "requires_change_notice_for_translation": True,
    },
}


class StandingLicenseHold(ValueError):
    """Bounded code only, never source body or provider content."""


def need(ok, reason):
    if not ok:
        raise StandingLicenseHold(reason)


def digest(data):
    need(type(data) is bytes, "invalid_hash_input")
    return hashlib.sha256(data).hexdigest()


def instant(value):
    need(type(value) is str and TIME.fullmatch(value) is not None,
         "invalid_license_observation_time")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise StandingLicenseHold("invalid_license_observation_time") from None


def safe_url(value, host, path_prefix):
    need(type(value) is str and 1 <= len(value) <= 2048
         and not any(ord(ch) < 33 or ord(ch) == 127 for ch in value),
         "invalid_first_party_url")
    try:
        u = urlsplit(value)
        matched = (u.scheme == "https" and u.hostname == host
                   and u.port is None and not u.username and not u.password
                   and not u.fragment and "\\" not in value
                   and u.path.startswith(path_prefix)
                   and not u.path.startswith("//"))
    except ValueError:
        matched = False
    need(matched, "publisher_outside_standing_policy_scope")


def validate_source(source, policy):
    need(type(source) is dict
         and set(source) == {
             "desk", "source_family", "source_identity", "official_url",
             "source_git_commit", "source_capture_sha256",
             "publisher_posted_date", "language"
         }, "source_provenance_incomplete")
    need(source["desk"] == policy["desk"]
         and source["source_family"] in POLICIES,
         "source_family_does_not_match_policy")
    safe_url(source["official_url"], policy["official_host"],
             policy["official_path_prefix"])
    need(type(source["source_identity"]) is str
         and 3 <= len(source["source_identity"]) <= 240,
         "source_identity_invalid")
    need(type(source["source_git_commit"]) is str
         and GIT.fullmatch(source["source_git_commit"]) is not None
         and type(source["source_capture_sha256"]) is str
         and HASH.fullmatch(source["source_capture_sha256"]) is not None,
         "original_source_version_not_pinned")
    need(source["language"] in ("ja", "ko")
         and source["language"] == ("ja" if policy["desk"] == "japan" else "ko"),
         "original_source_language_mismatch")
    need(type(source["publisher_posted_date"]) is str
         and re.fullmatch(r"20\d\d-\d\d-\d\d",
                          source["publisher_posted_date"]) is not None,
         "original_publication_date_missing")


def qualify_standing_text(source, *, kind, proposed_sha256,
                          attribution, now_utc,
                          source_replay=None, policy_replay=None,
                          exception_replay=None, item_license_replay=None):
    """Qualify text reuse WITHOUT a per-record human copyright check.

    These externally injected verifiers MUST be independent trusted code:
      source_replay: replay exact versioned first-party capture
      policy_replay: check current standing publisher license and exclusions
      exception_replay: inspect actual item for third-party/other rights issues
      item_license_replay: verify KOGL Type 1 MARK on the specific Korea item

    A self-reported boolean or a caller-manufactured JSON receipt is not
    a valid replacement for any of these verifiers. No provided verifier, or
    a changed/expired license, means HOLD. Qualified translation rights do
    not authorize its public release or bypass bilingual/editorial checks.
    """
    need(type(source) is dict, "source_provenance_incomplete")
    family = source.get("source_family")
    need(family in POLICIES, "source_family_has_no_standing_reuse_license")
    policy = POLICIES[family]
    validate_source(source, policy)
    need(kind in policy["permitted_scopes"], "requested_use_not_covered_by_license")
    need(type(proposed_sha256) is str and HASH.fullmatch(proposed_sha256) is not None,
         "proposed_content_version_missing")
    need(type(attribution) is str and 20 <= len(attribution) <= 1000
         and attribution == attribution.strip()
         and source["official_url"] in attribution
         and not any(ord(c) < 32 or ord(c) == 127 for c in attribution),
         "publisher_attribution_missing")
    if kind == "translation_en":
        need("IPR" in attribution
             and ("unofficial" in attribution.lower()
                  or "not an official" in attribution.lower()),
             "unofficial_translation_change_notice_missing")
    now = instant(now_utc)
    need(callable(source_replay) and callable(policy_replay)
         and callable(exception_replay),
         "trusted_source_policy_and_exception_verifiers_required")
    need(source_replay(source) is True,
         "versioned_first_party_source_not_authenticated")
    verified_policy = policy_replay(policy)
    need(type(verified_policy) is dict
         and set(verified_policy) == {
             "policy_id", "official_policy_url", "observed_at_utc",
             "publisher_policy_sha256", "text_reproduction_permitted",
             "derivatives_permitted", "third_party_exclusions_preserved",
             "policy_changed_or_withdrawn"
         }, "publisher_standing_policy_unverified")
    observed = instant(verified_policy["observed_at_utc"])
    need(verified_policy["policy_id"] == policy["policy_id"]
         and verified_policy["official_policy_url"] == policy["policy_url"]
         and type(verified_policy["publisher_policy_sha256"]) is str
         and HASH.fullmatch(verified_policy["publisher_policy_sha256"]) is not None
         and verified_policy["text_reproduction_permitted"] is True
         and verified_policy["derivatives_permitted"] is True
         and verified_policy["third_party_exclusions_preserved"] is True
         and verified_policy["policy_changed_or_withdrawn"] is False
         and timedelta(0) <= now - observed <= MAX_POLICY_AGE,
         "standing_license_missing_changed_or_stale")
    item = exception_replay(source, policy)
    need(type(item) is dict and set(item) == {
        "first_party_official_text", "third_party_text_present",
        "separate_terms_apply", "privacy_or_secrecy_exception",
        "includes_embedded_media", "entire_source_text_version_sha256"
    }, "source_exception_inspection_unavailable")
    need(item["first_party_official_text"] is True
         and item["third_party_text_present"] is False
         and item["separate_terms_apply"] is False
         and item["privacy_or_secrecy_exception"] is False
         and item["includes_embedded_media"] is False
         and type(item["entire_source_text_version_sha256"]) is str
         and HASH.fullmatch(item["entire_source_text_version_sha256"]) is not None,
         "source_item_excluded_by_rights_or_scope")
    if policy["item_license_mark_required"]:
        need(callable(item_license_replay)
             and item_license_replay(source, "KOGL_TYPE_1_TEXT") is True,
             "korea_specific_kogl_type1_text_mark_not_authenticated")
    if kind == "original_text":
        # Critical: the proposed public ORIGINAL text must be *exactly* the
        # clean original text observed by the trusted original replay. It
        # cannot be an altered summary or text harvested from unknown assets.
        need(proposed_sha256 == item["entire_source_text_version_sha256"],
             "proposed_original_text_does_not_match_source")
    return {
        "schema": RECEIPT_SCHEMA,
        "source_family": family,
        "desk": policy["desk"],
        "source_identity": source["source_identity"],
        "source_git_commit": source["source_git_commit"],
        "source_capture_sha256": source["source_capture_sha256"],
        "approved_text_sha256": proposed_sha256,
        "scope": kind,
        "license_id": policy["policy_id"],
        "policy_url": policy["policy_url"],
        "publisher_policy_sha256": verified_policy["publisher_policy_sha256"],
        "policy_checked_utc": verified_policy["observed_at_utc"],
        "publisher_attribution": attribution,
        "uses_standing_publisher_license_instead_of_per_record_rights_signoff": True,
        "original_text_matches_authenticated_capture": kind == "original_text",
        "translation_accuracy_editorially_approved": False,
        "analysis_editorially_approved": False,
        "publication_performed": False,
    }
