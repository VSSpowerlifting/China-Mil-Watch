"""
Singapore shadow review kit.

The kit reads evidence, so the tests are mostly about what it refuses: a
production path, a mutated input, an unknown schema, a ledger that disagrees
with itself. Everything runs from synthetic state built in a temp directory —
no network, no live state branch, no tracked artifact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "review_shadow_state", REPO_ROOT / "scripts" / "review_shadow_state.py")
rk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rk)

D0 = "2026-08-19T23:03:09+00:00"
URL = "https://www.mindef.gov.sg/news-and-events/latest-releases/%s/"


def body(n=600, text="Official release text. "):
    return (text * ((n // len(text)) + 1))[:n]


def record(slug, title=None, text=None):
    url = URL % slug
    t = text if text is not None else body()
    return {
        "url": url,
        "source_slug": "sg_mindef_releases",
        "title_original": title or ("Release " + slug),
        "text_original": t,
        "published_date": rk.slug_published_date(url),
        "language_tag": "en",
        "publication_kind": rk.publication_kind(url),
        "content_sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(),
        "capture_sha256": hashlib.sha256(b"capture").hexdigest(),
        "retrieved_at": "2026-08-19T23:03:00+00:00",
        "first_seen_run": "run-1",
    }


def write_db(path: Path, records):
    con = sqlite3.connect(str(path))
    con.executescript("""
CREATE TABLE IF NOT EXISTS shadow_records (
    url TEXT PRIMARY KEY, source_slug TEXT NOT NULL, title_original TEXT NOT NULL,
    text_original TEXT NOT NULL, published_date TEXT NOT NULL,
    language_tag TEXT NOT NULL, publication_kind TEXT NOT NULL,
    content_sha256 TEXT NOT NULL, capture_sha256 TEXT, retrieved_at TEXT,
    first_seen_run TEXT);
