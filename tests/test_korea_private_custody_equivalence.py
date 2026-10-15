"""Offline Korea archive equivalence tests: only synthetic local Git clones."""
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import verify_korea_private_custody_equivalence as custody


def git(path, *cmd):
    proc = subprocess.run(["git", "-C", str(path), *cmd], capture_output=True,
                          text=True, check=True, timeout=15)
    return proc.stdout.strip()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")


def stamp(state, content):
    sha = hashlib.sha256(content).hexdigest()
    (state / "captures" / (sha + ".bin")).write_bytes(content)
    return sha


def fixture(folder):
    src = Path(folder) / "source"
    src.mkdir()
    git(src, "init", "-q")
    git(src, "config", "user.email", "test@example.invalid")
    git(src, "config", "user.name", "Offline Fixture")
    state = src / "state"
    (state / "ledger").mkdir(parents=True)
    (state / "captures").mkdir()
    original = stamp(state, b"synthetic-hwpx-no-real-korean-original")
    article = stamp(state, b"synthetic-html-no-original-copy")
    write_json(state / "clock.json", {
        "desk": "korea", "day_zero_utc": "2026-10-06T16:52:01+00:00",
        "day_zero_run_id": "local-native-20261006-korea",
    })
    write_json(state / "ledger" / "20261014T205938.600469+0000-38636466191-1.json", {
        "desk": "korea", "run_id": "38636466191-1", "target_date": "2026-10-14",
        "target_date_source": "schedule-slot", "health": "ok", "result": "ok",
    })
    con = sqlite3.connect(state / "shadow.db")
    try:
        con.executescript("""
        CREATE TABLE shadow_meta (desk TEXT PRIMARY KEY);
        CREATE TABLE shadow_records (
          source_identity TEXT PRIMARY KEY, url TEXT NOT NULL,
          source_slug TEXT NOT NULL, text_original TEXT NOT NULL,
          content_sha256 TEXT NOT NULL, capture_sha256 TEXT NOT NULL,
          metadata_json TEXT NOT NULL
        );
        INSERT INTO shadow_meta VALUES ('korea');
        """)
        for i in range(5):
            ident = str(156784100 + i)
            text = "Synthetic original " + ident
            con.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?)", (
                "korea-policy:" + ident,
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + ident,
                "kr_policy_mnd_releases", text,
                hashlib.sha256(text.encode()).hexdigest(), article,
                json.dumps({"document_capture_sha256": original}),
            ))
        con.commit()
    finally:
        con.close()
    git(src, "add", "state")
    git(src, "commit", "-q", "-m", "synthetic pinned state")
    frozen = git(src, "rev-parse", "HEAD")
    dst = Path(folder) / "candidate"
    subprocess.run(["git", "clone", "-q", str(src), str(dst)], check=True,
                   capture_output=True, text=True, timeout=15)
    git(dst, "config", "user.email", "test@example.invalid")
    git(dst, "config", "user.name", "Offline Fixture")
    return src, dst, frozen, article, original


class KoreaPrivateCustodyEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source, self.candidate, self.frozen, self.html, self.hwpx = (
            fixture(self.temp.name)
        )

    def compare(self):
        return custody.compare(self.source, self.candidate,
                               frozen_commit=self.frozen)

    def test_exact_cloned_state_passes_but_never_authorizes_cutover(self):
        result = self.compare()
        self.assertEqual(result["preserved_git_commit"], self.frozen)
        self.assertEqual(result["original_count"], 5)
        self.assertEqual(result["capture_count"], 2)
        self.assertEqual(result["ledger_count"], 1)
        self.assertTrue(result["source_and_candidate_bytes_identical"])
        self.assertTrue(result["october_12_historical_gap_remains"])
        for key in ("candidate_repository_privacy_verified",
                    "credential_scope_verified", "restore_tested",
                    "scheduled_collector_switched", "migration_performed_by_this_tool",
                    "public_history_or_artifacts_deleted", "source_rights_approved",
                    "sunday_or_ai_or_email_authorized",
                    "production_promotion_authorized"):
            self.assertIs(result[key], False)
        data = json.dumps(result)
        self.assertNotIn("Synthetic original", data)
        self.assertNotIn("synthetic-hwpx", data)

    def test_same_tree_and_nested_tree_are_not_private_copies(self):
        for target in (self.source, self.source / "state"):
            with self.subTest(target=str(target)), self.assertRaises(custody.CustodyHold):
                custody.compare(self.source, target, frozen_commit=self.frozen)

    def test_corrupted_capture_refused_even_if_file_present(self):
        capture = self.candidate / "state" / "captures" / (self.hwpx + ".bin")
        capture.write_bytes(b"corrupted")
        with self.assertRaises(custody.CustodyHold):
            self.compare()
        git(self.candidate, "add", "-A")
        git(self.candidate, "commit", "-q", "-m", "bad capture")
        with self.assertRaises(custody.CustodyHold):
            self.compare()

    def test_missing_ledger_or_untracked_secret_file_fails(self):
        (self.candidate / "state" / "ledger" /
         "20261014T205938.600469+0000-38636466191-1.json").unlink()
        with self.assertRaises(custody.CustodyHold):
            self.compare()
        git(self.candidate, "reset", "--hard", "HEAD")
        (self.candidate / "state" / "private-reviewer-name.txt").write_text("secret")
        with self.assertRaises(custody.CustodyHold):
            self.compare()

    def test_unexpected_symlink_and_renamed_capture_refused(self):
        p = self.candidate / "state" / "captures" / "outside.bin"
        p.symlink_to(self.candidate / "state" / "clock.json")
        with self.assertRaises(custody.CustodyHold):
            self.compare()
        p.unlink()
        path = self.candidate / "state" / "captures" / (self.hwpx + ".bin")
        path.rename(path.with_name("b" * 64 + ".bin"))
        with self.assertRaises(custody.CustodyHold):
            self.compare()

    def test_fake_historical_october_12_success_never_requalifies(self):
        ledger = self.source / "state" / "ledger" / (
            "20261012T220000.000000+0000-1234567-1.json")
        write_json(ledger, {
            "desk": "korea", "run_id": "1234567-1",
            "target_date": "2026-10-12",
            "target_date_source": "schedule-slot",
            "health": "ok", "result": "ok",
        })
        git(self.source, "add", "state")
        git(self.source, "commit", "-q", "-m", "fabricated gap repair")
        with self.assertRaises(custody.CustodyHold):
            custody.inventory(self.source, frozen_commit=self.frozen)

    def test_wrong_desk_or_korean_original_text_hash_fails(self):
        p = self.source / "state" / "clock.json"
        write_json(p, {"desk": "indonesia",
                       "day_zero_utc": "2026-10-06T16:52:01+00:00"})
        with self.assertRaises(custody.CustodyHold):
            custody.inventory(self.source, frozen_commit=self.frozen)
        git(self.source, "reset", "--hard", "HEAD")
        con = sqlite3.connect(self.source / "state" / "shadow.db")
        con.execute("UPDATE shadow_records SET content_sha256=?", ("a" * 64,))
        con.commit()
        con.close()
        git(self.source, "add", "state")
        git(self.source, "commit", "-q", "-m", "spoofed original text")
        with self.assertRaises(custody.CustodyHold):
            custody.inventory(self.source, frozen_commit=self.frozen)

    def test_clone_is_not_sufficient_if_frozen_commit_missing(self):
        with self.assertRaises(custody.CustodyHold):
            custody.compare(self.source, self.candidate,
                            frozen_commit="f" * 40)


if __name__ == "__main__":
    unittest.main()
