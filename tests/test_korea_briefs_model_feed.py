"""Korea's private Sunday research lane: metadata cannot become unreviewed event facts."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import (
    EditorialEvidenceError, load_editorial_evidence, metadata_only_summary,
)
from scripts import prepare_korea_briefs_model_evidence as korea

WEEK = "2026-10-10"
COMMIT = "a" * 40


def record(number="156784297", day="2026-10-06"):
    return {
        "source_identity": "korea-policy:" + number,
        "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + number,
        "source_slug": "kr_policy_mnd_releases",
        "title_original": "국방부 보도자료 원문 발표 내용",
        "published_date": day,
        "language_tag": "ko",
        "metadata": {"issuer": "국방부"},
        "content_sha256": "b" * 64,
    }


class KoreaEvidenceTests(unittest.TestCase):
    def test_only_metadata_and_no_claimed_corroboration(self):
        row = korea.metadata_card(record(), COMMIT)
        self.assertEqual(row["desk"], "korea")
        self.assertEqual(row["source_kind"], "shadow-metadata-only")
        self.assertEqual(row["hash_rule"], "sha256-text-original-utf8")
        self.assertEqual(row["topics"], ["source_discovery"])
        self.assertEqual(row["summary"], metadata_only_summary("2026-10-06", desk="korea"))
        self.assertNotIn("text_original", row)
        self.assertNotIn("document_original", row)
        self.assertIn("republication", row["source_name"].lower())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / (WEEK + ".json")
            path.write_text(json.dumps({"schema": korea.SCHEMA, "status": korea.STATUS,
                                        "week_ending": WEEK, "items": [row]}))
            self.assertEqual(len(load_editorial_evidence(WEEK, WEEK, directory=Path(tmp))), 1)
            poisoned = dict(row, summary="The ministry announced an exercise involving a neighboring state.")
            path.write_text(json.dumps({"schema": korea.SCHEMA, "status": korea.STATUS,
                                        "week_ending": WEEK, "items": [poisoned]}))
            with self.assertRaises(EditorialEvidenceError):
                load_editorial_evidence(WEEK, WEEK, directory=Path(tmp))

    def test_refuse_wrong_mnd_issuer_and_link_spoof(self):
        bad = record()
        bad["metadata"]["issuer"] = "외교부"
        with self.assertRaises(korea.KoreaFeedRefused):
            korea.metadata_card(bad, COMMIT)
        bad = record()
        bad["url"] += "&redirect=https://example.org"
        with self.assertRaises(korea.KoreaFeedRefused):
            korea.metadata_card(bad, COMMIT)
        original = korea.metadata_card(record(), COMMIT)
        original["source_url"] += "&evil=1"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / (WEEK + ".json")
            p.write_text(json.dumps({"schema": korea.SCHEMA, "status": korea.STATUS,
                                     "week_ending": WEEK, "items": [original]}))
            with self.assertRaises(EditorialEvidenceError):
                load_editorial_evidence(WEEK, WEEK, directory=Path(tmp))

    def test_capacity_dedup_and_week_scope(self):
        records = [record(str(156784297 + n), "2026-10-06") for n in range(4)]
        records.append(record("156700000", "2026-09-20"))
        seed = [{"desk": "japan"}] * 4 + [{"desk": "vietnam"}]
        result, stats = korea.assemble(records, seed, COMMIT, WEEK)
        self.assertEqual(len(result["items"]), 8)
        self.assertEqual(stats["korea_in_window"], 4)
        self.assertEqual(stats["korea_in_model_pool"], 3)
        self.assertEqual(stats["korea_factual_synopses"], 0)
        self.assertEqual(len([r for r in result["items"] if r["desk"] == "korea"]), 3)

    def test_refuse_unreviewed_third_desk_input(self):
        with self.assertRaises(korea.KoreaFeedRefused):
            korea.assemble([record()], [{"desk": "korea"}], COMMIT, WEEK)

    def test_week_ending_and_dated_metadata(self):
        with self.assertRaises(korea.KoreaFeedRefused):
            korea.week_range("2026-10-09")
        with self.assertRaises(korea.KoreaFeedRefused):
            korea.metadata_card(dict(record(), content_sha256="BAD"), COMMIT)
        self.assertIn("2026-10-06", metadata_only_summary("2026-10-06", desk="korea"))

    def test_read_only_stacked_packet_and_refuse_stale_state(self):
        # Synthetic integration harness. Exact remote clone and real Git blob
        # replay are separate production proof gates; this mocks their APIs.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clone = root / "korea-clone"
            clone.mkdir()
            source = korea.ROOT / "research/briefs_editorial_evidence" / (WEEK + ".json")
            inpdir = root / "vietnam"
            inpdir.mkdir()
            inp = inpdir / (WEEK + ".json")
            inp.write_bytes(source.read_bytes())
            out = root / "combined" / (WEEK + ".json")
            original = inp.read_bytes()

            def export(_, commit, desk, destination):
                self.assertEqual(commit, COMMIT)
                self.assertEqual(desk, "korea")
                ledgers = destination / "state" / "ledger"
                ledgers.mkdir(parents=True)
                (ledgers / "first.json").write_text(json.dumps({
                    "health": "ok", "target_date": "2026-10-07"}))
                return "e" * 40

            def review(state, desk, dest, as_of, commit=None, tree=None):
                self.assertEqual(desk, "korea")
                dest.mkdir()
                (dest / "records.jsonl").write_text(json.dumps(record()) + "\n")
                return {"findings": [], "missing_successful_days": [], "records": 1,
                        "mode": "formal_commit_snapshot", "human_review_completed": False,
                        "promotion_authorized": False}

            def git(repo, *args):
                if args[0] == "rev-parse":
                    return COMMIT
                return "state"

            with patch.object(korea, "git", side_effect=git), \
                 patch.object(korea.formal, "export_commit", side_effect=export), \
                 patch.object(korea.formal, "review", side_effect=review):
                result = korea.prepare(clone, COMMIT, WEEK, inp, out,
                                       observed_on=date(2026, 10, 8))
                self.assertEqual(result["korea_in_model_pool"], 1)
                self.assertEqual(len(load_editorial_evidence(WEEK, WEEK,
                                      directory=out.parent)), 6)
                self.assertEqual(inp.read_bytes(), original)
                with self.assertRaises(korea.KoreaFeedRefused):
                    korea.prepare(clone, COMMIT, WEEK, inp, root / "second" / (WEEK + ".json"),
                                  observed_on=date(2026, 10, 11))
                with self.assertRaises(korea.KoreaFeedRefused):
                    korea.prepare(clone, COMMIT, WEEK, inp, out,
                                  observed_on=date(2026, 10, 8))


if __name__ == "__main__":
    unittest.main()
