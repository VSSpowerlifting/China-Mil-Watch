"""Offline, synthetic negative attestation fixtures. Never a real scheduled day."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.attest_us_bis_scheduled_receipt import (
    BISAttestationHold, REPO, WORKFLOW, WORKFLOW_NAME, attest)
from tests.test_us_bis_homepage_receipt import packet

RUN_ID = 38823500001
RUN_ATTEMPT = 1
DAY = "2026-10-15"
START = "2026-10-15T12:36:10Z"

def run_metadata():
    return {
        "id": RUN_ID, "run_attempt": RUN_ATTEMPT,
        "event": "schedule", "status": "completed", "conclusion": "success",
        "head_branch": "main", "head_sha": "b" * 40,
        "repository": {"full_name": REPO},
        "path": WORKFLOW, "name": WORKFLOW_NAME,
        "html_url": "https://github.com/" + REPO +
                    "/actions/runs/" + str(RUN_ID),
        "created_at": "2026-10-15T12:35:00Z",
        "run_started_at": START,
    }

def git(path, *args):
    return subprocess.check_output(
        ["git", "-C", str(path), *args], stderr=subprocess.DEVNULL).decode().strip()

class TestAttestation(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "isolated-shadow"
        self.path.mkdir()
        git(self.path, "init", "-q", "-b", "shadow/us-bis-homepage")
        git(self.path, "config", "user.name", "github-actions[bot]")
        git(self.path, "config", "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com")
        (self.path/"README.md").write_text("synthetic shadow only\n")
        (self.path/"observations").mkdir()
        self.receipt = self.path/"observations"/(DAY + ".json")
        self.receipt.write_text(json.dumps(packet()) + "\n", encoding="utf-8")
        git(self.path, "add", "--", "README.md", "observations")
        digest = packet()["official_listing_sha256"]
        self.message = ("\n".join((
            "BIS: genuine scheduled homepage metadata " + DAY,
            "", "Actions event: schedule", "",
            "Actions run: https://github.com/" + REPO +
            "/actions/runs/" + str(RUN_ID) + "/attempts/1",
            "", "Source listing SHA-256: " + digest,
        )))
        git(self.path, "commit", "-q", "-m", self.message)
        self.head = git(self.path, "rev-parse", "HEAD")
        self.run = run_metadata()

    def attest(self, run=None, sha=None):
        return attest(self.path, self.run if run is None else run,
                      expected_remote_head=self.head if sha is None else sha)

    def test_positive_synthetic_join_is_still_not_live_approval(self):
        r = self.attest()
        self.assertEqual(r["source_commit"], self.head)
        self.assertEqual(r["receipt_day"], DAY)
        self.assertEqual(r["verified_official_link_rows"], 2)
        self.assertFalse(r["qualified_clean_day_streak"])
        self.assertFalse(r["live_sqlite_admission_authorized"])
        self.assertFalse(r["public_site_publishing_authorized"])
        self.assertFalse(r["source_html_independently_rehashed"])

    def test_only_genuine_scheduled_success_is_allowed(self):
        for field,value in [
            ("event","workflow_dispatch"), ("event","pull_request"),
            ("conclusion","failure"), ("conclusion",None),
            ("status","in_progress"), ("head_branch","feature/bis"),
            ("head_sha","bad"), ("name","Treasury Official Press Metadata"),
            ("path",".github/workflows/treasury_verified_official_links_release.yml"),
            ("html_url","https://evil.invalid/run/1"), ("run_attempt",2),
            ("id",RUN_ID+1), ("created_at","bad"), ("run_started_at","bad"),
        ]:
            with self.subTest(field=field,value=value):
                item=copy.deepcopy(self.run);item[field]=value
                with self.assertRaises(BISAttestationHold):
                    self.attest(item)
        item=copy.deepcopy(self.run)
        item["repository"]["full_name"]="VSSpowerlifting/another"
        with self.assertRaises(BISAttestationHold):
            self.attest(item)

    def test_wrong_remote_sha_or_checkout_branch_holds(self):
        with self.assertRaises(BISAttestationHold):
            self.attest(sha="c"*40)
        git(self.path,"checkout","-q","-b","false-origin")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_mutating_receipt_after_creation_holds(self):
        p=packet();p["official_listing_sha256"]="c"*64
        self.receipt.write_text(json.dumps(p),encoding="utf-8")
        git(self.path,"add","--","observations")
        git(self.path,"commit","-q","-m","later unauthorized receipt rewrite")
        self.head=git(self.path,"rev-parse","HEAD")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_dirty_source_tree_holds(self):
        (self.path/"unexpected.json").write_text("{}")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_replayed_commit_marker_holds(self):
        (self.path/"notes.txt").write_text("not an original publisher record")
        git(self.path,"add","--","notes.txt")
        git(self.path,"commit","-q","-m",self.message)
        self.head=git(self.path,"rev-parse","HEAD")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_wrong_commit_digest_holds(self):
        git(self.path,"commit","--amend","-q","-m",
            self.message.replace(packet()["official_listing_sha256"],"f"*64))
        self.head=git(self.path,"rev-parse","HEAD")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_additional_unapproved_file_in_receipt_commit_holds(self):
        (self.path/"untrusted.txt").write_text("extra\n")
        git(self.path,"add","--","untrusted.txt")
        git(self.path,"commit","--amend","-q","--no-edit")
        self.head=git(self.path,"rev-parse","HEAD")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_wrong_day_and_unparseable_receipt_holds(self):
        p=packet()
        p["observed_on_utc"]="2026-10-14"
        self.receipt.write_text(json.dumps(p),encoding="utf-8")
        git(self.path,"add","--","observations")
        git(self.path,"commit","--amend","-q","--no-edit")
        self.head=git(self.path,"rev-parse","HEAD")
        with self.assertRaises(BISAttestationHold):
            self.attest()

    def test_source_commit_time_not_recency_proof(self):
        r=self.attest()
        self.assertNotIn("complete_publisher_history",r)
        self.assertFalse(r["qualified_clean_day_streak"])

if __name__=="__main__":
    unittest.main()
