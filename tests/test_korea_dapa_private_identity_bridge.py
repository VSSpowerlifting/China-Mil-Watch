"""No-network DAPA first-party candidate matching against synthetic HTML only."""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from core.korea_dapa_private_identity_bridge import (
    DAPAHold, canonical_article_identity, reconcile,
)

DETAIL = ("https://www.dapa.go.kr/dapa/doc/selectDoc.do?"
          "bbsSeq=326&docSeq=59293&menuSeq=3069")
LIST_DATE = "2026-10-15"
ARTICLE_DATE = "2026-10-15"


def listing(*, row_date=LIST_DATE, call="goDoc('59293')", second="", rows=""):
    return ("""<!doctype html><html lang="ko"><body>
    <table><tr><th>Number</th><th>Title</th><th>Posted</th></tr>
    <tr><td>701</td><td><a href="#" onclick="%s">PRIVATE GOVERNMENT RELEASE TITLE</a>%s</td>
    <td>%s</td></tr>%s
    </table></body></html>""" % (call, second, row_date, rows)).encode("utf-8")


def article(*, posted=ARTICLE_DATE, label="게시일", extra=""):
    return ("""<!doctype html><html lang="ko"><body><div>
    <h1>PRIVATE GOVERNMENT ARTICLE BODY</h1>
    <span>%s</span><time>%s</time>
    <p>Another unrelated policy date in the body is 2026-01-11.</p>
    %s</div></body></html>""" % (label, posted, extra)).encode("utf-8")


