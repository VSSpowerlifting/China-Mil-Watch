"""No-network, real Git/SQLite synthetic tests for private country research UI."""
from __future__ import annotations

import io
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.private_country_desk_reader import (
    ReaderHold, SCHEMA, SOURCES, build, main, parse_input, render_html,
)

SECRET = "PRIVATE PUBLISHER BODY CONTENT must not appear in output"
SQL_STD = """CREATE TABLE shadow_records (
source_identity TEXT, source_slug TEXT, url TEXT, title_original TEXT,
published_date TEXT, first_seen_run TEXT, text_original TEXT
)"""
SQL_VN = """CREATE TABLE shadow_records (
source_identity TEXT, source_slug TEXT, url TEXT,
published_date TEXT, first_seen_run TEXT, current_content_sha256 TEXT
)"""
SQL_VERSION = """CREATE TABLE shadow_versions (
source_identity TEXT, content_sha256 TEXT, title_original TEXT, text_original TEXT
)"""
SQL_KR = """CREATE TABLE shadow_records (
source_identity TEXT, source_slug TEXT, url TEXT, title_original TEXT,
published_date TEXT, first_seen_run TEXT, text_original TEXT,
language_tag TEXT, metadata_json TEXT, content_sha256 TEXT, capture_sha256 TEXT
)"""


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


def state_commit(folder, source, *, title, url, identity, content=SECRET,
                 date="2026-10-10", clock=None, kr_issuer="국방부",
                 kr_language="ko", kr_bad_sha=False, kr_state_desk="korea"):
    state = folder / "state"
    state.mkdir(exist_ok=True)
    with sqlite3.connect(state / "shadow.db") as cx:
        if SOURCES[source][3] == "korea":
            cx.execute(SQL_KR)
            cx.execute("CREATE TABLE shadow_meta (desk TEXT PRIMARY KEY)")
            cx.execute("INSERT INTO shadow_meta VALUES (?)", (kr_state_desk,))
            metadata = {
                "issuer": kr_issuer,
                "publisher": "대한민국 정책브리핑",
                "publication_kind": "syndicated_press_release",
                "body_scope": "published_hwpx_text",
                "attachments_collected": True,
                "document_url": "https://www.korea.kr/common/download.do?fileId=123456&tblKey=GMN",
                "document_capture_sha256": "b" * 64,
            }
            cx.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (identity, source, url, title, date, "38088742605-1", content,
                        kr_language, json.dumps(metadata, ensure_ascii=False),
                        ("a" * 64 if kr_bad_sha else hashlib.sha256(content.encode()).hexdigest()),
                        "c" * 64))
        elif SOURCES[source][3] == "vietnam":
            cx.execute(SQL_VN)
            cx.execute(SQL_VERSION)
            cx.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?)",
                       (identity, source, url, date, "38088742605-1", "a"*64))
            cx.execute("INSERT INTO shadow_versions VALUES (?,?,?,?)",
                       (identity, "a"*64, title, content))
        else:
            cx.execute(SQL_STD)
            cx.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?)",
                       (identity, source, url, title, date, "38088742605-1", content))
    (state / "clock.json").write_text(json.dumps(clock or {
        "day_zero_run_id": "37656171920-2",
        "day_zero_utc": "2026-10-07T17:16:33+00:00",
    }), encoding="utf-8")
    git(folder, "add", "state")
    git(folder, "commit", "-qm", "synthetic-source-" + source)
    result = git(folder, "rev-parse", "HEAD")
    (state / "shadow.db").unlink()
    return result


class PrivateCountryReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-reader-fixture-")
        self.folder = Path(self.tmp.name) / "isolated-shadow"
        self.folder.mkdir()
        git(self.folder, "init", "-q")
        git(self.folder, "config", "user.name", "Offline QA")
        git(self.folder, "config", "user.email", "offline@example.invalid")

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, slug="ph_afp_articles", **kwargs):
        host = SOURCES[slug][2]
        url = kwargs.pop("url", "https://" + host +
                         ("/news/test-press-release" if slug == "ph_afp_articles"
                          else "/briefing/pressReleaseView.do?newsId=156784000"
                          if slug == "kr_policy_mnd_releases"
                          else "/test-official-release"))
        identity = kwargs.pop("identity", "afp:11232" if slug == "ph_afp_articles"
                              else "korea-policy:156784000"
                              if slug == "kr_policy_mnd_releases"
                              else slug + ":12")
        title = kwargs.pop("title", "Official agency briefing")
        commit = state_commit(self.folder, slug, url=url, title=title,
                              identity=identity, **kwargs)
        return ",".join((slug, str(self.folder), commit))

    def test_two_desks_work_on_exact_separate_commits_and_do_not_export_body(self):
        afp = self.fixture("ph_afp_articles", content="Naval security " + SECRET)
        viet = self.fixture("vn_mps_foreign_affairs_vi",
                            content="Naval security " + SECRET)
        out = build([afp, viet], term="Naval", max_results=100)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["matched_total"], 2)
        self.assertEqual({r["country"] for r in out["results"]},
                         {"philippines", "vietnam"})
        self.assertEqual({r["source_slug"] for r in out["results"]},
                         {"ph_afp_articles", "vn_mps_foreign_affairs_vi"})
        for flag in ("source_body_text_exported", "automated_source_rights_approved",
                     "human_source_review_completed", "production_records_changed",
                     "country_desks_promoted", "public_release_authorized"):
            self.assertFalse(out[flag])
        self.assertNotIn(SECRET, json.dumps(out))
        rendered = render_html(out)
        self.assertNotIn(SECRET, rendered)
        self.assertIn('type="search"', rendered)
        self.assertIn("PUBLIC REVIEW PENDING", rendered)
        self.assertIn("https://www.afp.mil.ph", rendered)
        self.assertIn("https://bocongan.gov.vn", rendered)

    def test_korea_metadata_search_at_literal_commit_never_exposes_korean_body(self):
        k = self.fixture("kr_policy_mnd_releases", title="국방부 보도자료",
                         content="한글 원문 군사 협력 " + SECRET,
                         clock={"desk": "korea", "day_zero_run_id": "37656171920-2",
                                "day_zero_utc": "2026-10-07T17:16:33+00:00"})
        out = build([k], term="군사", country="korea")
        self.assertEqual(out["matched_total"], 1)
        self.assertEqual(out["results"][0]["identity"], "korea-policy:156784000")
        self.assertEqual(out["results"][0]["country"], "korea")
        self.assertIn("Ministry of National Defense", out["results"][0]["institution"])
        self.assertFalse(out["human_source_review_completed"])
        self.assertFalse(out["automated_source_rights_approved"])
        self.assertFalse(out["public_release_authorized"])
        self.assertNotIn(SECRET, json.dumps(out, ensure_ascii=False))
        self.assertNotIn("한글 원문", json.dumps(out, ensure_ascii=False))
        page = render_html(out)
        self.assertIn("South Korea", page)
        self.assertNotIn(SECRET, page)
        self.assertIn("PUBLIC REVIEW PENDING", page)

    def test_korea_fail_closed_for_issuer_identity_language_hash_and_desk(self):
        cases = [
            {"kr_issuer": "방위사업청"},
            {"identity": "korea-policy:156784001"},
            {"url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784000&tracking=1"},
            {"url": "https://dapa.go.kr/briefing/pressReleaseView.do?newsId=156784000"},
            {"kr_language": "en"},
            {"kr_bad_sha": True},
            {"kr_state_desk": "indonesia"},
            {"clock": {"desk": "indonesia", "day_zero_run_id": "37656171920-2",
                       "day_zero_utc": "2026-10-07T17:16:33+00:00"}},
        ]
        for modifications in cases:
            with self.subTest(modifications=modifications):
                k = self.fixture("kr_policy_mnd_releases", **modifications)
                with self.assertRaises(ReaderHold):
                    build([k], country="korea")

    def test_casefold_query_and_country_filter_and_cap(self):
        a = self.fixture("ph_afp_articles", title="Sanlakas exercise",
                         content="SPECIAL maritime security reconnaissance")
        v = self.fixture("vn_moit_energy_vi", title="Điện năng lượng",
                         content="ENERGY security context")
        matches = build([a, v], term="special", country="philippines")
        self.assertEqual(matches["matched_total"], 1)
        self.assertEqual(matches["results"][0]["title"], "Sanlakas exercise")
        matches = build([a, v], term="security")
        self.assertEqual(matches["matched_total"], 2)
        c = build([a, v], max_results=1)
        self.assertTrue(c["truncated"])
        self.assertEqual(len(c["results"]), 1)

    def test_escaped_html_titles_and_no_script_injection(self):
        a = self.fixture(title='Danger </script><img src=x onerror=alert(1)>')
        page = render_html(build([a]))
        self.assertNotIn('</script><img', page)
        self.assertIn("&lt;/script&gt;&lt;img", page)
        self.assertIn("<script>(function()", page)

    def test_wrong_source_slug_in_pinned_database_is_blocked(self):
        original = self.fixture("ph_afp_articles")
        parts = original.split(",", 2)
        as_wrong = ",".join(("ph_nsc_official_statements", *parts[1:]))
        with self.assertRaises(ReaderHold):
            build([as_wrong])

    def test_non_official_host_is_blocked(self):
        a = self.fixture(url="https://evil.example/press-release")
        with self.assertRaisesRegex(ReaderHold, "official"):
            build([a])

    def test_mutable_commit_and_duplicate_source_refused(self):
        a = self.fixture()
        slug, folder, sha = a.split(",")
        for bad in (
            slug + "," + folder + ",main",
            slug + "," + folder + "," + ("a"*40),
            "unregistered," + folder + "," + sha,
            slug + ",relative/path," + sha,
        ):
            with self.subTest(bad=bad), self.assertRaises(ReaderHold):
                build([bad])
        with self.assertRaises(ReaderHold):
            build([a, a])
        with self.assertRaises(ReaderHold):
            build([a], max_results=0)
        with self.assertRaises(ReaderHold):
            build([a], term="q" * 141)

    def test_incomplete_current_vietnam_version_join_rejected(self):
        v = self.fixture("vn_mps_foreign_affairs_vi")
        # The actual complete commit is valid; a wrong schema/source is refused.
        self.assertEqual(build([v])["matched_total"], 1)
        with self.assertRaises(ReaderHold):
            build([",".join(("vn_moit_energy_vi", *v.split(",")[1:]))])

    def test_html_export_is_private_external_and_non_overwriting(self):
        a = self.fixture()
        dest = Path(self.tmp.name) / "private-desk.html"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--source", a, "--format", "html",
                                   "--output", str(dest)]), 0)
        self.assertIn("<!doctype html>", dest.read_text())
        self.assertNotIn(SECRET, dest.read_text())
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            main(["--source", a, "--format", "html", "--output", str(dest)])

    def test_json_stdout_does_not_copy_article(self):
        a = self.fixture()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--source", a, "--query", "publisher",
                                   "--format", "json"]), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["matched_total"], 1)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertEqual(data["status"], "private_research_not_source_admitted")


if __name__ == "__main__":
    unittest.main()