CREATE INDEX IF NOT EXISTS idx_shadow_published ON shadow_records(published_date);
""")
    for r in records:
        con.execute("INSERT OR REPLACE INTO shadow_records (%s) VALUES (%s)"
                    % (", ".join(rk.EXPECTED_COLUMNS),
                       ", ".join("?" * len(rk.EXPECTED_COLUMNS))),
                    [r[c] for c in rk.EXPECTED_COLUMNS])
    con.commit()
    con.close()


def ledger(run_id, finished, result, *, inserted=0, duplicates=0, discovered=0,
           selected=0, retrieved=0, before=None, after=None, shadow_day=0,
           health=None, stored_total=None, fetch_failures=0,
           extraction_failures=0, access_failures=0):
    e = {
        "run_id": run_id, "collector_commit": "abc123",
        "started_utc": finished, "finished_utc": finished,
        "target_date": finished[:10], "lookback_days": 30, "cap": 40,
        "robots_status": "allowed", "listing_status": "ok",
        "discovered": discovered, "selected": selected, "retrieved": retrieved,
        "inserted": inserted, "duplicates": duplicates, "filtered": 0,
        "fetch_failures": fetch_failures,
        "extraction_failures": extraction_failures,
        "access_failures": access_failures,
        "content_hashes": [], "state_sha256_before": before,
        "state_sha256_after": after, "result": result,
        "health": health or ("ok" if result in rk.TERMINAL_OK else "fail"),
        "error_detail": None, "shadow_day": shadow_day,
        "day_zero_utc": D0,
    }
    if stored_total is not None:
        e["stored_total"] = stored_total
        e["corpus_range"] = [None, None]
    return e


class KitCase(unittest.TestCase):
    """A minimal but internally consistent state directory."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="review-kit-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "state"
        (self.state / "ledger").mkdir(parents=True)
        self.out = self.tmp / "out"
        self.records = [record("19aug26-nr"), record("20aug26-speech"),
                        record("18aug26-pq2")]
        write_db(self.state / "shadow.db", self.records)
        self.db_sha = hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest()
        (self.state / "clock.json").write_text(
            json.dumps({"day_zero_utc": D0, "day_zero_run_id": "run-1"}),
            encoding="utf-8")
        self.entries = [
            ledger("run-1", D0, rk.st.OK, inserted=3, discovered=3, selected=3,
                   retrieved=3, before=None, after=self.db_sha, shadow_day=0,
                   stored_total=3),
            ledger("run-2", "2026-08-20T21:41:50+00:00", rk.st.OK_ALL_DUPLICATES,
                   duplicates=3, discovered=3, selected=3, retrieved=3,
                   before=self.db_sha, after=self.db_sha, shadow_day=0,
                   stored_total=3),
        ]
        self.write_ledgers()

    def write_ledgers(self, entries=None):
        for p in (self.state / "ledger").glob("*.json"):
            p.unlink()
        for e in (entries if entries is not None else self.entries):
            name = rk.expected_ledger_filename(e)
            (self.state / "ledger" / name).write_text(
                json.dumps(e, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def run_kit(self, **kw):
        kw.setdefault("as_of", "2026-08-23")
        kw.setdefault("review_all", True)
        kw.setdefault("since_ledger", None)
        kw.setdefault("allow_tracked", False)
        return rk.build(self.state, kw.pop("out", self.out), **kw)


class TestValidStatePasses(KitCase):

    def test_a_consistent_state_produces_a_package_with_no_anomalies(self):
        m = self.run_kit()
        self.assertEqual(m["anomaly_count"], 0, m["anomalies"])
        self.assertEqual(m["corpus_count"], 3)
        self.assertEqual(m["state_chain_verdict"], "coherent")
        for name in ("review_manifest.json", "review_report.md",
                     "record_inventory.jsonl"):
            self.assertTrue((self.out / name).is_file(), name)

    def test_the_inventory_has_one_entry_per_record(self):
        self.run_kit()
        lines = (self.out / "record_inventory.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)
        entry = json.loads(lines[0])
        for field in ("identity", "canonical_url", "title", "published_date",
                      "publication_kind", "body_chars", "content_sha256",
                      "flags", "selected_for_review", "selected_because"):
            self.assertIn(field, entry)

    def test_two_runs_with_the_same_as_of_are_byte_identical(self):
        a, b = self.tmp / "a", self.tmp / "b"
        self.run_kit(out=a)
        self.run_kit(out=b)
        for name in ("review_report.md", "record_inventory.jsonl"):
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)
        ma = json.loads((a / "review_manifest.json").read_text())
        mb = json.loads((b / "review_manifest.json").read_text())
        self.assertEqual(ma["deterministic_sha256"], mb["deterministic_sha256"])
        ma.pop("generated"); mb.pop("generated")
        self.assertEqual(ma, mb)


class TestInputSafety(KitCase):

    def test_the_input_database_is_opened_read_only(self):
        con = rk.open_readonly(self.state / "shadow.db")
        self.addCleanup(con.close)
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("DELETE FROM shadow_records")

    def test_inputs_are_unchanged_and_no_sidecar_appears(self):
        before = rk.hash_inputs(self.state)
        self.run_kit()
        self.assertEqual(rk.hash_inputs(self.state), before)
        for s in ("shadow.db-wal", "shadow.db-shm"):
            self.assertFalse((self.state / s).exists(), s)

    def test_a_changed_input_voids_the_package(self):
        original = rk.hash_inputs
        state = self.state

        def mutate_after_read(path):
            out = original(path)
            if not getattr(mutate_after_read, "done", False):
                mutate_after_read.done = True
            else:
                (state / "clock.json").write_text("{}", encoding="utf-8")
                return original(path)
            return out
        rk.hash_inputs = mutate_after_read
        self.addCleanup(setattr, rk, "hash_inputs", original)
        with self.assertRaises(rk.ReviewError) as caught:
            self.run_kit()
        self.assertIn("input state changed", str(caught.exception))

    def test_the_repository_root_is_refused(self):
        with self.assertRaises(rk.ReviewError):
            rk.assert_safe_state_dir(REPO_ROOT)

    def test_a_state_dir_holding_the_production_database_is_refused(self):
        (self.state / "pla_watch.db").write_bytes(b"x")
        with self.assertRaises(rk.ReviewError) as c:
            rk.assert_safe_state_dir(self.state)
        self.assertIn("pla_watch.db", str(c.exception))

    def test_a_state_dir_holding_public_output_is_refused(self):
        (self.state / "output").mkdir()
        with self.assertRaises(rk.ReviewError) as c:
            rk.assert_safe_state_dir(self.state)
        self.assertIn("output", str(c.exception))

    def test_a_tracked_destination_is_refused_without_the_override(self):
        with self.assertRaises(rk.ReviewError):
            rk.assert_safe_out_dir(REPO_ROOT / "output" / "x", False)
        rk.assert_safe_out_dir(REPO_ROOT / "output" / "x", True)

    def test_the_kit_imports_nothing_network_capable(self):
        """
        Checked against the import statements, not the prose: the module
        docstring names `sg_mindef` precisely to explain why it is not
        imported, and a substring search cannot tell those apart.
        """
        import ast
        src = (REPO_ROOT / "scripts"
               / "review_shadow_state.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for forbidden in ("requests", "urllib.request", "urllib3", "http.client",
                          "socket", "config", "scraper.sources.sg_mindef",
                          "storage.db", "site.render"):
            with self.subTest(module=forbidden):
                self.assertNotIn(forbidden, imported)
        # Only stdlib plus the pure status-constant module.
        self.assertTrue(
            imported <= {"__future__", "argparse", "hashlib", "json", "re",
                         "sqlite3", "sys", "datetime", "pathlib",
                         "core.collection"},
            "unexpected runtime import(s): %s" % sorted(imported))


class TestStateContractRefusals(KitCase):

    def test_an_unknown_schema_is_refused(self):
        con = sqlite3.connect(str(self.state / "shadow.db"))
        con.execute("ALTER TABLE shadow_records ADD COLUMN surprise TEXT")
        con.commit(); con.close()
        with self.assertRaises(rk.ReviewError) as c:
            self.run_kit()
        self.assertIn("unknown shadow_records shape", str(c.exception))

    def test_a_missing_clock_is_refused(self):
        (self.state / "clock.json").unlink()
        with self.assertRaises(rk.ReviewError) as c:
            self.run_kit()
        self.assertIn("clock", str(c.exception))

    def test_an_unrecognised_ledger_format_is_refused(self):
        p = next((self.state / "ledger").glob("*.json"))
        data = json.loads(p.read_text()); data.pop("state_sha256_after")
        p.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(rk.ReviewError) as c:
            self.run_kit()
        self.assertIn("missing required field", str(c.exception))

    def test_a_malformed_ledger_filename_is_flagged(self):
        p = next((self.state / "ledger").glob("*.json"))
        p.rename(p.with_name("not-the-right-name.json"))
        m = self.run_kit()
        self.assertTrue(any("does not match its contents" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_a_duplicate_run_id_is_flagged(self):
        dup = ledger("run-1", "2026-08-21T21:37:45+00:00", rk.st.OK_ALL_DUPLICATES,
                     duplicates=3, before=self.db_sha, after=self.db_sha,
                     shadow_day=1, stored_total=3)
        self.write_ledgers(self.entries + [dup])
        m = self.run_kit()
        self.assertTrue(any("duplicate run id" in x for x in m["anomalies"]))

    def test_a_clock_run_mismatch_is_flagged(self):
        (self.state / "clock.json").write_text(json.dumps(
            {"day_zero_utc": "2026-08-01T00:00:00+00:00",
             "day_zero_run_id": "run-1"}), encoding="utf-8")
        m = self.run_kit()
        self.assertTrue(any("day-zero timestamp mismatch" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_an_unknown_result_is_flagged(self):
        self.entries[1]["result"] = "totally_made_up"
        self.entries[1]["health"] = "ok"
        self.write_ledgers()
        m = self.run_kit()
        self.assertTrue(any("unrecognised result" in x for x in m["anomalies"]))

    def test_counts_that_contradict_the_result_are_flagged(self):
        self.entries[1]["inserted"] = 5          # says ok_all_duplicates
        self.write_ledgers()
        m = self.run_kit()
        self.assertTrue(any("counts imply" in x for x in m["anomalies"]),
                        m["anomalies"])

    def test_a_broken_state_chain_is_flagged(self):
        self.entries[1]["state_sha256_before"] = "0" * 64
        self.write_ledgers()
        m = self.run_kit()
        self.assertEqual(m["state_chain_verdict"], "BROKEN")
        self.assertTrue(any("state chain broken" in x for x in m["anomalies"]))

    def test_a_final_hash_that_does_not_match_the_database_is_flagged(self):
        self.entries[-1]["state_sha256_after"] = "1" * 64
        self.write_ledgers()
        m = self.run_kit()
        self.assertTrue(any("does not match the last ledger" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_a_duplicate_only_run_that_changed_the_database_is_flagged(self):
        self.entries[1]["state_sha256_after"] = "2" * 64
        self.write_ledgers()
        m = self.run_kit()
        self.assertTrue(any("duplicate-only run changed the database" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_a_failed_run_that_advanced_the_clock_is_flagged(self):
        bad = ledger("run-3", "2026-08-21T21:37:45+00:00", rk.st.LISTING_FAILURE,
                     before=self.db_sha, after=self.db_sha, shadow_day=1)
        self.write_ledgers(self.entries + [bad])
        m = self.run_kit()
        self.assertTrue(any("failed run advanced the clock" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_an_off_by_one_shadow_day_is_flagged(self):
        self.entries[1]["shadow_day"] = 1        # only ~22h have elapsed
        self.write_ledgers()
        m = self.run_kit()
        self.assertTrue(any("complete 24-hour periods" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_a_missing_scheduled_day_is_flagged(self):
        later = ledger("run-9", "2026-08-24T21:35:00+00:00",
                       rk.st.OK_ALL_DUPLICATES, duplicates=3,
                       before=self.db_sha, after=self.db_sha, shadow_day=4,
                       stored_total=3)
        self.write_ledgers(self.entries + [later])
        m = self.run_kit()
        self.assertIn("2026-08-21", m["missing_days"])
        self.assertIn("2026-08-22", m["missing_days"])


class TestRecordValidation(KitCase):

    def _rewrite(self, url, **cols):
        con = sqlite3.connect(str(self.state / "shadow.db"))
        for k, v in cols.items():
            con.execute("UPDATE shadow_records SET %s=? WHERE url=?" % k, (v, url))
        con.commit(); con.close()
        self.entries[-1]["state_sha256_after"] = hashlib.sha256(
            (self.state / "shadow.db").read_bytes()).hexdigest()
        self.entries[1]["state_sha256_before"] = self.entries[0]["state_sha256_after"]
        self.write_ledgers()

    def test_a_missing_required_field_is_flagged(self):
        self._rewrite(URL % "19aug26-nr", title_original="")
        m = self.run_kit()
        self.assertTrue(any("missing:title_original" in x for x in m["anomalies"]))

    def test_an_incorrect_content_hash_is_flagged(self):
        self._rewrite(URL % "19aug26-nr", content_sha256="3" * 64)
        m = self.run_kit()
        self.assertTrue(any("hash:mismatch" in x for x in m["anomalies"]))

    def test_an_empty_body_is_flagged(self):
        self._rewrite(URL % "19aug26-nr", text_original="   ")
        m = self.run_kit()
        self.assertTrue(any("body:empty" in x for x in m["anomalies"]))

    def test_a_known_challenge_or_error_stub_is_flagged(self):
        stub = ("Attention Required! | Cloudflare  Please enable JavaScript "
                "and cookies to continue. " * 8)
        self._rewrite(URL % "19aug26-nr", text_original=stub,
                      content_sha256=hashlib.sha256(
                          stub.encode("utf-8")).hexdigest())
        m = self.run_kit()
        self.assertTrue(any("body:stub-marker" in x for x in m["anomalies"]),
                        m["anomalies"])

    def test_a_foreign_production_record_is_flagged(self):
        self._rewrite(URL % "19aug26-nr", source_slug="pla_daily")
        m = self.run_kit()
        self.assertTrue(any("source:foreign-pla_daily" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_a_date_that_contradicts_the_official_slug_is_flagged(self):
        self._rewrite(URL % "19aug26-nr", published_date="2020-01-01")
        m = self.run_kit()
        self.assertTrue(any("date:slug-says-2026-08-19" in x
                            for x in m["anomalies"]), m["anomalies"])

    def test_same_title_different_url_records_stay_distinct(self):
        shared = "Identical Headline"
        recs = [record("19aug26-nr", title=shared),
                record("20aug26-speech", title=shared)]
        (self.state / "shadow.db").unlink()      # replace, do not merge
        write_db(self.state / "shadow.db", recs)
        sha = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()
        self.entries[0]["state_sha256_after"] = sha
        self.entries[0]["inserted"] = 2
        self.entries[0]["stored_total"] = 2
        self.entries[1]["state_sha256_before"] = sha
        self.entries[1]["state_sha256_after"] = sha
        self.entries[1]["duplicates"] = 2
        self.entries[1]["stored_total"] = 2
        self.write_ledgers()
        m = self.run_kit()
        self.assertEqual(m["corpus_count"], 2)
        report = (self.out / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("Identical Headline", report)
        self.assertFalse(any("duplicate canonical URL" in x
                             for x in m["anomalies"]))


class TestReviewQueue(KitCase):

    def test_review_all_queues_every_record(self):
        m = self.run_kit(review_all=True)
        self.assertEqual(m["review_queue_size"], m["corpus_count"])

    def test_the_incremental_queue_includes_every_new_record(self):
        con = sqlite3.connect(str(self.state / "shadow.db"))
        r = record("21aug26-fs")
        r["first_seen_run"] = "run-2"
        con.execute("INSERT INTO shadow_records (%s) VALUES (%s)"
                    % (", ".join(rk.EXPECTED_COLUMNS),
                       ", ".join("?" * len(rk.EXPECTED_COLUMNS))),
                    [r[c] for c in rk.EXPECTED_COLUMNS])
        con.commit(); con.close()
        sha = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()
        self.entries[1]["state_sha256_after"] = sha
        self.entries[1]["inserted"] = 1
        self.entries[1]["duplicates"] = 3
        self.entries[1]["result"] = rk.st.OK
        self.entries[1]["stored_total"] = 4
        self.write_ledgers()
        m = self.run_kit(review_all=False,
                         since_ledger=rk.expected_ledger_filename(self.entries[0]))
        self.assertIn(r["url"], m["review_queue"])

    def test_an_unknown_since_ledger_is_refused(self):
        with self.assertRaises(rk.ReviewError):
            self.run_kit(review_all=False, since_ledger="nope.json")

    def test_the_focused_queue_covers_every_publication_kind(self):
        m = self.run_kit(review_all=False)
        inv = [json.loads(l) for l in (self.out / "record_inventory.jsonl")
               .read_text(encoding="utf-8").strip().splitlines()]
        queued_kinds = {e["publication_kind"] for e in inv
                        if e["selected_for_review"]}
        self.assertEqual(queued_kinds, {e["publication_kind"] for e in inv})

    def test_the_queue_is_deterministic(self):
        a = self.run_kit(review_all=False, out=self.tmp / "qa")
        b = self.run_kit(review_all=False, out=self.tmp / "qb")
        self.assertEqual(a["review_queue"], b["review_queue"])

    def test_the_hash_selected_remainder_is_deterministic(self):
        """
        The three-record fixture never reaches the remainder rule: the explicit
        rules already queue everything, so a nondeterministic remainder would
        leave no trace. This corpus is large enough that the remainder is the
        only thing deciding most of the queue.
        """
        recs = [record("%dau g26-nr".replace(" ", "") % d, title="Release %d" % d,
                       text=body(600 + d))
                for d in range(1, 26)]
        (self.state / "shadow.db").unlink()
        write_db(self.state / "shadow.db", recs)
        sha = hashlib.sha256((self.state / "shadow.db").read_bytes()).hexdigest()
        self.entries[0].update(state_sha256_after=sha, inserted=len(recs),
                               stored_total=len(recs))
        self.entries[1].update(state_sha256_before=sha, state_sha256_after=sha,
                               duplicates=len(recs), stored_total=len(recs))
        self.write_ledgers()

        a = self.run_kit(review_all=False, out=self.tmp / "ra")
        b = self.run_kit(review_all=False, out=self.tmp / "rb")
        self.assertEqual(a["corpus_count"], len(recs))
        self.assertLess(a["review_queue_size"], a["corpus_count"],
                        "fixture must not queue everything, or the remainder "
                        "rule is untested")
        self.assertEqual(a["review_queue"], b["review_queue"])
        self.assertEqual((self.tmp / "ra" / "review_report.md").read_bytes(),
                         (self.tmp / "rb" / "review_report.md").read_bytes())


class TestTheReportIsNotEvidence(KitCase):

    def test_the_report_says_an_unfilled_form_is_not_a_completed_review(self):
        self.run_kit()
        text = (self.out / "review_report.md").read_text(encoding="utf-8")
        self.assertIn("An unfilled report is not evidence of a completed review",
                      text)
        self.assertIn("Reviewer identity", text)
        self.assertIn("Review completion timestamp", text)

    def test_the_manifest_states_that_automation_is_not_the_review(self):
        m = self.run_kit()
        self.assertIn("automated_checks_are_not_the_human_review", m)

    def test_every_queued_record_gets_an_empty_reviewer_form(self):
        self.run_kit()
        text = (self.out / "review_report.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("| Source page opened | |"),
                         self.run_kit()["review_queue_size"])


class TestAgreesWithTheCollector(unittest.TestCase):
    """
    The kit re-derives the URL shape, slug date and slug kind rather than
    importing the adapter, which pulls in `requests`. This is what stops the
    two copies from drifting apart.
    """

    def test_the_rederived_helpers_match_the_adapter(self):
        spec = importlib.util.spec_from_file_location(
            "sg_adapter", REPO_ROOT / "scraper" / "sources" / "sg_mindef.py")
        sg = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(sg)
        except ImportError:                                    # pragma: no cover
            raise unittest.SkipTest("adapter dependencies unavailable")
        self.assertEqual(rk.KINDS, sg.KINDS)
        self.assertEqual(rk.RELEASE_RE.pattern, sg.RELEASE_RE.pattern)
        self.assertEqual(rk.COLLECTOR_MIN_BODY_CHARS, sg.MIN_BODY_CHARS)
        for slug in ("15aug26-speech", "5aug26-pq2", "12aug26-nr1",
                     "14aug26-mq", "12aug26-fs", "1jan26-xyz"):
            url = URL % slug
            with self.subTest(slug=slug):
                self.assertEqual(rk.slug_published_date(url),
                                 sg.slug_published_date(url))
                self.assertEqual(rk.publication_kind(url),
                                 sg.publication_kind(url))


if __name__ == "__main__":
    unittest.main()