class DapaPrivateRowToArticleContracts(unittest.TestCase):
    def test_matching_candidate_requires_review_and_stays_private(self):
        l, a = listing(), article()
        result = reconcile(l, a, DETAIL)
        self.assertEqual(result["status"], "PRIVATE_SELF_CONSISTENT_UNVERIFIED")
        self.assertEqual(result["provisional_docseq"], "59293")
        self.assertEqual(result["provisional_posted_date"], "2026-10-15")
        self.assertEqual(result["listing_dated_rows_seen"], 1)
        self.assertEqual(result["listing_sha256"], hashlib.sha256(l).hexdigest())
        self.assertEqual(result["article_sha256"], hashlib.sha256(a).hexdigest())
        for key in (
            "publisher_capture_attested", "real_js_handler_semantics_verified",
            "item_local_issuer_verified", "rights_cleared_for_republication",
            "original_document_bytes_verified", "attachment_reuse_cleared",
            "editorial_review_approved", "production_admission_authorized",
            "public_release_authorized",
        ):
            self.assertIs(result[key], False)
        for private in ("PRIVATE GOVERNMENT RELEASE TITLE", "PRIVATE GOVERNMENT ARTICLE BODY",
                        "goDoc", "2026-01-11"):
            self.assertNotIn(private, str(result))

    def test_ordinary_navigational_params_do_not_change_docseq_identity(self):
        sample = DETAIL + "&currentPageNo=1&recordCountPerPage=10"
        row = reconcile(listing(), article(), sample)
        self.assertEqual(row["provisional_article_url"], DETAIL)
        self.assertEqual(row["provisional_docseq"], "59293")

    def test_wrong_board_wrong_host_fragment_duplicate_or_unknown_query_held(self):
        for url in (
            DETAIL.replace("www.dapa.go.kr", "www.dapa.go.kr.evil.example"),
            DETAIL.replace("https://", "http://"),
            DETAIL.replace("bbsSeq=326", "bbsSeq=999"),
            DETAIL.replace("docSeq=59293", "docSeq=0"),
            DETAIL.replace("menuSeq=3069", "menuSeq=999"),
            DETAIL + "#x",
            DETAIL + "&docSeq=59294",
            DETAIL + "&unrecognized=foo",
            DETAIL + "&recordCountPerPage=all",
            DETAIL + "&currentPageNo=-1",
            DETAIL.replace("/selectDoc.do", "/selectDocList.do"),
            DETAIL.replace("www.dapa.go.kr", "dapa.go.kr"),
        ):
            with self.subTest(url=url), self.assertRaises(DAPAHold):
                canonical_article_identity(url)

    def test_row_number_is_never_article_identity(self):
        with self.assertRaisesRegex(
                DAPAHold, "row_identity_absent_or_ambiguous"):
            reconcile(listing(call="goDoc(701)"), article(), DETAIL)

    def test_mismatching_click_argument_is_held_without_guessing(self):
        for action in (
            "goDoc(59294)", "goDoc('59293', 326)", "goDoc(59293, '326')",
            "eval('goDoc(59293)')", "window.open('59293')",
            "submitDoc(this)", "javascript:openDoc(59293);doOther()",
            "goDoc(59293)//comment", "goDoc('59293');window.alert(1)",
        ):
            with self.subTest(action=action), self.assertRaisesRegex(
                    DAPAHold, "row_identity_absent_or_ambiguous"):
                reconcile(listing(call=action), article(), DETAIL)

    def test_multiple_qualifying_rows_or_actions_are_ambiguous(self):
        other = """<tr><td>700</td><td><a href="javascript:goDoc('59293')">
        ANOTHER PRIVATE HEADLINE</a></td><td>2026-10-15</td></tr>"""
        with self.assertRaisesRegex(DAPAHold, "row_identity_absent_or_ambiguous"):
            reconcile(listing(rows=other), article(), DETAIL)
        two_actions = """<a href="#" onclick="goDoc('59293')"
        >PRIVATE</a><a href="javascript:goDoc('59293')">PRIVATE AGAIN</a>"""
        with self.assertRaisesRegex(DAPAHold, "row_identity_absent_or_ambiguous"):
            reconcile(listing(call="goDoc('59293')", second=two_actions),
                      article(), DETAIL)

    def test_listing_date_and_article_posting_field_must_match(self):
        for row, doc in (("2026-10-08", "2026-10-15"),
                         ("2026-10-15", "2026-10-08"),
                         ("2026-13-15", "2026-10-15")):
            with self.subTest(row=row, doc=doc), self.assertRaises(DAPAHold):
                reconcile(listing(row_date=row), article(posted=doc), DETAIL)

    def test_no_unlabeled_or_script_only_page_dates(self):
        for raw in (
            article(label="Event date"),
            b"<html><body><script>var d='2026-10-15';</script></body></html>",
            article(extra="<span>게시일</span><span>2026-10-15</span>"),
        ):
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(
                    DAPAHold, "date_mismatch"):
                reconcile(listing(), raw, DETAIL)

    def test_too_big_invalid_unicode_and_challenge_fail_closed(self):
        bad = (
            b"", b"no html at all", b"<html>access denied</html>",
            b"<html>captcha required</html>",
            b"<html>\xff</html>", b"<html>" + b"x" * 800000,
        )
        for payload in bad:
            with self.subTest(size=len(payload)), self.assertRaises(DAPAHold):
                reconcile(listing(), payload, DETAIL)
                # only an offline bytes contract, not an article retrieval
        with self.assertRaises(DAPAHold):
            reconcile(b"<html>" + b"a" * 350001, article(), DETAIL)

    def test_pure_parser_has_no_network_cli_or_production_io(self):
        code = (Path(__file__).resolve().parents[1] /
                "core/korea_dapa_private_identity_bridge.py"
                ).read_text(encoding="utf-8")
        for blocked in (
            "urllib.request", "requests.get", "httpx", "socket",
            "sqlite3", "subprocess", "open(", "Path(", "gh-pages",
            "pla_watch.db", "editorial_status='approved'",
            "workflow_dispatch",
        ):
            with self.subTest(blocked=blocked):
                self.assertNotIn(blocked, code)


if __name__ == "__main__":
    unittest.main()
