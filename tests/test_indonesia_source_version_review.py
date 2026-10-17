"""Synthetic fail-closed Indonesia immutable-original review version contracts."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.bind_indonesia_review_versions import (
    HELD_ID, PIN, IndonesiaReviewHold, build_manifest, write_private,
)
from scripts.prepare_indonesia_reference_review_queue import HELD_PATH


def fixture():
    raw, rows = [], []
    for i in range(31):
        held = i == 30
        path = HELD_PATH if held else (
            "/2026/10/15/synthetic-indonesian-original-%02d.html" % i)
        sid = "kemhan:" + path
        title = "Synthetic Ministry title %02d" % i
        text = "Fictional Indonesian source text number %02d" % i
        url = "https://www.kemhan.go.id" + path
        raw.append({
            "source_identity": sid, "source_slug": "id_kemhan_news",
            "url": url, "title_original": title,
            "published_date": "2026-10-02" if held else "2026-10-15",
            "first_seen_run": "39000000001-1", "language_tag": "id",
            "text_original": text,
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "capture_sha256": hashlib.sha256(
                ("fictional-capture-%02d" % i).encode()).hexdigest(),
        })
        rows.append({
            "publication_date": raw[-1]["published_date"],
            "title_original": title,
            "official_url": url, "source_identity": sid,
            "first_seen_run": "39000000001-1",
            "disposition": (
                "hold_publisher_geography_inconsistent" if held else
                "official_link_already_public_not_reviewed" if i < 15 else
                "new_source_review_candidate"),
            "independent_human_review_complete": False,
            "publisher_body_reuse_authorized": False,
            "eligible_for_public_corpus": False,
        })
    return {
        "schema": "ipr-indonesia-private-review-queue/1",
        "source_family": "id_kemhan_news",
        "state_commit": PIN,
        "stored_originals": 31,
        "counts": {
            "official_link_already_public_not_reviewed": 15,
            "hold_publisher_geography_inconsistent": 1,
            "new_source_review_candidate": 15,
        },
        "public_renderer_consumes_queue": False,
        "independent_human_review_completed": False,
        "source_reuse_approved": False,
        "public_corpus_admitted": False,
        "rows": rows,
    }, raw


class IndonesiaVersionBoundReview(unittest.TestCase):
    def setUp(self):
        self.queue, self.originals = fixture()

    def test_every_original_bound_without_body_or_approval(self):
        packet = build_manifest(self.queue, self.originals)
        self.assertEqual(packet["originals_version_bound"], 31)
        self.assertEqual(packet["known_geography_holds"], 1)
        self.assertEqual(len(packet["records"]), 31)
        self.assertFalse(packet["human_review_authenticated"])
        self.assertFalse(packet["production_admission_authorized"])
        self.assertFalse(packet["archived_capture_bytes_independently_authenticated"])
        self.assertEqual(
            sum(x["known_geography_hold"] for x in packet["records"]), 1)
        self.assertEqual(next(x for x in packet["records"]
                              if x["known_geography_hold"])["source_identity"], HELD_ID)
        serialized = json.dumps(packet)
        self.assertNotIn(self.originals[0]["text_original"], serialized)
        self.assertNotIn(self.originals[0]["title_original"], serialized)
        self.assertNotIn("original_text", packet["records"][0])
        for record in packet["records"]:
            self.assertEqual(len(record["source_version_sha256"]), 64)
            self.assertFalse(record["rights_or_publication_authorized"])

    def test_mutating_a_source_version_changes_exact_identity_digest(self):
        before = build_manifest(self.queue, self.originals)
        after = copy.deepcopy(self.originals)
        after[0]["text_original"] += " new publisher version"
        after[0]["content_sha256"] = hashlib.sha256(
            after[0]["text_original"].encode()).hexdigest()
        next_packet = build_manifest(self.queue, after)
        self.assertNotEqual(before["manifest_sha256"],
                            next_packet["manifest_sha256"])
        m1 = {x["source_identity"]: x["source_version_sha256"]
              for x in before["records"]}
        m2 = {x["source_identity"]: x["source_version_sha256"]
              for x in next_packet["records"]}
        changed = [k for k in m1 if m1[k] != m2[k]]
        self.assertEqual(len(changed), 1)

    def test_original_body_or_digest_mutation_is_rejected(self):
        damaged = copy.deepcopy(self.originals)
        damaged[0]["text_original"] = "unpreserved substituted text"
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(self.queue, damaged)
        damaged = copy.deepcopy(self.originals)
        damaged[0]["capture_sha256"] = "bad"
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(self.queue, damaged)

    def test_missing_duplicate_extra_or_inconsistent_source_fails(self):
        cases = [
            self.originals[:-1], self.originals + [self.originals[0]],
        ]
        for originals in cases:
            with self.subTest(n=len(originals)):
                with self.assertRaises(IndonesiaReviewHold):
                    build_manifest(self.queue, originals)
        damaged = copy.deepcopy(self.originals)
        damaged[0]["url"] = "https://untrusted.example/story"
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(self.queue, damaged)
        damaged = copy.deepcopy(self.queue)
        damaged["rows"][0]["official_url"] = "https://untrusted.example/story"
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(damaged, self.originals)

    def test_false_review_or_semantic_hold_release_is_refused(self):
        for key in ("independent_human_review_completed",
                    "source_reuse_approved", "public_corpus_admitted"):
            damaged = copy.deepcopy(self.queue)
            damaged[key] = True
            with self.subTest(key=key), self.assertRaises(IndonesiaReviewHold):
                build_manifest(damaged, self.originals)
        changed = copy.deepcopy(self.queue)
        changed["rows"][30]["disposition"] = "new_source_review_candidate"
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(changed, self.originals)
        changed = copy.deepcopy(self.queue)
        changed["rows"][0]["publisher_body_reuse_authorized"] = True
        with self.assertRaises(IndonesiaReviewHold):
            build_manifest(changed, self.originals)

    def test_private_csv_contains_blank_review_cells_and_permanent_hold(self):
        packet = build_manifest(self.queue, self.originals)
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "review"
            folder.mkdir()
            write_private(packet, folder)
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["original_version_manifest.json",
                              "review_decisions_UNSIGNED.csv"])
            with (folder/"review_decisions_UNSIGNED.csv").open(
                    newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 31)
            self.assertEqual({r["reviewer_name"] for r in rows}, {""})
            self.assertEqual({r["reviewed_at_utc"] for r in rows}, {""})
            self.assertEqual({r["publisher_link_use_review"] for r in rows},
                             {""})
            self.assertEqual({r["source_body_reuse_review"] for r in rows},
                             {""})
            held = [x for x in rows
                    if x["source_identity"] == HELD_ID]
            self.assertEqual(held[0]["source_geography_hold"],
                             "YES — MUST REMAIN HELD")
            self.assertRaises(
                IndonesiaReviewHold, write_private, packet, folder)

    def test_pinned_git_and_private_workflow_guards(self):
        root = Path(__file__).resolve().parents[1]
        script = (root/"scripts/bind_indonesia_review_versions.py").read_text()
        workflow = (root/".github/workflows/"
                    "indonesia_pinned_reference_review_queue.yml").read_text()
        for snippet in (
            "reader._read_snapshot(", "reader.git(",
            "?mode=ro&immutable=1", "PRAGMA integrity_check",
            "count == len(items) == 31",
        ):
            self.assertIn(snippet, script)
        for snippet in (
            "scripts.bind_indonesia_review_versions",
            "original_version_manifest.json",
            "review_decisions_UNSIGNED.csv",
        ):
            self.assertIn(snippet, workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("git push ", workflow)


if __name__ == "__main__":
    unittest.main()
