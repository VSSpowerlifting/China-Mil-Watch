"""USCC/Treasury production writer must repair pending schema before admission.

Real tracked SQLite bytes are copied into a disposable temp; never modify main.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_db_current import classify

ROOT = Path(__file__).resolve().parents[1]
TRACKED = ROOT / "pla_watch.db"
WORKFLOWS = [
    ROOT / ".github/workflows/uscc_verified_official_links_release.yml",
    ROOT / ".github/workflows/treasury_verified_official_links_release.yml",
]


class USMetadataMigrationPreflight(unittest.TestCase):
    def test_both_source_release_writers_migrate_before_admitting_records(self):
        for p in WORKFLOWS:
            with self.subTest(workflow=p.name):
                yaml = p.read_text(encoding="utf-8")
                preflight = ('python -m migrations.cli --apply --db '
                             '"$GITHUB_WORKSPACE/pla_watch.db"')
                assert_index = yaml.index(preflight)
                admit_index = yaml.index("python -m scripts.admit_")
                verify_index = yaml.index("python scripts/verify_db_current.py")
                self.assertLess(assert_index, verify_index)
                self.assertLess(verify_index, admit_index)
                self.assertIn("git add -- pla_watch.db output/us-indopacific.html", yaml)
                self.assertIn("sha256sum output/us-indopacific.html", yaml)
                self.assertIn("cp ../output/us-indopacific.html", yaml)

    def test_disposable_preflight_repairs_partial_migration_without_data_loss(self):
        # Reproduce the exact observed production failure mode: one migration
        # was merged on main, and the stored schema ledger was missing a row.
        self.assertTrue(TRACKED.is_file())
        before_hash = hashlib.sha256(TRACKED.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="ipr-us-schema-preflight-") as directory:
            db = Path(directory) / "archive-copy.sqlite"
            shutil.copyfile(TRACKED, db)
            with sqlite3.connect(str(db)) as con:
                counts_before = {
                    tbl: con.execute("SELECT COUNT(*) FROM " + tbl).fetchone()[0]
                    for tbl in ("articles", "sources", "scrape_runs")
                }
                con.execute("DELETE FROM schema_migrations WHERE version='0008'")
                con.commit()
                self.assertEqual(classify(con), "partially_applied")
            # Run precisely the repair command both U.S. workflows invoke,
            # against ONLY this temporary copy. The real DB is untouched.
            subprocess.run(
                [sys.executable, "-m", "migrations.cli",
                 "--apply", "--db", str(db)],
                cwd=ROOT, check=True, text=True, capture_output=True,
            )
            with sqlite3.connect(str(db)) as con:
                self.assertEqual(classify(con), "fully_current")
                self.assertEqual(
                    {tbl: con.execute("SELECT COUNT(*) FROM " + tbl).fetchone()[0]
                     for tbl in counts_before},
                    counts_before,
                )
                self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0],
                                 "ok")
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version='0008'"
                ).fetchone()[0], 1)
        self.assertEqual(hashlib.sha256(TRACKED.read_bytes()).hexdigest(),
                         before_hash)
        self.assertFalse((ROOT / "pla_watch.db-wal").exists())
        self.assertFalse((ROOT / "pla_watch.db-shm").exists())


if __name__ == "__main__":
    unittest.main()
