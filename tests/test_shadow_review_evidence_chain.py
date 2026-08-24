"""
Evidence-chain red team for the Singapore shadow review kit.

Every test here reproduces an attack that the first version of the kit accepted.
The theme is one question: *can a formal packet claim evidence it was not built
from?* A 40-character SHA is a string. Provenance is a tree.

Everything runs against disposable local repositories. No network, no real
remote, no live state.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rk = _load("review_shadow_state", REPO_ROOT / "scripts" / "review_shadow_state.py")
pub = _load("publish_shadow_review",
            REPO_ROOT / "scripts" / "publish_shadow_review.py")

D0 = "2026-08-19T23:03:09+00:00"
URL = "https://www.mindef.gov.sg/news-and-events/latest-releases/%s/"
DEFAULT_RECS = (("19aug26-nr", 600), ("20aug26-speech", 900),
                ("18aug26-pq2", 700), ("17aug26-fs", 500))


def _body(n):
    return ("Official release text. " * ((n // 23) + 2))[:n]


def _record(slug, run, n=600, title_suffix=""):
    url = URL % slug
    text = _body(n)
    return {
        "url": url, "source_slug": "sg_mindef_releases",
        "title_original": "Release %s%s" % (slug, title_suffix),
        "text_original": text,
        "published_date": rk.slug_published_date(url), "language_tag": "en",
        "publication_kind": rk.publication_kind(url),
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "capture_sha256": hashlib.sha256(b"c").hexdigest(),
        "retrieved_at": "2026-08-19T23:03:00+00:00", "first_seen_run": run,
    }


def build_state(state: Path, runs: int, recs=DEFAULT_RECS, title_suffix=""):
    """Synthetic state whose last ledger records `runs - 1` elapsed days."""
    (state / "ledger").mkdir(parents=True, exist_ok=True)
    rows = [_record(s, "r0", n, title_suffix) for s, n in recs]
    db = state / "shadow.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(str(db))
    con.executescript("""
CREATE TABLE shadow_records (url TEXT PRIMARY KEY, source_slug TEXT NOT NULL,
 title_original TEXT NOT NULL, text_original TEXT NOT NULL,
 published_date TEXT NOT NULL, language_tag TEXT NOT NULL,
 publication_kind TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 capture_sha256 TEXT, retrieved_at TEXT, first_seen_run TEXT);
CREATE INDEX idx_shadow_published ON shadow_records(published_date);""")
    cols = rk.EXPECTED_COLUMNS
    for r in rows:
        con.execute("INSERT INTO shadow_records (%s) VALUES (%s)"
                    % (", ".join(cols), ", ".join("?" * len(cols))),
                    [r[c] for c in cols])
    con.commit()
    con.close()
    sha = hashlib.sha256(db.read_bytes()).hexdigest()
    (state / "clock.json").write_text(
        json.dumps({"day_zero_utc": D0, "day_zero_run_id": "r0"}, indent=1) + "\n",
        encoding="utf-8")
    for old in (state / "ledger").glob("*.json"):
        old.unlink()
    d0 = datetime.fromisoformat(D0)
    prev = None
    for i in range(runs):
        fin = (d0 if i == 0 else d0 + timedelta(days=i)).isoformat()
        e = {"run_id": "r%d" % i, "collector_commit": "c0ffee",
             "started_utc": fin, "finished_utc": fin, "target_date": fin[:10],
             "lookback_days": 30, "cap": 40, "robots_status": "allowed",
             "listing_status": "ok", "discovered": len(rows),
             "selected": len(rows), "retrieved": len(rows),
             "inserted": len(rows) if i == 0 else 0,
             "duplicates": 0 if i == 0 else len(rows), "filtered": 0,
             "fetch_failures": 0, "extraction_failures": 0,
             "access_failures": 0, "content_hashes": [],
             "state_sha256_before": prev, "state_sha256_after": sha,
             "result": "ok" if i == 0 else "ok_all_duplicates", "health": "ok",
             "error_detail": None,
             "shadow_day": (datetime.fromisoformat(fin) - d0).days,
             "day_zero_utc": D0, "stored_total": len(rows),
             "corpus_range": [None, None]}
        prev = sha
        (state / "ledger" / rk.expected_ledger_filename(e)).write_text(
            json.dumps(e, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return state


def git(args, cwd, check=True):
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@x",
                "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@x",
                "GIT_AUTHOR_DATE": "2026-08-20T00:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-08-20T00:00:00+00:00"})
    for stray in ("GIT_DIR", "GIT_WORK_TREE"):
        env.pop(stray, None)
    p = subprocess.run(["git"] + list(args), cwd=str(cwd), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and p.returncode:
        raise RuntimeError("git %s failed: %s" % (args, p.stdout))
    return p.stdout.strip()


class EvidenceChainCase(unittest.TestCase):
    """A disposable state repository with two distinguishable state commits."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="evidence-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "staterepo"
        self.repo.mkdir()
        git(["init", "--quiet", "-b", rk.STATE_BRANCH, "."], self.repo)
        build_state(self.repo / "state", 8)
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "state A"], self.repo)
        self.A = git(["rev-parse", "HEAD"], self.repo)
        build_state(self.repo / "state", 8,
                    recs=DEFAULT_RECS + (("16aug26-mq", 800),),
                    title_suffix=" [B]")
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "state B"], self.repo)
        self.B = git(["rev-parse", "HEAD"], self.repo)
        git(["checkout", "--quiet", "-b", "unrelated"], self.repo)
        (self.repo / "state" / "note.txt").write_text("x\n", encoding="utf-8")
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "unrelated"], self.repo)
        self.unrelated = git(["rev-parse", "HEAD"], self.repo)
        git(["checkout", "--quiet", rk.STATE_BRANCH], self.repo)

    def export(self, commit, name):
        """Materialise state/ from a commit, the way an operator would."""
        dest = self.tmp / name
        dest.mkdir(parents=True, exist_ok=True)
        tar = subprocess.run(["git", "archive", commit, "state"],
                             cwd=str(self.repo), stdout=subprocess.PIPE,
                             check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(dest)], input=tar, check=True)
        return dest / "state"

    def formal(self, commit, out="out", checkpoint="day-07", **kw):
        kw.setdefault("state_repo", self.repo)
        return rk.build(None, self.tmp / out, "2026-08-27", True, None, False,
                        commit, checkpoint, **kw)


