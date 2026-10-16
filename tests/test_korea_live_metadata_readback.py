"""Source-free, isolated fixtures for Korea production readback."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.verify_korea_live_metadata_readback import ReadbackHold, verify, PREFIX

FIVE = ["korea-policy:" + str(155000000 + i) for i in range(5)]
NINE = ["korea-policy:" + str(155000100 + i) for i in range(9)]
LIVE = "korea-policy:155001000"


def html(with_live=True):
    rows = ['<li data-korea-public-link="%s"></li>' % i for i in FIVE]
    rows += ['<li data-korea-additional-link="%s"></li>' % i for i in NINE]
    if with_live:
        rows.append(
            '<li data-korea-auto-official-link="%s">'
            '<h4><a href="%s">MND official press release 155001000</a></h4>'
            '<p>Issuer: Republic of Korea Ministry of National Defense (국방부) · '
            'Republication: Republic of Korea Policy Briefing (대한민국 정책브리핑) · '
            'Portal posted: <time datetime="2026-10-15">2026-10-15</time> '
            '· Official government outbound link only</p></li>'
            % (LIVE, PREFIX + "155001000"))
    return "<html><body><ol>" + "".join(rows) + "</ol></body></html>"


class TestKoreaLivePublicationReadback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db = root / "pla_watch.db"
        self.main = root / "main.html"
        self.pages = root / "pages.html"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE korea_official_source_records ("
                       "source_identity TEXT, canonical_official_url TEXT,"
                       "publisher_posted_date TEXT, official_issuer TEXT,"
                       "official_republisher TEXT, public_scope TEXT,"
                       "candidate_version_sha256 TEXT,original_title_sha256 TEXT)")
            db.execute("INSERT INTO korea_official_source_records VALUES "
                       "(?,?,?,?,?,?,?,?)",
                       (LIVE, PREFIX + "155001000", "2026-10-15",
                        "kr_mnd", "kr_policy_briefing", "official_link_only",
                        "a" * 64, "b" * 64))
        self.main.write_text(html(), encoding="utf-8")
        self.pages.write_text(html(), encoding="utf-8")

    def test_matching_committed_db_and_pages(self):
        result = verify(self.db, self.main, self.pages)
        self.assertEqual(result["published_additional_live_links"], 1)
        self.assertFalse(result["new_source_arrival_proven"])
        self.assertFalse(Path(str(self.db) + "-wal").exists())

    def test_pages_mismatch_is_hold(self):
        self.pages.write_text(html(False), encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "mismatch"):
            verify(self.db, self.main, self.pages)

    def test_missing_newly_admitted_reference_is_hold(self):
        self.main.write_text(html(False), encoding="utf-8")
        self.pages.write_text(html(False), encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "do_not_match"):
            verify(self.db, self.main, self.pages)

    def test_wrong_url_or_date_is_hold(self):
        for replacement in ("https://evil.example/155001000", "2026-10-16"):
            with self.subTest(replacement=replacement):
                tampered = (html().replace(PREFIX + "155001000", replacement)
                            if "evil" in replacement else
                            html().replace('datetime="2026-10-15"',
                                           'datetime="2026-10-16"'))
                self.main.write_text(tampered, encoding="utf-8")
                self.pages.write_text(tampered, encoding="utf-8")
                with self.assertRaisesRegex(ReadbackHold, "mismatch"):
                    verify(self.db, self.main, self.pages)

    def test_media_injected_in_auto_row_is_hold(self):
        tampered = html().replace("</a></h4>", "</a><img src='outside'></h4>")
        self.main.write_text(tampered, encoding="utf-8")
        self.pages.write_text(tampered, encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "unauthorized_media"):
            verify(self.db, self.main, self.pages)

    def test_extra_original_title_text_is_hold(self):
        tampered = html().replace(
            'Official government outbound link only',
            'Original Korean headline not authorized · Official government outbound link only')
        self.main.write_text(tampered, encoding="utf-8")
        self.pages.write_text(tampered, encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "unexpected_text"):
            verify(self.db, self.main, self.pages)

    def test_held_chronology_source_cannot_publish(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO korea_official_source_records VALUES (?,?,?,?,?,?,?,?)",
                       ("korea-policy:156785161", PREFIX + "156785161", "2026-10-15",
                        "kr_mnd", "kr_policy_briefing", "official_link_only",
                        "a" * 64, "b" * 64))
        with self.assertRaisesRegex(ReadbackHold, "chronology_exception"):
            verify(self.db, self.main, self.pages)

    def test_missing_table_is_hold(self):
        with sqlite3.connect(self.db) as db:
            db.execute("DROP TABLE korea_official_source_records")
        with self.assertRaisesRegex(ReadbackHold, "not_in_production"):
            verify(self.db, self.main, self.pages)


if __name__ == "__main__":
    unittest.main()
