"""One-week JP MOD shadow intake never promotes metadata into model evidence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.japan_weekly_shadow_intake import (
    IntakeError, snapshot_bytes, summarize, build, main,
)
from scripts.shadow_collect_japan import SCHEMA

WEEK = "2026-10-10"
STATE_SHA = "a" * 40
URL = "https://www.mod.go.jp/j/press/news/2026/10/05b.pdf"


def fake_db(*, url=URL, body="公式発表の完全な原文" * 38,
            language="ja", bad_hash=False, data_day="2026-10-05",
            source="jp_mod_news_ja", make_gap=True, malformed_capture=False):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "shadow.db"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with sqlite3.connect(path) as cx:
            cx.executescript(SCHEMA)
            cx.execute(
                "INSERT INTO shadow_records (url,source_slug,title_original,"
                "text_original,published_date,language_tag,publication_kind,"
                "content_sha256,capture_sha256,first_seen_run)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (url, source, "日米合同委員会合意について",
                 body, data_day, language, "press release",
                 "0" * 64 if bad_hash else digest,
                 "notahash" if malformed_capture else "b" * 64,
                 "37404326269-1"),
            )
            if make_gap:
                cx.execute(
                    "INSERT INTO shadow_unretrieved (url,title_original,published_date,reason,"
                    "first_seen_run,last_seen_run,seen_count)"
                    " VALUES (?,?,?,?,?,?,?)",
                    ("https://www.mod.go.jp/j/press/news/2026/10/other.html",
                     "Unretrieved HTML", "2026-10-06", "access_challenged",
                     "attempt-1", "attempt-2", 2)
                )
            cx.commit()
        return path.read_bytes()


def report(data=None, *, as_of=WEEK):
    return summarize(fake_db() if data is None else data,
                     state_commit=STATE_SHA, week_ending=WEEK, as_of=as_of)


class JapanWeeklyShadowIntake(unittest.TestCase):
    def test_original_text_verifies_but_never_enters_model(self):
        r = report()
        self.assertEqual(r["current_week_text_records"], 1)
        self.assertEqual(r["archive_total_original_text_records"], 1)
        self.assertEqual(r["unretrieved_counts_by_reason"], {"access_challenged": 1})
        self.assertEqual(r["source_candidates"][0]["text_sha256"],
                         hashlib.sha256(("公式発表の完全な原文" * 38).encode()).hexdigest())
        self.assertEqual(r["source_candidates"][0]["text_chars"],
                         len("公式発表の完全な原文" * 38))
        self.assertEqual(r["source_candidates"][0]["first_seen_run"], "37404326269-1")
        self.assertNotIn("公式発表の完全な原文", json.dumps(r, ensure_ascii=False))
        for field in (
            "known_publication_coverage_incomplete",):
            self.assertTrue(r[field])
        for field in ("eligible_for_automatic_model_drafting",
                      "candidate_human_review_completed", "source_rights_approved",
                      "english_press_collected", "joint_staff_collected",
                      "original_pdf_bytes_retained", "weekly_edition_approved",
                      "production_eligible"):
            self.assertIs(r[field], False)
        self.assertEqual(r["state_or_production_writes"], 0)

    def test_data_cutoff_and_empty_week_do_not_invent_silence(self):
        r = report(as_of="2026-10-09")
        self.assertEqual(r["current_week_text_records"], 1)
        self.assertEqual(r["source_cutoff"], "2026-10-09")
        r = report(fake_db(data_day="2026-09-24"))
        self.assertEqual(r["current_week_text_records"], 0)
        self.assertTrue(r["known_publication_coverage_incomplete"])

    def test_invalid_date_scope_rejected(self):
        for saturday, cutoff in [
            ("2026-10-11","2026-10-11"),
            ("2026-10-10","2026-10-03"),
            ("2026-10-10","2026-10-11"),
            ("2026-10-10","2026-10-9"),
        ]:
            with self.subTest(saturday=saturday,cutoff=cutoff):
                with self.assertRaises(IntakeError):
                    summarize(fake_db(),state_commit=STATE_SHA,
                              week_ending=saturday, as_of=cutoff)

    def test_partial_week_never_claims_snapshot_completeness(self):
        r = report(as_of="2026-10-08")
        self.assertEqual(r["source_cutoff"], "2026-10-08")
        self.assertIs(r["full_reporting_week_elapsed_at_cutoff"], False)
        self.assertIs(r["source_snapshot_completeness_attested"], False)
        self.assertEqual(r["current_week_text_records"], 1)
        self.assertTrue(r["known_publication_coverage_incomplete"])
        full_cutoff = report(as_of="2026-10-10")
        self.assertIs(full_cutoff["full_reporting_week_elapsed_at_cutoff"], True)
        self.assertIs(full_cutoff["source_snapshot_completeness_attested"], False)

    def test_text_hash_or_capture_digest_tamper_refused(self):
        for key in ("bad_hash", "malformed_capture"):
            with self.subTest(key=key), self.assertRaises(IntakeError):
                report(fake_db(**{key:True}))

    def test_rejects_forged_outside_host_source_or_language(self):
        for opts in (
            {"url":"https://evil.example/j/press/2026/10/05.pdf"},
            {"url":"http://www.mod.go.jp/j/press/news/2026/10/05b.pdf"},
            {"url":"https://www.mod.go.jp/en/press/foreign.html"},
            {"language":"en"},
            {"source":"jp_joint_staff_en"},
        ):
            with self.subTest(opts=opts), self.assertRaises(IntakeError):
                report(fake_db(**opts))

    def test_cannot_claim_original_pdf_capture_from_hash_alone(self):
        r = report()
        item = r["source_candidates"][0]
        self.assertIs(item["original_pdf_bytes_retained"], False)
        self.assertIs(item["human_language_and_rights_review_complete"], False)
        self.assertIs(item["eligible_for_automatic_model_drafting"], False)
        self.assertEqual(item["verification"],
                         "text_digest_verified_from_immutable_shadow_sqlite")

    def test_exact_git_db_blob_not_mutable_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            state=root / "state"
            state.mkdir()
            db=state/"shadow.db"
            expected=fake_db()
            db.write_bytes(expected)
            subprocess.run(["git","add","."],cwd=root,check=True)
            subprocess.run(["git","-c","user.name=Test",
                            "-c","user.email=test@example.invalid",
                            "commit","-qm","source evidence"],cwd=root,check=True)
            head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,
                                         text=True).strip()
            db.write_bytes(b"tampered mutable worktree")
            actual,blob=snapshot_bytes(root,head)
            self.assertEqual(actual,expected)
            self.assertEqual(len(blob),40)
            with self.assertRaises(IntakeError):
                snapshot_bytes(root,"shadow/jp-mod")
            built=build(state_repo=root,state_commit=head,
                        week_ending=WEEK,as_of=WEEK)
            self.assertEqual(built["shadow_db_git_blob_sha1"],blob)
            self.assertEqual(built["current_week_text_records"],1)

    def test_extra_tree_file_or_missing_git_object_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(IntakeError):
                snapshot_bytes(tmp,"f"*40)

    def test_invalid_sqlite_or_commit_refused(self):
        with self.assertRaises(IntakeError):
            summarize(b"random",state_commit=STATE_SHA,week_ending=WEEK,as_of=WEEK)
        with self.assertRaises(IntakeError):
            summarize(fake_db(),state_commit="main",week_ending=WEEK,as_of=WEEK)

    def test_cli_existing_output_refused_before_any_git_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"already.json"
            out.write_text("preserve me")
            with self.assertRaises(SystemExit):
                main(["--state-repo", tmp, "--state-commit", STATE_SHA,
                      "--week-ending",WEEK,"--as-of",WEEK,"--output",str(out)])
            self.assertEqual(out.read_text(),"preserve me")


if __name__ == "__main__":
    unittest.main()
