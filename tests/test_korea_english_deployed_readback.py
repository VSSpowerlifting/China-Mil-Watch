"""Synthetic, no-secret verification of first Korea reviewed-English HTTPS release."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.korea_english_publication import render_analysis, render_translation
from scripts.verify_korea_english_deployed_readback import (
    EnglishReadbackHold, validate_branch_parity, verify_readback,
)
from tests.test_korea_english_publication import make_review, TEXT, SHA, ID


class Response:
    def __init__(self, data, url, *, status=200, kind="text/html"):
        self.content = data
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": kind + "; charset=utf-8"}
        self.history = []


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        assert kwargs.get("allow_redirects") is False
        self.calls.append(url)
        return self.responses[url]


class KoreaApprovedEnglishReadbackTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.main = self.root / "main"
        self.pages = self.root / "gh-pages"
        (self.main / "research/korea_published_original_texts").mkdir(parents=True)
        (self.main / "research/korea_english_reviewed").mkdir(parents=True)
        for root in (self.main / "output", self.pages):
            for folder in ("korea-translations", "korea-analysis"):
                (root / folder).mkdir(parents=True)

        self.review = make_review()
        self.number = ID.split(":")[1]
        (self.main / "research/korea_published_original_texts" /
         (self.number + ".txt")).write_text(TEXT, encoding="utf-8")
        self.original = {
            "source_identity": ID,
            "official_url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + self.number,
            "publisher_posted_date": "2026-10-06",
            "source_git_commit": "a"*40,
            "original_text_sha256": SHA,
            "policy_sha256": "b"*64,
            "source_html_sha256": "c"*64,
            "release_decision_sha256": "d"*64,
            "released_at_utc": "2026-10-16T01:43:03Z",
            "release_decision_sha256": "d"*64,
        }
        (self.main / "research/korea_published_original_texts.json").write_text(
            json.dumps({"schema": "ipr-korea-public-original-text-index/1",
                        "records": [self.original]}), encoding="utf-8")
        self.review_hash = hashlib.sha256(json.dumps(
            self.review, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        (self.main / "research/korea_english_reviewed" /
         (self.number + ".json")).write_text(
             json.dumps(self.review, ensure_ascii=False), encoding="utf-8")
        (self.main / "research/korea_english_publications.json").write_text(
            json.dumps({
                "schema": "ipr-korea-editorial-english-publications/1",
                "releases": [{
                    "source_identity": ID, "source_sha256": SHA,
                    "review_sha256": self.review_hash,
                    "owner_run_id": "38939356835",
                    "released_at_utc": "2026-10-16T18:00:00Z",
                }]
            }), encoding="utf-8")

        desk = (
            '<li data-korea-english-reviewed="' + ID + '">'
            '<a href="korea-translations/' + self.number + '.html">Translation</a>'
            '<a href="korea-analysis/' + self.number + '.html">Analysis</a>'
            '<a href="korea-originals/' + self.number + '.html">Original</a></li>'
        ).encode("utf-8")
        self.https = {
            "https://indopacificrecord.org/korea.html":
            Response(desk, "https://indopacificrecord.org/korea.html"),
        }
        for root in (self.main / "output", self.pages):
            (root / "korea.html").write_bytes(desk)
        (self.pages / "CNAME").write_text("indopacificrecord.org\n")
        self.routes = {}
        for folder, renderer in (
            ("korea-translations", render_translation),
            ("korea-analysis", render_analysis),
        ):
            path = folder + "/" + self.number + ".html"
            html = renderer({}, self.review, {
                **self.original, "text_original": TEXT,
            }).encode("utf-8")
            self.routes[path] = html
            for root in (self.main / "output", self.pages):
                (root / path).write_bytes(html)
            url = "https://indopacificrecord.org/" + path
            self.https[url] = Response(html, url)

    def _verify(self, **kwargs):
        return verify_readback(self.main, self.pages, **kwargs)

    def test_verified_branches_are_not_equivalent_to_https(self):
        result = self._verify()
        self.assertEqual(result["approved_source_pairs"], 1)
        self.assertEqual(result["html_paths_verified"], 3)
        self.assertEqual(result["status"], "GIT_BRANCH_READBACK_VERIFIED")
        self.assertFalse(result["public_https_verified"])
        self.assertFalse(result["pages_written"])

    def test_live_200_requires_exact_desk_and_both_reviewed_pages(self):
        sess = Session(self.https)
        result = self._verify(require_https=True, session=sess, attempts=1)
        self.assertEqual(result["status"], "PUBLIC_HTTPS_EXACT_BYTES_VERIFIED")
        self.assertTrue(result["public_https_verified"])
        self.assertEqual(len(sess.calls), 3)

    def test_successful_status_with_stale_live_analysis_is_hold(self):
        responses = dict(self.https)
        url = "https://indopacificrecord.org/korea-analysis/" + self.number + ".html"
        responses[url] = Response(b"stale, not approved", url)
        with self.assertRaisesRegex(EnglishReadbackHold, "content_sha_mismatch"):
            self._verify(require_https=True, session=Session(responses), attempts=1)

    def test_live_redirect_is_held_even_if_final_content_matches(self):
        responses = dict(self.https)
        url = "https://indopacificrecord.org/korea-translations/" + self.number + ".html"
        responses[url] = Response(self.routes[
            "korea-translations/" + self.number + ".html"], url, status=301)
        with self.assertRaisesRegex(EnglishReadbackHold, "status_or_origin_mismatch"):
            self._verify(require_https=True, session=Session(responses), attempts=1)

    def test_wrong_content_type_is_not_live_html(self):
        responses = dict(self.https)
        url = "https://indopacificrecord.org/korea-translations/" + self.number + ".html"
        responses[url] = Response(self.routes[
            "korea-translations/" + self.number + ".html"], url, kind="text/plain")
        with self.assertRaisesRegex(EnglishReadbackHold, "content_type_mismatch"):
            self._verify(require_https=True, session=Session(responses), attempts=1)

    def test_ghost_analysis_path_rejected(self):
        (self.pages / "korea-analysis/999999999.html").write_bytes(b"ghost")
        with self.assertRaisesRegex(EnglishReadbackHold, "pages_route_inventory_drift"):
            validate_branch_parity(self.main, self.pages)

    def test_changed_pages_html_rejected_even_if_official_source_matches(self):
        (self.pages / ("korea-translations/" + self.number + ".html")).write_bytes(
            b"tampered")
        with self.assertRaisesRegex(EnglishReadbackHold, "main_pages_bytes_differ"):
            validate_branch_parity(self.main, self.pages)

    def test_reviewed_packet_changed_after_approval_hash_is_hold(self):
        path = self.main / "research/korea_english_reviewed" / (self.number + ".json")
        packet = json.loads(path.read_text(encoding="utf-8"))
        packet["translations"][0]["text_en"] = "Changed after review"
        path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_branch_parity(self.main, self.pages)

    def test_registry_empty_is_not_publication_success(self):
        path = self.main / "research/korea_english_publications.json"
        path.write_text(json.dumps({
            "schema": "ipr-korea-editorial-english-publications/1",
            "releases": []
        }), encoding="utf-8")
        with self.assertRaisesRegex(EnglishReadbackHold, "no_reviewed_releases_yet"):
            validate_branch_parity(self.main, self.pages)

    def test_reviewed_desk_mismatch_is_hold(self):
        (self.pages / "korea.html").write_text("unreviewed", encoding="utf-8")
        with self.assertRaisesRegex(EnglishReadbackHold, "desk_main_pages_bytes_differ"):
            validate_branch_parity(self.main, self.pages)

    def test_never_writes_publication_state(self):
        original = (self.pages / "korea.html").read_bytes()
        result = self._verify()
        self.assertFalse(result["db_changed"])
        self.assertFalse(result["pages_written"])
        self.assertEqual(original, (self.pages / "korea.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
