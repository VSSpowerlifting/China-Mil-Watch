"""Offline tests for the source-static Pages writer inventory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.audit_pages_writers import inventory_directory, inventory_file


class PagesWriterInventoryTests(unittest.TestCase):
    def write(self, root: Path, name: str, contents: str) -> Path:
        path = root / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_workflow_level_daily_serialization(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.write(Path(t), "daily.yml", """name: daily
concurrency:
  group: daily-update
  cancel-in-progress: false
jobs:
  deployment:
    runs-on: ubuntu-latest
    steps:
      - uses: peaceiris/actions-gh-pages@v3
        with:
          publish_branch: gh-pages
""")
            [w] = inventory_file(p)
            self.assertEqual(w.job, "deployment")
            self.assertEqual(w.effective_group, "daily-update")
            self.assertFalse(w.report()["requires_runtime_freshness_review"])

    def test_job_level_override_and_direct_push(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.write(Path(t), "korea.yml", """name: Korea
concurrency:
  group: daily-update
jobs:
  release:
    concurrency:
      group: korea-only
      cancel-in-progress: false
    steps:
      - name: Push one file
        run: git push origin HEAD:refs/heads/gh-pages
""")
            [w] = inventory_file(p)
            self.assertEqual(w.primitive, "git-push-gh-pages")
            self.assertEqual(w.effective_group, "korea-only")
            self.assertTrue(w.report()["requires_runtime_freshness_review"])

    def test_retired_job_is_separate_from_active_publication(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.write(Path(t), "retired.yml", """jobs:
  retired:
    if: false
    steps:
      - uses: peaceiris/actions-gh-pages@v3
  active:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/deploy-pages@v4
""")
            writers = inventory_file(p)
            self.assertEqual(len(writers), 2)
            self.assertTrue(writers[0].disabled_job)
            self.assertFalse(writers[1].disabled_job)

    def test_comments_and_non_pages_push_do_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.write(Path(t), "ignored.yml", """# - uses: peaceiris/actions-gh-pages@v3
jobs:
  tests:
    steps:
      # git push origin HEAD:gh-pages
      - run: git push origin HEAD:main
""")
            self.assertEqual(inventory_file(p), [])

    def test_directory_scan_includes_both_yaml_suffixes(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.write(root, "a.yaml", """jobs:
  ship:
    steps:
      - uses: actions/deploy-pages@v4
""")
            self.write(root, "b.yml", """jobs:
  ship:
    steps:
      - run: git push origin HEAD:gh-pages
""")
            self.assertEqual(len(inventory_directory(root)), 2)

    def test_nonexistent_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError, "does not exist"):
                inventory_directory(Path(t) / "not-there")


if __name__ == "__main__":
    unittest.main()
