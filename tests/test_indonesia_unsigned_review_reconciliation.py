"""No-network adversarial tests of UNAUTHENTICATED Indonesia reviewer claims."""
from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.bind_indonesia_review_versions import build_manifest, REVIEW_FIELDS
from scripts.reconcile_indonesia_unsigned_reviews import (
    ReviewReconciliationHold, reconcile, main, SCHEMA,
    EXPECTED_MANIFEST_SHA256,
)
from tests.test_indonesia_source_version_review import fixture

AS_OF = datetime(2026, 10, 16, 23, 59, 59, tzinfo=timezone.utc)


class ReviewReconciliationContracts(unittest.TestCase):
    def setUp(self):
        queue, originals = fixture()
        self.manifest = build_manifest(queue, originals)
        self.sha = self.manifest["manifest_sha256"]
        self.rows = []
        for entry in self.manifest["records"]:
            self.rows.append({
                "source_identity": entry["source_identity"],
                "source_version_sha256": entry["source_version_sha256"],
                "official_url": entry["official_url"],
                "publication_date": entry["publication_date"],
                "disposition": entry["disposition"],
                "source_geography_hold": (
                    "YES — MUST REMAIN HELD" if entry["known_geography_hold"]
                    else "NO"
                ),
                **{name: "" for name in REVIEW_FIELDS[6:]},
            })

    def check(self, *, rows=None, manifest=None, sha=None):
        return reconcile(
            self.manifest if manifest is None else manifest,
            self.rows if rows is None else rows,
            expected_sha=self.sha if sha is None else sha,
            as_of_utc=AS_OF,
        )

    def complete(self, row, *, link="allow"):
        row.update({
            "reviewer_name": "Synthetic reviewer — not a real attestation",
            "reviewed_at_utc": "2026-10-16T19:30:00Z",
            "original_language_checked": "yes",
            "publisher_date_and_title_checked": "yes",
            "factual_claims_checked": "yes",
            "publisher_link_use_review": link,
            "source_body_reuse_review": "deny",
            "translation_reuse_review": "unclear",
            "media_reuse_review": "deny",
            "review_notes": "Fictional review only. No real authority established.",
        })

    def test_blank_realistic_31_original_roster_remains_held(self):
        report = self.check()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["review_rows_reconciled"], 31)
        self.assertEqual(report["counts"], {
            "not_started": 30, "held_exception": 1,
            "unsigned_review_complete": 0})
        self.assertTrue(report["row_original_versions_matched"])
        self.assertFalse(report["reviewer_identity_authenticated"])
        self.assertFalse(report["review_evidence_independently_authenticated"])
        self.assertFalse(report["publisher_link_use_authority_authenticated"])
        self.assertFalse(report["production_admission_authorized"])
        self.assertFalse(report["public_site_publication_authorized"])
        self.assertEqual(report["approved_official_links"], 0)
        self.assertEqual(report["production_writes"], 0)

    def test_completely_claimed_review_is_still_unsigned_not_release_evidence(self):
        valid = next(x for x in self.rows if x["source_geography_hold"] == "NO")
        self.complete(valid)
        report = self.check()
        self.assertEqual(report["counts"]["unsigned_review_complete"], 1)
        self.assertEqual(report["counts"]["not_started"], 29)
        self.assertFalse(report["reviewer_identity_authenticated"])
        self.assertFalse(report["publisher_link_use_authority_authenticated"])
        self.assertEqual(report["approved_official_links"], 0)

    def test_known_geography_exception_cannot_receive_allow_even_from_named_claim(self):
        row = next(x for x in self.rows
                   if x["source_geography_hold"] == "YES — MUST REMAIN HELD")
        self.complete(row)
        with self.assertRaisesRegex(
                ReviewReconciliationHold, "geography_discrepancy"):
            self.check()
        row["publisher_link_use_review"] = "deny"
        report = self.check()
        self.assertEqual(report["counts"]["held_exception"], 1)
        self.assertEqual(report["approved_official_links"], 0)

    def test_swapped_version_date_url_or_disposition_cannot_be_reviewed(self):
        def reject(field, new):
            candidate = copy.deepcopy(self.rows)
            candidate[0][field] = new
            with self.assertRaises(ReviewReconciliationHold):
                self.check(rows=candidate)
        reject("source_version_sha256", "f" * 64)
        reject("publication_date", "2026-10-14")
        reject("official_url", "https://www.kemhan.go.id/different.html")
        reject("source_identity", "kemhan:/nonexistent.html")
        reject("source_geography_hold", "NO — removed")
        reject("disposition", "release_allowed")

    def test_incomplete_duplicated_extra_or_missing_roster_is_rejected(self):
        for rows in (self.rows[:-1], self.rows + [self.rows[0]]):
            with self.assertRaises(ReviewReconciliationHold):
                self.check(rows=rows)
        duplicate = copy.deepcopy(self.rows)
        duplicate[1] = copy.deepcopy(duplicate[0])
        with self.assertRaises(ReviewReconciliationHold):
            self.check(rows=duplicate)
        other = copy.deepcopy(self.rows)
        other[0]["reviewer_signed"] = True
        with self.assertRaises(ReviewReconciliationHold):
            self.check(rows=other)

    def test_rehashed_forged_manifest_is_blocked_by_independent_digest(self):
        altered = copy.deepcopy(self.manifest)
        altered["records"][0]["source_version_sha256"] = "f" * 64
        with self.assertRaises(ReviewReconciliationHold):
            self.check(manifest=altered)
        from scripts.bind_indonesia_review_versions import digest
        altered["manifest_sha256"] = digest(altered["records"])
        with self.assertRaises(ReviewReconciliationHold):
            self.check(manifest=altered)
        self.assertEqual(len(EXPECTED_MANIFEST_SHA256), 64)
        self.assertNotEqual(self.sha, EXPECTED_MANIFEST_SHA256)

    def test_claims_require_named_reviewer_date_checks_rights_and_notes(self):
        for changes in (
            {"reviewer_name": "Unnamed, no other fields"},
            {"reviewed_at_utc": "2026-10-16T19:20:00Z"},
            {"reviewer_name": "Reviewer", "reviewed_at_utc": "bad"},
        ):
            other = copy.deepcopy(self.rows)
            other[0].update(changes)
            with self.assertRaises(ReviewReconciliationHold):
                self.check(rows=other)
        for invalid in (
            {"reviewer_name": ""},
            {"reviewed_at_utc": "2026-10-18T13:00:00Z"},
            {"reviewed_at_utc": "2026-13-16T19:30:00Z"},
            {"publisher_link_use_review": "licensed"},
            {"publisher_link_use_review": ""},
            {"original_language_checked": "maybe"},
            {"review_notes": ""},
        ):
            other = copy.deepcopy(self.rows)
            self.complete(other[0])
            other[0].update(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(
                    ReviewReconciliationHold):
                self.check(rows=other)

    def test_reviewer_names_and_private_notes_are_never_exported(self):
        # The historical geographic hold sorts before other originals; do
        # not accidentally turn the privacy test into an illegal allow claim.
        candidate = next(
            row for row in self.rows if row["source_geography_hold"] == "NO")
        self.complete(candidate)
        out = json.dumps(self.check())
        self.assertNotIn("Synthetic reviewer", out)
        self.assertNotIn("Fictional review", out)
        self.assertNotIn(candidate["official_url"], out)
        self.assertNotIn(candidate["source_identity"], out)

    def test_cli_strict_headers_size_and_no_raw_personal_errors(self):
        with tempfile.TemporaryDirectory() as dirname:
            directory = Path(dirname)
            manifest_path = directory / "manifest.json"
            worksheet_path = directory / "worksheet.csv"
            manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
            def save(rows, headers=REVIEW_FIELDS):
                with worksheet_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
            # Synthetic manifest does not match genuine pinned digest; the
            # production CLI must NOT accept it even when its hash is coherent.
            save(self.rows)
            self.assertEqual(main(["--manifest", str(manifest_path),
                                   "--worksheet", str(worksheet_path)]), 2)
            worksheet_path.write_text("name,not_a_review\nfoo,bar\n",
                                      encoding="utf-8")
            self.assertEqual(main(["--manifest", str(manifest_path),
                                   "--worksheet", str(worksheet_path)]), 2)
            worksheet_path.write_text("x" * 350001, encoding="utf-8")
            self.assertEqual(main(["--manifest", str(manifest_path),
                                   "--worksheet", str(worksheet_path)]), 2)

    def test_doc_and_workflow_are_not_promotional(self):
        source = (Path(__file__).resolve().parents[1] / ".github" /
                  "workflows" / "indonesia_unsigned_review_reconciliation.yml"
                  ).read_text(encoding="utf-8")
        self.assertIn("contents: read", source)
        self.assertNotIn("contents: write", source)
        self.assertNotIn("pages: write", source)
        self.assertNotIn("git push ", source)
        self.assertNotIn("schedule:", source)
        self.assertIn("tests.test_indonesia_unsigned_review_reconciliation",
                      source)


if __name__ == "__main__":
    unittest.main()
