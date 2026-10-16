"""Hermetic Git-object regression tests for the eight-desk parity witness."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.verify_eight_desk_pages_parity import ROUTES, ParityHold, verify


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


def html(route):
    return ('<!DOCTYPE html>\n<html lang="en" data-surface="desk" '
            'data-route="%s"><head><title>Desk</title></head>'
            '<body><main><h1>Official links</h1><p>%s</p></main></body>'
            '</html>\n' % (route, "reference" * 15))


class EightDeskParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.email", "tests@example.invalid")
        git(self.repo, "config", "user.name", "IPR synthetic tests")
        (self.repo / "output").mkdir()
        for route in ROUTES:
            (self.repo / "output" / route).write_text(html(route))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "synthetic main")
        self.main_sha = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "--orphan", "gh-pages")
        if (self.repo / "output").exists():
            shutil.rmtree(self.repo / "output")
        for route in ROUTES:
            (self.repo / route).write_text(html(route))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "synthetic pages")
        self.pages_sha = git(self.repo, "rev-parse", "HEAD")

    def check(self, pages_sha=None):
        return verify(self.repo, self.main_sha, pages_sha or self.pages_sha)

    def commit_pages(self):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "synthetic page mutation")
        return git(self.repo, "rev-parse", "HEAD")

    def test_all_eight_exact_git_objects_pass(self):
        result = self.check()
        self.assertEqual(result["desk_pages_verified"], 8)
        self.assertEqual(len({p["sha256"] for p in result["pages"]}), 8)
        self.assertFalse(result["public_https_verified"])
        self.assertFalse(result["collector_history_verified"])

    def test_one_byte_stale_page_holds(self):
        path = self.repo / "korea.html"
        path.write_text(path.read_text().replace("reference", "REFERENCE", 1))
        with self.assertRaisesRegex(ParityHold, "main_pages_drift:korea.html"):
            self.check(self.commit_pages())

    def test_missing_pages_route_holds(self):
        (self.repo / "japan.html").unlink()
        with self.assertRaisesRegex(ParityHold, "missing_or_nonregular_page:japan.html"):
            self.check(self.commit_pages())

    def test_symlink_is_not_a_regular_page(self):
        (self.repo / "vietnam.html").unlink()
        os.symlink("china.html", self.repo / "vietnam.html")
        with self.assertRaisesRegex(ParityHold, "missing_or_nonregular_page:vietnam.html"):
            self.check(self.commit_pages())

    def test_wrong_route_identity_holds(self):
        path = self.repo / "philippines.html"
        path.write_text(path.read_text().replace('data-route="philippines.html"',
                                                 'data-route="indonesia.html"'))
        with self.assertRaisesRegex(ParityHold, "unrecognized_desk_html:philippines.html"):
            self.check(self.commit_pages())

    def test_empty_or_truncated_html_holds(self):
        (self.repo / "china.html").write_text("<html>broken</html>")
        with self.assertRaisesRegex(ParityHold, "unbounded_page:china.html"):
            self.check(self.commit_pages())

    def test_untrusted_ref_string_holds(self):
        with self.assertRaisesRegex(ParityHold, "invalid_commit_sha"):
            verify(self.repo, "main^{commit}", self.pages_sha)

    def test_nonexistent_commit_holds(self):
        with self.assertRaisesRegex(ParityHold, "git_object_unavailable"):
            verify(self.repo, "0" * 40, self.pages_sha)

    def test_does_not_change_git_worktree_or_refs(self):
        before = (git(self.repo, "status", "--porcelain"),
                  git(self.repo, "rev-parse", "HEAD"))
        self.check()
        after = (git(self.repo, "status", "--porcelain"),
                 git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
