"""No-network tests for the unsigned Vietnam MPS metadata-only preview."""
import copy
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import preview_vietnam_mps_metadata as p


def queue():
    records = []
    for identity, entry in p.DRAFTS.items():
        n = identity.split(":")[1]
        records.append({
            "source_identity": identity,
            "source_slug": p.SOURCE,
            "canonical_url": "https://bocongan.gov.vn/bai-viet/synthetic-%s" % n,
            "published_date": "2026-10-05",
            "title_original": "Synthetic ministry title for %s" % n,
            "content_sha256": entry["digest"],
            "first_capture_sha256": "b" * 64,
            "machine_review_candidate": True,
            "machine_blockers": [],
            "human_source_reviewed": False,
            "reuse_rights_reviewed": False,
            "production_publication_authorized": False,
        })
    return {
        "state_commit": p.PINNED_COMMIT,
        "state_tree": p.PINNED_TREE,
        "queue_sha256": p.PINNED_QUEUE,
        "human_approvals": 0,
        "rights_approvals": 0,
        "automatic_production_admission": False,
        "records": records,
    }


def create_prod(path, with_collisions=()):
    with sqlite3.connect(str(path)) as conn:
        conn.executescript("""
            CREATE TABLE desks (desk_id TEXT);
            CREATE TABLE institutions (institution_id TEXT);
            CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT);
            CREATE TABLE articles (
              id INTEGER PRIMARY KEY,url TEXT UNIQUE,content_hash TEXT,
              source_id INTEGER,title_original TEXT,text_original TEXT
            );
        """)
        for i, url in enumerate(with_collisions):
            conn.execute("INSERT INTO articles(url,content_hash,source_id) VALUES (?,?,?)",
                         (url, "%064d" % i, 1))


class MetadataPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prod = self.root / "production-snapshot.db"
        create_prod(self.prod)

    def conn(self):
        return sqlite3.connect(self.prod)

    def test_exact_pinned_queue_creates_metadata_rows(self):
        with self.conn() as conn:
            rows = p.prepare_rows(queue(), conn)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(x["rights_state"] == "unresolved" for x in rows))
        self.assertTrue(all(x["publication_authorized"] == 0 for x in rows))
        self.assertTrue(all(x["original_article_body_retained"] == 0 for x in rows))
        self.assertTrue(all(x["language_tag"] == "vi" for x in rows))
        self.assertEqual({x["institution_id"] for x in rows}, {"vn_mps"})
        self.assertTrue(all(x["review_state"] == "pending_human_signoff" for x in rows))
        self.assertTrue(all(x["draft_abstract"] for x in rows))
        self.assertEqual({x["content_sha256"] for x in rows},
                         {d["digest"] for d in p.DRAFTS.values()})

    def test_preview_sqlite_is_separate_and_only_contains_metadata(self):
        with self.conn() as conn:
            rows = p.prepare_rows(queue(), conn)
        dest = self.root / "metadata-preview.db"
        digest = p.write_preview(dest, rows)
        self.assertEqual(digest, hashlib.sha256(dest.read_bytes()).hexdigest())
        with sqlite3.connect(dest) as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(tables, {"preview_records"})
            self.assertEqual(con.execute("SELECT count(*) FROM preview_records").fetchone()[0], 3)
            self.assertEqual(con.execute("SELECT sum(publication_authorized) FROM preview_records").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT sum(original_article_body_retained) FROM preview_records").fetchone()[0], 0)
        raw = dest.read_bytes()
        for token in (b"Vietnamese text as captured", b"source HTML", b"article body"):
            self.assertNotIn(token, raw)
        self.assertTrue(self.prod.is_file())

    def test_existing_production_url_only_flags_collision(self):
        q = queue()
        url = q["records"][0]["canonical_url"]
        with sqlite3.connect(self.prod) as conn:
            conn.execute("INSERT INTO articles(url,content_hash) VALUES (?,?)",
                         (url, "x" * 64))
        prod_before = self.prod.read_bytes()
        with self.conn() as conn:
            rows = p.prepare_rows(q, conn)
        self.assertEqual(sum(x["production_collision"] for x in rows), 1)
        p.write_preview(self.root / "preview.db", rows)
        self.assertEqual(self.prod.read_bytes(), prod_before)

    def test_bad_identity_and_mismatched_source_version_refused(self):
        q = queue()
        q["records"][0]["canonical_url"] = "https://elsewhere.example/article"
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "canonical"):
            p.prepare_rows(q, conn)
        q = queue()
        q["records"][0]["content_sha256"] = "0" * 64
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "another source"):
            p.prepare_rows(q, conn)
        q = queue()
        q["records"][0]["source_slug"] = "vn_moit_energy_vi"
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "another source"):
            p.prepare_rows(q, conn)

    def test_machine_holds_are_never_imported_even_into_preview(self):
        for key, value in (
            ("machine_review_candidate", False),
            ("machine_blockers", ["possible_capture_mismatch"]),
            ("human_source_reviewed", True),
            ("reuse_rights_reviewed", True),
            ("production_publication_authorized", True),
        ):
            q = queue()
            q["records"][0][key] = value
            with self.subTest(field=key), self.conn() as conn, self.assertRaises(p.PreviewRefused):
                p.prepare_rows(q, conn)

    def test_incorrect_queue_digest_and_record_roster_refused(self):
        q = queue()
        q["queue_sha256"] = "f" * 64
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "independently verified"):
            p.prepare_rows(q, conn)
        q = queue()
        q["records"].pop()
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "three pinned"):
            p.prepare_rows(q, conn)
        q = queue()
        q["automatic_production_admission"] = True
        with self.conn() as conn, self.assertRaisesRegex(p.PreviewRefused, "automatic approval"):
            p.prepare_rows(q, conn)

    def test_audited_readonly_production_snapshot_is_byte_unchanged(self):
        before = p.digest_bytes(self.prod)
        for conn, prod_hash in p.read_production_snapshot(self.prod):
            self.assertEqual(prod_hash, before)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO articles(url) VALUES ('test')")
        self.assertEqual(before, p.digest_bytes(self.prod))

    def test_refuse_repository_paths_symlinks_and_existing_preview(self):
        with self.assertRaisesRegex(p.PreviewRefused, "outside repository"):
            p._outside_repo(p.ROOT / "pla_watch.db")
        alias = self.root / "prod-symlink.db"
        alias.symlink_to(self.prod)
        with self.assertRaisesRegex(p.PreviewRefused, "symbolic"):
            next(p.read_production_snapshot(alias))
        with self.conn() as conn:
            rows = p.prepare_rows(queue(), conn)
        target = self.root / "existing.db"
        target.write_text("untouched")
        with self.assertRaisesRegex(p.PreviewRefused, "must not already exist"):
            p.write_preview(target, rows)
        self.assertEqual(target.read_text(), "untouched")

    def test_preview_db_constraint_refuses_approval_or_fulltext_flag(self):
        with self.conn() as conn:
            rows = p.prepare_rows(queue(), conn)
        dest = self.root / "metadata.db"
        p.write_preview(dest, rows)
        with sqlite3.connect(dest) as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE preview_records SET publication_authorized=1")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE preview_records SET original_article_body_retained=1")

    def test_pinned_source_does_not_accept_other_commit(self):
        with self.assertRaisesRegex(p.PreviewRefused, "pinned"):
            p.verified_queue(self.root, "0" * 40)

    def test_missing_or_unmigrated_prod_refused(self):
        with self.assertRaisesRegex(p.PreviewRefused, "existing production"):
            next(p.read_production_snapshot(self.root / "missing.db"))
        bad = self.root / "unmigrated.db"
        sqlite3.connect(bad).close()
        with self.assertRaisesRegex(p.PreviewRefused, "migrated"):
            next(p.read_production_snapshot(bad))


if __name__ == "__main__":
    unittest.main()
