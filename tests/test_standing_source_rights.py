"""No-network standing-license tests. Fictional capture and policy evidence."""
import copy
import unittest

from core import standing_source_rights as rights

JP_URL = "https://www.mod.go.jp/j/press/news/fictional-release.html"
KR_URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784652"
TIME = "2026-10-15T20:00:00Z"
JAPANESE = "a" * 64
KOREAN = "b" * 64
POLICY_DIGEST = "c" * 64


def original(desk="japan"):
    korea = desk == "korea"
    return {
        "desk": desk,
        "source_family": "kr_policy_mnd_releases" if korea else "jp_mod_news_ja",
        "source_identity": "korea-policy:156784652" if korea else "japan-mod:fictional-01",
        "official_url": KR_URL if korea else JP_URL,
        "source_git_commit": "f" * 40,
        "source_capture_sha256": "e" * 64,
        "publisher_posted_date": "2026-10-15",
        "language": "ko" if korea else "ja",
    }


def license_replay(policy):
    return {
        "policy_id": policy["policy_id"],
        "official_policy_url": policy["policy_url"],
        "observed_at_utc": TIME,
        "publisher_policy_sha256": POLICY_DIGEST,
        "text_reproduction_permitted": True,
        "derivatives_permitted": True,
        "third_party_exclusions_preserved": True,
        "policy_changed_or_withdrawn": False,
    }


def exception_replay(source, policy):
    return {
        "first_party_official_text": True,
        "third_party_text_present": False,
        "separate_terms_apply": False,
        "privacy_or_secrecy_exception": False,
        "includes_embedded_media": False,
        "entire_source_text_version_sha256":
            KOREAN if source["desk"] == "korea" else JAPANESE,
    }


def options(source, *, translation=False):
    return {
        "kind": "translation_en" if translation else "original_text",
        "proposed_sha256": "d" * 64 if translation else
                            (KOREAN if source["desk"] == "korea" else JAPANESE),
        "attribution": ("Unofficial IPR translation based on " if translation
                        else "Original source: ") + source["official_url"],
        "now_utc": TIME,
        "source_replay": lambda _: True,
        "policy_replay": license_replay,
        "exception_replay": exception_replay,
        "item_license_replay": lambda *_: True,
    }


