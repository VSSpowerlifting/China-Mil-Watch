"""Offline-only DAPA first-party listing access gates; every publisher page is fake."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.probe_korea_dapa_native_access import (
    AccessHold, LISTING, MAX_LISTING, MAX_ROBOTS, ROBOTS,
    fetch_once, inspect_listing, main, provisional_doc_sequence, probe,
)

ALLOW = b"User-agent: *\nAllow: /\n"
DENY = b"User-agent: *\nDisallow: /dapa/doc/\n"
HTML = b"""<!doctype html><html><body>
<a href="/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58803&menuSeq=3069">A</a>
<a href="/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58803&menuSeq=3069">duplicate</a>
<a href="https://www.dapa.go.kr/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58804">B</a>
<a href="https://evil.example/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58805">no</a>
<a href="/dapa/doc/selectDoc.do?bbsSeq=243&docSeq=58806">wrong board</a>
<a href="/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58807&docSeq=58808">duplicate query</a>
<a href="javascript:docView('58809')">unknown script</a>
</body></html>"""


class NativeDapaCanaryContracts(unittest.TestCase):
    def test_requires_new_manual_permission_and_never_fetches_implicitly(self):
        with patch("scripts.probe_korea_dapa_native_access.fetch_once") as network:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([])
            network.assert_not_called()

    def test_at_most_two_allowlisted_gets_and_no_release_effects(self):
        seen, pauses = [], []
        def mock_get(url, cap):
            seen.append((url, cap))
            return ALLOW if url == ROBOTS else HTML
        result = probe(fetch=mock_get, sleep=pauses.append)
        self.assertEqual(seen, [(ROBOTS, MAX_ROBOTS), (LISTING, MAX_LISTING)])
        self.assertEqual(pauses, [2.0])
        self.assertTrue(result["robots_checked"])
        self.assertTrue(result["listing_checked"])
        self.assertEqual(result["state"], "listing_shape_observed_unverified")
        self.assertEqual(result["provisional_docseq_count"], 2)
        self.assertEqual(result["sample_unverified_docseq"], ["58803", "58804"])
        for field in ("dapa_issuer_per_article_verified", "rights_cleared",
                      "original_text_saved", "collector_enabled", "production_published"):
            self.assertFalse(result[field])
        self.assertEqual(result["article_requests"], 0)
        self.assertEqual(result["attachment_requests"], 0)
        self.assertNotIn("duplicate", str(result))
        self.assertNotIn("evil.example", str(result))

    def test_robots_denial_timeout_html_and_disallow_all_stop_before_listing(self):
        for body, reason in (
            (DENY, "publisher_robots_disallow_listing"),
            (b"<html>blocked</html>", "publisher_robots_unreadable_or_challenged"),
            (b"this is not a robots file", "publisher_robots_unreadable_or_challenged"),
            (b"\xff", "publisher_robots_not_utf8"),
        ):
            seen = []
            def mock_get(url, cap):
                seen.append(url)
                return body
            result = probe(fetch=mock_get, sleep=lambda s: self.fail("unexpected sleep"))
            with self.subTest(reason=reason):
                self.assertEqual(result["state"], "blocked")
                self.assertEqual(result["reason_code"], reason)
                self.assertEqual(seen, [ROBOTS])
                self.assertEqual(result["requests_attempted"], 1)

        seen = []
        def timeout(url, cap):
            seen.append(url)
            raise AccessHold("publisher_network_unavailable")
        result = probe(fetch=timeout, sleep=lambda s: self.fail("unexpected sleep"))
        self.assertEqual(result["reason_code"], "publisher_network_unavailable")
        self.assertEqual(seen, [ROBOTS])

    def test_off_domain_wrong_board_duplicate_id_and_non_href_filtered(self):
        for href in (
            "https://evil.example/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=123",
            "//evil.example/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=123",
            "/dapa/doc/selectDoc.do?bbsSeq=243&docSeq=123",
            "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=123&docSeq=124",
            "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=123&menuSeq=2",
            "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=0",
            "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=123#fragment",
            "javascript:doc(123)",
        ):
            with self.subTest(href=href):
                self.assertIsNone(provisional_doc_sequence(href))
        self.assertEqual(provisional_doc_sequence(
            "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=58803"), "58803")

    def test_wrong_url_content_type_redirect_empty_and_oversized_block(self):
        class Response:
            def __init__(self, *, target=ROBOTS, kind="text/plain", data=ALLOW, code=200):
                self.status=code
                self.headers={"Content-Type":kind}
                self.target=target
                self.data=data
            def geturl(self):
                return self.target
            def read(self, n):
                return self.data[:n]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        class Opener:
            def __init__(self, response):
                self.response=response
            def open(self, request, timeout):
                return self.response
        self.assertEqual(fetch_once(
            ROBOTS, MAX_ROBOTS, opener=Opener(Response())), ALLOW)
        for response, reason in (
            (Response(target="https://www.dapa.go.kr/another"), "status_or_redirect"),
            (Response(kind="text/html"), "content_type_unexpected"),
            (Response(code=500), "status_or_redirect"),
            (Response(data=b""), "empty_or_oversize"),
            (Response(data=b"x" * (MAX_ROBOTS + 1)), "empty_or_oversize"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(AccessHold, reason):
                    fetch_once(ROBOTS, MAX_ROBOTS, opener=Opener(response))
        with self.assertRaisesRegex(AccessHold, "unapproved_dapa_native_destination"):
            fetch_once("https://www.korea.kr/robots.txt", MAX_ROBOTS)

    def test_link_shape_counters_observe_js_form_and_missing_detail_url(self):
        # All labels, HTML and JS are fictional; output must be counts only.
        sample = b"""<!doctype html><html><body>
        <form method="post"><input type="hidden" name="docSeq" value="91293"></form>
        <a href="javascript:void(0)" onclick="viewDetail('91293')">SENSITIVE TEST HEADLINE</a>
        <a href="#" onclick="viewDetail('91294')">SENSITIVE OTHER HEADLINE</a>
        <a data-docseq="91295">SENSITIVE ANCHOR WITHOUT HREF</a>
        <a href="/dapa/doc/selectDoc.do?bbsSeq=326&menuSeq=3069">Missing ID</a>
        <a href="/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=91296&menuSeq=3069">Qualified</a>
        </body></html>"""
        report = inspect_listing(sample)
        shapes = report["structure_counts"]
        self.assertEqual(report["observed_anchor_count"], 5)
        self.assertEqual(report["provisional_docseq_count"], 1)
        self.assertEqual(shapes["anchors_with_javascript_href"], 1)
        self.assertEqual(shapes["anchors_with_fragment_href"], 1)
        self.assertEqual(shapes["anchors_with_onclick"], 2)
        self.assertEqual(shapes["anchors_missing_href"], 1)
        self.assertEqual(shapes["anchors_with_direct_detail_path"], 2)
        self.assertEqual(shapes["direct_detail_path_without_qualified_docseq"], 1)
        self.assertEqual(shapes["forms_post"], 1)
        self.assertEqual(shapes["hidden_inputs"], 1)
        self.assertEqual(shapes["inputs_named_docseq"], 1)
        self.assertEqual(shapes["anchors_with_numeric_docseq_attribute"], 1)
        self.assertNotIn("SENSITIVE", str(report))
        self.assertNotIn("viewDetail", str(report))
        self.assertNotIn("91293", str(report))
        self.assertNotIn("91294", str(report))
        self.assertNotIn("91295", str(report))

    def test_zero_qualified_ids_remains_unknown_after_aggregate_diagnostic(self):
        sample = b"""<html><body>
        <form method="get"></form>
        <a href="#" onclick="open('99999')">PRIVATE HEADING</a>
        <a href="javascript:open('99998')">PRIVATE SECOND HEADING</a>
        </body></html>"""
        result = inspect_listing(sample)
        self.assertEqual(result["provisional_docseq_count"], 0)
        self.assertEqual(result["sample_unverified_docseq"], [])
        self.assertTrue(result["zero_matching_links_is_not_zero_publications"])
        self.assertEqual(result["structure_counts"]["anchors_with_onclick"], 1)
        self.assertEqual(result["structure_counts"]["forms_get"], 1)
        self.assertEqual(result["structure_counts"]["anchors_with_javascript_href"], 1)
        self.assertNotIn("99999", str(result))
        self.assertNotIn("PRIVATE", str(result))

    def test_dated_release_rows_are_counted_without_forged_docseq(self):
        sample = b"""<html><body><table><tbody>
        <tr><th>Board header</th></tr>
        <tr><td>701</td><td><a href="#" onclick="openDoc(59299)">PRIVATE PRESS RELEASE ALPHA</a></td>
        <td>2026-10-15</td><td>144</td></tr>
        <tr><td>700</td><td><a href="javascript:openDoc(59298)">PRIVATE PRESS RELEASE BETA</a></td>
        <td>2026-10-15</td><td>108</td></tr>
        <tr><td>699</td><td><a href="/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=59297&menuSeq=3069">THIRD</a></td>
        <td>2026-10-08</td><td>207</td></tr>
        </tbody></table></body></html>"""
        result = inspect_listing(sample)
        rows = result["date_row_shape_counts"]
        self.assertEqual(rows["table_rows"], 4)
        self.assertEqual(rows["table_data_cells"], 12)
        self.assertEqual(rows["table_rows_with_iso_date"], 3)
        self.assertEqual(rows["dated_rows_with_any_anchor"], 3)
        self.assertEqual(rows["dated_rows_with_js_or_click_activation"], 2)
        self.assertEqual(rows["dated_rows_with_qualified_static_docseq"], 1)
        self.assertEqual(rows["dated_rows_without_qualified_static_docseq"], 2)
        self.assertEqual(result["provisional_docseq_count"], 1)
        self.assertEqual(result["sample_unverified_docseq"], ["59297"])
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("59299", str(result))
        self.assertNotIn("59298", str(result))
        self.assertNotIn("2026-10-15", str(result))
        self.assertNotIn("ALPHA", str(result))

    def test_no_table_rows_must_not_be_misrepresented_as_empty_listing(self):
        sample = b"""<html><body><div class="items">
        <a href="javascript:go(10001)">PRIVATE RELEASE</a>
        <p>2026-10-15</p></div></body></html>"""
        result = inspect_listing(sample)
        self.assertEqual(result["date_row_shape_counts"]["table_rows"], 0)
        self.assertEqual(result["date_row_shape_counts"]["table_rows_with_iso_date"], 0)
        self.assertTrue(result["zero_matching_links_is_not_zero_publications"])
        self.assertNotIn("PRIVATE", str(result))
        self.assertFalse(result.get("collector_enabled", False))

    def test_dated_row_click_argument_shapes_never_promote_unverified_ids(self):
        sample = b"""<html><body><table>
        <tr><td><a href="#" onclick="goDetail('59293')">PRIVATE A</a></td>
        <td>2026-10-15</td></tr>
        <tr><td><a href="javascript:openDetail(59292)">PRIVATE B</a></td>
        <td>2026-10-15</td></tr>
        <tr><td><a href="#" onclick="goDetail('59291',326)">PRIVATE C</a></td>
        <td>2026-10-08</td></tr>
        <tr><td><a href="#" onclick="openDocument(this)">PRIVATE D</a></td>
        <td>2026-10-08</td></tr>
        <tr><td><a href="#">PRIVATE E</a></td>
        <td>2026-10-07</td></tr>
        <tr><td><a href="#" onclick="goDetail('59290')">Not dated</a></td></tr>
        </table></body></html>"""
        from scripts.probe_korea_dapa_native_access import _action_argument_shape
        rows = inspect_listing(sample)["date_row_shape_counts"]
        self.assertEqual(rows["table_rows_with_iso_date"], 5)
        self.assertEqual(rows["dated_rows_with_single_numeric_js_shape"], 2)
        self.assertEqual(rows["dated_rows_with_ambiguous_numeric_js_shape"], 1)
        self.assertEqual(rows["dated_rows_with_only_non_numeric_js"], 1)
        self.assertEqual(rows["dated_rows_without_js_call_shape"], 1)
        result = inspect_listing(sample)
        self.assertEqual(result["provisional_docseq_count"], 0)
        self.assertEqual(result["sample_unverified_docseq"], [])
        self.assertTrue(result["zero_matching_links_is_not_zero_publications"])
        for prohibited in ("PRIVATE", "goDetail", "openDetail", "59293",
                           "59292", "59291", "59290", "2026-10-15"):
            self.assertNotIn(prohibited, str(result))
        for sample in ("goDetail('59293')", "goDetail(59293)",
                       "javascript:openDetail(59292)"):
            self.assertIn(_action_argument_shape(sample),
                          ("single_integer", "single_quoted_integer"))
        for sample in ("goDetail('59291',326)", "openDocument(this)",
                       "javascript:alert('oops')", "jQuery(this)"):
            self.assertNotIn(_action_argument_shape(sample),
                             ("single_integer", "single_quoted_integer"))

    def test_dated_js_shapes_do_not_change_live_fetch_budget(self):
        seen = []
        def fetch(url, limit):
            seen.append(url)
            if url == ROBOTS:
                return ALLOW
            return b"""<html><body><table>
            <tr><td><a onclick="detail(59293)" href="#">test</a></td>
            <td>2026-10-15</td></tr></table></body></html>"""
        result = probe(fetch=fetch, sleep=lambda _: None)
        self.assertEqual(seen, [ROBOTS, LISTING])
        self.assertEqual(result["article_requests"], 0)
        self.assertFalse(result["collector_enabled"])
        self.assertFalse(result["production_published"])
        self.assertFalse(result["dapa_issuer_per_article_verified"])
        self.assertEqual(result["date_row_shape_counts"]["dated_rows_with_single_numeric_js_shape"], 1)

    def test_challenge_and_invalid_listing_cannot_establish_dapa(self):
        for raw, code in (
            (b"\xff", "publisher_listing_not_utf8"),
            (b"ordinary plain text", "publisher_listing_unrecognized_markup"),
            (b"<html><body>captcha<a href='/'>Login</a></body></html>",
             "publisher_listing_challenge"),
        ):
            with self.subTest(code=code):
                with self.assertRaisesRegex(AccessHold, code):
                    inspect_listing(raw)
        unknown = inspect_listing(b"<html><body><a href='/other'>Go</a></body></html>")
        self.assertTrue(unknown["zero_matching_links_is_not_zero_publications"])
        self.assertEqual(unknown["provisional_docseq_count"], 0)


if __name__ == "__main__":
    unittest.main()
