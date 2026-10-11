"""No-network DAPA government-portal source and rights hold regression."""
import unittest

from scripts.review_korea_dapa_source_contract import (
    DAPASourceHold, article_identity, download_identity,
    inspect_provisional_article, listing_filter,
)

LIST = ("https://www.korea.kr/briefing/pressReleaseList.do?"
        "pWiseMinistry=ministryNews&repCode=B00008&"
        "repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98")
ARTICLE = ("https://www.korea.kr/briefing/pressReleaseView.do?"
           "endDate=2026-10-11&newsId=156784618&pageIndex=1&"
           "period=&repCode=B00008&repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98"
           "&srchWord=&startDate=2025-10-11")
CANON = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784618"
ATTACH_HWPX = "/common/download.do?fileId=2345678&tblKey=GMN"
ATTACH_PDF = "/common/download.do?fileId=2345679&tblKey=GMN"


def page(*, issuer="방위사업청", code="B00008", date="2026.10.08",
         extra="", licence="공공누리 제0유형(자유이용) 텍스트에 한하여"):
    return """<html><div class="view_title"><h1>합동 방산정책 보도자료</h1></div>
<div class="variety"><div class="info"><span>{date}</span>
<a class="gotosite" href="/news/ministryNewsList.do?repCode={code}">{issuer}</a>
</div></div>
<div data-ipr-role="publisher-text-license">{licence}</div>
<div class="files">
<a href="{hwpx}">261008 방위사업청 보도자료.hwpx</a>
<a href="{pdf}">261008 방위사업청 보도자료.pdf</a>
{extra}
</div></html>""".format(
        date=date, issuer=issuer, code=code,
        licence=licence, hwpx=ATTACH_HWPX, pdf=ATTACH_PDF, extra=extra,
    )


class KoreanDAPAIdentityTests(unittest.TestCase):
    def test_explicit_dapa_filtered_listing_and_canonical_id(self):
        self.assertEqual(listing_filter(LIST)["filter_code"], "B00008")
        ident = article_identity(ARTICLE)
        self.assertEqual(ident["canonical_url"], CANON)
        self.assertEqual(ident["source_identity"], "korea-dapa-policy:156784618")
        self.assertFalse(ident["direct_dapa_website_original"])
        self.assertTrue(ident["issuer_human_verification_required"])
        self.assertEqual(article_identity(CANON)["source_identity"], ident["source_identity"])

    def test_parallel_hwpx_and_pdf_allowed_but_not_fetched(self):
        d = inspect_provisional_article(page(), ARTICLE, expected_listing_date="2026-10-08")
        self.assertEqual(d["declared_issuer"], "방위사업청")
        self.assertEqual(d["portal_post_date"], "2026-10-08")
        self.assertEqual(d["observed_text_license"], "KOGL_type_0_notice_only")
        self.assertTrue(d["has_hwpx"])
        self.assertTrue(d["has_pdf"])
        self.assertEqual(len(d["document_attachments"]), 2)
        self.assertNotEqual(d["document_attachments"][0]["file_id"],
                            d["document_attachments"][1]["file_id"])
        for k in ("actual_publisher_access_verified", "document_bytes_verified",
                  "content_text_verified", "publisher_permission_approved",
                  "production_collection_enabled", "desk_registry_changed"):
            self.assertFalse(d[k])
        self.assertNotIn("article full text", str(d))

    def test_explicit_page_licence_variation_does_not_approve_reuse(self):
        p = page(licence="텍스트에 한하여 공공누리 제1유형 출처표시")
        d = inspect_provisional_article(p, CANON)
        self.assertEqual(d["observed_text_license"], "KOGL_type_1_notice_only")
        self.assertFalse(d["publisher_permission_approved"])
        unknown = page().replace("data-ipr-role=\"publisher-text-license\"",
                                 "class=\"unspecified-license\"")
        d = inspect_provisional_article(unknown, CANON)
        self.assertEqual(d["observed_text_license"], "unverified")
        self.assertFalse(d["text_only_notice_present"])

    def test_wrong_portal_issuer_or_faked_canonical_filter_refused(self):
        for url in (
            LIST.replace("repCode=B00008", "repCode=A00005"),
            LIST.replace("www.korea.kr", "admin.korea.kr"),
            LIST.replace("https://", "http://"),
            LIST.replace("repCodeType=", "repCodeType=wrong"),
            LIST + "&repCode=B00008",
        ):
            with self.subTest(url=url), self.assertRaises(DAPASourceHold):
                listing_filter(url)
        for url in (
            ARTICLE.replace("newsId=156784618", "newsId=0"),
            ARTICLE.replace("repCode=B00008", "repCode=A00005"),
            ARTICLE.replace("https://", "http://"),
            ARTICLE + "#fragment",
            ARTICLE.replace("www.korea.kr", "admin.korea.kr"),
            ARTICLE + "&newsId=156784619",
            ARTICLE + "&extra=1",
        ):
            with self.subTest(url=url), self.assertRaises(DAPASourceHold):
                article_identity(url)
        for html in (
            page(issuer="국방부"),
            page(code="A00005"),
            page(date="bad"),
            page().replace("<h1>합동 방산정책 보도자료</h1>", ""),
            page().replace(ATTACH_HWPX, ATTACH_PDF),
            page().replace(ATTACH_PDF, "https://evil.example/malicious.pdf"),
            page(extra='<a href="/common/download.do?fileId=6&tblKey=GMN">'
                       "other.hwp</a>"),
            page(licence="공공누리 제0유형 텍스트에 한하여 공공누리 제1유형"),
        ):
            with self.subTest(html=html[:70]), self.assertRaises(DAPASourceHold):
                inspect_provisional_article(html, ARTICLE)

    def test_wrong_document_host_or_query_or_duplicated_id_rejected(self):
        for href in (
            "https://evil.example/common/download.do?fileId=42&tblKey=GMN",
            "/common/download.do?fileId=42&tblKey=X",
            "/common/download.do?fileId=0&tblKey=GMN",
            "/common/download.do?fileId=42&tblKey=GMN&fileId=99",
            "/common/download.do?fileId=42&tblKey=GMN#frag",
            "/common/download.do?fileId=42&tblKey=GMN&token=x",
        ):
            with self.subTest(href=href), self.assertRaises(DAPASourceHold):
                download_identity(CANON, href)

    def test_no_article_body_or_url_collection_entrypoint(self):
        from scripts import review_korea_dapa_source_contract as m
        self.assertFalse(hasattr(m, "collect"))
        self.assertFalse(hasattr(m, "fetch"))
        self.assertFalse(hasattr(m, "send"))
        with self.assertRaises(SystemExit):
            m.main()


if __name__ == "__main__":
    unittest.main()
