"""No-network DAPA end-to-end source capture, custody, and rights-hold tests."""
import hashlib
import io
import json
import requests
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.manifests import load_manifest
from scraper.sources.kr_dapa_policy_briefing import (
    KoreaDapaPolicyAdapter, IDENTITY_PREFIX, observed_text_notice,
)
from scraper.sources.kr_policy_briefing import KoreaPolicyAdapter
from scripts import shadow_collect_desk as runner

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "shadow" / "kr_dapa_policy_briefing" / "manifest.json"
ARTICLE = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784625"
LISTING = "https://www.korea.kr/briefing/pressReleaseList.do"
DOC = "https://www.korea.kr/common/download.do?fileId=123456&tblKey=GMN"
ORIGINAL_TITLE = "제8회 국방사업관리사 국가자격검정, 역대 최다 인원 접수"


def document():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("Contents/section0.xml",
                   "<root><p><run><t>방위사업청 원문 첫 문단.</t></run></p></root>")
    return stream.getvalue()


def listing(issuer="방위사업청", code="B00008", date_text="2026.10.08",
            search_code="B00008", count=1):
    return """<html><form id="mainForm" method="post" action="/briefing/pressReleaseList.do">
<input name="repCode" value="{search_code}"><input name="pageIndex" value="1">
<input name="startDate" value="2026-10-08"><input name="endDate" value="2026-10-08">
</form><label for="{code}">방위사업청</label><div class="result"><strong>{count}</strong></div>
<a href="/briefing/pressReleaseView.do?newsId=156784625&pageIndex=1">
<span class="source"><span>{date_text}</span><span>{issuer}</span></span>
<strong>{title}</strong></a><div class="paging"></div></html>""".format(
        issuer=issuer, code=code, search_code=search_code,
        date_text=date_text, count=count, title=ORIGINAL_TITLE)


def article(issuer="방위사업청", code="B00008", date_text="2026.10.08",
            title=ORIGINAL_TITLE, license_type="0"):
    return """<html><head><link rel="canonical" href="{article}"></head><body>
<div class="view_title"><h1>{title}</h1></div><div class="variety">
<div class="info"><span>{date}</span>
<a class="gotosite" href="/news/ministryNewsList.do?repCode={code}">{issuer}</a>
</div></div><div class="files">
<a href="/common/download.do?fileId=123456&tblKey=GMN">document.hwpx</a>
<a href="/common/download.do?fileId=123457&tblKey=GMN">document.pdf</a>
</div><p>이 자료는 텍스트에 한하여 공공누리 제{license_type}유형의 조건에 따라 이용할 수 있습니다.</p>
</body></html>""".format(
        article=ARTICLE, title=title, issuer=issuer,
        code=code, date=date_text, license_type=license_type)


class FakeResponse:
    def __init__(self, url, payload, ctype):
        self.url = url
        self.payload = payload
        self.status_code = 200
        self.headers = {"Content-Type": ctype}

    def iter_content(self, chunk_size):
        for i in range(0, len(self.payload), chunk_size):
            yield self.payload[i:i + chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, item=None, index=None, hwpx=None):
        self.calls = []
        self.trust_env = False
        self.pages = {
            "https://www.korea.kr/robots.txt":
                FakeResponse("https://www.korea.kr/robots.txt",
                             b"User-agent: *\nAllow: /\n", "text/plain"),
            LISTING: FakeResponse(LISTING, (index or listing()).encode(), "text/html"),
            ARTICLE: FakeResponse(ARTICLE, (item or article()).encode(), "text/html"),
            DOC: FakeResponse(DOC, hwpx or document(), "application/zip"),
        }

    def request(self, method, url, data=None, headers=None, **kwargs):
        if url not in self.pages:
            raise AssertionError("unapproved destination: " + url)
        if url == LISTING:
            assert method == "POST" and data["repCode"] == "B00008"
            assert data["startDate"] == "2026-10-08"
        else:
            assert method == "GET"
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        self.calls.append((method, url))
        return self.pages[url]


def instance(**kwargs):
    source = load_manifest(MANIFEST).sources[0]
    session = FakeSession(**kwargs)
    return KoreaDapaPolicyAdapter(source, session=session, sleeper=lambda _: None), session


