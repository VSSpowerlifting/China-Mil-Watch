"""Offline, synthetic-Git contracts for the v2 evidence verifier.

No production archives, SQLite databases, network calls, or topic writes.
Each test builds temporary *synthetic* archives; no synthetic fact or reviewer
approval may be confused with original IPR records.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import verify_topic_v2_evidence as verifier  # noqa: E402


TOPIC_ROWS = (
    ("space_security", ("positive", "positive", "negative", "borderline")),
    ("east_china_sea", ("positive", "positive", "negative", "unassessable")),
    ("export_controls_sanctions", ("positive", "positive", "borderline")),
    ("military_hadr", ("positive", "positive", "positive", "negative")),
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()


class EvidenceVerifierSyntheticGit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ipr-topic-verifier-")
        cls.root = Path(cls.temp.name)
        (cls.root / "output" / "record").mkdir(parents=True)
        (cls.root / "research" / "topic_v2_evidence").mkdir(parents=True)
        _git(cls.root, "init")
        source_rows = []
        cls.examples = {}
        next_id = 101

        for topic, statuses in TOPIC_ROWS:
            cls.examples[topic] = []
            for status in statuses:
                record_id = next_id
                next_id += 1
                source_url = (
                    "https://official.example.test/record/%d" % record_id
                )
                # Synthetic UTF-16 supplementary character preceding evidence
                # verifies that offsets are code units, not Python code points.
                if status == "unassessable":
                    html = (
                        '<section><th>Original URL</th><td><a href="%s">'
                        'Source</a></td></section>'
                    ) % source_url
                else:
                    html = (
                        '<section><th>Original URL</th><td><a href="%s">'
                        'Source</a></td></section>'
                        '<div class="original-text" lang="en">'
                        '<p>SYNTHETIC &#x1F680; archive %d: '
                        'specific action &#39;for testing only&#39;.</p>'
                        '</div>'
                    ) % (source_url, record_id)
                archive = (
                    cls.root / "output" / "record"
                    / ("%d.html" % record_id)
                )
                archive.write_text(html, encoding="utf-8")
                normalized = verifier._body_from_archived_html(html)
                evidence = None
                if status != "unassessable":
                    marker = "specific action"
                    start = verifier._utf16_units(
                        normalized[:normalized.index(marker)]
                    )
                    end = start + verifier._utf16_units(
                        normalized[normalized.index(marker):]
                    )
                    evidence = {
                        "offset_start": start,
                        "offset_end": end,
                        "quote": normalized[normalized.index(marker):],
                    }
                row = {
                    "record_id": record_id,
                    "desk_id": "china",
                    "source_slug": "synthetic_official",
                    "source_stated_date": "2026-10-07",
                    "title_original": "SYNTHETIC Title %d" % record_id,
                    "title_english": None,
                    "canonical_url": source_url,
                    "archive_path": "output/record/%d.html" % record_id,
                    "review_state": "pending_human",
                    "provisional_status": status,
                    "rationale": "Synthetic non-editorial fixture.",
                    "stored_text_chars": verifier._utf16_units(normalized),
                    "evidence": evidence,
                }
                cls.examples[topic].append(row)
                source_rows.append([
                    record_id, "2026-10-07", 0, 0,
                    "", "SYNTHETIC Title %d" % record_id,
                ])

        assert len(source_rows) == 15
        index = {
            "snapshot": {"records": len(source_rows)},
            "sources": [
                {"code": "synthetic_official",
                 "desk": {"code": "china"}},
            ],
            "records": source_rows,
        }
        (cls.root / "output" / "corpus-index.json").write_text(
            json.dumps(index, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        _git(cls.root, "add", "output")
        _git(
            cls.root, "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=synthetic@example.test",
            "commit", "-m", "fixture: pin nonproduction source objects",
        )
        cls.source_commit = _git(cls.root, "rev-parse", "HEAD")
        cls.index_sha = _git(
            cls.root, "rev-parse", "HEAD:output/corpus-index.json"
        )
        for examples in cls.examples.values():
            for row in examples:
                row["archive_blob_sha"] = _git(
                    cls.root, "rev-parse",
                    "HEAD:%s" % row["archive_path"],
                )
        cls.docs = {
            topic: {
                "sample_version": 1,
                "topic": topic,
                "source_commit": cls.source_commit,
                "source_index_path": "output/corpus-index.json",
                "source_index_blob_sha": cls.index_sha,
                "classification_status":
                    "provisional_control_candidates_only",
                "records": rows,
            }
            for topic, rows in cls.examples.items()
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.docs = copy.deepcopy(self.docs)
        self._write_docs()

    def _write_docs(self):
        for topic, doc in self.docs.items():
            path = (
                self.root / "research" / "topic_v2_evidence"
                / ("%s.json" % topic)
            )
            path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def _validate(self):
        self._write_docs()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(verifier, "ROOT", self.root)
            )
            stack.enter_context(
                patch.object(
                    verifier,
                    "EVIDENCE_DIR",
                    self.root / "research" / "topic_v2_evidence",
                )
            )
            return verifier.validate()

    def test_exact_pinned_fixture_with_unicode_offsets_passes(self):
        rows = self._validate()
        self.assertEqual(len(rows), 15)
        self.assertEqual(
            sum(r["provisional_status"] == "positive" for r in rows), 9
        )
        self.assertEqual(
            sum(r["provisional_status"] == "unassessable" for r in rows), 1
        )

    def test_excerpt_tampering_is_refused(self):
        self.docs["space_security"]["records"][0]["evidence"]["quote"] = (
            "fabricated evidence"
        )
        with self.assertRaisesRegex(ValueError, "excerpt mismatch"):
            self._validate()

    def test_historical_record_blob_substitution_is_refused(self):
        self.docs["space_security"]["records"][0][
            "archive_blob_sha"
        ] = "0" * 40
        with self.assertRaisesRegex(ValueError, "archive blob differs"):
            self._validate()

    def test_canonical_source_url_drift_is_refused(self):
        self.docs["space_security"]["records"][0]["canonical_url"] = (
            "https://unrelated.example.test/record/101"
        )
        with self.assertRaisesRegex(ValueError, "canonical source URL mismatch"):
            self._validate()

    def test_source_index_date_drift_is_refused(self):
        self.docs["space_security"]["records"][0][
            "source_stated_date"
        ] = "2026-10-08"
        with self.assertRaisesRegex(ValueError, "index mismatch"):
            self._validate()

    def test_wrong_source_index_blob_is_refused(self):
        self.docs["space_security"]["source_index_blob_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "cross-topic source pins diverge"):
            self._validate()

    def test_unknown_archive_commit_is_refused(self):
        for doc in self.docs.values():
            doc["source_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "git rev-parse failed"):
            self._validate()

    def test_mutated_reviewer_state_cannot_be_laundered_as_human(self):
        self.docs["space_security"]["records"][0][
            "review_state"
        ] = "human_approved"
        with self.assertRaisesRegex(ValueError, "no human review is authorized"):
            self._validate()

    def test_invalid_approval_status_is_refused(self):
        self.docs["space_security"]["records"][0][
            "provisional_status"
        ] = "approved"
        with self.assertRaisesRegex(ValueError, "invalid status"):
            self._validate()

    def test_unassessable_source_never_carries_a_quote(self):
        self.docs["east_china_sea"]["records"][-1]["evidence"] = {
            "offset_start": 0, "offset_end": 1, "quote": "a",
        }
        with self.assertRaisesRegex(ValueError, "missing-body entry"):
            self._validate()

    def test_duplicate_identity_is_refused(self):
        records = self.docs["space_security"]["records"]
        records[1]["record_id"] = records[0]["record_id"]
        with self.assertRaisesRegex(ValueError, "duplicate record"):
            self._validate()

    def test_positive_control_floor_is_enforced(self):
        records = self.docs["export_controls_sanctions"]["records"]
        records[0]["provisional_status"] = "negative"
        with self.assertRaisesRegex(ValueError, "fewer than two"):
            self._validate()

    def test_missing_evidence_is_refused(self):
        self.docs["military_hadr"]["records"][0]["evidence"] = None
        with self.assertRaisesRegex(ValueError, "absent exact source evidence"):
            self._validate()

    def test_empty_rationale_is_refused(self):
        self.docs["military_hadr"]["records"][0]["rationale"] = "  "
        with self.assertRaisesRegex(ValueError, "no rationale"):
            self._validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
