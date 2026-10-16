"""Negative and production contracts for post-cull frozen China research receipts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import verify_china_research_postcull as audit


def current():
    packet = json.loads(audit.PACKET.read_text(encoding="utf-8"))
    index = json.loads(audit.INDEX.read_text(encoding="utf-8"))
    from scripts.reconcile_db import read_only
    with read_only(audit.DATABASE) as conn:
        retired = {row[0] for row in conn.execute(
            "SELECT original_article_id FROM retired_article_urls")}
        ids = sorted(audit.RETIRED | audit.SURVIVING)
        active = {row[0] for row in conn.execute(
            "SELECT id FROM articles WHERE id IN (" +
            ",".join("?" for _ in ids) + ")", ids)}
    return packet, index, retired, active


class FrozenOriginalResearchAfterCull(unittest.TestCase):
    def assert_reconciled(self, packet, index, retired, active, record_dir=None):
        return audit.validate_postcull(
            packet, index, retired, active,
            record_dir or audit.ROOT / "output/record",
            audit.ROOT / "output/article")

    def test_current_real_corpus_preserves_retired_and_surviving_cases(self):
        packet, index, retired, active = current()
        original = copy.deepcopy((packet, index, retired, active))
        result = self.assert_reconciled(packet, index, retired, active)
        self.assertEqual(result["retired_cases_tombstoned_and_not_public"], 15)
        self.assertEqual(result["surviving_cases_current_source_checked"], 3)
        self.assertFalse(result["publication_authorized"])
        self.assertTrue(result["human_reverification_of_retired_originals_required"])
        self.assertEqual((packet, index, retired, active), original)

    def test_missing_retirement_evidence_fails_closed(self):
        packet, index, retired, active = current()
        with self.assertRaisesRegex(ValueError, "no ledger tombstone"):
            self.assert_reconciled(packet, index, retired - {2180}, active)

    def test_retired_id_in_active_corpus_fails_closed(self):
        packet, index, retired, active = current()
        with self.assertRaisesRegex(ValueError, "reentered active"):
            self.assert_reconciled(packet, index, retired, active | {2180})

    def test_ghost_public_page_fails_closed(self):
        packet, index, retired, active = current()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for ident in audit.SURVIVING:
                (path / ("%d.html" % ident)).write_bytes(
                    (audit.ROOT / "output/record" / ("%d.html" % ident)).read_bytes())
            (path / "2180.html").write_text("retired route", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "republished"):
                self.assert_reconciled(packet, index, retired, active, path)

    def test_approval_and_history_rebinding_fail_closed(self):
        packet, index, retired, active = current()
        packet["owner_approved"] = True
        with self.assertRaisesRegex(ValueError, "cannot authorize"):
            self.assert_reconciled(packet, index, retired, active)
        packet, index, retired, active = current()
        packet["baseline_snapshot"] = index["snapshot"]
        with self.assertRaisesRegex(ValueError, "historical research snapshot drift"):
            self.assert_reconciled(packet, index, retired, active)

    def test_survivor_title_drift_still_fails_original_validator(self):
        packet, index, retired, active = current()
        index = copy.deepcopy(index)
        row = next(r for r in index["records"] if r[0] == 2849)
        row[5] = "unrelated title"
        with self.assertRaisesRegex(ValueError, "case source/title/date drift"):
            self.assert_reconciled(packet, index, retired, active)

    def test_historical_packet_cannot_drop_or_duplicate_cases(self):
        packet, index, retired, active = current()
        packet["checks"].pop()
        with self.assertRaisesRegex(ValueError, "cardinality drift"):
            self.assert_reconciled(packet, index, retired, active)
        packet, index, retired, active = current()
        packet["checks"][-1]["id"] = packet["checks"][0]["id"]
        with self.assertRaisesRegex(ValueError, "identities drift"):
            self.assert_reconciled(packet, index, retired, active)


if __name__ == "__main__":
    unittest.main()
