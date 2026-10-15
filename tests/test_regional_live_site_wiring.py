"""AFP/Kemhan public-site binding — disposable SQLite and template contracts.

No production DB, shadow checkout, website or live publisher is read or written.
"""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from core.regional_official_link_release import SCHEMA_SQL
from core.regional_official_link_render import (
    RegionalRenderHold, load_admitted_links,
)
from tests.test_regional_official_link_render import insert

ROOT = Path(__file__).resolve().parents[1]


def desk(slug):
    return SimpleNamespace(
        slug=slug,
        name={"philippines": "Philippines Desk",
              "indonesia": "Indonesia Desk"}[slug],
        route=slug + ".html",
        scope="Single verified institutional source family",
        status="shadow",
        status_label="Shadow — original texts not admitted",
        status_explanation="The public corpus remains unavailable",
        record_count=None,
        limits=[],
    )


def html_for(slug, references):
    env = Environment(loader=FileSystemLoader(
        str(ROOT / "site" / "preview" / "templates")),
        autoescape=True, trim_blocks=True, lstrip_blocks=True)
    return env.get_template("desk.html").render(
        title="Indo-Pacific Record", page=slug + ".html",
        desk=desk(slug),
        regional_official_links=references,
        public_source_links=[],
        published_research=[],
        public_source_options=[],
        public_reference_languages=[],
        indonesia_official_links=[], indonesia_press_links=[],
        us_pacom_official_links=[], uscc_official_links=[],
        us_treasury_official_links=[],
        korea_public_links=[], korea_additional_links=[],
        display_limits=[], source_options=[],
    )


class RegionalLiveSiteWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "source-index-test.sqlite"
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE scratch (n INTEGER)")
        conn.commit()
        conn.close()

    def migrate(self):
        con = sqlite3.connect(str(self.db))
        con.execute(SCHEMA_SQL)
        con.commit()
        return con

    def _digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()

    def test_missing_source_index_does_not_claim_any_live_feed(self):
        before = self._digest()
        rows = load_admitted_links(self.db, "philippines")
        self.assertEqual(rows, [])
        h = html_for("philippines", rows)
        self.assertNotIn("data-regional-official-source-id", h)
        self.assertNotIn("Verified official-link metadata admitted", h)
        self.assertEqual(self._digest(), before)
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_migrated_but_empty_does_not_claim_live_feed(self):
        conn = self.migrate()
        conn.close()
        self.assertEqual(load_admitted_links(self.db, "indonesia"), [])
        self.assertNotIn("data-regional-official-source-id",
                         html_for("indonesia", []))

    def test_admitted_afp_source_is_html_escaped_and_not_corpus_promotion(self):
        conn = self.migrate()
        insert(conn)
        conn.commit()
        conn.close()
        before = self._digest()
        rows = load_admitted_links(self.db, "philippines")
        self.assertEqual(len(rows), 1)
        page = html_for("philippines", rows)
        self.assertIn('data-regional-official-source-id="afp:1499"', page)
        self.assertIn("https://www.afp.mil.ph/news/fictional-exercise", page)
        self.assertIn('datetime="2026-10-15"', page)
        self.assertIn("AFP official source", page)
        self.assertIn("Verified official-link metadata admitted", page)
        self.assertIn("original-text corpus remains in shadow", page)
        self.assertNotIn("Kemhan Berita official source", page)
        self.assertNotIn("title_original", page)
        self.assertEqual(self._digest(), before)
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_only_correct_desk_can_render_admitted_link(self):
        conn = self.migrate()
        insert(conn)
        conn.commit()
        conn.close()
        self.assertEqual(load_admitted_links(self.db, "indonesia"), [])
        self.assertNotIn("data-regional-official-source-id",
                         html_for("indonesia", []))

    def test_kemhan_first_party_does_not_appear_as_republisher(self):
        conn = self.migrate()
        sid = "kemhan:/2026/10/15/fictional-ministry-article.html"
        insert(conn, family="id_kemhan_news", desk="indonesia",
               ident=sid,
               url="https://www.kemhan.go.id/2026/10/15/fictional-ministry-article.html",
               issuer=None, publisher="id_kemhan")
        conn.commit()
        conn.close()
        rows = load_admitted_links(self.db, "indonesia")
        page = html_for("indonesia", rows)
        self.assertIn(sid, page)
        self.assertIn("Kemhan Berita official source", page)
        self.assertIn("Indonesian Ministry of Defense", page)
        self.assertNotIn("AFP official source", page)

    def test_existing_but_corrupt_source_index_is_hard_failure(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE regional_official_source_links (source_family TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(RegionalRenderHold,
                                    "regional_source_index_unavailable_or_schema_drift"):
            load_admitted_links(self.db, "philippines")

    def test_hostile_database_url_is_rejected_before_html_render(self):
        conn = self.migrate()
        insert(conn, url="https://example.invalid/news/fictional-exercise")
        conn.commit()
        conn.close()
        with self.assertRaises(ValueError):
            load_admitted_links(self.db, "philippines")

    def test_shadow_or_unknown_desk_cannot_be_read(self):
        for slug in ("china", "singapore", "korea", "ph_afp_articles"):
            with self.subTest(slug=slug):
                with self.assertRaisesRegex(RegionalRenderHold,
                                            "not_a_supported_regional_live_desk"):
                    load_admitted_links(self.db, slug)

    def test_public_generator_references_only_db_reader(self):
        source = (ROOT / "site/preview/generate_preview.py").read_text(
            encoding="utf-8")
        self.assertIn("load_admitted_links(db_path, desk.slug)", source)
        self.assertIn("regional_official_links=regional_official_links", source)
        self.assertNotIn("stage_afp_kemhan_official_links", source)
        self.assertNotIn("reconcile_ph_afp_first23_originals", source)
        template = (ROOT / "site/preview/templates/desk.html").read_text(
            encoding="utf-8")
        self.assertIn("regional_official_links | default([])", template)
        self.assertIn("data-regional-official-source-id", template)


if __name__ == "__main__":
    unittest.main()
