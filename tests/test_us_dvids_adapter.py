"""
US Indo-Pacific (DVIDS) shadow adapter: identity, dates, extraction, refusal.

The collector's job in this phase is to prove it can retrieve and identify
official documents reliably. These tests' job is to prove it refuses everything
it cannot identify honestly, and that it never reports a failure as silence.

Everything runs from saved bounded fixtures. No network, no tracked-database
access, no writes outside a temporary directory.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import (                          # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow)
from scraper.sources import us_dvids as us                      # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "us_dvids"

REAL_FEED = (FIX / "feed_usindopacom.xml").read_bytes()
DEFECT_FEED = (FIX / "derived_feed_defects.xml").read_bytes()
ROBOTS_REAL = (FIX / "robots.txt").read_text(encoding="utf-8")
ROBOTS_DENY_ALL = "User-agent: *\nDisallow: /\n"
ROBOTS_DENY_RSS = "User-agent: *\nDisallow: /rss/\nAllow: /\n"

ARTICLES = {
    "574946": "article_574946_uc26_patient_insertion.html",
    "574942": "article_574942_kosovo_pen_pal.html",
    "574940": "article_574940_188th_isr_short.html",
}
WINDOW = CollectionWindow(target_date=date(2026, 9, 16), lookback_days=7)

CURLY_APOSTROPHE = "’"
CURLY_QUOTE = "“"
EM_DASH = "—"
EN_DASH = "–"
#: What a UTF-8 curly apostrophe looks like when it is decoded as latin-1.
#: Built rather than written literally: the middle byte is a C1 control
#: character, and source files should not carry those.
MOJIBAKE = CURLY_APOSTROPHE.encode("utf-8").decode("latin-1")


def art(ident):
    return (FIX / ARTICLES[ident]).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, body=b"", status_code=200, headers=None, url=""):
        if isinstance(body, str):
            self.content = body.encode("utf-8")
            self.text = body
        else:
            self.content = body
            self.text = body.decode("utf-8", "replace")
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self.url = url


class Boom(Exception):
    """A transport failure, as requests would raise one."""


class FakeSession:
    """Serves the saved fixtures. Records every URL it was asked for."""

    def __init__(self, robots=ROBOTS_REAL, robots_status=200,
                 feed=REAL_FEED, feed_status=200, article_status=200,
                 raise_on=None, final_url=None):
        self.robots = robots
        self.robots_status = robots_status
        self.feed = feed
        self.feed_status = feed_status
        self.article_status = article_status
        self.raise_on = raise_on or ()
        self.final_url = final_url
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        if any(tok in url for tok in self.raise_on):
            raise Boom("connection reset")
        if url == us.ROBOTS:
            return FakeResponse(self.robots, self.robots_status)
        if url == us.FEED:
            return FakeResponse(self.feed, self.feed_status)
        for ident in ARTICLES:
            if "/news/%s/" % ident in url:
                if self.article_status != 200:
                    return FakeResponse(b"", self.article_status)
                return FakeResponse(art(ident), 200, url=self.final_url or url)
        return FakeResponse(b"", 404)


class FakeSource:
    slug = "us_dvids_indopacom"
    enabled = False
    base_url = "https://www.dvidshub.net"
    language_tag = "en"


def adapter(session=None, cap=40):
    return us.USDvidsAdapter(FakeSource(), session=session or FakeSession(),
                             cap=cap, sleeper=lambda _s: None)


# -- 1. Feed parsing ----------------------------------------------------------

class TestTheFeedIsParsedForWhatItActuallyContains(unittest.TestCase):

    def test_only_news_items_survive_parsing(self):
        items, rej = us.parse_feed(REAL_FEED)
        self.assertEqual(len(items), 6)
        self.assertEqual(rej[us.R_NOT_NEWS_MEDIA], 6)

    def test_every_parsed_item_carries_the_fields_a_record_needs(self):
        items, _ = us.parse_feed(REAL_FEED)
        for it in items:
            self.assertTrue(it.identity, it.url)
            self.assertTrue(it.url.startswith("https://www.dvidshub.net/news/"))
            self.assertTrue(it.title.strip())
            self.assertRegex(it.published_date, r"^\d{4}-\d{2}-\d{2}$")

    def test_a_feed_with_no_items_at_all_is_a_listing_failure(self):
        a = adapter(FakeSession(feed=b'<?xml version="1.0"?><rss><channel>'
                                     b'<title>x</title></channel></rss>'))
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("zero items", result.error_detail)

    def test_a_window_with_no_matching_items_is_a_success(self):
        a = adapter()
        result = a.discover(CollectionWindow(target_date=date(2020, 1, 1),
                                             lookback_days=1))
        self.assertEqual(result.status, st.OK_NO_PUBLICATIONS)
        self.assertTrue(st.is_success(result.status))

    def test_selection_is_deterministic_regardless_of_feed_order(self):
        items, _ = us.parse_feed(REAL_FEED)
        first = us.select_window(items, WINDOW, 40)
        second = us.select_window(list(reversed(items)), WINDOW, 40)
        self.assertEqual([i.identity for i in first],
                         [i.identity for i in second])

    def test_the_cap_bounds_a_run_without_changing_its_order(self):
        items, _ = us.parse_feed(REAL_FEED)
        full = us.select_window(items, WINDOW, 40)
        capped = us.select_window(items, WINDOW, 2)
        self.assertEqual(len(capped), 2)
        self.assertEqual([i.identity for i in capped],
                         [i.identity for i in full[:2]])


# -- 2. GUID and URL identity -------------------------------------------------

class TestIdentityComesFromTheSourceNotFromUs(unittest.TestCase):

    def test_the_guid_supplies_the_identity(self):
        self.assertEqual(us.guid_identity("news:574946"), "574946")

    def test_a_guid_in_an_unknown_form_yields_no_identity(self):
        for bad in ("574946", "news-574946", "image:9942539", "", None):
            self.assertIsNone(us.guid_identity(bad), bad)

    def test_the_url_carries_the_same_identity_as_the_guid(self):
        items, _ = us.parse_feed(REAL_FEED)
        for it in items:
            self.assertEqual(us.url_identity(it.url), it.identity)

    def test_an_item_whose_guid_and_link_disagree_is_refused(self):
        items, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual(rej[us.R_IDENTITY_MISMATCH], 1)
        self.assertNotIn("500002", [i.identity for i in items])
        self.assertNotIn("500003", [i.identity for i in items])

    def test_an_item_with_no_guid_is_refused_not_identified_by_slug(self):
        _, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual(rej[us.R_MISSING_GUID], 1)

    def test_identity_is_stable_across_a_reworded_slug(self):
        a = "https://www.dvidshub.net/news/574946/army-reserve-patient-insert"
        b = "https://www.dvidshub.net/news/574946/completely-different-wording"
        self.assertEqual(us.url_identity(a), us.url_identity(b))


# -- 3. Canonicalization and allowed-host enforcement -------------------------

class TestOnlyPermittedHostsAreEverRetrieved(unittest.TestCase):

    def test_query_strings_and_fragments_are_not_part_of_identity(self):
        base = "https://www.dvidshub.net/news/574946/army-reserve-patient"
        for variant in (base + "?utm_source=rss", base + "#top",
                        base + "/", base + "?a=1&b=2#x"):
            self.assertEqual(us.canonical_url(variant), base, variant)

    def test_a_foreign_host_is_refused_never_rewritten(self):
        for bad in ("https://www.pacom.mil/news/1/x",
                    "https://www.defense.gov/news/1/x",
                    "https://dvidshub.net.evil.example/news/1/x",
                    "https://www.dvidshub.net.evil.example/news/1/x"):
            self.assertIsNone(us.canonical_url(bad), bad)

    def test_the_bare_apex_host_is_permitted_and_normalized(self):
        self.assertEqual(
            us.canonical_url("https://dvidshub.net/news/574946/slug"),
            "https://www.dvidshub.net/news/574946/slug")

    def test_a_non_news_path_is_not_a_document(self):
        for bad in ("https://www.dvidshub.net/image/9942539/photo",
                    "https://www.dvidshub.net/search/?q=x",
                    "https://www.dvidshub.net/tags/pacific",
                    "https://www.dvidshub.net/news/",
                    "https://www.dvidshub.net/news/abc/slug"):
            self.assertIsNone(us.canonical_url(bad), bad)

    def test_fetch_refuses_a_reference_it_did_not_discover(self):
        a = adapter()
        cap = a.fetch(CandidateReference(url="https://www.pacom.mil/news/1/x",
                                         source_slug=a.slug))
        self.assertEqual(cap.status, st.DISALLOWED_REDIRECT)
        self.assertEqual(a._session.calls, [])

    def test_a_redirect_off_the_permitted_host_is_refused(self):
        sess = FakeSession(final_url="https://cdn.example.net/elsewhere")
        a = adapter(sess)
        a.discover(WINDOW)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/x", source_slug=a.slug))
        self.assertEqual(cap.status, st.DISALLOWED_REDIRECT)
        self.assertIn("cdn.example.net", cap.error_detail)

    def test_the_disallowed_dvids_paths_are_never_requested(self):
        a = adapter()
        a.discover(WINDOW)
        for call in a._session.calls:
            self.assertNotIn("/search/", call)
            self.assertNotIn("/tags/", call)
            self.assertNotIn("/download/", call)


# -- 4. Publication dates and time zones --------------------------------------

class TestDatesAreThePublishersNotOurs(unittest.TestCase):

    def test_the_date_is_read_in_the_offset_the_publisher_declared(self):
        # 22:13 -0400 is the 16th where it was published, the 17th in UTC.
        got = us.parse_pubdate("Wed, 16 Sep 2026 22:13:04 -0400")
        self.assertEqual(got[0], "2026-09-16")
        self.assertEqual(got[1], "2026-09-17T02:13:04+00:00")

    def test_the_utc_instant_is_preserved_beside_the_date(self):
        items, _ = us.parse_feed(REAL_FEED)
        late = [i for i in items if i.identity == "574946"][0]
        self.assertEqual(late.published_date, "2026-09-16")
        self.assertTrue(late.published_at_utc.startswith("2026-09-17"))
        self.assertEqual(late.published_at_original,
                         "Wed, 16 Sep 2026 22:13:04 -0400")

    def test_a_timestamp_without_an_offset_is_refused_not_guessed(self):
        self.assertIsNone(us.parse_pubdate("Tue, 15 Sep 2026 16:00:00"))
        _, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual(rej[us.R_UNPARSEABLE_PUBDATE], 2)

    def test_a_different_offset_yields_a_different_local_date(self):
        eastern = us.parse_pubdate("Wed, 16 Sep 2026 22:13:04 -0400")
        utc = us.parse_pubdate("Thu, 17 Sep 2026 02:13:04 +0000")
        self.assertEqual(eastern[1], utc[1])          # same instant
        self.assertNotEqual(eastern[0], utc[0])       # different published day

    def test_an_absent_pubdate_is_counted_not_defaulted_to_today(self):
        _, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual(rej[us.R_MISSING_PUBDATE], 1)


# -- 5. Body extraction -------------------------------------------------------

class TestBodiesComeFromTheArticlePageNotTheTeaser(unittest.TestCase):

    def test_a_full_article_yields_its_prose(self):
        body, present = us.document_body(art("574946"))
        self.assertTrue(present)
        self.assertGreater(len(body), 3000)
        self.assertIn("SCOTT AIR FORCE BASE", body)

    def test_a_genuinely_short_article_is_kept_not_discarded(self):
        body, present = us.document_body(art("574940"))
        self.assertTrue(present)
        self.assertGreater(len(body), us.MIN_BODY_CHARS)
        self.assertLess(len(body), 2000)

    def test_the_related_image_rail_is_not_swept_into_the_body(self):
        body, _ = us.document_body(art("574946"))
        self.assertNotIn("relatedimage", body)
        self.assertNotIn("cloudfront.net", body)

    def test_the_title_comes_from_og_title_not_the_truncated_h1(self):
        title = us.document_title(art("574946"))
        self.assertTrue(title.endswith("UC26"))       # the h1 is cut short

    def test_extraction_produces_one_document_with_full_provenance(self):
        a = adapter()
        a.discover(WINDOW)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/x", source_slug=a.slug))
        res = a.extract(cap)
        self.assertEqual(res.status, st.OK)
        doc = res.documents[0]
        self.assertEqual(doc.extra["source_identity"], "574946")
        self.assertEqual(doc.published_date, "2026-09-16")
        self.assertEqual(doc.language_tag, "en")
        self.assertTrue(doc.has_usable_text)
        for key in ("published_at_utc", "published_at_original",
                    "content_sha256", "capture_sha256", "retrieved_at"):
            self.assertIsNotNone(doc.extra[key], key)

    def test_the_feed_teaser_is_never_stored_as_a_body(self):
        a = adapter()
        a.discover(WINDOW)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574940/x", source_slug=a.slug))
        doc = a.extract(cap).documents[0]
        self.assertGreater(len(doc.text_original), 1000)

    def test_a_document_never_seen_in_the_feed_is_refused(self):
        # Identity and date come from the feed. An article page alone cannot
        # supply them, so extracting one we never discovered is a refusal.
        a = adapter()
        cap = CaptureResult(
            CandidateReference(url="https://www.dvidshub.net/news/574946/x",
                               source_slug=a.slug),
            st.OK, "https://www.dvidshub.net/news/574946/x",
            body=art("574946"))
        res = a.extract(cap)
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("no feed record", res.error_detail)


# -- 6. Missing bodies: drift and media-only are different facts --------------

class TestAnEmptyBodyIsNeverStoredAsARecord(unittest.TestCase):

    def test_a_renamed_container_reports_template_drift(self):
        html = (FIX / "derived_article_container_renamed.html").read_text(
            encoding="utf-8")
        body, present = us.document_body(html)
        self.assertFalse(present)
        self.assertEqual(body, "")

    def test_a_container_with_no_prose_is_a_media_only_entry(self):
        html = (FIX / "derived_article_media_only.html").read_text(
            encoding="utf-8")
        body, present = us.document_body(html)
        self.assertTrue(present)          # found it; it simply has no prose
        self.assertLess(len(body.strip()), us.MIN_BODY_CHARS)

    def test_the_two_failures_are_reported_differently(self):
        a = adapter()
        a.discover(WINDOW)
        ref = CandidateReference(url="https://www.dvidshub.net/news/574940/x",
                                 source_slug=a.slug)
        drift = a.extract(CaptureResult(
            ref, st.OK, ref.url,
            body=(FIX / "derived_article_container_renamed.html").read_text(
                encoding="utf-8")))
        media = a.extract(CaptureResult(
            ref, st.OK, ref.url,
            body=(FIX / "derived_article_media_only.html").read_text(
                encoding="utf-8")))
        self.assertEqual(drift.status, st.EXTRACTION_FAILURE)
        self.assertEqual(media.status, st.EXTRACTION_FAILURE)
        self.assertIn("template drift", drift.error_detail)
        self.assertIn("no prose", media.error_detail)
        self.assertNotEqual(drift.error_detail, media.error_detail)

    def test_neither_case_yields_a_document(self):
        a = adapter()
        a.discover(WINDOW)
        ref = CandidateReference(url="https://www.dvidshub.net/news/574940/x",
                                 source_slug=a.slug)
        for name in ("derived_article_container_renamed.html",
                     "derived_article_media_only.html"):
            res = a.extract(CaptureResult(
                ref, st.OK, ref.url,
                body=(FIX / name).read_text(encoding="utf-8")))
            self.assertEqual(res.documents, [], name)


# -- 7. Photo, video and audio entries ----------------------------------------

class TestNonTextItemsAreCountedAndRejected(unittest.TestCase):

    def test_image_video_and_audio_items_never_become_records(self):
        items, rej = us.parse_feed(REAL_FEED)
        self.assertEqual(rej[us.R_NOT_NEWS_MEDIA], 6)
        for it in items:
            self.assertEqual(us.url_media_segment(it.url), "news")

    def test_a_rejected_photo_is_visible_in_the_count(self):
        a = adapter()
        a.discover(WINDOW)
        self.assertEqual(a.rejections[us.R_NOT_NEWS_MEDIA], 6)
        self.assertGreater(sum(a.rejections.values()), 0)

    def test_every_media_segment_is_classified(self):
        for seg in us.MEDIA_SEGMENTS:
            url = "https://www.dvidshub.net/%s/1/slug" % seg
            self.assertEqual(us.url_media_segment(url), seg)
            self.assertIsNone(us.canonical_url(url))


# -- 8. Duplicates ------------------------------------------------------------

class TestDuplicatesAreCountedOnce(unittest.TestCase):

    def test_the_same_guid_twice_in_one_feed_is_kept_once(self):
        items, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual(rej[us.R_DUPLICATE_IN_FEED], 1)
        self.assertEqual([i.identity for i in items].count("500001"), 1)

    def test_the_real_feed_carries_no_duplicate_identity_or_url(self):
        items, _ = us.parse_feed(REAL_FEED)
        self.assertEqual(len({i.identity for i in items}), len(items))
        self.assertEqual(len({i.url for i in items}), len(items))


# -- 9. Malformed feeds -------------------------------------------------------

class TestAMalformedFeedIsAFailureNotSilence(unittest.TestCase):

    def test_a_truncated_feed_raises_rather_than_parsing_to_nothing(self):
        with self.assertRaises(us.FeedUnparseable):
            us.parse_feed((FIX / "derived_feed_truncated.xml").read_bytes())

    def test_a_non_xml_body_served_with_200_is_a_listing_failure(self):
        a = adapter(FakeSession(
            feed=(FIX / "derived_feed_not_xml.xml").read_bytes()))
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("did not parse as XML", result.error_detail)

    def test_one_bad_item_does_not_discard_the_good_ones(self):
        items, rej = us.parse_feed(DEFECT_FEED)
        self.assertEqual([i.identity for i in items], ["500001"])
        self.assertEqual(sum(rej.values()), 11)

    def test_every_rejection_reason_is_exercised_by_the_fixture(self):
        _, rej = us.parse_feed(DEFECT_FEED)
        unexercised = [r for r in us.REJECTION_REASONS
                       if r != us.R_OUTSIDE_WINDOW and not rej[r]]
        self.assertEqual(unexercised, [])


# -- 10. Blocked and transient responses --------------------------------------

class TestRefusalsAreRecordedNotRetried(unittest.TestCase):

    def test_robots_403_is_an_auth_failure_exactly_as_pacom_mil_is(self):
        a = adapter(FakeSession(robots_status=403))
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertIn("no basis", result.error_detail)

    def test_a_robots_disallow_stops_the_run(self):
        a = adapter(FakeSession(robots=ROBOTS_DENY_ALL))
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertNotIn(us.FEED, a._session.calls)

    def test_a_disallow_on_the_feed_path_alone_stops_the_run(self):
        a = adapter(FakeSession(robots=ROBOTS_DENY_RSS))
        self.assertEqual(a.discover(WINDOW).status, st.AUTH_FAILURE)

    def test_the_real_robots_file_permits_the_feed(self):
        a = adapter()
        self.assertEqual(a.discover(WINDOW).status, st.OK)

    def test_a_feed_403_is_an_auth_failure_not_a_fetch_failure(self):
        a = adapter(FakeSession(feed_status=403))
        self.assertEqual(a.discover(WINDOW).status, st.AUTH_FAILURE)

    def test_a_feed_500_is_a_listing_failure(self):
        a = adapter(FakeSession(feed_status=500))
        self.assertEqual(a.discover(WINDOW).status, st.LISTING_FAILURE)

    def test_an_item_403_is_recorded_not_retried(self):
        sess = FakeSession(article_status=403)
        a = adapter(sess)
        a.discover(WINDOW)
        before = len(sess.calls)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/x", source_slug=a.slug))
        self.assertEqual(cap.status, st.AUTH_FAILURE)
        self.assertEqual(len(sess.calls) - before, 1)      # asked exactly once

    def test_an_item_404_is_recorded_not_retried(self):
        sess = FakeSession(article_status=404)
        a = adapter(sess)
        a.discover(WINDOW)
        before = len(sess.calls)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/x", source_slug=a.slug))
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertEqual(len(sess.calls) - before, 1)

    def test_a_transport_error_is_retried_then_reported(self):
        sess = FakeSession(raise_on=("/news/",))
        a = adapter(sess)
        a.discover(WINDOW)
        before = len(sess.calls)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/x", source_slug=a.slug))
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertEqual(len(sess.calls) - before, us.MAX_RETRIES + 1)

    def test_an_unreachable_robots_file_is_a_listing_failure(self):
        a = adapter(FakeSession(raise_on=("robots.txt",)))
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("robots.txt unreachable", result.error_detail)

    def test_an_oversized_feed_is_refused_unread(self):
        a = adapter(FakeSession(feed=b"<rss/>" + b"x" * us.MAX_FEED_BYTES))
        self.assertEqual(a.discover(WINDOW).status, st.OVERSIZED_RESPONSE)

    def test_robots_is_re_read_on_every_discover(self):
        a = adapter()
        a.discover(WINDOW)
        a.discover(WINDOW)
        self.assertEqual(a._session.calls.count(us.ROBOTS), 2)


# -- 11. HTML and encoding ----------------------------------------------------

class TestEncodingSurvivesRetrieval(unittest.TestCase):

    def test_typographic_punctuation_is_preserved_not_mojibaked(self):
        body, _ = us.document_body(art("574942"))
        self.assertIn(CURLY_APOSTROPHE, body)
        self.assertIn(CURLY_QUOTE, body)
        self.assertNotIn(MOJIBAKE, body)

    def test_the_em_dash_dateline_survives(self):
        body, _ = us.document_body(art("574946"))
        self.assertTrue(EM_DASH in body or EN_DASH in body)

    def test_html_entities_are_decoded_not_left_raw(self):
        body, _ = us.document_body(art("574942"))
        for ent in ("&amp;", "&#39;", "&quot;", "&nbsp;"):
            self.assertNotIn(ent, body)

    def test_markup_does_not_leak_into_the_stored_text(self):
        for ident in ARTICLES:
            body, _ = us.document_body(art(ident))
            self.assertNotIn("<p", body)
            self.assertNotIn("</", body)
            self.assertNotIn("<script", body)

    def test_a_bytes_feed_and_a_str_feed_parse_identically(self):
        a, _ = us.parse_feed(REAL_FEED)
        b, _ = us.parse_feed(REAL_FEED.decode("utf-8"))
        self.assertEqual([i.identity for i in a], [i.identity for i in b])
        self.assertEqual([i.title for i in a], [i.title for i in b])


# -- 12. The adapter's own declarations ---------------------------------------

class TestTheAdapterDeclaresWhatItIs(unittest.TestCase):

    def test_it_is_not_a_stub(self):
        self.assertTrue(us.USDvidsAdapter.implemented)

    def test_healthcheck_reports_shadow_not_ok(self):
        self.assertEqual(adapter().healthcheck().status, st.SKIPPED_DISABLED)

    def test_the_user_agent_identifies_the_project_honestly(self):
        self.assertIn("ChinaMilWatch", us.USER_AGENT)
        self.assertIn("http", us.USER_AGENT)
        for evasive in ("Mozilla", "Chrome", "Safari", "Gecko"):
            self.assertNotIn(evasive, us.USER_AGENT)

    def test_the_request_interval_is_not_aggressive(self):
        self.assertGreaterEqual(us.REQUEST_INTERVAL, 2.0)

    def test_the_module_does_not_name_production_paths_in_code(self):
        # The docstring names both, to say it reaches neither. What matters is
        # that no executable line does, so the prose is stripped before the
        # assertion rather than the assertion being weakened to accommodate it.
        source = (REPO_ROOT / "scraper" / "sources" / "us_dvids.py").read_text(
            encoding="utf-8")
        body = source.split('"""', 2)[2]
        self.assertNotIn("pla_watch.db", body)
        self.assertNotIn("output/", body)

    def test_identity_survives_a_reworded_slug_end_to_end(self):
        # The same document under a slug the feed never emitted still resolves,
        # because the id is the identity.
        a = adapter()
        a.discover(WINDOW)
        cap = a.fetch(CandidateReference(
            url="https://www.dvidshub.net/news/574946/renamed-by-the-publisher",
            source_slug=a.slug))
        res = a.extract(cap)
        self.assertEqual(res.status, st.OK)
        self.assertEqual(res.documents[0].extra["source_identity"], "574946")


if __name__ == "__main__":
    unittest.main()
