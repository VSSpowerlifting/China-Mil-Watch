"""Read-only desk link rail: synthetic SQLite, no publisher data or output."""
import sqlite3
import unittest

from core.regional_official_link_release import SCHEMA_SQL
from core.regional_official_link_render import (
    RegionalRenderHold, read_live_links, render_live_links,
)


def db():
    cx = sqlite3.connect(":memory:")
    cx.execute(SCHEMA_SQL)
    return cx


def insert(cx, *, family="ph_afp_articles", desk="philippines",
           ident="afp:1499", url="https://www.afp.mil.ph/news/fictional-exercise",
           day="2026-10-15", issuer="ph_afp", publisher="ph_afp",
           republisher=None, scope="official_link_only", version="a"*64,
           proof="b"*64):
    cx.execute(
        "INSERT INTO regional_official_source_links "
        "(source_family,source_identity,desk,canonical_official_url,"
        "publisher_posted_date,official_issuer,official_publisher,"
        "official_republisher,source_git_commit,metadata_version_sha256,"
        "first_seen_run,release_scope,release_proof_sha256,released_at_utc) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (family,ident,desk,url,day,issuer,publisher,republisher,
         "c"*40,version,"123456-1",scope,proof,"2026-10-15T20:00:00Z"),
    )


class RegionalRenderTests(unittest.TestCase):
    def test_absent_migration_holds_not_fakes_empty_feed(self):
        with self.assertRaisesRegex(RegionalRenderHold,
                                    "regional_source_index_unavailable"):
            render_live_links(sqlite3.connect(":memory:"), "philippines")

    def test_empty_migrated_table_has_no_public_link_claim(self):
        self.assertEqual(render_live_links(db(), "philippines"), "")

    def test_afp_render_from_db_only_uses_neutral_attribution(self):
        cx = db()
        insert(cx)
        h = render_live_links(cx, "philippines")
        self.assertIn("https://www.afp.mil.ph/news/fictional-exercise", h)
        self.assertIn("AFP official source", h)
        self.assertIn('datetime="2026-10-15"', h)
        self.assertIn('rel="noopener noreferrer"', h)
        self.assertIn('data-source-scope="official-link-only"', h)
        self.assertNotIn("<script", h)
        self.assertNotIn("original_text", h)
        self.assertEqual(len(read_live_links(cx, "philippines")),1)

    def test_kemhan_first_party_publisher_label(self):
        cx=db()
        ident="kemhan:/2026/10/15/fictional-notice.html"
        insert(cx,family="id_kemhan_news",desk="indonesia",
               ident=ident,
               url="https://www.kemhan.go.id/2026/10/15/fictional-notice.html",
               issuer=None,publisher="id_kemhan")
        h=render_live_links(cx,"indonesia")
        self.assertIn("Kemhan Berita official source",h)
        self.assertIn(ident,h)
        self.assertNotIn("AFP official source",h)

    def test_no_cross_desk_leak(self):
        cx=db()
        insert(cx)
        self.assertEqual(render_live_links(cx,"indonesia"),"")

    def test_foreign_url_and_html_injection_is_held(self):
        cx=db()
        insert(cx,url="https://evil.example/notice\" onmouseover=\"alert(1)")
        with self.assertRaisesRegex(ValueError,"noncanonical_or_foreign"):
            render_live_links(cx,"philippines")

    def test_tampered_date_fails_hermetically(self):
        cx=db()
        insert(cx,day="2026-10-42")
        with self.assertRaisesRegex(RegionalRenderHold,"invalid_publisher_date"):
            render_live_links(cx,"philippines")

    def test_attribution_drift_is_hold_not_rebranding(self):
        cx=db()
        insert(cx,publisher="imposter")
        with self.assertRaisesRegex(RegionalRenderHold,
                                    "published_reference_missing_authenticity"):
            render_live_links(cx,"philippines")

    def test_invalid_publisher_proof_sha_rejected(self):
        cx=db()
        insert(cx,proof="not-a-sha")
        with self.assertRaisesRegex(RegionalRenderHold,
                                    "published_reference_missing_authenticity"):
            render_live_links(cx,"philippines")

    def test_invalid_desk_refuses_even_when_table_has_records(self):
        cx=db()
        insert(cx)
        with self.assertRaisesRegex(RegionalRenderHold,
                                    "not_a_supported_regional_live_desk"):
            render_live_links(cx,"japan")

    def test_render_does_not_modify_underlying_sqlite(self):
        cx=db()
        insert(cx)
        before=cx.execute("SELECT quote(canonical_official_url) FROM regional_official_source_links").fetchall()
        for _ in range(3):
            render_live_links(cx,"philippines")
        after=cx.execute("SELECT quote(canonical_official_url) FROM regional_official_source_links").fetchall()
        self.assertEqual(before,after)


if __name__ == "__main__":
    unittest.main()