class StandingReuseContracts(unittest.TestCase):
    def test_verified_japan_first_party_text_requires_no_item_rights_signature(self):
        s = original()
        receipt = rights.qualify_standing_text(s, **options(s))
        self.assertEqual(receipt["scope"], "original_text")
        self.assertTrue(receipt[
            "uses_standing_publisher_license_instead_of_per_record_rights_signoff"])
        self.assertTrue(receipt["original_text_matches_authenticated_capture"])
        self.assertFalse(receipt["publication_performed"])

    def test_korea_kogl_type1_text_must_verify_item_specific_mark(self):
        s=original("korea")
        r=rights.qualify_standing_text(s,**options(s))
        self.assertEqual(r["license_id"],"korea-policy-briefing-kogl-type1-text")
        self.assertEqual(r["approved_text_sha256"],KOREAN)

    def test_korea_without_item_mark_fails_even_with_global_policy(self):
        s=original("korea")
        x=options(s);x["item_license_replay"]=lambda *_: False
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "korea_specific_kogl_type1"):
            rights.qualify_standing_text(s,**x)

    def test_korea_without_item_mark_verifier_fails(self):
        s=original("korea")
        x=options(s);x["item_license_replay"]=None
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "korea_specific_kogl_type1"):
            rights.qualify_standing_text(s,**x)

    def test_human_rights_signoff_not_replaced_with_self_reported_boolean(self):
        s=original();x=options(s);x["policy_replay"]=None
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "trusted_source_policy_and_exception_verifiers_required"):
            rights.qualify_standing_text(s,**x)

    def test_missing_item_exception_checker_holds(self):
        s=original();x=options(s);x["exception_replay"]=None
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "trusted_source_policy_and_exception_verifiers_required"):
            rights.qualify_standing_text(s,**x)

    def test_source_replay_failure_holds(self):
        s=original();x=options(s);x["source_replay"]=lambda _: False
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "versioned_first_party_source_not_authenticated"):
            rights.qualify_standing_text(s,**x)

    def test_changed_policy_holds_even_if_family_is_preapproved(self):
        s=original();x=options(s)
        def changed(policy):
            value=license_replay(policy);value["policy_changed_or_withdrawn"]=True
            return value
        x["policy_replay"]=changed
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "standing_license_missing_changed_or_stale"):
            rights.qualify_standing_text(s,**x)

    def test_policy_older_than_one_week_cannot_auto_authorize(self):
        s=original();x=options(s)
        def stale(policy):
            value=license_replay(policy);value["observed_at_utc"]="2026-10-01T20:00:00Z"
            return value
        x["policy_replay"]=stale
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "standing_license_missing_changed_or_stale"):
            rights.qualify_standing_text(s,**x)

    def test_future_policy_check_is_not_credible(self):
        s=original();x=options(s)
        def future(policy):
            value=license_replay(policy);value["observed_at_utc"]="2026-10-16T20:00:00Z"
            return value
        x["policy_replay"]=future
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "standing_license_missing_changed_or_stale"):
            rights.qualify_standing_text(s,**x)

    def test_policy_from_another_publisher_does_not_transfer(self):
        s=original();x=options(s)
        def not_mod(policy):
            value=license_replay(policy);value["official_policy_url"] = (
                "https://www.korea.kr/guide/copyRight.do")
            return value
        x["policy_replay"]=not_mod
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "standing_license_missing_changed_or_stale"):
            rights.qualify_standing_text(s,**x)

    def test_vendor_republication_or_third_party_text_blocks_auto_use(self):
        s=original();x=options(s)
        def vendor(source,policy):
            value=exception_replay(source,policy)
            value["third_party_text_present"]=True
            return value
        x["exception_replay"]=vendor
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "source_item_excluded_by_rights_or_scope"):
            rights.qualify_standing_text(s,**x)

    def test_embedded_media_blocks_original_text_only_path(self):
        s=original();x=options(s)
        def media(source,policy):
            value=exception_replay(source,policy)
            value["includes_embedded_media"]=True
            return value
        x["exception_replay"]=media
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "source_item_excluded_by_rights_or_scope"):
            rights.qualify_standing_text(s,**x)

    def test_privacy_or_secrecy_exception_blocks(self):
        s=original();x=options(s)
        def excluded(source,policy):
            value=exception_replay(source,policy)
            value["privacy_or_secrecy_exception"]=True
            return value
        x["exception_replay"]=excluded
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "source_item_excluded_by_rights_or_scope"):
            rights.qualify_standing_text(s,**x)

    def test_no_auto_pdfs_photos_or_attachments_even_japan(self):
        s=original()
        for kind in ("original_pdf","original_media","embedded_assets"):
            with self.subTest(kind=kind):
                x=options(s);x["kind"]=kind
                with self.assertRaisesRegex(rights.StandingLicenseHold,
                                            "requested_use_not_covered_by_license"):
                    rights.qualify_standing_text(s,**x)

    def test_no_inherited_rights_for_kemhan_afp_vietnam_singapore_us_china(self):
        s=original()
        for family in ("id_kemhan_news", "ph_afp_articles",
                       "vn_moit_energy_vi", "sg_mindef_releases",
                       "us_uscc_press", "cn_pla_daily"):
            with self.subTest(family=family):
                s["source_family"]=family
                with self.assertRaisesRegex(rights.StandingLicenseHold,
                                            "source_family_has_no_standing_reuse_license"):
                    rights.qualify_standing_text(s,**options(s))

    def test_japan_does_not_inherit_korea_rights_by_changing_source_family(self):
        s=original();s["source_family"]="kr_policy_mnd_releases"
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "source_family_does_not_match_policy"):
            rights.qualify_standing_text(s,**options(s))

    def test_policy_does_not_cover_external_news_on_mod_host(self):
        s=original()
        s["official_url"] = "https://www.mod.go.jp.evil.invalid/j/foo.html"
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "publisher_outside_standing_policy_scope"):
            rights.qualify_standing_text(s,**options(s))

    def test_edited_original_text_does_not_match_authenticated_bytes(self):
        s=original();x=options(s);x["proposed_sha256"]="9"*64
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "proposed_original_text_does_not_match_source"):
            rights.qualify_standing_text(s,**x)

    def test_translation_rights_can_be_qualified_without_editorial_approval(self):
        s=original();x=options(s,translation=True)
        r=rights.qualify_standing_text(s,**x)
        self.assertEqual(r["scope"],"translation_en")
        self.assertFalse(r["translation_accuracy_editorially_approved"])
        self.assertFalse(r["publication_performed"])

    def test_translation_without_unofficial_notice_fails(self):
        s=original();x=options(s,translation=True)
        x["attribution"]="Translated from "+s["official_url"]
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "unofficial_translation_change_notice_missing"):
            rights.qualify_standing_text(s,**x)

    def test_unrelated_license_policy_proof_fields_cannot_be_accepted(self):
        s=original();x=options(s)
        def extra(policy):
            value=license_replay(policy);value["permissions"]=True
            return value
        x["policy_replay"]=extra
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "publisher_standing_policy_unverified"):
            rights.qualify_standing_text(s,**x)

    def test_changing_git_capture_identity_requires_fresh_replay(self):
        s=original();s["source_git_commit"]="broken"
        with self.assertRaisesRegex(rights.StandingLicenseHold,
                                    "original_source_version_not_pinned"):
            rights.qualify_standing_text(s,**options(s))

    def test_no_public_release_api_or_network_access_in_module(self):
        self.assertFalse(hasattr(rights,"publish"))
        self.assertFalse(hasattr(rights,"deploy"))
        self.assertNotIn("original_pdf",rights.POLICIES["jp_mod_news_ja"]["permitted_scopes"])
        self.assertFalse(rights.POLICIES["jp_mod_news_ja"]["item_license_mark_required"])
        self.assertTrue(rights.POLICIES["kr_policy_mnd_releases"]["item_license_mark_required"])


if __name__ == "__main__":
    unittest.main()
