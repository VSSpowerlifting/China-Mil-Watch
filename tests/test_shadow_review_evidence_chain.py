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

    def formal(self, commit, out="out", **kw):
        kw.setdefault("state_repo", self.repo)
        return rk.build(None, self.tmp / out, "2026-08-27", True, None, False,
                        commit, "day-07", **kw)


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
