"""Finite, source-scoped JCG companion PDF audit contracts (no network)."""
import io
import unittest

from pypdf import PdfWriter

from scripts.probe_japan_jcg_pdf_completeness import (
    CLIENT, HOST, MAX_HTML_BYTES, MAX_PDF_BYTES, PREFIX, RELEASES, NoRedirect,
    _pdf_metrics, audit, official_pdf,
)


def sample_html(pdf_link='upload/official.pdf'):
    prose = ("The Japan Coast Guard and partner coast guards held maritime law "
             "enforcement capacity-building training and published a summary. " * 6)
    return ("""<html><nav>UNRELATED SITE NAVIGATION</nav>
      <main><article class="main-article">
      <section class="topics topics-article">
      <div class="topics-article__main tich-text"><p>""" + prose +
      """</p><p><a href="%s">Original PDF</a></p></div></section>
      </article></main><footer>UNRELATED FOOTER</footer></html>""" % pdf_link
    ).encode("utf-8")


def response(body, mime):
    return {"status": 200, "mime": mime, "bytes": body}


class FakeTransport:
    def __init__(self, robots=404, invalid_pdf=False, invalid_article=None):
        self.calls = []
        self.robots = robots
        self.invalid_pdf = invalid_pdf
        self.invalid_article = invalid_article

    def __call__(self, url, limit, *, opener):
        self.calls.append((url, limit))
        if url == PREFIX + "/robots.txt":
            if self.robots == 404:
                return {"status": 404, "error": "http_not_served"}
            if self.robots == 403:
                return {"status": 403, "error": "http_not_served"}
            return response(self.robots.encode(), "text/plain")
        if url in [article for _, article in RELEASES]:
            if url == self.invalid_article:
                return {"status": 403, "error": "http_not_served"}
            return response(sample_html(), "text/html")
        if url.endswith("/e/topics_archive/upload/official.pdf"):
            return response(b"INVALID" if self.invalid_pdf else b"%PDF-synthetic",
                            "application/pdf")
        raise AssertionError("unrecognized URL request " + url)


def parsed(_):
    return {
        "page_count": 2, "pages_without_text": 0,
        "text": ("The Japan Coast Guard and partner coast guards held maritime "
                 "enforcement training; further official details, images, and "
                 "a mission overview are documented here. " * 8),
    }


class JCGAuditContracts(unittest.TestCase):
    def test_html_article_has_one_same_host_declared_pdf(self):
        article = RELEASES[0][1]
        url, text = official_pdf(article, sample_html())
        self.assertEqual(url, PREFIX + "/e/topics_archive/upload/official.pdf")
        self.assertIn("maritime law enforcement", text)
        self.assertNotIn("UNRELATED", text)

    def test_external_mutable_and_multiple_pdfs_are_refused(self):
        article = RELEASES[0][1]
        for link in ("https://mirror.example/press.pdf",
                     "upload/official.pdf?revision=2",
                     "/e/other/official.pdf"):
            with self.subTest(link=link), self.assertRaises(ValueError):
                official_pdf(article, sample_html(link))
        repeated = sample_html().replace(b"</p></div>", (
            b'<a href="upload/another.pdf">Second PDF</a></p></div>'))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            official_pdf(article, repeated)

    def test_stable_declared_scope_never_hunt_urls(self):
        self.assertEqual([item[0] for item in RELEASES],
                         ["jcg-en:9455", "jcg-en:9453", "jcg-en:9436"])
        self.assertTrue(all(u.startswith(PREFIX + "/e/topics_archive/article")
                            for _, u in RELEASES))
        self.assertEqual(HOST, "www.kaiho.mlit.go.jp")
        self.assertEqual(len(RELEASES), 3)

    def test_exact_absent_robots_allows_six_fixed_requests_and_no_text_output(self):
        fetch = FakeTransport()
        output = audit(opener=object(), fetch=fetch, pdf_metrics=parsed,
                       sleep=lambda _: None)
        self.assertEqual(output["robots"], "confirmed_absent_404")
        self.assertEqual(output["complete_metadata_observations"], 3)
        self.assertEqual(len(fetch.calls), 7)  # 1 policy + 3 article + 3 pdf
        self.assertEqual(fetch.calls[1][1], MAX_HTML_BYTES)
        self.assertEqual(fetch.calls[2][1], MAX_PDF_BYTES)
        self.assertTrue(all(r["assessment"] == "ready_for_human_original_comparison"
                            for r in output["records"]))
        self.assertTrue(all(r["pdf_pages"] == 2 for r in output["records"]))
        self.assertTrue(all(0 <= r["html_coverage_ratio"] <= 1
                            for r in output["records"]))
        self.assertFalse(output["human_original_document_review_completed"])
        self.assertFalse(output["source_promoted"])
        self.assertFalse(output["source_text_or_pdf_persisted"])
        self.assertNotIn("The Japan Coast Guard", str(output))
        self.assertNotIn("UNRELATED", str(output))
        self.assertNotIn("%PDF", str(output))

    def test_refused_robots_cannot_trigger_article_requests(self):
        fetch = FakeTransport(robots=403)
        with self.assertRaisesRegex(ValueError, "robots policy unreadable"):
            audit(opener=object(), fetch=fetch, pdf_metrics=parsed,
                  sleep=lambda _: None)
        self.assertEqual(len(fetch.calls), 1)

    def test_robots_disallow_prevents_pdf_and_html(self):
        fetch = FakeTransport(robots="User-agent: *\nDisallow: /\n")
        result = audit(opener=object(), fetch=fetch, pdf_metrics=parsed,
                       sleep=lambda _: None)
        self.assertEqual(len(fetch.calls), 1)
        self.assertEqual(result["complete_metadata_observations"], 0)
        self.assertTrue(all(r["failure"] == "article_robots_disallow"
                            for r in result["records"]))

    def test_article_failure_does_not_issue_uncontrolled_pdf_request(self):
        fetch = FakeTransport(invalid_article=RELEASES[1][1])
        result = audit(opener=object(), fetch=fetch, pdf_metrics=parsed,
                       sleep=lambda _: None)
        self.assertEqual(result["complete_metadata_observations"], 2)
        self.assertEqual(result["records"][1]["failure"],
                         "html_unavailable_or_invalid")
        self.assertEqual(len(fetch.calls), 6)

    def test_invalid_pdf_is_fidelity_failure_not_approval(self):
        fetch = FakeTransport(invalid_pdf=True)
        result = audit(opener=object(), fetch=fetch,
                       sleep=lambda _: None)
        self.assertEqual(result["complete_metadata_observations"], 0)
        self.assertTrue(all(r["assessment"] == "incomplete_not_reviewed"
                            for r in result["records"]))
        self.assertTrue(all(r["failure"] == "pdf_parser_ValueError"
                            for r in result["records"]))

    def test_blank_pdf_parser_reports_text_sparse_not_full_original(self):
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        out = io.BytesIO()
        writer.write(out)
        result = _pdf_metrics(out.getvalue())
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["pages_without_text"], 1)
        self.assertEqual(result["text"], "")

    def test_redirect_handler_refuses_any_location(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302,
                                                   "Redirect", {},
                                                   "https://elsewhere.example/path"))


if __name__ == "__main__":
    unittest.main()