class PacketFixtureCase(unittest.TestCase):
    """A pristine formal packet, an honest sign-off, and an empty bare remote."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="packet-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "staterepo"
        self.repo.mkdir()
        git(["init", "--quiet", "-b", rk.STATE_BRANCH, "."], self.repo)
        build_state(self.repo / "state", 8)
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "state"], self.repo)
        self.commit = git(["rev-parse", "HEAD"], self.repo)
        self.packet = self.tmp / "packet"
        self.manifest = rk.build(None, self.packet, "2026-08-27", True, None,
                                 False, self.commit, "day-07",
                                 state_repo=self.repo)
        self.signoff_path = self.tmp / "signoff.json"
        self.write_signoff(self.complete_signoff())
        self.remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(self.remote)],
                       check=True)

    def complete_signoff(self) -> dict:
        t = json.loads((self.packet / "signoff_template.json")
                       .read_text(encoding="utf-8"))
        t.update({"reviewer": "Auditor",
                  "attestation": "Compared each record with the ministry pages.",
                  "review_started_utc": "2026-08-27T09:00:00+00:00",
                  "review_completed_utc": "2026-08-27T11:00:00+00:00",
                  "verdict": "pass"})
        for r in t["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
        for a in t.get("anomalies", []):
            a["disposition"] = "reviewed; benign"
        return t

    def write_signoff(self, obj, raw=None):
        self.signoff_path.write_text(
            raw if raw is not None
            else json.dumps(obj, indent=1, sort_keys=True) + "\n",
            encoding="utf-8")

    def run_pub(self, packet=None, signoff=None, remote=None, extra=(),
                publish=True, bootstrap=True):
        argv = ["--packet", str(packet or self.packet),
                "--signoff", str(signoff or self.signoff_path),
                "--remote", str(remote if remote is not None else self.remote),
                "--checkpoint", "day-07"] + list(extra)
        if bootstrap:
            argv.append("--bootstrap")
        if publish:
            argv.append("--publish")
        return pub.main(argv)

    def remote_git(self, *args):
        return subprocess.run(["git", "--git-dir", str(self.remote)] + list(args),
                              stdout=subprocess.PIPE, text=True).stdout

    def head(self):
        return self.remote_git("rev-parse", "review/singapore-mindef").strip()


class AStateCommitIsNotAString(EvidenceChainCase):
    """
    The attack the first kit accepted: review one tree, name another.

    `--state-commit` was checked against a regular expression and then written
    into the manifest. Every test here supplies a syntactically perfect SHA and
    asks the only question that matters — did the bytes come from it?
    """

    def test_reviewing_one_commit_while_naming_another_is_impossible(self):
        """The reviewed tree is the named tree; there is no second input to lie with."""
        a = self.formal(self.A, out="a")
        b = self.formal(self.B, out="b")
        self.assertNotEqual(a["corpus_count"], b["corpus_count"])
        self.assertEqual(a["state_commit"], self.A)
        self.assertEqual(b["state_commit"], self.B)
        self.assertNotEqual(a["state_tree"], b["state_tree"])

    def test_a_working_copy_cannot_stand_in_for_the_committed_tree(self):
        forged = self.export(self.B, "forged")
        with self.assertRaises(rk.ReviewError) as c:
            rk.build(forged, self.tmp / "out", "2026-08-27", True, None, False,
                     self.A, "day-07", state_repo=self.repo)
        self.assertIn("mutually exclusive", str(c.exception))

    def test_a_formal_packet_without_a_state_repo_is_refused(self):
        honest = self.export(self.A, "honest")
        with self.assertRaises(rk.ReviewError) as c:
            rk.build(honest, self.tmp / "out", "2026-08-27", True, None, False,
                     self.A, "day-07")
        self.assertIn("requires --state-repo", str(c.exception))

    def test_a_nonexistent_commit_is_refused(self):
        with self.assertRaises(rk.ReviewError) as c:
            self.formal("de" + "ad" * 19)
        self.assertIn("does not exist", str(c.exception))

    def test_a_commit_unreachable_from_the_state_ref_is_refused(self):
        with self.assertRaises(rk.ReviewError) as c:
            self.formal(self.unrelated)
        self.assertIn("not reachable", str(c.exception))

    def test_a_repository_without_git_objects_is_refused(self):
        stripped = self.tmp / "stripped"
        stripped.mkdir()
        (stripped / "state").mkdir()
        with self.assertRaises(rk.ReviewError) as c:
            rk.build(None, self.tmp / "out", "2026-08-27", True, None, False,
                     self.A, "day-07", state_repo=stripped)
        self.assertIn("not a Git repository", str(c.exception))

    def test_tampering_after_checkout_cannot_reach_the_packet(self):
        """
        The classic: clone, remove `.git`, edit a ledger, quote the original
        SHA. The edit now lives in a directory the formal path never reads.
        """
        tampered = self.export(self.A, "tampered")
        led = sorted((tampered / "ledger").glob("*.json"))[-1]
        entry = json.loads(led.read_text(encoding="utf-8"))
        entry["cap"] = 999
        led.write_text(json.dumps(entry, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
        honest = self.formal(self.A, out="honest-out")
        self.assertEqual(
            honest["input_sha256"][led.relative_to(tampered).as_posix()
                                   if False else "ledger/" + led.name],
            hashlib.sha256(
                subprocess.run(["git", "cat-file", "blob",
                                "%s:state/ledger/%s" % (self.A, led.name)],
                               cwd=str(self.repo), stdout=subprocess.PIPE,
                               check=True).stdout).hexdigest())

    def test_a_ledger_added_after_the_commit_is_not_incorporated(self):
        packet = self.formal(self.A, out="add")
        n_committed = len(subprocess.run(
            ["git", "ls-tree", "--name-only", "%s:state/ledger" % self.A],
            cwd=str(self.repo), stdout=subprocess.PIPE, text=True,
            check=True).stdout.split())
        self.assertEqual(packet["ledger_count"], n_committed)

    def test_a_symlink_in_the_committed_tree_is_refused_not_followed(self):
        outside = self.tmp / "outside.json"
        outside.write_text('{"leaked": true}\n', encoding="utf-8")
        git(["checkout", "--quiet", "-b", "symlinked", self.A], self.repo)
        link = self.repo / "state" / "ledger" / "zz.json"
        link.symlink_to(outside)
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "symlink"], self.repo)
        bad = git(["rev-parse", "HEAD"], self.repo)
        with self.assertRaises(rk.ReviewError) as c:
            self.formal(bad, state_ref="symlinked")
        self.assertIn("regular files only", str(c.exception))

    def test_an_unexpected_file_in_the_committed_tree_is_refused(self):
        git(["checkout", "--quiet", "-b", "extra", self.A], self.repo)
        (self.repo / "state" / "surprise.json").write_text("{}\n", encoding="utf-8")
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "extra"], self.repo)
        bad = git(["rev-parse", "HEAD"], self.repo)
        with self.assertRaises(rk.ReviewError) as c:
            self.formal(bad, state_ref="extra")
        self.assertIn("unexpected file", str(c.exception))

    def test_a_commit_with_no_state_tree_is_refused(self):
        git(["checkout", "--quiet", "-b", "nostate", self.A], self.repo)
        git(["rm", "-r", "--quiet", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", "no state"], self.repo)
        bad = git(["rev-parse", "HEAD"], self.repo)
        with self.assertRaises(rk.ReviewError) as c:
            self.formal(bad, state_ref="nostate")
        self.assertIn("no state/ tree", str(c.exception))

    def test_the_manifest_carries_the_verified_tree_not_only_the_claim(self):
        m = self.formal(self.A)
        tree = git(["rev-parse", "%s:state" % self.A], self.repo)
        self.assertEqual(m["state_tree"], tree)
        self.assertEqual(m["provenance"], "git-verified-tree/1")
        self.assertIn(rk.STATE_BRANCH, m["state_ref"])

    def test_a_rehearsal_packet_says_its_inputs_are_unverified(self):
        honest = self.export(self.A, "rehearse")
        m = rk.build(honest, self.tmp / "reh", "2026-08-27", True, None, False)
        self.assertEqual(m["provenance"], "unverified-working-copy")
        self.assertFalse(m["publishable"])
        report = (self.tmp / "reh" / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("NOT PUBLISHABLE", report)
        self.assertIn("working-tree copy that nothing", report)
        self.assertIn("--state-repo", report)

    def test_verification_needs_no_network(self):
        """
        Every Git call reads objects the clone already has. The check is that
        the exported bytes equal the committed blobs, which no fetch could
        change.
        """
        m = self.formal(self.A, out="offline")
        for name, digest in m["input_sha256"].items():
            blob = subprocess.run(
                ["git", "cat-file", "blob", "%s:state/%s" % (self.A, name)],
                cwd=str(self.repo), stdout=subprocess.PIPE, check=True).stdout
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, name)


class ARemoteIsNotAnOption(PacketFixtureCase):
    """
    `--remote` reaches `git ls-remote` as an argument, and Git reads a leading
    `-` as an option. `--upload-pack=<cmd>` is therefore a command Git runs.
    An argument array prevents shell metacharacters, not option injection.
    """

    def test_a_remote_beginning_with_a_dash_is_refused(self):
        canary = self.tmp / "executed"
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path,
                        "--upload-pack=touch %s" % canary, "day-07",
                        None, True, True)
        self.assertIn("may not begin with '-'", str(c.exception))
        self.assertFalse(canary.exists(),
                         "git executed the injected --upload-pack command")

    def test_the_injected_command_never_runs_through_main(self):
        canary = self.tmp / "executed-main"
        rc = self.run_pub(remote="--upload-pack=touch %s" % canary)
        self.assertEqual(rc, 2)
        self.assertFalse(canary.exists())

    def test_an_expected_head_beginning_with_a_dash_is_refused(self):
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", "--upload-pack=false", False, True)
        self.assertIn("may not begin with '-'", str(c.exception))

    def test_a_hijacked_git_environment_cannot_redirect_the_publisher(self):
        evil = self.tmp / "evil.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(evil)], check=True)
        old = dict(os.environ)
        os.environ.update({"GIT_DIR": str(evil), "GIT_WORK_TREE": str(self.tmp)})
        try:
            rc = self.run_pub()
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(rc, 0, "a scrubbed environment should publish normally")
        refs = subprocess.run(["git", "--git-dir", str(evil), "for-each-ref",
                               "--format=%(refname)"], stdout=subprocess.PIPE,
                              text=True).stdout.split()
        self.assertEqual(refs, [], "the hijacked GIT_DIR was written to")
        self.assertTrue(self.head())


class APacketIsOnlyItsOwnFiles(PacketFixtureCase):
    """
    The publisher copied three names out of the packet directory without
    asking what they were. A symlink is read as its target, so the file that
    reached the review branch could come from anywhere on the machine — and the
    manifest travelling beside it still named the real report's digest.
    """

    def test_a_packet_file_that_is_a_symlink_is_refused(self):
        outside = self.tmp / "outside.md"
        outside.write_text("# not review evidence\n", encoding="utf-8")
        (self.packet / "review_report.md").unlink()
        (self.packet / "review_report.md").symlink_to(outside)
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("symlink", str(c.exception))
        self.assertEqual(self.remote_git("for-each-ref").strip(), "")

    def test_a_symlink_pointing_inside_the_packet_is_still_refused(self):
        real = self.tmp / "real.md"
        shutil.move(str(self.packet / "review_report.md"), str(real))
        (self.packet / "review_report.md").symlink_to(real)
        with self.assertRaises(pub.PublishError):
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)

    def test_an_edited_packet_no_longer_matches_its_own_manifest(self):
        report = self.packet / "review_report.md"
        report.write_text(report.read_text(encoding="utf-8") + "\nappended\n",
                          encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("altered after it was generated", str(c.exception))

    def test_an_honest_packet_still_publishes(self):
        self.assertEqual(self.run_pub(), 0)
        self.assertTrue(self.head())


class AReviewerFieldIsNotACommitMessage(PacketFixtureCase):
    """
    `reviewer` is written into the preserved commit message. A newline in it
    forges a trailer, so `git log` on the review branch shows a `state-commit`
    that the receipt never named — two contradictory records of what was
    reviewed, both preserved, neither flagged.
    """

    def test_a_newline_in_reviewer_is_refused(self):
        s = self.complete_signoff()
        s["reviewer"] = "Auditor\nstate-commit " + "9" * 40
        self.write_signoff(s)
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("control character", str(c.exception))
        self.assertEqual(self.remote_git("for-each-ref").strip(), "")

    def test_a_carriage_return_or_null_in_reviewer_is_refused(self):
        for bad in ("Auditor\rX", "Auditor\x00X", "Auditor\x1b[2J"):
            with self.subTest(reviewer=repr(bad)):
                s = self.complete_signoff()
                s["reviewer"] = bad
                self.write_signoff(s)
                with self.assertRaises(pub.PublishError):
                    pub.publish(self.packet, self.signoff_path,
                                str(self.remote), "day-07", None, True, True)

    def test_the_preserved_commit_message_names_the_verified_tree(self):
        self.assertEqual(self.run_pub(), 0)
        msg = self.remote_git("log", "--format=%B", "-1",
                              "review/singapore-mindef")
        trailers = [l for l in msg.splitlines() if l.startswith("state-commit ")]
        self.assertEqual(trailers, ["state-commit " + self.commit])
        self.assertIn("state-tree " + self.manifest["state_tree"], msg)


class PreservedEvidenceIsNotInheritedOnFaith(PacketFixtureCase):
    """
    The publisher gathered a digest of every preserved file and never compared
    it. A `fail` receipt on the remote could be edited to `pass`, and the next
    publication would clone it, build on top of it, and push the rewrite along
    with its own honest review.
    """

    def _published_clone(self):
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "--quiet", "-b",
                        "review/singapore-mindef", str(self.remote), str(clone)],
                       check=True)
        return clone

    def _push(self, clone, message):
        for a in (["add", "-A"],
                  ["-c", "user.name=x", "-c", "user.email=x@x", "commit",
                   "--quiet", "-m", message]):
            subprocess.run(["git"] + a, cwd=str(clone), check=True,
                           stdout=subprocess.DEVNULL)
        subprocess.run(["git", "push", "--quiet", "origin",
                        "review/singapore-mindef"], cwd=str(clone), check=True)
        return self.head()

    def _second_review(self):
        s = self.complete_signoff()
        s["reviewer"] = "Second Auditor"
        path = self.tmp / "signoff2.json"
        path.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
        return path

    def test_a_rewritten_receipt_is_refused(self):
        s = self.complete_signoff()
        s["verdict"] = "fail"
        s["records"][0]["title_matches"] = False
        self.write_signoff(s)
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        receipt = next(clone.glob("reviews/day-07/*/receipt.json"))
        d = json.loads(receipt.read_text(encoding="utf-8"))
        d["verdict"] = "pass"
        d["false_checks"] = 0
        receipt.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        head = self._push(clone, "rewrite the verdict")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("disagrees with the evidence", str(c.exception))
        self.assertEqual(self.head(), head, "the remote must be untouched")

    def test_a_rewritten_signoff_no_longer_names_its_own_directory(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        signoff = next(clone.glob("reviews/day-07/*/signoff.json"))
        d = json.loads(signoff.read_text(encoding="utf-8"))
        d["attestation"] = "something the reviewer never wrote"
        signoff.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        head = self._push(clone, "rewrite the sign-off")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("no longer hashes to its own id", str(c.exception))

    def test_a_rewritten_manifest_no_longer_hashes_to_its_package_id(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        manifest = next(clone.glob("reviews/day-07/*/review_manifest.json"))
        d = json.loads(manifest.read_text(encoding="utf-8"))
        d["state_commit"] = "0" * 40          # the package id is left alone
        manifest.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
        head = self._push(clone, "rewrite the state commit")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("no longer hashes to its own package id",
                      str(c.exception))

    def test_a_rewritten_report_is_refused(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        report = next(clone.glob("reviews/day-07/*/review_report.md"))
        report.write_text(report.read_text(encoding="utf-8") + "\nedited\n",
                          encoding="utf-8")
        head = self._push(clone, "rewrite the report")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("altered after it was generated", str(c.exception))

    def test_a_tampered_index_line_is_refused(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        index = clone / "index.jsonl"
        line = json.loads(index.read_text(encoding="utf-8").strip())
        line["state_commit"] = "0" * 40
        index.write_text(json.dumps(line, sort_keys=True,
                                    separators=(",", ":")) + "\n",
                         encoding="utf-8")
        head = self._push(clone, "rewrite the index")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("index.jsonl", str(c.exception))

    def test_a_deleted_review_is_refused(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self._published_clone()
        shutil.rmtree(str(next(clone.glob("reviews/day-07/*")).resolve()))
        head = self._push(clone, "delete a review")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("not preserved on the branch", str(c.exception))

    def test_an_untouched_branch_still_accepts_the_next_review(self):
        self.assertEqual(self.run_pub(), 0)
        head = self.head()
        r = pub.publish(self.packet, self._second_review(), str(self.remote),
                        "day-07", head, False, True)
        self.assertTrue(r["published"])
        self.assertEqual(r["action"], "fast-forward")


class ASignoffSaysOneThing(PacketFixtureCase):
    """JSON that can be read two ways is not a record of what a person answered."""

    def test_a_duplicate_key_is_refused(self):
        raw = json.dumps(self.complete_signoff(), indent=1, sort_keys=True)
        raw = raw.replace('"verdict": "pass"',
                          '"verdict": "fail",\n "verdict": "pass"', 1)
        self.write_signoff(None, raw=raw + "\n")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("duplicate key", str(c.exception))
        self.assertEqual(self.remote_git("for-each-ref").strip(), "")

    def test_nan_and_infinity_are_refused(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal):
                raw = json.dumps(self.complete_signoff(), indent=1,
                                 sort_keys=True)
                raw = raw.replace('"verdict":',
                                  '"stray": %s,\n "verdict":' % literal, 1)
                self.write_signoff(None, raw=raw + "\n")
                with self.assertRaises(pub.PublishError):
                    pub.publish(self.packet, self.signoff_path,
                                str(self.remote), "day-07", None, True, True)

    def test_a_timestamp_without_a_timezone_is_refused(self):
        s = self.complete_signoff()
        s["review_started_utc"] = "2026-08-27T09:00:00"
        s["review_completed_utc"] = "2026-08-27T11:00:00"
        self.write_signoff(s)
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("no timezone", str(c.exception))

    def test_an_unexpected_file_in_the_packet_is_refused(self):
        (self.packet / "addendum.md").write_text("# read but not preserved\n",
                                                 encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("neither preserved nor expected", str(c.exception))

    def test_the_sidecars_the_kit_writes_do_not_block_publication(self):
        self.assertTrue((self.packet / "signoff_template.json").is_file())
        self.assertEqual(self.run_pub(), 0)


class OnePackageIdIsOneSetOfBytes(EvidenceChainCase):
    """
    `generated` used to sit in the manifest, excluded from the package id. Two
    honest generations of the same commit therefore agreed on the id and
    disagreed on the bytes — so the id identified nothing in particular, and
    republishing an independently regenerated packet was refused as
    conflicting content.
    """

    FILES = ("review_manifest.json", "review_report.md",
             "record_inventory.jsonl", "signoff_template.json")

    def _two_generations(self):
        first = self.formal(self.A, out="first")
        time.sleep(1.1)                       # a different wall clock
        second = self.formal(self.A, out="second-run-elsewhere")
        return first, second

    def test_every_packet_file_is_byte_identical(self):
        first, second = self._two_generations()
        self.assertEqual(first["deterministic_sha256"],
                         second["deterministic_sha256"])
        for name in self.FILES:
            a = (self.tmp / "first" / name).read_bytes()
            b = (self.tmp / "second-run-elsewhere" / name).read_bytes()
            self.assertEqual(hashlib.sha256(a).hexdigest(),
                             hashlib.sha256(b).hexdigest(), name)

    def test_the_manifest_carries_no_wall_clock_and_no_local_paths(self):
        m = self.formal(self.A, out="clean")
        text = (self.tmp / "clean" / "review_manifest.json").read_text(
            encoding="utf-8")
        self.assertNotIn("generated", m)
        self.assertNotIn(str(self.tmp), text,
                         "the manifest leaks a local filesystem path")

    def test_the_generation_context_is_beside_the_package_not_in_it(self):
        self.formal(self.A, out="ctx")
        ctx = json.loads((self.tmp / "ctx" / "generation_context.json")
                         .read_text(encoding="utf-8"))
        self.assertIn("generated_utc", ctx)
        self.assertNotIn("generation_context.json", pub.PACKET_FILES)

    def test_an_independently_regenerated_packet_republishes_as_a_no_op(self):
        first, second = self._two_generations()
        t = json.loads((self.tmp / "first" / "signoff_template.json")
                       .read_text(encoding="utf-8"))
        t.update({"reviewer": "Auditor", "attestation": "compared each record",
                  "review_started_utc": "2026-08-27T09:00:00+00:00",
                  "review_completed_utc": "2026-08-27T11:00:00+00:00",
                  "verdict": "pass"})
        for r in t["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
        for a in t.get("anomalies", []):
            a["disposition"] = "benign"
        signoff = self.tmp / "signoff.json"
        signoff.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)],
                       check=True)
        r1 = pub.publish(self.tmp / "first", signoff, str(remote), "day-07",
                         None, True, True)
        self.assertEqual(r1["action"], "bootstrap")
        head = subprocess.run(["git", "--git-dir", str(remote), "rev-parse",
                               "review/singapore-mindef"],
                              stdout=subprocess.PIPE, text=True).stdout.strip()
        r2 = pub.publish(self.tmp / "second-run-elsewhere", signoff,
                         str(remote), "day-07", head, False, True)
        self.assertEqual(r2["action"], "idempotent-no-op")
        self.assertEqual(r1["completed_review_id"], r2["completed_review_id"])
        after = subprocess.run(["git", "--git-dir", str(remote), "rev-parse",
                                "review/singapore-mindef"],
                               stdout=subprocess.PIPE, text=True).stdout.strip()
        self.assertEqual(after, head, "a no-op must not move the branch")


class PublishableMeansPublishable(EvidenceChainCase):
    """
    The real Singapore state at the time of this audit records shadow_day 2. A
    day-07 packet built from it was pinned to its commit correctly and labelled
    `publishable: true` — a claim the publisher was always going to refuse. A
    reviewer could work through the whole packet before finding out.
    """

    def _short_state(self, runs, name):
        git(["checkout", "--quiet", "-b", name, self.A], self.repo)
        build_state(self.repo / "state", runs)
        git(["add", "-A", "--", "state"], self.repo)
        git(["commit", "--quiet", "-m", name], self.repo)
        return git(["rev-parse", "HEAD"], self.repo)

    def test_a_checkpoint_that_has_not_arrived_is_not_publishable(self):
        early = self._short_state(3, "day2")         # last ledger = day 2
        m = self.formal(early, out="early", state_ref="day2")
        self.assertTrue(m["formal"])
        self.assertEqual(m["latest_shadow_day"], 2)
        self.assertFalse(m["publishable"])
        report = (self.tmp / "early" / "review_report.md").read_text(
            encoding="utf-8")
        self.assertIn("NOT PUBLISHABLE YET", report)

    def test_the_publisher_agrees_with_the_label(self):
        early = self._short_state(3, "day2b")
        self.formal(early, out="early2", state_ref="day2b")
        packet = self.tmp / "early2"
        t = json.loads((packet / "signoff_template.json")
                       .read_text(encoding="utf-8"))
        t.update({"reviewer": "R", "attestation": "a",
                  "review_started_utc": "2026-08-27T09:00:00+00:00",
                  "review_completed_utc": "2026-08-27T11:00:00+00:00",
                  "verdict": "pass"})
        for r in t["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
        for a in t.get("anomalies", []):
            a["disposition"] = "n/a"
        signoff = self.tmp / "early-signoff.json"
        signoff.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        remote = self.tmp / "early-remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)],
                       check=True)
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(packet, signoff, str(remote), "day-07", None, True, True)
        self.assertIn("shadow_day >= 7", str(c.exception))

    def test_an_arrived_checkpoint_is_still_publishable(self):
        m = self.formal(self.A, out="arrived")
        self.assertEqual(m["latest_shadow_day"], 7)
        self.assertTrue(m["publishable"])
        self.assertNotIn("NOT PUBLISHABLE",
                         (self.tmp / "arrived" / "review_report.md")
                         .read_text(encoding="utf-8"))


class TheSecondLayerIsAlsoPinned(PacketFixtureCase):
    """
    Three guards a red-team mutation survived, because the checks in front of
    them caught everything first. A guard nothing pins is a guard that can be
    deleted by accident, so each is exercised directly here. They exist because
    the check in front of them could itself be wrong.
    """

    def test_a_packet_claiming_unverified_provenance_is_refused(self):
        """
        The kit only emits verified packets now, so nothing else hands the
        publisher an unverified one. A packet from an older kit, or one edited
        by hand, still can.
        """
        manifest = self.packet / "review_manifest.json"
        d = json.loads(manifest.read_text(encoding="utf-8"))
        d["provenance"] = "unverified-working-copy"
        manifest.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", None, True, True)
        self.assertIn("provenance", str(c.exception))
        self.assertEqual(self.remote_git("for-each-ref").strip(), "")

    def test_a_packet_without_a_verified_tree_is_refused(self):
        for value in (None, "", "abc123", "1" * 39):
            with self.subTest(state_tree=value):
                manifest = self.packet / "review_manifest.json"
                d = json.loads(manifest.read_text(encoding="utf-8"))
                d["state_tree"] = value
                manifest.write_text(
                    json.dumps(d, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
                with self.assertRaises(pub.PublishError) as c:
                    pub.publish(self.packet, self.signoff_path,
                                str(self.remote), "day-07", None, True, True)
                self.assertIn("state_tree", str(c.exception))

    def test_a_rewrite_during_this_publication_is_caught(self):
        """
        `assert_existing_evidence_is_intact` guards this publisher's own write
        path: if a future change made it write over a review already on the
        branch, the digests taken before the write would no longer match.
        """
        work = self.tmp / "work"
        (work / "reviews" / "day-07" / "abc").mkdir(parents=True)
        preserved = work / "reviews" / "day-07" / "abc" / "review_report.md"
        preserved.write_text("original evidence\n", encoding="utf-8")
        snapshot = pub.snapshot_existing(work)
        self.assertEqual(list(snapshot), ["reviews/day-07/abc/review_report.md"])
        pub.assert_existing_evidence_is_intact(work, snapshot)   # no-op

        preserved.write_text("rewritten\n", encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.assert_existing_evidence_is_intact(work, snapshot)
        self.assertIn("was rewritten", str(c.exception))

        preserved.unlink()
        with self.assertRaises(pub.PublishError) as c:
            pub.assert_existing_evidence_is_intact(work, snapshot)
        self.assertIn("append-only", str(c.exception))

    def test_an_index_that_was_not_appended_to_is_caught(self):
        work = self.tmp / "work-index"
        work.mkdir()
        index = work / "index.jsonl"
        prior = '{"a":1}\n{"b":2}\n'

        index.write_text(prior + '{"c":3}\n', encoding="utf-8")
        pub.assert_index_only_grew(work, prior)                  # no-op

        index.write_text('{"a":1}\n{"c":3}\n', encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.assert_index_only_grew(work, prior)
        self.assertIn("rewritten rather than appended", str(c.exception))

        index.write_text('{"a":1}\n', encoding="utf-8")
        with self.assertRaises(pub.PublishError):
            pub.assert_index_only_grew(work, prior)

    def test_an_index_with_a_partial_last_line_is_refused(self):
        self.assertEqual(self.run_pub(), 0)
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "--quiet", "-b",
                        "review/singapore-mindef", str(self.remote), str(clone)],
                       check=True)
        index = clone / "index.jsonl"
        index.write_text(index.read_text(encoding="utf-8").rstrip("\n"),
                         encoding="utf-8")
        for a in (["add", "-A"],
                  ["-c", "user.name=x", "-c", "user.email=x@x", "commit",
                   "--quiet", "-m", "truncate"]):
            subprocess.run(["git"] + a, cwd=str(clone), check=True,
                           stdout=subprocess.DEVNULL)
        subprocess.run(["git", "push", "--quiet", "origin",
                        "review/singapore-mindef"], cwd=str(clone), check=True)
        head = self.head()
        s = self.complete_signoff()
        s["reviewer"] = "Second"
        path = self.tmp / "s2.json"
        path.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, path, str(self.remote), "day-07", head,
                        False, True)
        self.assertIn("index.jsonl", str(c.exception))
