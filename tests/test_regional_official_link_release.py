"""Synthetic-only regional official-link release and SQLite gate tests."""
from __future__ import annotations

import copy
import sqlite3
import unittest
from unittest.mock import patch

from core import regional_official_link_release as link
from core.crossdesk_official_metadata_candidates import FAMILIES


SHA = "a" * 40


def data(family="ph_afp_articles", count=1, with_hold=False):
    policy = copy.deepcopy(link.load_owner_policy())
    spec = next(x for x in policy["source_families"] if x["source_family"] == family)
    spec["frozen_review_cohort_commit"] = SHA
    rows = []
    for n in range(count):
        if family == "ph_afp_articles":
            identity = "afp:%d" % (1400+n)
            url = "https://www.afp.mil.ph/news/fictional-exercise-%d" % n
            day = "2026-10-15"
        else:
            day = "2026-10-15"
            suffix = "/2026/10/15/fake-%d.html" % n
            identity = "kemhan:" + suffix
            url = "https://www.kemhan.go.id" + suffix
        source = {"desk": FAMILIES[family]["desk"],
                  "source_family": family, "source_identity": identity,
                  "canonical_official_url": url,
                  "publisher_posted_date": day,
                  "official_issuer": FAMILIES[family]["issuer"],
                  "official_publisher": FAMILIES[family]["publisher"],
                  "official_republisher": FAMILIES[family]["republisher"],
                  "source_git_commit": SHA, "first_seen_run": "123456-1"}
        rows.append({**source, "metadata_version_sha256": link.digest(source),
                     "review_state": "held", "semantic_exception_hold": None,
                     "production_admission_authorized": False,
                     "automatic_public_link_authorized": False,
                     "publisher_body_reuse_authorized": False})
    if with_hold:
        assert family == "id_kemhan_news"
        sid = "kemhan:" + link.KEMHAN_HELD
        source = {"desk": "indonesia", "source_family": family,
                  "source_identity": sid,
                  "canonical_official_url": "https://www.kemhan.go.id" + link.KEMHAN_HELD,
                  "publisher_posted_date": "2026-10-02",
                  "official_issuer": None, "official_publisher": "id_kemhan",
                  "official_republisher": None, "source_git_commit": SHA,
                  "first_seen_run": "123456-1"}
        rows.append({**source, "metadata_version_sha256": link.digest(source),
                     "review_state": "held",
                     "semantic_exception_hold": "publisher_geography_discrepancy",
                     "production_admission_authorized": False,
                     "automatic_public_link_authorized": False,
                     "publisher_body_reuse_authorized": False})
    rows.sort(key=lambda r: (r["source_identity"], r["canonical_official_url"]))
    packet = {
        "schema": "ipr-afp-kemhan-held-metadata-candidates/1",
        "desk": FAMILIES[family]["desk"], "source_family": family,
        "source_git_commit": SHA,
        "candidate_count": len(rows),
        "semantic_exception_count": int(with_hold),
        "all_candidates_held": True,
        "production_import_enabled": False, "public_release_enabled": False,
        "source_capture_bytes_authenticated_by_this_projection": False,
        "seven_scheduled_days_authenticated_by_this_projection": False,
        "source_specific_reuse_authorized_by_this_projection": False,
        "original_title_or_body_exported": False,
        "records": rows,
        "metadata_manifest_sha256": link.digest(rows),
    }
    spec["frozen_review_cohort_candidate_count"] = len(rows)
    spec["frozen_review_cohort_metadata_manifest_sha256"] = packet[
        "metadata_manifest_sha256"]
    # The known Indonesia exception MUST stay held in its owner policy.
    if family == "id_kemhan_news" and not with_hold:
        # Use AFP for nonexception tests; require genuine Indonesia hold.
        spec["known_excluded_source_identities"] = []
    eligible = [r for r in rows if r["semantic_exception_hold"] is None]
    proof = {"schema": "ipr-crossdesk-independent-release-proof/1",
             "source_family": family,
             "source_git_commit": SHA,
             "metadata_manifest_sha256": packet["metadata_manifest_sha256"],
             "eligible_source_identities_sha256":
                 link.digest(sorted(r["source_identity"] for r in eligible)),
             "review_receipts_version_matched": True,
             "seven_actual_scheduled_days_authenticated": True,
             "all_visible_actions_attempts_reconciled": True,
             "official_metadata_link_use_checked": True,
             "known_semantic_holds_enforced": True,
             "production_live_site_authorized": True,
             "source_capture_version_reverified": True,
             "trusted_validator_ref": "b" * 40}
    return policy, packet, proof


