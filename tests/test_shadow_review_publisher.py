"""
Orphan review-branch publisher.

The publisher preserves a completed checkpoint review. Almost every test here
is a refusal, because the value of the mechanism is what it will not record: an
unfilled form, a sign-off that belongs to a different package, a `pass` verdict
over a failed check, an anomaly that quietly disappeared, or a passing review
written over a failing one.

Everything runs against temporary local bare repositories and synthetic packets.
No network, no real remote, no live state.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
COMMIT = "1" * 40


def _body(n):
    return ("Official release text. " * ((n // 23) + 2))[:n]


def _record(slug, run, n=600):
    url = URL % slug
    text = _body(n)
    return {
        "url": url, "source_slug": "sg_mindef_releases",
        "title_original": "Release " + slug, "text_original": text,
        "published_date": rk.slug_published_date(url), "language_tag": "en",
        "publication_kind": rk.publication_kind(url),
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "capture_sha256": hashlib.sha256(b"c").hexdigest(),
        "retrieved_at": "2026-08-19T23:03:00+00:00", "first_seen_run": run,
    }


def build_state(root: Path, runs: int) -> Path:
    """Synthetic state whose last ledger records `runs - 1` elapsed days."""
    state = root / "state"
    (state / "ledger").mkdir(parents=True)
    recs = [_record("19aug26-nr", "r0"), _record("20aug26-speech", "r0", 900),
            _record("18aug26-pq2", "r0", 700), _record("17aug26-fs", "r0", 500)]
    con = sqlite3.connect(str(state / "shadow.db"))
    con.executescript("""
CREATE TABLE shadow_records (url TEXT PRIMARY KEY, source_slug TEXT NOT NULL,
 title_original TEXT NOT NULL, text_original TEXT NOT NULL,
 published_date TEXT NOT NULL, language_tag TEXT NOT NULL,
 publication_kind TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 capture_sha256 TEXT, retrieved_at TEXT, first_seen_run TEXT);
