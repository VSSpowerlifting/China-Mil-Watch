"""Korea five-original review/rights/owner boundary regression tests."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core import korea_reference_gate as kr
from scripts import korea_reference_workbench as cli

NOW = datetime(2026, 10, 11, 23, 0, 0, tzinfo=timezone.utc)


def synthetic_approval(row):
    return {
        "source_identity": row["source_identity"],
        "content_sha256": row["content_sha256"],
        "document_capture_sha256": row["document_capture_sha256"],
        "human_korean_review": {
            "reviewer": "Fixture Korean linguist",
            "reviewed_at_utc": "2026-10-11T18:00:00Z",
            "rendered_hwpx_compared": True,
            "korean_semantics_verified": True,
            "names_dates_verified": True,
            "distribution_versus_posting_checked": True,
            "evidence_anchors_checked": True,
        },
        "source_rights_review": {
            "reviewer": "Fixture rights reviewer",
            "reviewed_at_utc": "2026-10-11T19:00:00Z",
            "page_notice_verified": True,
            "attribution_required": True,
            "text_only": True,
            "nontext_media_excluded": True,
            "intended_use_approved": True,
        },
        "owner_publication_approval": {
            "reviewer": "Fixture editor only",
            "reviewed_at_utc": "2026-10-11T20:00:00Z",
            "explicit_approval_for_reference_only": True,
        },
        "evidence_anchors": [{
            "line_number": 1, "line_sha256": "a" * 64,
            "claim_kind": "assessment",
            "editorial_linkage": "Synthetic pointer only, not authenticated against original.",
        }],
        "english_description": "Synthetic fixture only: MND stated a policy position. No actual public approval.",
    }


class KoreaGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-gate-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = kr.load_candidates()

    def approval_file(self, approvals):
        p = self.root / "signed-fixture.json"
        p.write_text(json.dumps({
            "schema": kr.APPROVAL_SCHEMA,
            "state_commit": kr.STATE_SHA,
            "entries": approvals,
        }), encoding="utf-8")
        return p

    def test_real_archived_five_hashes_and_dates_are_pinned(self):
        self.assertEqual(len(self.rows), 5)
        self.assertEqual({r["source_identity"].split(":")[1] for r in self.rows},
                         kr.ALLOWED_IDS)
        missile = next(r for r in self.rows if r["source_identity"].endswith("156784297"))
        self.assertEqual((missile["document_distribution_date"],
                          missile["published_date"]),
                         ("2026-10-04", "2026-10-06"))
        self.assertTrue(all(len(r["document_capture_sha256"]) == 64 for r in self.rows))
        self.assertTrue(all(r["language"] == "ko" for r in self.rows))

    def test_unsigned_five_record_workbench_is_usable_and_not_a_public_preview(self):
        self.assertEqual(kr.approve(self.rows, None), [])
        page = kr.render(self.rows, mode="workbench")
        self.assertEqual(page.count("<article>"), 5)
        self.assertIn("HOLD — human review pending", page)
        self.assertIn("2026-10-04", page)
        self.assertIn("2026-10-06", page)
        self.assertNotIn("Fixture Korean linguist", page)
        self.assertNotIn("Synthetic fixture only", page)
        self.assertIn("noindex,nofollow", page)

    def test_candidate_inventory_refuses_extra_changed_or_body_fields(self):
        source = json.loads(kr.CANDIDATES.read_text(encoding="utf-8"))
        mutations = []
        d = copy.deepcopy(source); d["entries"][0]["text_original"] = "PRIVATE BODY"; mutations.append(d)
        d = copy.deepcopy(source); d["entries"].append(copy.deepcopy(d["entries"][0])); mutations.append(d)
        d = copy.deepcopy(source); d["entries"][0]["issuer"] = "방위사업청"; mutations.append(d)
        d = copy.deepcopy(source); d["entries"][0]["source_url"] += "&bad=1"; mutations.append(d)
        d = copy.deepcopy(source); d["entries"][0]["document_capture_sha256"] = "1" * 63; mutations.append(d)
        d = copy.deepcopy(source); d["entries"][0]["document_distribution_date"] = "2026-11-01"; mutations.append(d)
        d = copy.deepcopy(source); d["state_commit"] = "b" * 40; mutations.append(d)
        d = copy.deepcopy(source); d["entries"][0]["source_identity"] = "korea-policy:156784618"; mutations.append(d)
        for index, item in enumerate(mutations):
            with self.subTest(index=index):
                path = self.root / ("candidate-%s.json" % index)
                path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(kr.KoreaGateHold):
                    kr.load_candidates(path)

    def test_valid_structural_fixture_is_private_only(self):
        item = synthetic_approval(self.rows[0])
        approved = kr.approve(self.rows, self.approval_file([item]), now=NOW)
        self.assertEqual(len(approved), 1)
        page = kr.render(self.rows, mode="release-preview", accepted=approved)
        self.assertEqual(page.count("<article>"), 1)
        self.assertIn("Synthetic fixture only", page)
        self.assertNotIn("Fixture Korean linguist", page)
        self.assertNotIn("Fixture rights reviewer", page)
        self.assertNotIn("Fixture editor only", page)
        self.assertNotIn("text_original", page)
        self.assertNotIn("line_sha256", page)
        self.assertNotIn("HOLD — human review pending", page)
        self.assertIn("not a live public Korea Desk", page)

    def test_each_unsigned_or_unscoped_claim_blocks_approved_row(self):
        baseline = synthetic_approval(self.rows[0])
        cases = [
            ("human_korean_review", "korean_semantics_verified", False),
            ("human_korean_review", "rendered_hwpx_compared", None),
            ("human_korean_review", "distribution_versus_posting_checked", False),
            ("source_rights_review", "page_notice_verified", False),
            ("source_rights_review", "nontext_media_excluded", False),
            ("owner_publication_approval", "explicit_approval_for_reference_only", False),
            ("owner_publication_approval", "reviewer", ""),
            ("human_korean_review", "reviewed_at_utc", "2026-10-12T18:00:00Z"),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                item = copy.deepcopy(baseline)
                item[section][key] = value
                with self.assertRaises(kr.KoreaGateHold):
                    kr.approve(self.rows, self.approval_file([item]), now=NOW)

    def test_original_line_anchors_fail_closed(self):
        fixture = synthetic_approval(self.rows[0])
        cases = []
        a = copy.deepcopy(fixture); del a["evidence_anchors"]; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"] = []; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"][0]["line_sha256"] = "f" * 63; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"][0]["line_number"] = True; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"][0]["line_number"] = 0; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"][0]["claim_kind"] = "proven_fact"; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"][0]["editorial_linkage"] = "<b>faked</b>"; cases.append(a)
        a = copy.deepcopy(fixture); a["evidence_anchors"].append(copy.deepcopy(a["evidence_anchors"][0])); cases.append(a)
        a = copy.deepcopy(fixture); a["human_korean_review"]["evidence_anchors_checked"] = False; cases.append(a)
        for i, item in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(kr.KoreaGateHold):
                kr.approve(self.rows, self.approval_file([item]), now=NOW)

    def test_malformed_stale_or_extra_approval_refuses(self):
        original = synthetic_approval(self.rows[0])
        cases = []
        a = copy.deepcopy(original); a["content_sha256"] = "f" * 64; cases.append([a])
        a = copy.deepcopy(original); a["document_capture_sha256"] = "f" * 64; cases.append([a])
        a = copy.deepcopy(original); a["source_identity"] = "korea-policy:156784618"; cases.append([a])
        a = copy.deepcopy(original); a["text_original"] = "INTERNAL PRIVATE"; cases.append([a])
        a = copy.deepcopy(original); a["english_description"] = "<script>x</script>" + "x"*80; cases.append([a])
        a = copy.deepcopy(original); a["owner_publication_approval"]["reviewed_at_utc"] = "2026-10-11T17:00:00Z"; cases.append([a])
        cases.append([original, copy.deepcopy(original)])
        for i, approval in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(kr.KoreaGateHold):
                kr.approve(self.rows, self.approval_file(approval), now=NOW)

    def test_no_approvals_means_zero_preview_records(self):
        p = self.approval_file([])
        self.assertEqual(kr.approve(self.rows, p, now=NOW), [])
        html = kr.render(self.rows, mode="release-preview")
        self.assertNotIn("<article>", html)
        self.assertIn("Nothing eligible for publication", html)

    def test_output_cannot_overwrite_or_enter_repo(self):
        dest = self.root / "private-workbench.html"
        result = kr.write_private(dest, kr.render(self.rows, mode="workbench"))
        self.assertEqual(result, str(dest))
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(kr.KoreaGateHold):
            kr.write_private(dest, "second")
        with self.assertRaises(kr.KoreaGateHold):
            kr.write_private(kr.ROOT / "korea-illegal-output.html", "unsafe")

    def test_cli_real_unsigned_workbench_and_preview_refusal(self):
        dest = self.root / "launch.html"
        self.assertEqual(cli.main(["--mode", "workbench", "--out", str(dest)]), 0)
        self.assertIn("156784297", dest.read_text(encoding="utf-8"))
        with self.assertRaises(SystemExit):
            cli.main(["--mode", "release-preview", "--out",
                      str(self.root / "blocked.html")])
        self.assertFalse((self.root / "blocked.html").exists())


if __name__ == "__main__":
    unittest.main()
