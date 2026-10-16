"""Hermetic reproductions of gh-pages stale-deployment interleavings (#346).

Every repository here is a temporary local bare repo reached over file://.
Nothing touches GitHub, the network, production SQLite or real output/.

The publish primitives mirror the release mechanics in this repository:

* ``full_tree``: peaceiris/actions-gh-pages@v3 (373f7f26). It clones gh-pages
  at depth 1, runs ``git rm -r '*'`` unless keep_files, copies publish_dir,
  commits and runs a NON-force ``git push origin gh-pages``. It does not retry.
* ``file_only``: the korea/us/treasury/uscc/bis workflows. They check out
  gh-pages, copy one file, require ``origin/gh-pages`` to be unchanged, then
  push without force.

Tests named ``test_current_*`` CHARACTERIZE today's behaviour, including the
unsafe outcomes. They pass because the hazard is real, not because it is
fixed. ``ReferenceFence`` is a test-only sketch of the recommended fix; no
workflow uses it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

MANIFEST = ".ipr-release.json"


class StaleRefused(Exception):
    """A guarded writer refused to publish."""


class GitSandbox:
    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        self.url = self.origin.as_uri()
        self.n = 0
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_TERMINAL_PROMPT="0", HOME=str(root), GIT_AUTHOR_DATE="2026-10-15T00:00:00Z",
                        GIT_COMMITTER_DATE="2026-10-15T00:00:00Z")
        self.git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))

    def git(self, cwd, *args):
        cmd = ["git", "-c", "user.name=sandbox", "-c", "user.email=sandbox@example.invalid",
               "-c", "commit.gpgsign=false", "-c", "protocol.file.allow=always", *args]
        return subprocess.run(cmd, cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def workdir(self, label):
        self.n += 1
        path = self.root / ("%02d-%s" % (self.n, label))
        return path

    # ── main branch ──
    def seed(self, files):
        work = self.workdir("seed")
        self.git(self.root, "clone", "-q", self.url, str(work))
        self.git(work, "checkout", "-q", "-b", "main")
        self._write(work / "output", files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "seed")
        self.git(work, "push", "-q", "origin", "main")
        self.git(work, "checkout", "-q", "--orphan", "gh-pages")
        self.git(work, "rm", "-r", "-q", "--cached", ".")
        for child in work.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        self._write(work, files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "initial pages")
        self.git(work, "push", "-q", "origin", "gh-pages")

    def checkout_main(self, label="job"):
        """actions/checkout of main at job start: a frozen snapshot."""
        work = self.workdir(label)
        self.git(self.root, "clone", "-q", "--branch", "main", self.url, str(work))
        return work

    def commit_main(self, files, label="writer"):
        work = self.checkout_main(label)
        self._write(work / "output", files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "update " + ",".join(sorted(files)))
        self.git(work, "push", "-q", "origin", "HEAD:main")
        return work

    def main_sha(self):
        return self.git(self.origin, "rev-parse", "main")

    # ── gh-pages writers ──
    def full_tree(self, src_output, message="Deploy", keep_files=False, before_push=None,
                  extra=None):
        work = self.workdir("peaceiris")
        self.git(self.root, "clone", "-q", "--depth=1", "--single-branch", "--branch",
                 "gh-pages", self.url, str(work))
        if not keep_files:
            self.git(work, "rm", "-r", "-q", "--ignore-unmatch", "*")
        for path in sorted(Path(src_output).rglob("*")):
            if path.is_file():
                dest = work / path.relative_to(src_output)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
        if extra:
            self._write(work, extra)
        self.git(work, "add", "-A")
        if self.git(work, "status", "--porcelain"):
            self.git(work, "commit", "-q", "-m", message)
        if before_push:
            before_push()
        self.git(work, "push", "-q", "origin", "gh-pages")
        return work

    def file_only(self, src_file, name, message="file-only", before_push=None):
        work = self.workdir("file-only")
        self.git(self.root, "clone", "-q", "--branch", "gh-pages", self.url, str(work))
        old = self.git(work, "rev-parse", "HEAD")
        shutil.copyfile(src_file, work / name)
        self.git(work, "add", "--", name)
        staged = self.git(work, "diff", "--cached", "--name-only")
        if staged:
            self.git(work, "commit", "-q", "-m", message)
        if before_push:
            before_push()
        self.git(work, "fetch", "-q", "origin", "gh-pages")
        if self.git(work, "rev-parse", "origin/gh-pages") != old:
            raise StaleRefused("gh-pages moved; never overwrite a concurrent release")
        if staged:
            self.git(work, "push", "-q", "origin", "HEAD:gh-pages")

    def out_of_band(self, files, message="owner-local scoped push"):
        work = self.workdir("owner")
        self.git(self.root, "clone", "-q", "--branch", "gh-pages", self.url, str(work))
        self._write(work, files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", message)
        self.git(work, "push", "-q", "origin", "HEAD:gh-pages")

    # ── reads ──
    def pages(self, path):
        return self._show("gh-pages", path)

    def main(self, path):
        return self._show("main", "output/" + path)

    def pages_message(self):
        return self.git(self.origin, "log", "-1", "--format=%s", "gh-pages")

    def _show(self, ref, path):
        try:
            return self.git(self.origin, "show", "%s:%s" % (ref, path))
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def _write(base, files):
        for rel, body in files.items():
            dest = Path(base) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")


class ReferenceFence:
    """Test-only reference design. NOT used by any workflow.

    Content and a release manifest land in ONE gh-pages commit. A publish
    states the generation it expects; a forward publish must descend from
    the deployed source; a rollback must name both the expected current
    source and its target. Push stays non-force so the parent CAS also holds.
    """

    def __init__(self, box: GitSandbox):
        self.box = box

    def current(self):
        raw = self.box.pages(MANIFEST)
        return json.loads(raw) if raw else {"generation": 0, "source_sha": None}

    def publish(self, src_checkout, writer, expected_generation, rollback=None, files=None):
        box = self.box
        source_sha = box.git(src_checkout, "rev-parse", "HEAD")
        cur = self.current()
        if cur["generation"] != expected_generation:
            raise StaleRefused("generation %s != expected %s"
                               % (cur["generation"], expected_generation))
        if rollback is None:
            if cur["source_sha"]:
                box.git(src_checkout, "fetch", "-q", "origin", "main")
                ok = subprocess.run(
                    ["git", "merge-base", "--is-ancestor", cur["source_sha"], source_sha],
                    cwd=src_checkout, env=box.env).returncode == 0
                if not ok:
                    raise StaleRefused("source is not a descendant of the deployed source")
        elif (rollback.get("expected_current") != cur["source_sha"]
              or rollback.get("target") != source_sha):
            raise StaleRefused("rollback authorization does not match deployed state")
        manifest = {"generation": cur["generation"] + 1, "source_sha": source_sha,
                    "writer": writer, "rollback": bool(rollback)}
        extra = {MANIFEST: json.dumps(manifest, sort_keys=True)}
        if files is None:
            box.full_tree(src_checkout / "output", message="Deploy %s" % source_sha[:12],
                          extra=extra)
        else:
            for name in files:
                extra[name] = (src_checkout / "output" / name).read_text(encoding="utf-8")
            empty = box.root / ("overlay-src-%s" % source_sha[:8])
            empty.mkdir(exist_ok=True)
            box.full_tree(empty, keep_files=True, extra=extra,
                          message="Overlay %s" % source_sha[:12])
        return manifest


class RaceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.box = GitSandbox(self.tmp)
        self.box.seed({"index.html": "home v1", "korea.html": "korea v1",
                       "desks.html": "desks v1"})


class CurrentProtocol(RaceCase):
    def test_current_stale_full_tree_overwrites_newer_file_only_release(self):
        box = self.box
        a = box.checkout_main("A-daily")                      # A: job-start snapshot
        b = box.commit_main({"korea.html": "korea v2"}, "B-korea")
        box.file_only(b / "output" / "korea.html", "korea.html")
        self.assertEqual(box.pages("korea.html"), "korea v2")
        box.full_tree(a / "output", "Deploy: 1001")           # A publishes later
        self.assertEqual(box.pages("korea.html"), "korea v1")  # B was rolled back
        self.assertEqual(box.main("korea.html"), "korea v2")   # main still has B

    def test_current_parent_cas_only_covers_clone_to_push_window(self):
        box = self.box
        fresh = box.checkout_main("A")
        mover = box.commit_main({"desks.html": "desks v2"}, "B")

        def concurrent():
            box.file_only(mover / "output" / "desks.html", "desks.html")

        with self.assertRaises(subprocess.CalledProcessError):
            box.full_tree(fresh / "output", before_push=concurrent)
        self.assertEqual(box.pages("desks.html"), "desks v2")
        # The same stale tree, re-cloned a moment later, publishes cleanly.
        box.full_tree(fresh / "output")
        self.assertEqual(box.pages("desks.html"), "desks v1")

    def test_current_file_only_cas_refuses_when_pages_moved(self):
        box = self.box
        b = box.commit_main({"korea.html": "korea v2"}, "B")
        with self.assertRaises(StaleRefused):
            box.file_only(b / "output" / "korea.html", "korea.html",
                          before_push=lambda: box.out_of_band({"other.html": "x"}))
        self.assertEqual(box.pages("korea.html"), "korea v1")

    def test_current_fresh_full_tree_erases_pages_only_content(self):
        box = self.box
        box.out_of_band({"receipts.html": "reviewed receipt"})
        fresh = box.checkout_main("A-fresh")
        box.full_tree(fresh / "output")
        self.assertIsNone(box.pages("receipts.html"))

    def test_current_overlay_preserves_others_but_stale_overlay_reverts_its_own(self):
        box = self.box
        stale = box.checkout_main("A-desks")
        newer = box.commit_main({"desks.html": "desks v2", "korea.html": "korea v2"}, "B")
        box.full_tree(newer / "output")
        patch = self.tmp / "patch"
        patch.mkdir()
        shutil.copyfile(stale / "output" / "desks.html", patch / "desks.html")
        box.full_tree(patch, keep_files=True)
        self.assertEqual(box.pages("korea.html"), "korea v2")  # unrelated page kept
        self.assertEqual(box.pages("desks.html"), "desks v1")  # own page reverted

    def test_current_daily_no_commit_path_reverts_out_of_group_writer(self):
        box = self.box
        daily = box.checkout_main("daily")                    # daily-update lock
        korea = box.commit_main({"korea.html": "korea v2"}, "korea-verified")
        box.file_only(korea / "output" / "korea.html", "korea.html")
        box.git(daily, "add", "output")
        self.assertEqual(box.git(daily, "diff", "--cached", "--name-only"), "")  # nothing new
        box.full_tree(daily / "output", "Deploy: 2002")       # Step 7 still deploys
        self.assertEqual(box.pages("korea.html"), "korea v1")

    def test_current_daily_commit_path_window_after_rebase(self):
        box = self.box
        daily = box.checkout_main("daily")
        (daily / "output" / "index.html").write_text("home v2", encoding="utf-8")
        box.git(daily, "commit", "-q", "-am", "daily")
        box.git(daily, "pull", "-q", "--rebase", "origin", "main")
        box.git(daily, "push", "-q", "origin", "HEAD:main")
        korea = box.commit_main({"korea.html": "korea v2"}, "korea-verified")
        box.file_only(korea / "output" / "korea.html", "korea.html")
        box.full_tree(daily / "output")
        self.assertEqual(box.pages("index.html"), "home v2")
        self.assertEqual(box.pages("korea.html"), "korea v1")
        self.assertEqual(box.main("korea.html"), "korea v2")

    def test_current_serialized_writers_that_refetch_are_safe(self):
        box = self.box
        b = box.commit_main({"korea.html": "korea v2"}, "B")
        box.file_only(b / "output" / "korea.html", "korea.html")
        a = box.checkout_main("A-after-lock")                 # snapshot AFTER B finished
        box.full_tree(a / "output")
        self.assertEqual(box.pages("korea.html"), "korea v2")

    def test_current_protocol_cannot_tell_rollback_from_stale_republish(self):
        box = self.box
        v1 = box.checkout_main("v1")
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        box.full_tree(v2 / "output", "Deploy: 3003")
        box.full_tree(v1 / "output", "Deploy: 3004")          # "authorized rollback"
        rollback_tree = box.git(box.origin, "rev-parse", "gh-pages^{tree}")
        box.full_tree(v2 / "output", "Deploy: 3005")
        box.full_tree(v1 / "output", "Deploy: 3006")          # stale republish
        self.assertEqual(box.git(box.origin, "rev-parse", "gh-pages^{tree}"), rollback_tree)

    def test_current_crash_after_deploy_leaves_no_source_attestation(self):
        box = self.box
        daily = box.commit_main({"index.html": "home v2"}, "daily")
        box.full_tree(daily / "output", "Deploy: 4004")
        # Crash here: Step 8 never writes .github/state/last_daily_run_date.txt.
        message = box.pages_message()
        self.assertNotIn(box.main_sha()[:7], message)
        self.assertIsNone(box.pages(MANIFEST))


class FencedProtocol(RaceCase):
    def setUp(self):
        super().setUp()
        self.fence = ReferenceFence(self.box)
        self.fence.publish(self.box.checkout_main("gen1"), "daily", expected_generation=0)

    def test_fence_refuses_stale_full_tree_and_preserves_newer_page(self):
        box, fence = self.box, self.fence
        a = box.checkout_main("A-stale")
        b = box.commit_main({"korea.html": "korea v2"}, "B")
        fence.publish(b, "korea-file-only", expected_generation=1, files=["korea.html"])
        with self.assertRaises(StaleRefused):
            fence.publish(a, "daily", expected_generation=1)   # stale generation
        with self.assertRaises(StaleRefused):
            fence.publish(a, "daily", expected_generation=2)   # not a descendant
        self.assertEqual(box.pages("korea.html"), "korea v2")
        # Recovery preserves the other desk: rebuild from current main.
        a2 = box.checkout_main("A-rebuilt")
        fence.publish(a2, "daily", expected_generation=2)
        self.assertEqual(box.pages("korea.html"), "korea v2")

    def test_fence_accepts_only_explicit_matching_rollback(self):
        box, fence = self.box, self.fence
        v1 = box.checkout_main("v1")
        v1_sha = box.git(v1, "rev-parse", "HEAD")
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        v2_sha = box.git(v2, "rev-parse", "HEAD")
        fence.publish(v2, "daily", expected_generation=1)
        with self.assertRaises(StaleRefused):
            fence.publish(v1, "deploy-output-only", expected_generation=2)
        m = fence.publish(v1, "owner-rollback", expected_generation=2,
                          rollback={"expected_current": v2_sha, "target": v1_sha})
        self.assertTrue(m["rollback"])
        self.assertEqual(box.pages("index.html"), "home v1")
        with self.assertRaises(StaleRefused):                  # authorization is now stale
            fence.publish(v1, "owner-rollback", expected_generation=3,
                          rollback={"expected_current": v2_sha, "target": v1_sha})

    def test_fence_accepts_fresh_descendant(self):
        box, fence = self.box, self.fence
        v2 = box.commit_main({"desks.html": "desks v2"}, "v2")
        m = fence.publish(v2, "desks", expected_generation=1)
        self.assertEqual(m["generation"], 2)
        self.assertEqual(json.loads(box.pages(MANIFEST))["source_sha"], box.main_sha())

    def test_fence_lets_crash_recovery_skip_redeploy(self):
        box, fence = self.box, self.fence
        daily = box.commit_main({"index.html": "home v2"}, "daily")
        fence.publish(daily, "daily", expected_generation=1)
        # Crash before the success marker. Recovery reads the attestation:
        deployed = json.loads(box.pages(MANIFEST))
        self.assertEqual(deployed["source_sha"], box.main_sha())  # write marker only
        box.commit_main({"korea.html": "korea v2"}, "later")
        self.assertNotEqual(json.loads(box.pages(MANIFEST))["source_sha"], box.main_sha())

    def test_fence_does_not_cover_writers_that_bypass_it(self):
        box, fence = self.box, self.fence
        box.out_of_band({"receipts.html": "reviewed receipt"})   # no manifest bump
        self.assertEqual(fence.current()["generation"], 1)
        fresh = box.checkout_main("fresh")
        fence.publish(fresh, "daily", expected_generation=1)
        self.assertIsNone(box.pages("receipts.html"))            # still erased


if __name__ == "__main__":
    unittest.main()