def memory_db():
    cx = sqlite3.connect(":memory:")
    cx.execute(link.SCHEMA_SQL)
    return cx


class ReleaseContracts(unittest.TestCase):
    def test_owner_decision_records_review_claim_separately_from_proofs(self):
        policy = link.load_owner_policy()
        self.assertTrue(policy["owner_confirms_human_review_occurred"])
        self.assertTrue(policy["owner_authorizes_automated_verified_link_metadata"])
        self.assertFalse(policy[
            "machine_verified_record_specific_human_review_receipts_in_repository"])
        self.assertFalse(policy[
            "all_actions_attempts_and_release_gates_approved_by_this_declaration"])

    def test_real_pinned_commit_cannot_be_replaced_by_synthetic(self):
        _, packet, _ = data()
        with self.assertRaisesRegex(link.RegionalLinkHold,
                                    "source_candidate_cohort_not_owner_pinned"):
            link.verify_cohort(packet, link.load_owner_policy())

    def test_fictional_afp_cohort_is_metadata_only(self):
        policy, packet, _ = data()
        records = link.verify_cohort(packet, policy)
        self.assertEqual(len(records), 1)
        self.assertNotIn("original_title", records[0])
        self.assertFalse(records[0]["production_admission_authorized"])

    def test_missing_independent_validator_refuses_without_any_db_write(self):
        policy, packet, proof = data()
        cx = memory_db()
        with patch.object(link, "load_owner_policy", return_value=policy):
            with self.assertRaisesRegex(link.RegionalLinkHold,
                                        "trusted_release_evidence_validator_missing"):
                link.admit(cx, packet, policy, proof,
                           as_of_utc="2026-10-15T20:00:00Z")
        self.assertEqual(cx.execute(
            "SELECT count(*) FROM regional_official_source_links").fetchone()[0],0)

    def test_self_forged_policy_refused_before_validator(self):
        policy, packet, proof = data()
        cx=memory_db()
        with self.assertRaisesRegex(link.RegionalLinkHold,
                                    "owner_policy_is_not_repository_pinned"):
            link.admit(cx, packet, policy, proof,
                       as_of_utc="2026-10-15T20:00:00Z",
                       trusted_validator=lambda *_: True)

    def test_synthetic_provenance_gate_idempotent(self):
        policy, packet, proof = data()
        cx=memory_db()
        with patch.object(link, "load_owner_policy", return_value=policy):
            one=link.admit(cx, packet, policy, proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_: True)
            two=link.admit(cx, packet, policy, proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_: True)
        self.assertEqual((one["new_official_links"],two["new_official_links"]), (1,0))
        self.assertEqual(two["unchanged_official_links"],1)
        r=cx.execute("SELECT release_scope,official_publisher FROM regional_official_source_links").fetchone()
        self.assertEqual(tuple(r),("official_link_only","ph_afp"))
        self.assertNotIn("text_original", link.SCHEMA_SQL)
        self.assertNotIn("title_original", link.SCHEMA_SQL)

    def test_indonesia_semantic_hold_does_not_enter_db(self):
        policy, packet, proof = data("id_kemhan_news", with_hold=True)
        cx=memory_db()
        self.assertEqual(len(link.verify_cohort(packet, policy)),1)
        with patch.object(link, "load_owner_policy", return_value=policy):
            result=link.admit(cx, packet, policy, proof,
                              as_of_utc="2026-10-15T20:00:00Z",
                              trusted_validator=lambda *_: True)
        self.assertEqual(result["held_semantic_exceptions"],1)
        self.assertEqual(cx.execute("SELECT count(*) FROM regional_official_source_links").fetchone()[0],1)
        self.assertEqual(cx.execute(
            "SELECT count(*) FROM regional_official_source_links "
            "WHERE canonical_official_url LIKE '%kunker-ke-kaltara%'").fetchone()[0],0)

    def test_changed_source_url_after_release_refused(self):
        policy, packet, proof=data()
        cx=memory_db()
        with patch.object(link,"load_owner_policy",return_value=policy):
            link.admit(cx,packet,policy,proof,as_of_utc="2026-10-15T20:00:00Z",
                       trusted_validator=lambda *_:True)
        cx.execute("UPDATE regional_official_source_links "
                   "SET publisher_posted_date='2026-10-14'")
        with patch.object(link,"load_owner_policy",return_value=policy):
            with self.assertRaisesRegex(link.RegionalLinkHold,
                                        "previously_released_source_version_changed"):
                link.admit(cx,packet,policy,proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_:True)

    def test_collision_with_legacy_article_rolls_back_entire_batch(self):
        policy, packet, proof=data(count=2)
        cx=memory_db()
        cx.execute("CREATE TABLE articles (url TEXT NOT NULL)")
        cx.execute("INSERT INTO articles(url) VALUES(?)",(
            packet["records"][1]["canonical_official_url"],))
        with patch.object(link,"load_owner_policy",return_value=policy):
            with self.assertRaisesRegex(link.RegionalLinkHold,"legacy_article_url_collision"):
                link.admit(cx,packet,policy,proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_:True)
        self.assertEqual(cx.execute("SELECT COUNT(*) FROM regional_official_source_links").fetchone()[0],0)

    def test_unverified_review_truth_flag_alone_not_enough(self):
        policy,packet,proof=data()
        proof["review_receipts_version_matched"]=False
        cx=memory_db()
        with patch.object(link,"load_owner_policy",return_value=policy):
            with self.assertRaisesRegex(link.RegionalLinkHold,"independent_release_evidence_missing"):
                link.admit(cx,packet,policy,proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_:True)
        self.assertEqual(cx.execute("SELECT COUNT(*) FROM regional_official_source_links").fetchone()[0],0)

    def test_semantic_exception_cannot_be_reclassified(self):
        policy,packet,_=data("id_kemhan_news",with_hold=True)
        packet["records"][-1]["semantic_exception_hold"]=None
        packet["metadata_manifest_sha256"]=link.digest(packet["records"])
        spec=next(x for x in policy["source_families"]
                  if x["source_family"]=="id_kemhan_news")
        spec["frozen_review_cohort_metadata_manifest_sha256"]=packet["metadata_manifest_sha256"]
        with self.assertRaisesRegex(link.RegionalLinkHold,"semantic_exception_hold_drift"):
            link.verify_cohort(packet,policy)

    def test_original_body_field_is_never_allowed_in_source_candidate(self):
        policy,packet,_=data()
        packet["records"][0]["original_text"]="unsafe"
        packet["metadata_manifest_sha256"]=link.digest(packet["records"])
        policy["source_families"][0]["frozen_review_cohort_metadata_manifest_sha256"]=packet["metadata_manifest_sha256"]
        with self.assertRaisesRegex(link.RegionalLinkHold,"unexpected_candidate_public_content"):
            link.verify_cohort(packet,policy)

    def test_proof_must_match_entire_reviewed_id_set(self):
        policy,packet,proof=data()
        proof["eligible_source_identities_sha256"]="0"*64
        with self.assertRaisesRegex(link.RegionalLinkHold,"independent_release_evidence_missing"):
            link.verify_release_evidence(proof,packet,link.verify_cohort(packet,policy))

    def test_schema_missing_prevents_any_write(self):
        policy,packet,proof=data()
        cx=sqlite3.connect(":memory:")
        with patch.object(link,"load_owner_policy",return_value=policy):
            with self.assertRaisesRegex(link.RegionalLinkHold,"regional_official_index_not_migrated"):
                link.admit(cx,packet,policy,proof,
                           as_of_utc="2026-10-15T20:00:00Z",
                           trusted_validator=lambda *_:True)


if __name__ == "__main__":
    unittest.main()
