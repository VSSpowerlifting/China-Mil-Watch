"""Regression: the actual daily workflow and Git driver launch as a script.

Importing scripts.reconcile_db in the offline suite masks Python's different
sys.path[0] when Actions calls "python scripts/reconcile_db.py --install-driver".
Use isolated subprocesses, not a test-process import or PYTHONPATH crutch.
No production DB, main Git config, network or publisher is touched.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_db.py"


class DailyReconcilerEntrypointContracts(unittest.TestCase):
    def test_help_loads_core_with_isolated_interpreter_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "--help"],
                cwd=cwd, capture_output=True, text=True, timeout=15,
                env={**os.environ, "PYTHONPATH": ""},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--install-driver", proc.stdout)
            self.assertNotIn("ModuleNotFoundError", proc.stderr)

    def test_daily_cli_registers_real_merge_driver_in_disposable_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "scripts").mkdir()
            (root / "core").mkdir()
            shutil.copy2(SCRIPT, root / "scripts" / "reconcile_db.py")
            shutil.copy2(ROOT / "core" / "retired_article_urls.py",
                         root / "core" / "retired_article_urls.py")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True,
                           capture_output=True, timeout=15)
            proc = subprocess.run(
                [sys.executable, "-I", "scripts/reconcile_db.py",
                 "--install-driver"],
                cwd=root, capture_output=True, text=True, timeout=15,
                env={**os.environ, "PYTHONPATH": ""},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            driver = subprocess.run(
                ["git", "config", "--local", "--get", "merge.reconcile-db.driver"],
                cwd=root, check=True, capture_output=True, text=True,
                timeout=15,
            ).stdout.strip()
            self.assertIn("scripts/reconcile_db.py --merge-driver %O %A %B",
                          driver)
            self.assertTrue(driver.startswith(sys.executable), driver)
            self.assertNotIn("ModuleNotFoundError", proc.stderr)


if __name__ == "__main__":
    unittest.main()
