"""One private Sunday Vietnam lane can retain every verified in-window source.

The synthetic queue intentionally has no raw publisher bodies, network access,
source approval, model call, SMTP call, production DB write or public rendering.
"""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.prepare_vietnam_briefs_evidence import (
    MAX_VIETNAM, VietnamFeederError, canonical_json, make_packet,
)

ROOT = Path(__file__).resolve().parents[1]
SATURDAY = "2026-10-10"
IDS = (1791535381, 1791366010, 1791199677, 1791199100,
       1791608910, 1791608999)


def fixture(size):
    rows = []
    notes = []
    dates = ("2026-10-09", "2026-10-07", "2026-10-05", "2026-10-05",
             "2026-10-10", "2026-10-10")
    for index, number in enumerate(IDS[:size]):
        ident = "mps-vi:" + str(number)
        url = "https://bocongan.gov.vn/bai-viet/synthetic-case-" + str(number)
        digest = hashlib.sha256(ident.encode("utf-8")).hexdigest()
        rows.append({
            "source_identity": ident, "source_slug": "vn_mps_foreign_affairs_vi",
            "canonical_url": url, "published_date": dates[index],
            "title_original": "Synthetic source — never an official record",
            "content_sha256": digest, "body_status": "text",
            "machine_review_candidate": True, "machine_blockers": [],
            "human_source_reviewed": False, "reuse_rights_reviewed": False,
            "production_publication_authorized": False,
        })
        notes.append({
            "source_identity": ident, "source_url": url,
            "published_date": dates[index], "content_sha256": digest,
            "summary": ("Synthetic review synopsis for a verified security "
                        "meeting. It describes only reported discussions, "
                        "not any completed operation or signed agreement."),
            "caveats": [
                "This is a synthetic fixture, not source-use approval or evidence."
            ],
            "topics": ["regional_partnerships"],
        })
    queue = {
        "schema": "vietnam-mps-pilot-review-queue/1",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "state_branch": "shadow/vietnam-mps-foreign-affairs",
        "state_commit": "a" * 40, "state_tree": "b" * 40,
        "successful_run_count": 1, "record_count": len(rows),
        "human_approvals": 0, "rights_approvals": 0,
        "automatic_production_admission": False,
        "full_desk_qualification": False,
        "original_article_bodies_in_packet": False,
        "records": rows,
    }
    queue["queue_sha256"] = hashlib.sha256(
        canonical_json(queue).encode("utf-8")).hexdigest()
    return queue, {"schema": "vietnam-editorial-notes/1", "entries": notes}


def existing_japan():
    path = ROOT / "research/briefs_editorial_evidence/2026-10-10.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema": data["schema"], "week_ending": data["week_ending"],
        "status": data["status"],
        "items": [copy.deepcopy(x) for x in data["items"]
                  if x["desk"] == "japan"],
    }


class VietnamSundayCandidateQuotaTests(unittest.TestCase):
    def test_four_version_matched_vietnam_sources_preserve_japan(self):
        self.assertEqual(MAX_VIETNAM, 5)
        queue, authored = fixture(4)
        packet = make_packet(queue, authored, SATURDAY,
                             previous=existing_japan())
        self.assertEqual(len(packet["items"]), 7)
        self.assertEqual(sum(x["desk"] == "vietnam" for x in packet["items"]), 4)
        self.assertEqual(sum(x["desk"] == "japan" for x in packet["items"]), 3)
        self.assertEqual(packet["items"][3]["id"], "VN-MPS-1791535381")
        self.assertTrue(all(x["copy_scope"] ==
                            "private-model-drafting-only-no-source-body"
                            for x in packet["items"]))
        self.assertTrue(all(x["status"] ==
                            "unapproved-source-linked-editorial-candidate"
                            for x in packet["items"]))
        self.assertNotIn("text_original", canonical_json(packet))
        self.assertNotIn("human_approved", canonical_json(packet))

    def test_five_fits_exact_combined_eight_source_budget(self):
        queue, authored = fixture(5)
        packet = make_packet(queue, authored, SATURDAY,
                             previous=existing_japan())
        self.assertEqual(len(packet["items"]), 8)
        self.assertEqual(sum(x["desk"] == "vietnam" for x in packet["items"]), 5)

    def test_six_th_source_stays_out_and_strict_sunday_gate_must_refuse(self):
        queue, authored = fixture(6)
        packet = make_packet(queue, authored, SATURDAY,
                             previous=existing_japan())
        offered = sum(x["desk"] == "vietnam" for x in packet["items"])
        self.assertEqual(offered, 5)
        # The existing Oct10 workflow checks machine_eligible_count == offered.
        self.assertNotEqual(len(queue["records"]), offered)

    def test_version_drift_of_new_lao_source_refuses(self):
        queue, authored = fixture(4)
        authored["entries"][0]["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(VietnamFeederError, "not pinned"):
            make_packet(queue, authored, SATURDAY,
                        previous=existing_japan())

    def test_actual_oct9_lao_note_is_pinned_and_cautious(self):
        path = (ROOT / "research/vietnam_briefs_candidates" /
                "editorial_notes_2026-10-10.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        notes = {x["source_identity"]: x for x in data["entries"]}
        self.assertEqual(len(notes), 5)
        lao = notes["mps-vi:1791535381"]
        self.assertEqual(lao["published_date"], "2026-10-09")
        self.assertEqual(
            lao["content_sha256"],
            "8775cb700db1dddfb17209c292b7a03864c65683cc190792c88939a9dd7740ef")
        self.assertIn("public security ministries", " ".join(lao["caveats"]))
        self.assertIn("not proof", " ".join(lao["caveats"]))
        self.assertNotIn("text_original", lao)
        cambodia = notes["mps-vi:1791608910"]
        self.assertEqual(cambodia["published_date"], "2026-10-10")
        self.assertEqual(cambodia["content_sha256"],
                         "d5b372499a12ff3df54c74d768d93d20da1913280eb2b4c4cda851345f731224")
        self.assertIn("Cambodia", cambodia["summary"])
        self.assertTrue(any("not the Lao" in c for c in cambodia["caveats"]))
        self.assertNotIn("text_original", cambodia)


if __name__ == "__main__":
    unittest.main()