class DapaPrivateCollection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "private-dapa"

    def test_manifest_and_independent_issuer_not_mnd(self):
        source = load_manifest(MANIFEST).sources[0]
        self.assertEqual(source.slug, "kr_policy_dapa_releases")
        self.assertEqual(source.adapter,
                         "scraper.sources.kr_dapa_policy_briefing:KoreaDapaPolicyAdapter")
        self.assertEqual(runner.DESKS["korea_dapa"][2], "private/korea-dapa-policy-briefing")
        self.assertIs(runner.DESKS["korea"][1], KoreaPolicyAdapter)
        self.assertEqual(runner.DESKS["korea"][0], "kr_policy_briefing")

    def test_private_runner_refuses_unapproved_dapa_before_creating_files(self):
        source, session = instance()
        with self.assertRaisesRegex(ValueError, "separate one-time owner authorization"):
            runner.run("korea_dapa", self.state, date(2026, 10, 8),
                       adapter=source)
        self.assertEqual(session.calls, [])
        self.assertFalse(self.state.exists())
        self.assertEqual(runner.main(["--desk", "korea_dapa",
                                     "--state-dir", str(self.state),
                                     "--target-date", "2026-10-08",
                                     "--event-name", "workflow_dispatch"]), 2)
        self.assertFalse(self.state.exists())

    def test_private_full_capture_duplicates_and_no_public_admission(self):
        adapter, session = instance()
        result = runner.run(
            "korea_dapa", self.state, date(2026, 10, 8), lookback=0,
            cap=4, run_id="dapa-fixture-1", commit="synthetic",
            adapter=adapter, dapa_original_access_authorized=True)
        self.assertEqual(result["result"], st.OK, result)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(len(session.calls), 4)
        self.assertEqual(session.calls[0][1], "https://www.korea.kr/robots.txt")
        self.assertNotIn("www.dapa.go.kr", str(session.calls))
        with sqlite3.connect(self.state / "shadow.db") as conn:
            row = conn.execute(
                "SELECT source_identity, url, text_original, published_date, metadata_json "
                "FROM shadow_records").fetchone()
            self.assertEqual(conn.execute("SELECT desk FROM shadow_meta").fetchone()[0],
                             "korea_dapa")
        self.assertEqual(row[0], IDENTITY_PREFIX + "156784625")
        self.assertEqual(row[1], ARTICLE)
        self.assertEqual(row[3], "2026-10-08")
        self.assertIn("방위사업청 원문", row[2])
        meta = json.loads(row[4])
        self.assertEqual(meta["issuer"], "방위사업청")
        self.assertEqual(meta["publisher_text_license_notice"], "KOGL_type_0_text_notice_only")
        for flag in ("public_metadata_admission_approved", "public_full_text_approved",
                     "document_reuse_approved", "third_party_media_approved",
                     "korean_semantic_review_approved"):
            self.assertFalse(meta[flag])
        self.assertTrue(meta["additional_issuers_review_required"])
        capture = self.state / "captures" / (
            hashlib.sha256(document()).hexdigest() + ".bin")
        self.assertEqual(capture.read_bytes(), document())

        next_adapter, _ = instance()
        again = runner.run(
            "korea_dapa", self.state, date(2026, 10, 8), lookback=0,
            cap=4, run_id="dapa-fixture-2", commit="synthetic",
            adapter=next_adapter, dapa_original_access_authorized=True)
        self.assertEqual(again["result"], st.OK_ALL_DUPLICATES, again)
        self.assertEqual(again["inserted"], 0)
        self.assertEqual(again["duplicates"], 1)

    def test_issuer_or_date_mismatch_cannot_create_corpus(self):
        for kwargs in (
            {"index": listing(issuer="국방부")},
            {"item": article(issuer="국방부")},
            {"item": article(date_text="2026.10.07")},
            {"item": article(title="different release")},
            {"item": article(code="A00005")},
            {"item": article().replace("document.hwpx", "document.hwp")},
        ):
            with self.subTest(kwargs=repr(kwargs)[:85]):
                with tempfile.TemporaryDirectory() as td:
                    adapter, _ = instance(**kwargs)
                    result = runner.run(
                        "korea_dapa", Path(td) / "held",
                        date(2026, 10, 8), lookback=0,
                        adapter=adapter, dapa_original_access_authorized=True)
                    self.assertNotEqual(result["health"], "ok", result)
                    self.assertFalse((Path(td) / "held" / "shadow.db").exists())

    def test_dapa_robots_timeout_never_inherits_mnd_retry(self):
        adapter, session = instance()
        with mock.patch.object(session, "request", side_effect=requests.Timeout()) as request:
            result = adapter.discover(CollectionWindow(date(2026, 10, 8)))
        self.assertEqual(result.status, st.TIMEOUT)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(session.calls, [])

    def test_license_observations_never_grant_rights(self):
        self.assertEqual(observed_text_notice(article(license_type="1")),
                         "KOGL_type_1_text_notice_only")
        self.assertEqual(observed_text_notice(article(license_type="0")),
                         "KOGL_type_0_text_notice_only")
        self.assertEqual(observed_text_notice(article().replace("텍스트에 한하여", "다른 권리")),
                         "unverified")
        self.assertEqual(observed_text_notice(
            article() + "<p>공공누리 제1유형</p>"), "unverified")

    def test_existing_mnd_listing_filter_is_unchanged(self):
        mnd_source = load_manifest(
            ROOT / "shadow/kr_policy_briefing/manifest.json").sources[0]
        mnd = KoreaPolicyAdapter(mnd_source, session=FakeSession(), sleeper=lambda _: None)
        url, form = mnd.first_request(CollectionWindow(date(2026, 10, 8)))
        self.assertEqual(url, LISTING)
        self.assertEqual(form["repCode"], "A00005")
        self.assertEqual(mnd_source.slug, "kr_policy_mnd_releases")


if __name__ == "__main__":
    unittest.main()
