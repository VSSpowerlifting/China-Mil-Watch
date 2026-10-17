"""Exact branch and HTTPS readback contracts using fictional source text only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_korea_original_deployed_readback import (
    ReadbackHold, validate_branch_parity, verify_readback,
)
from core.korea_published_originals import read_release_index, render_original_page

ID = "156784297"
RAW = ("국방부의 가상 시험 공표 문장입니다. " * 16).encode("utf-8")


class Response:
    def __init__(self, data, url, *, status=200):
        self.content = data
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.history = []


class Session:
    def __init__(self, pages):
        self.pages = pages
    def get(self, url, **kwargs):
        assert kwargs.get("allow_redirects") is False
        return Response(self.pages[url], url)


class KoreaOriginalReadbackTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.main = self.root / "main"
        self.pages = self.root / "gh-pages"
        (self.main / "research/korea_published_original_texts").mkdir(parents=True)
        (self.main / "output/korea-originals").mkdir(parents=True)
        (self.pages / "korea-originals").mkdir(parents=True)
        self.row = {
            "source_identity": "korea-policy:" + ID,
            "official_url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + ID,
            "publisher_posted_date": "2026-10-06",
            "source_git_commit": "a" * 40,
            "original_text_sha256": hashlib.sha256(RAW).hexdigest(),
            "policy_sha256": "b" * 64,
            "source_html_sha256": "c" * 64,
            "release_decision_sha256": "d" * 64,
            "released_at_utc": "2026-10-16T01:43:03Z",
        }
        (self.main / "research/korea_published_original_texts" /
         (ID + ".txt")).write_bytes(RAW)
        self._index([self.row])
        rows = read_release_index(self.main / "research/korea_published_original_texts.json",
                                  self.main / "research/korea_published_original_texts")
        page = render_original_page(rows[0]).encode("utf-8")
        for parent in [self.main / "output", self.pages]:
            (parent / "korea-originals" / (ID + ".html")).write_bytes(page)
        desk = (
            '<li data-korea-original-text="korea-policy:' + ID + '">'
            '<a href="korea-originals/' + ID + '.html">Open</a>'
            '<a href="' + self.row["official_url"] + '">Official</a></li>'
        ).encode("utf-8")
        (self.main / "output/korea.html").write_bytes(desk)
        (self.pages / "korea.html").write_bytes(desk)
        (self.pages / "CNAME").write_text("indopacificrecord.org\n")
        self.http_pages = {
            "https://indopacificrecord.org/korea.html": desk,
            "https://indopacificrecord.org/korea-originals/" + ID + ".html": page,
        }

    def _index(self, records):
        (self.main / "research/korea_published_original_texts.json").write_text(
            json.dumps({"schema": "ipr-korea-public-original-text-index/1",
                        "records": records}), encoding="utf-8")

    def _verify(self, **kwargs):
        return verify_readback(self.main, self.pages, **kwargs)

    def test_workflow_installs_template_renderer_for_pr_and_scheduled_jobs(self):
        # The exact original-page readback invokes render_original_page(),
        # which imports jinja2 lazily. The runner must install it in BOTH
        # offline contracts and public verification paths, not just site CI.
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/korea_original_deployed_readback.yml"
                    ).read_text(encoding="utf-8")
        self.assertEqual(
            workflow.count("python -m pip install requests 'jinja2>=3.1.4,<4'"),
            2,
            "PR and scheduled source-rendering jobs must both install Jinja2",
        )

    def test_exact_branch_parity_verified_not_misreported_as_https(self):
        out = self._verify()
        self.assertEqual(out["registered_originals"], 1)
        self.assertEqual(out["korea_html_paths_verified"], 2)
        self.assertEqual(out["status"], "GIT_BRANCH_READBACK_VERIFIED")
        self.assertFalse(out["public_https_verified"])

    def test_actual_http_byte_readback_requires_both_desk_and_original(self):
        out = self._verify(require_https=True,
                           session=Session(self.http_pages), attempts=1)
        self.assertTrue(out["public_https_verified"])
        self.assertEqual(out["status"], "PUBLIC_HTTPS_EXACT_BYTES_VERIFIED")

    def test_http_200_different_bytes_is_not_deployed(self):
        wrong = dict(self.http_pages)
        wrong["https://indopacificrecord.org/korea-originals/"+ID+".html"] = b"stale body"
        with self.assertRaisesRegex(ReadbackHold, "public_https_content_sha_mismatch"):
            self._verify(require_https=True, session=Session(wrong), attempts=1)

    def test_pages_html_modified_after_main_publishing_is_held(self):
        (self.pages / "korea-originals" / (ID + ".html")).write_bytes(b"tampered")
        with self.assertRaisesRegex(ReadbackHold, "main_pages_bytes_differ"):
            validate_branch_parity(self.main, self.pages)

    def test_pages_desk_link_lost_is_held(self):
        (self.pages / "korea.html").write_text("No sources", encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "korea_desk_main_pages_bytes_differ"):
            validate_branch_parity(self.main, self.pages)

    def test_source_txt_changed_even_with_old_pages_is_held(self):
        (self.main / "research/korea_published_original_texts" /
         (ID + ".txt")).write_bytes(RAW + b"x")
        with self.assertRaises(ValueError):
            validate_branch_parity(self.main, self.pages)

    def test_ghost_pages_extra_source_refused(self):
        (self.pages / "korea-originals" / "999999999.html").write_bytes(b"ghost")
        with self.assertRaisesRegex(ReadbackHold, "pages_published_original_route_inventory_drift"):
            validate_branch_parity(self.main, self.pages)

    def test_custom_domain_must_be_stable(self):
        (self.pages / "CNAME").write_text("invalid.example")
        with self.assertRaisesRegex(ReadbackHold, "korea_pages_canonical_domain_changed"):
            validate_branch_parity(self.main, self.pages)

    def test_empty_index_is_not_successful_publication(self):
        self._index([])
        with self.assertRaisesRegex(ReadbackHold, "original_release_registry_still_empty"):
            validate_branch_parity(self.main, self.pages)

    def test_never_writes_database_or_pages(self):
        before = (self.pages / "korea.html").read_bytes()
        result = self._verify()
        self.assertFalse(result["db_changed"])
        self.assertFalse(result["pages_written"])
        self.assertEqual((self.pages / "korea.html").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