CREATE INDEX idx_shadow_published ON shadow_records(published_date);""")
    cols = rk.EXPECTED_COLUMNS
    for r in recs:
        con.execute("INSERT INTO shadow_records (%s) VALUES (%s)"
                    % (", ".join(cols), ", ".join("?" * len(cols))),
                    [r[c] for c in cols])
    con.commit(); con.close()
    sha = hashlib.sha256((state / "shadow.db").read_bytes()).hexdigest()
    (state / "clock.json").write_text(
        json.dumps({"day_zero_utc": D0, "day_zero_run_id": "r0"}, indent=1) + "\n",
        encoding="utf-8")
    d0 = datetime.fromisoformat(D0)
    prev = None
    for i in range(runs):
        fin = (d0 if i == 0 else d0 + timedelta(days=i)).isoformat()
        e = {"run_id": "r%d" % i, "collector_commit": "c0ffee",
             "started_utc": fin, "finished_utc": fin, "target_date": fin[:10],
             "lookback_days": 30, "cap": 40, "robots_status": "allowed",
             "listing_status": "ok", "discovered": 4, "selected": 4,
             "retrieved": 4, "inserted": 4 if i == 0 else 0,
             "duplicates": 0 if i == 0 else 4, "filtered": 0,
             "fetch_failures": 0, "extraction_failures": 0,
             "access_failures": 0, "content_hashes": [],
             "state_sha256_before": prev, "state_sha256_after": sha,
             "result": "ok" if i == 0 else "ok_all_duplicates", "health": "ok",
             "error_detail": None,
             "shadow_day": (datetime.fromisoformat(fin) - d0).days,
             "day_zero_utc": D0, "stored_total": 4, "corpus_range": [None, None]}
        prev = sha
        (state / "ledger" / rk.expected_ledger_filename(e)).write_text(
            json.dumps(e, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return state


class PublisherCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pub-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = build_state(self.tmp / "s", 8)      # last ledger = day 7
        self.packet = self.tmp / "packet"
        rk.build(self.state, self.packet, "2026-08-27", True, None, False,
                 COMMIT, "day-07")
        self.manifest = json.loads(
            (self.packet / "review_manifest.json").read_text(encoding="utf-8"))
        self.signoff_path = self.tmp / "signoff.json"
        self.write_signoff(self.complete_signoff())
        self.remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(self.remote)],
                       check=True)

    # -- helpers --------------------------------------------------------------

    def complete_signoff(self, **over):
        s = json.loads(
            (self.packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s.update(reviewer="Fixture Reviewer",
                 review_started_utc="2026-08-27T22:00:00+00:00",
                 review_completed_utc="2026-08-27T22:45:00+00:00",
                 verdict="pass", notes="", attestation="Compared each record.")
        s.update(over)
        return s

    def write_signoff(self, s):
        self.signoff_path.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8")

    def run_pub(self, *, signoff=None, checkpoint="day-07", expected_head=None,
                bootstrap=True, do_publish=False, packet=None):
        if signoff is not None:
            self.write_signoff(signoff)
        return pub.publish(packet or self.packet, self.signoff_path,
                           str(self.remote), checkpoint, expected_head,
                           bootstrap, do_publish)

    def head(self):
        return pub.remote_head(str(self.remote))

    def clone(self):
        dst = Path(tempfile.mkdtemp(prefix="pub-clone-"))
        self.addCleanup(shutil.rmtree, dst, True)
        subprocess.run(["git", "clone", "--quiet", "--branch", pub.REVIEW_BRANCH,
                        "--single-branch", str(self.remote), str(dst / "c")],
                       check=True)
        return dst / "c"


class TestFormalBinding(PublisherCase):

    def test_a_rehearsal_packet_is_not_publishable(self):
        rehearsal = self.tmp / "rehearsal"
        rk.build(self.state, rehearsal, "2026-08-27", True, None, False)
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(packet=rehearsal)
        self.assertIn("rehearsal", str(c.exception))
        self.assertIsNone(self.head())

    def test_a_formal_packet_requires_a_full_state_commit(self):
        with self.assertRaises(rk.ReviewError):
            rk.build(self.state, self.tmp / "x", "2026-08-27", True, None,
                     False, "abc123", "day-07")

    def test_the_packet_binds_the_state_it_reviewed(self):
        for field in ("state_commit", "clock_sha256", "shadow_db_sha256",
                      "ledger_set_sha256", "latest_ledger", "latest_run_id",
                      "latest_shadow_day", "corpus_count", "corpus_range",
                      "queue_algorithm", "required_review_records", "desk"):
            self.assertIn(field, self.manifest, field)

    def test_the_checkpoint_must_match_the_packet(self):
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(checkpoint="day-14")
        self.assertIn("checkpoint", str(c.exception))

    def test_a_checkpoint_below_its_shadow_day_is_refused(self):
        """A day-2 corpus cannot be filed as a Day 7 review."""
        early = build_state(self.tmp / "early", 3)        # last ledger = day 2
        packet = self.tmp / "early-packet"
        rk.build(early, packet, "2026-08-22", True, None, False, COMMIT, "day-07")
        # Build the sign-off from THIS packet, so the shadow-day rule is what
        # refuses it rather than an incidental package-id mismatch.
        s = json.loads((packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s.update(reviewer="R", review_started_utc="2026-08-22T22:00:00+00:00",
                 review_completed_utc="2026-08-22T22:30:00+00:00",
                 verdict="pass", attestation="a")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s, packet=packet)
        self.assertIn("shadow_day >= 7", str(c.exception))


class TestSignoffCompleteness(PublisherCase):

    def test_an_empty_template_is_refused(self):
        blank = json.loads(
            (self.packet / "signoff_template.json").read_text(encoding="utf-8"))
        with self.assertRaises(pub.PublishError):
            self.run_pub(signoff=blank)
        self.assertIsNone(self.head())

    def test_a_partially_filled_signoff_is_refused(self):
        s = self.complete_signoff()
        s["records"][0]["title_matches"] = None
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("explicit true or false", str(c.exception))

    def test_a_truthy_string_is_not_an_answer(self):
        s = self.complete_signoff()
        s["records"][0]["title_matches"] = "yes"
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("explicit true or false", str(c.exception))

    def test_a_missing_record_result_is_refused(self):
        s = self.complete_signoff()
        s["records"] = s["records"][:-1]
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("no review result", str(c.exception))

    def test_an_extra_record_result_is_refused(self):
        s = self.complete_signoff()
        extra = dict(s["records"][0]); extra["identity"] = URL % "1jan26-nr"
        s["records"].append(extra)
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("not required", str(c.exception))

    def test_a_duplicate_record_result_is_refused(self):
        s = self.complete_signoff()
        s["records"].append(dict(s["records"][0]))
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("duplicate review result", str(c.exception))

    def test_a_package_id_mismatch_is_refused(self):
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=self.complete_signoff(
                automated_package_id="0" * 64))
        self.assertIn("does not belong to this package", str(c.exception))

    def test_a_state_commit_mismatch_is_refused(self):
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=self.complete_signoff(state_commit="2" * 40))
        self.assertIn("does not belong to this package", str(c.exception))

    def test_an_invalid_timestamp_is_refused(self):
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=self.complete_signoff(
                review_completed_utc="last Tuesday"))
        self.assertIn("ISO-8601", str(c.exception))

    def test_completion_before_start_is_refused(self):
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=self.complete_signoff(
                review_completed_utc="2026-08-27T21:00:00+00:00"))
        self.assertIn("precedes", str(c.exception))

    def test_an_empty_reviewer_or_attestation_is_refused(self):
        for field in ("reviewer", "attestation"):
            with self.subTest(field=field):
                with self.assertRaises(pub.PublishError) as c:
                    self.run_pub(signoff=self.complete_signoff(**{field: "  "}))
                self.assertIn("unfilled form", str(c.exception))


class TestVerdictRules(PublisherCase):

    def test_pass_is_refused_when_a_check_is_false(self):
        s = self.complete_signoff()
        s["records"][0]["body_appears_complete"] = False
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s)
        self.assertIn("'pass' but", str(c.exception))

    def test_pass_with_findings_is_accepted_for_a_false_check(self):
        s = self.complete_signoff(verdict="pass_with_findings")
        s["records"][0]["body_appears_complete"] = False
        r = self.run_pub(signoff=s, do_publish=True)
        self.assertTrue(r["published"])
        self.assertEqual(r["verdict"], "pass_with_findings")

    def test_an_honest_failing_review_is_preserved(self):
        s = self.complete_signoff(verdict="fail",
                                  notes="Body truncated on two records.")
        s["records"][0]["body_appears_complete"] = False
        s["records"][1]["body_appears_complete"] = False
        r = self.run_pub(signoff=s, do_publish=True)
        self.assertTrue(r["published"], "a failing review must be publishable")
        self.assertEqual(r["verdict"], "fail")
        tree = subprocess.run(
            ["git", "--git-dir", str(self.remote), "show",
             "%s:index.jsonl" % pub.REVIEW_BRANCH],
            stdout=subprocess.PIPE, text=True, check=True).stdout
        self.assertIn('"verdict":"fail"', tree)

    def test_an_unknown_verdict_is_refused(self):
        with self.assertRaises(pub.PublishError):
            self.run_pub(signoff=self.complete_signoff(verdict="looks-fine"))


class TestAnomalyDisposition(PublisherCase):

    def _packet_with_anomaly(self):
        con = sqlite3.connect(str(self.state / "shadow.db"))
        con.execute("UPDATE shadow_records SET content_sha256='3'*64 "
                    "WHERE url=?", (URL % "19aug26-nr",))
        con.commit(); con.close()
        sha = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()
        for p in sorted((self.state / "ledger").glob("*.json")):
            e = json.loads(p.read_text(encoding="utf-8"))
            if e["state_sha256_before"] is not None:
                e["state_sha256_before"] = sha
            e["state_sha256_after"] = sha
            p.write_text(json.dumps(e, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
        packet = self.tmp / "anom"
        rk.build(self.state, packet, "2026-08-27", True, None, False, COMMIT,
                 "day-07")
        return packet, json.loads(
            (packet / "review_manifest.json").read_text(encoding="utf-8"))

    def test_pass_is_refused_while_an_anomaly_has_no_disposition(self):
        packet, manifest = self._packet_with_anomaly()
        self.assertGreater(manifest["anomaly_count"], 0)
        s = json.loads((packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s.update(reviewer="R", review_started_utc="2026-08-27T22:00:00+00:00",
                 review_completed_utc="2026-08-27T22:45:00+00:00",
                 verdict="pass", attestation="a")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s, packet=packet)
        self.assertIn("no disposition", str(c.exception))

    def test_an_anomaly_cannot_be_dropped_from_the_signoff(self):
        packet, manifest = self._packet_with_anomaly()
        s = json.loads((packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s["anomalies"] = []                     # quietly forgotten
        s.update(reviewer="R", review_started_utc="2026-08-27T22:00:00+00:00",
                 review_completed_utc="2026-08-27T22:45:00+00:00",
                 verdict="pass", attestation="a")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(signoff=s, packet=packet)
        self.assertIn("absent from the sign-off", str(c.exception))

    def test_pass_with_findings_is_accepted_once_disposed(self):
        packet, manifest = self._packet_with_anomaly()
        s = json.loads((packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        for a in s["anomalies"]:
            a["disposition"] = "Known fixture mutation; accepted."
        s.update(reviewer="R", review_started_utc="2026-08-27T22:00:00+00:00",
                 review_completed_utc="2026-08-27T22:45:00+00:00",
                 verdict="pass_with_findings", attestation="a")
        r = self.run_pub(signoff=s, packet=packet, do_publish=True)
        self.assertTrue(r["published"])


class TestCompletedReviewIdentity(PublisherCase):

    def test_the_id_is_deterministic(self):
        s = self.complete_signoff()
        a = pub.completed_review_id(self.manifest, s)
        b = pub.completed_review_id(self.manifest, json.loads(json.dumps(s)))
        self.assertEqual(a, b)

    def test_key_order_does_not_change_the_id(self):
        s = self.complete_signoff()
        shuffled = dict(reversed(list(s.items())))
        self.assertEqual(pub.completed_review_id(self.manifest, s),
                         pub.completed_review_id(self.manifest, shuffled))

    def test_a_changed_answer_changes_the_id(self):
        s = self.complete_signoff()
        base = pub.completed_review_id(self.manifest, s)
        s["records"][0]["kind_is_reasonable"] = False
        self.assertNotEqual(base, pub.completed_review_id(self.manifest, s))

    def test_the_id_is_bound_to_the_package(self):
        s = self.complete_signoff()
        other = dict(self.manifest, deterministic_sha256="9" * 64)
        self.assertNotEqual(pub.completed_review_id(self.manifest, s),
                            pub.completed_review_id(other, s))


class TestPublishSafety(PublisherCase):

    def test_dry_run_is_the_default_and_touches_nothing(self):
        r = self.run_pub()
        self.assertEqual(r["action"], "dry-run")
        self.assertFalse(r["published"])
        self.assertIsNone(self.head())

    def test_the_target_branch_is_fixed(self):
        """
        Checked against the CLI definition, not the source text: `git clone
        --branch` legitimately contains that literal, and a substring search
        cannot tell a git flag from a user-settable option.
        """
        import ast
        self.assertEqual(pub.REVIEW_BRANCH, "review/singapore-mindef")
        src = (REPO_ROOT / "scripts"
               / "publish_shadow_review.py").read_text(encoding="utf-8")
        options = set()
        for node in ast.walk(ast.parse(src)):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        options.add(arg.value)
        for forbidden in ("--branch", "--ref", "--target-branch", "--target"):
            with self.subTest(option=forbidden):
                self.assertNotIn(forbidden, options)
        self.assertNotIn("args.branch", src)

    def test_no_force_or_delete_is_ever_used(self):
        src = (REPO_ROOT / "scripts"
               / "publish_shadow_review.py").read_text(encoding="utf-8")
        for forbidden in ("--force", "--force-with-lease", "--delete",
                          "push --delete", "+refs/"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, src)

    def test_git_is_invoked_with_argument_arrays(self):
        src = (REPO_ROOT / "scripts"
               / "publish_shadow_review.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", src)

    def test_bootstrap_creates_a_genuinely_orphan_branch(self):
        self.run_pub(do_publish=True)
        log = subprocess.run(
            ["git", "--git-dir", str(self.remote), "log", "--format=%p",
             pub.REVIEW_BRANCH], stdout=subprocess.PIPE, text=True,
            check=True).stdout.strip()
        self.assertEqual(log, "", "the first commit must have no parent")

    def test_only_allowlisted_paths_are_preserved(self):
        self.run_pub(do_publish=True)
        files = subprocess.run(
            ["git", "--git-dir", str(self.remote), "ls-tree", "-r",
             "--name-only", pub.REVIEW_BRANCH], stdout=subprocess.PIPE,
            text=True, check=True).stdout.split()
        self.assertIn("README.md", files)
        self.assertIn("index.jsonl", files)
        for f in files:
            with self.subTest(path=f):
                self.assertFalse(f.endswith((".db", ".db-wal", ".db-shm",
                                             ".py", ".yml", ".yaml")))
                self.assertNotIn(".github", f)

    def test_a_database_in_the_packet_is_refused(self):
        (self.packet / "shadow.db").write_bytes(b"SQLite format 3\x00")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub()
        self.assertIn("never be preserved", str(c.exception))

    def test_a_workflow_file_in_the_packet_is_refused(self):
        (self.packet / "deploy.yml").write_text("on: push\n", encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub()
        self.assertIn("workflow", str(c.exception))

    def test_a_credential_in_the_packet_is_refused(self):
        (self.packet / "review_report.md").write_text(
            "token ghp_" + "A" * 30 + "\n", encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub()
        self.assertIn("credential", str(c.exception))

    def test_an_executable_in_the_packet_is_refused(self):
        script = self.packet / "helper.txt"
        script.write_text("echo hi\n", encoding="utf-8")
        script.chmod(0o755)
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub()
        self.assertIn("executable", str(c.exception))

    def test_the_packet_and_state_are_not_modified(self):
        def digest(root):
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.rglob("*")) if p.is_file()}
        pb, sb = digest(self.packet), digest(self.state)
        self.run_pub(do_publish=True)
        self.assertEqual(digest(self.packet), pb)
        self.assertEqual(digest(self.state), sb)

    def test_no_ref_but_the_review_branch_is_created(self):
        self.run_pub(do_publish=True)
        refs = subprocess.run(
            ["git", "--git-dir", str(self.remote), "for-each-ref",
             "--format=%(refname)"], stdout=subprocess.PIPE, text=True,
            check=True).stdout.split()
        self.assertEqual(refs, ["refs/heads/" + pub.REVIEW_BRANCH])


class TestAppendOnly(PublisherCase):

    def _day14(self):
        state = build_state(self.tmp / "s14", 15)
        packet = self.tmp / "p14"
        rk.build(state, packet, "2026-09-03", True, None, False, "2" * 40,
                 "day-14")
        s = json.loads((packet / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s.update(reviewer="Fixture Reviewer",
                 review_started_utc="2026-09-03T22:00:00+00:00",
                 review_completed_utc="2026-09-03T22:30:00+00:00",
                 verdict="pass", attestation="Compared each record.")
        p = self.tmp / "signoff14.json"
        p.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
        return packet, p

    def test_a_second_checkpoint_fast_forwards(self):
        self.run_pub(do_publish=True)
        head = self.head()
        packet, signoff = self._day14()
        r = pub.publish(packet, signoff, str(self.remote), "day-14", head,
                        False, True)
        self.assertEqual(r["action"], "fast-forward")
        parents = subprocess.run(
            ["git", "--git-dir", str(self.remote), "log", "--format=%p",
             pub.REVIEW_BRANCH], stdout=subprocess.PIPE, text=True,
            check=True).stdout.split()
        self.assertEqual(len(parents), 1, "second commit must have one parent")

    def test_an_identical_republish_is_an_idempotent_no_op(self):
        self.run_pub(do_publish=True)
        head = self.head()
        r = pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", head, False, True)
        self.assertEqual(r["action"], "idempotent-no-op")
        self.assertEqual(self.head(), head)

    def test_conflicting_content_under_the_same_id_is_refused(self):
        self.run_pub(do_publish=True)
        head = self.head()
        (self.packet / "review_report.md").write_text("tampered\n",
                                                      encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(self.packet, self.signoff_path, str(self.remote),
                        "day-07", head, False, True)
        self.assertIn("append-only", str(c.exception))
        self.assertEqual(self.head(), head)

    def test_a_stale_writer_is_rejected(self):
        self.run_pub(do_publish=True)
        stale = self.head()
        packet, signoff = self._day14()
        pub.publish(packet, signoff, str(self.remote), "day-14", stale, False, True)
        moved = self.head()
        self.assertNotEqual(stale, moved)
        state30 = build_state(self.tmp / "s30", 31)
        p30 = self.tmp / "p30"
        rk.build(state30, p30, "2026-09-19", True, None, False, "3" * 40, "day-30")
        s = json.loads((p30 / "signoff_template.json").read_text(encoding="utf-8"))
        for r in s["records"]:
            for f in pub.CHECK_FIELDS:
                r[f] = True
            r["note"] = ""
        s.update(reviewer="R", review_started_utc="2026-09-19T22:00:00+00:00",
                 review_completed_utc="2026-09-19T22:30:00+00:00",
                 verdict="pass", attestation="a")
        sp = self.tmp / "signoff30.json"
        sp.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(p30, sp, str(self.remote), "day-30", stale, False, True)
        self.assertIn("another writer", str(c.exception))
        self.assertEqual(self.head(), moved, "the remote must be untouched")

    def test_existing_evidence_is_never_rewritten(self):
        self.run_pub(do_publish=True)
        first = self.clone()
        before = {str(p.relative_to(first)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(first.rglob("*"))
                  if p.is_file() and ".git" not in p.parts}
        packet, signoff = self._day14()
        pub.publish(packet, signoff, str(self.remote), "day-14", self.head(),
                    False, True)
        after_clone = self.clone()
        after = {str(p.relative_to(after_clone)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(after_clone.rglob("*"))
                 if p.is_file() and ".git" not in p.parts}
        for path, digest in before.items():
            if path == "index.jsonl":
                continue                      # append-only, checked below
            with self.subTest(path=path):
                self.assertEqual(after.get(path), digest)
        old_index = (first / "index.jsonl").read_text(encoding="utf-8")
        new_index = (after_clone / "index.jsonl").read_text(encoding="utf-8")
        self.assertTrue(new_index.startswith(old_index),
                        "index.jsonl must only ever be appended to")

    def test_an_existing_branch_requires_an_expected_head(self):
        self.run_pub(do_publish=True)
        packet, signoff = self._day14()
        with self.assertRaises(pub.PublishError) as c:
            pub.publish(packet, signoff, str(self.remote), "day-14", None,
                        False, True)
        self.assertIn("--expected-head is required", str(c.exception))

    def test_bootstrap_over_an_existing_branch_is_refused(self):
        self.run_pub(do_publish=True)
        with self.assertRaises(pub.PublishError) as c:
            self.run_pub(do_publish=True)
        self.assertIn("already exists", str(c.exception))


class TestFailurePathsLeaveTheRemoteAlone(PublisherCase):

    def test_a_validation_failure_leaves_the_remote_unchanged(self):
        self.run_pub(do_publish=True)
        head = self.head()
        packet, signoff = self.packet, self.signoff_path
        bad = json.loads(signoff.read_text(encoding="utf-8"))
        bad["verdict"] = "nonsense"
        signoff.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(pub.PublishError):
            pub.publish(packet, signoff, str(self.remote), "day-07", head,
                        False, True)
        self.assertEqual(self.head(), head)

    def test_an_interrupted_preparation_leaves_the_remote_unchanged(self):
        self.run_pub(do_publish=True)
        head = self.head()
        original = pub.git

        def explode(args, cwd=None, check=True):
            if args and args[0] == "commit":
                raise pub.PublishError("simulated interruption before commit")
            return original(args, cwd=cwd, check=check)
        pub.git = explode
        self.addCleanup(setattr, pub, "git", original)
        packet, signoff = self.packet, self.signoff_path
        (packet / "review_report.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(pub.PublishError):
            pub.publish(packet, signoff, str(self.remote), "day-07", head,
                        False, True)
        self.assertEqual(self.head(), head)


if __name__ == "__main__":
    unittest.main()
