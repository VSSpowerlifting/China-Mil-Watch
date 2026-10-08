"""Network-free checks for the disposable four-category journal probe."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import research_vietnam_journal_categories as p


def article(n, category="theory-and-practice", slug="sample"):
    return "https://tapchiqptd.vn/en/%s/%s/%s.html" % (category,slug,n)


def listing(name, ids):
    content = ["<html><body><form id='aspnetForm'>",
               "<p id='header'>Thursday, October 08, 2026, 08:15 (GMT+7)</p>"]
    for n in ids:
        content.append("<div class='list-item'>"
                       "<a href='%s'>Synthetic headline %s</a>"
                       "<span>Wednesday, September 30, 2026, 14:48 (GMT+7)</span>"
                       "</div>" % (article(n),n))
    content.extend(["<div class='mostread'>"
                    "<a href='%s'>Repeated synthetic headline</a></div>" % article(ids[0]),
                    "<div class='pager'>"
                    "<a href='javascript:__doPostBack(\"ctl00$Page\", \"2\")' "
                    "onclick='__doPostBack(\"ctl00$Page\", \"2\")'>Next</a>"
                    "<input type='hidden' name='__EVENTTARGET' value=''>"
                    "</div></form></body></html>"])
    return "".join(content)


class FakeResponse:
    def __init__(self, url, text, status=200, ctype="text/html", extra=None):
        self.url=url
        self.text=text
        self.status_code=status
        self.headers={"Content-Type":ctype}
        self.headers.update(extra or {})
        self.closed=False

    def iter_content(self, size):
        yield self.text.encode("utf-8")

    def close(self):
        self.closed=True


class Cookies:
    def __init__(self):self.clears=0
    def clear(self):self.clears+=1


class FakeSession:
    def __init__(self, responses):
        self.responses=list(responses)
        self.calls=[]
        self.headers={}
        self.trust_env=True
        self.cookies=Cookies()

    def get(self, url, *,timeout,stream,allow_redirects):
        assert timeout==20 and stream and not allow_redirects
        assert self.headers["User-Agent"]==p.USER_AGENT
        assert self.headers["Accept-Encoding"]=="identity"
        self.calls.append(url)
        if not self.responses:
            raise AssertionError("unexpected extra GET")
        response=self.responses.pop(0)
        assert response.url==url,(response.url,url)
        return response


def allowed_five():
    response=[FakeResponse(p.ROBOTS,"User-agent: *\nAllow: /\n",ctype="text/plain")]
    for i,(name,url) in enumerate(p.CATEGORIES):
        response.append(FakeResponse(url,listing(name,[str(20010+i),str(20020+i)])))
    return response


class CategoryDiscoveryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp=Path(tmp.name)
        self.out=self.tmp/"category.json"
        z=patch("scripts.research_vietnam_journal_categories.time.sleep")
        z.start()
        self.addCleanup(z.stop)

    def test_four_categories_and_bounded_five_gets(self):
        session=FakeSession(allowed_five())
        result=p.run(self.out,session)
        self.assertEqual(result["request_count"],5)
        self.assertEqual(len(session.calls),5)
        self.assertEqual(session.cookies.clears,5)
        self.assertFalse(session.trust_env)
        self.assertTrue(result["all_four_sections_measured"])
        self.assertFalse(result["listing_completeness_proven"])
        self.assertEqual(result["unique_ids_across_pages"],8)
        self.assertEqual([z["article_count"] for z in result["category_pages"]],[2,2,2,2])
        self.assertEqual([z["date_hint_count"] for z in result["category_pages"]],[2,2,2,2])

    def test_duplicates_never_create_extra_article_id(self):
        data=p.page_evidence(listing("theory-and-practice",["26936","26937"]),"theory-and-practice")
        self.assertEqual(data["article_count"],2)
        self.assertEqual(data["article_links_total"],3)
        self.assertEqual(data["article_id_inventory"][0]["listing_date_hint"],"2026-09-30")
        self.assertEqual(data["article_id_inventory"][0]["matches"],2)
        self.assertGreaterEqual(len(data["pagination_control_candidates"]),1)
        self.assertFalse(data["chronological_completeness_proven"])

    def test_source_title_or_prose_is_never_retained(self):
        session=FakeSession(allowed_five())
        report=p.run(self.out,session)
        text=self.out.read_text(encoding="utf-8")
        self.assertFalse(report["article_html_retained"])
        self.assertFalse(report["article_text_retained"])
        self.assertNotIn("Synthetic headline",text)
        self.assertNotIn("Repeated synthetic headline",text)
        self.assertNotIn("Wednesday, September",text)
        self.assertNotIn("__doPostBack",text)

    def test_only_article_permalinks_are_discovered(self):
        h=("<html><body><a href='https://m.tapchiqptd.vn/en/theory-and-practice/sample-26936.html'>mobile</a>"
           "<a href='http://tapchiqptd.vn/en/theory-and-practice/sample/26936.html'>http</a>"
           "<a href='https://evil.example/en/theory-and-practice/sample/26936.html'>foreign</a>"
           "<a href='https://tapchiqptd.vn/en/theory-and-practice/sample/26936.html?q=1'>query</a>"
           "<a href='%s'>legitimate</a></body></html>" % article("26936"))
        obj=p.page_evidence(h,"theory-and-practice")
        self.assertEqual(obj["article_count"],1)
        self.assertEqual(obj["article_id_inventory"][0]["id"],"26936")

    def test_unreadable_robots_never_requests_listings(self):
        session=FakeSession([FakeResponse(p.ROBOTS,"<html>script</html>",ctype="text/html")])
        with self.assertRaisesRegex(p.Refusal,"robots policy"):
            p.run(self.out,session)
        self.assertEqual(session.calls,[p.ROBOTS])
        self.assertFalse(self.out.exists())

    def test_disallowed_category_is_held_independently(self):
        s=FakeSession([FakeResponse(p.ROBOTS,
          "User-agent: *\nDisallow: /en/research-and-discussion-58.html\nAllow: /\n",
          ctype="text/plain")]+
          [FakeResponse(url,listing(name,[str(30000+i)]))
           for i,(name,url) in enumerate(p.CATEGORIES[:3])])
        report=p.run(self.out,s)
        self.assertEqual(report["request_count"],4)
        self.assertEqual(report["category_pages"][-1]["robots_allowed"],False)
        self.assertEqual(len(s.calls),4)
        self.assertFalse(report["all_four_sections_measured"])

    def test_rejects_unexpected_html_or_existing_output(self):
        with self.assertRaisesRegex(p.Refusal,"no complete HTML"):
            p.page_evidence("<p>partial</p>","news")
        self.out.write_text("existing")
        with self.assertRaisesRegex(p.Refusal,"output must be a new"):
            p.run(self.out,FakeSession([]))
        with self.assertRaisesRegex(p.Refusal,"output must be a new"):
            p.run(p.ROOT/"output-in-repo.json",FakeSession([]))
        self.assertEqual(self.out.read_text(),"existing")


if __name__=="__main__":
    unittest.main()
