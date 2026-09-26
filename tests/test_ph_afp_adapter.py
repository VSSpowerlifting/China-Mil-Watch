"""
Philippines (AFP) shadow adapter: policy, discovery, retrieval, extraction.

The collector's job in this phase is to prove it can retrieve and identify
official documents reliably. These tests' job is to prove it refuses everything
it cannot identify honestly, and that it never reports a failure as silence.

Everything runs from saved responses of `api.afp.mil.ph` (tests/fixtures/
ph_afp) or from those responses edited in memory. No network, no
tracked-database access, no writes outside a temporary directory.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                         # noqa: E402
from core.collection.contract import (                           # noqa: E402
    CandidateReference, CollectionWindow)
from scraper.sources import ph_afp as ph                          # noqa: E402
from tests import ph_afp_support as S                             # noqa: E402

WIDE = CollectionWindow(target_date=date(2026, 9, 26), lookback_days=4000)


def capture_for(adapter, ident):
    """Discover-free fetch of one real detail through a fake session."""
    d = S.detail_obj(ident)
    ref = CandidateReference(ph.canonical_url(d["slug"]), "ph_afp_articles")
    return adapter.fetch(ref)


class TestUrlsAndIdentity(unittest.TestCase):

    def test_a_slug_round_trips_through_the_canonical_url(self):
        url = ph.canonical_url("afp-advances-chr-leadership")
        self.assertEqual(url, "https://www.afp.mil.ph/news/afp-advances-chr-leadership")
        self.assertEqual(ph.slug_from_canonical(url), "afp-advances-chr-leadership")

    def test_the_detail_url_is_the_api_route_keyed_by_slug(self):
        self.assertEqual(ph.detail_url("a-b"), "https://api.afp.mil.ph/articles/a-b/")

    def test_a_non_slug_is_not_turned_into_a_url(self):
        for bad in ("", "Has Caps", "a/b", "../x", "a b", None, 12, "-a", "a--b"):
            with self.subTest(slug=bad):
                self.assertIsNone(ph.canonical_url(bad))
                self.assertIsNone(ph.detail_url(bad))

    def test_no_foreign_host_is_accepted_as_a_canonical_url(self):
        for host in ("evil.test", "www.afp.mil.ph.evil.test", "afp.mil.ph.evil.test",
                     "api.afp.mil.ph", "www.dnd.gov.ph", "localhost"):
            with self.subTest(host=host):
                self.assertIsNone(ph.slug_from_canonical(
                    "https://%s/news/some-slug" % host))

    def test_only_the_article_route_is_a_canonical_url(self):
        for path in ("/news/", "/news/a/b", "/articles/a", "/news/a?x=1",
                     "/news/a#frag", "/news/UPPER"):
            with self.subTest(path=path):
                self.assertIsNone(ph.slug_from_canonical(
                    "https://www.afp.mil.ph" + path))

    def test_the_bare_host_is_a_permitted_site_host(self):
        self.assertEqual(
            ph.slug_from_canonical("https://afp.mil.ph/news/x-y"), "x-y")

    def test_only_the_api_host_under_articles_is_a_permitted_retrieval_url(self):
        self.assertTrue(ph.is_permitted_api_url("https://api.afp.mil.ph/articles/?page=2"))
        for bad in ("https://evil.test/articles/", "https://api.afp.mil.ph/other/",
                    "https://www.afp.mil.ph/articles/", "ftp://api.afp.mil.ph/articles/",
                    "https://api.afp.mil.ph.evil.test/articles/", ""):
            with self.subTest(url=bad):
                self.assertFalse(ph.is_permitted_api_url(bad))

    def test_identity_is_the_positive_integer_id(self):
        self.assertEqual(ph.source_identity(1384), "afp:1384")
        self.assertEqual(ph.source_identity("1384"), "afp:1384")

    def test_anything_else_is_not_an_identity(self):
        for bad in (True, False, 0, -3, "12a", "", None, 1.5, [], {}):
            with self.subTest(value=bad):
                self.assertIsNone(ph.source_identity(bad))


class TestDates(unittest.TestCase):

    def test_a_stated_offset_is_kept_and_the_utc_instant_derived(self):
        local, original, utc = ph.parse_published_at("2026-09-15T16:00:00+08:00")
        self.assertEqual(local, "2026-09-15")
        self.assertEqual(original, "2026-09-15T16:00:00+08:00")
        self.assertEqual(utc, "2026-09-15T08:00:00+00:00")

    def test_the_local_date_is_the_date_in_the_stated_offset_not_the_utc_date(self):
        local, _, utc = ph.parse_published_at("2026-09-15T00:30:00+08:00")
        self.assertEqual(local, "2026-09-15")
        self.assertEqual(utc, "2026-09-14T16:30:00+00:00")

    def test_microseconds_in_the_real_api_format_parse(self):
        got = ph.parse_published_at("2026-06-12T15:33:51.401316+08:00")
        self.assertEqual(got[0], "2026-06-12")

    def test_a_short_fraction_parses(self):
        self.assertIsNotNone(ph.parse_published_at("2026-06-12T15:33:51.4+08:00"))

    def test_z_is_an_explicit_offset(self):
        self.assertEqual(ph.parse_published_at("2026-06-12T01:00:00Z")[2],
                         "2026-06-12T01:00:00+00:00")

    def test_a_timestamp_with_no_offset_is_refused_not_assumed(self):
        self.assertIsNone(ph.parse_published_at("2026-09-15T16:00:00"))
        self.assertIsNone(ph.parse_published_at("2026-09-15"))

    def test_garbage_is_refused(self):
        for bad in ("", None, 12, "yesterday", "2026-13-40T00:00:00+08:00",
                    "2026-09-15T25:00:00+08:00", "2026-09-15T16:00:00+99:00"):
            with self.subTest(value=bad):
                self.assertIsNone(ph.parse_published_at(bad))


class TestText(unittest.TestCase):

    def test_paragraphs_become_blank_line_separated_text(self):
        self.assertEqual(ph.html_to_text("<p>One.</p><p>Two <strong>bold</strong>.</p>"),
                         "One.\n\nTwo bold.")

    def test_source_whitespace_inside_a_paragraph_is_collapsed(self):
        self.assertEqual(ph.html_to_text("<p>a\r\n   b\n\tc</p>"), "a b c")

    def test_a_break_is_a_line_break_and_entities_are_decoded(self):
        self.assertEqual(ph.html_to_text("<p>a<br>b &amp; c&nbsp;d</p>"),
                         "a\nb & c d")

    def test_scripts_styles_and_comments_are_not_text(self):
        self.assertEqual(ph.html_to_text(
            "<style>x{}</style><p>Kept</p><script>evil()</script><!-- c -->"),
            "Kept")

    def test_adjacent_table_cells_are_not_joined_into_one_word(self):
        self.assertEqual(
            ph.html_to_text("<table><tr><td>Alpha</td><td>Beta</td></tr></table>"),
            "Alpha\n\nBeta")

    def test_an_image_only_fragment_has_no_text(self):
        self.assertEqual(ph.html_to_text('<p><img src="/media/a.jpg" alt="x"></p>'), "")
        self.assertEqual(ph.html_to_text(""), "")
        self.assertEqual(ph.html_to_text(None), "")

    def test_no_word_is_added_or_removed(self):
        d = S.detail_obj(1384)
        text = ph.html_to_text(d["body_html"])
        self.assertTrue(text.startswith(
            "CAMP AGUINALDO, Quezon City -- The Armed Forces of the Philippines"))
        self.assertTrue(text.endswith("Photos by SSg Ambay PA / PAOAFP"))

    def test_a_current_cms_intro_that_prefixes_the_body_is_not_repeated(self):
        d = S.detail_obj(1384)
        text, how = ph.assemble_text(d["intro_html"], d["body_html"])
        self.assertEqual(how, "body")
        self.assertEqual(text.count("CAMP AGUINALDO"), 1)

    def test_a_migrated_items_intro_and_body_are_both_kept(self):
        d = S.detail_obj(1211)
        text, how = ph.assemble_text(d["intro_html"], d["body_html"])
        self.assertEqual(how, "intro+body")
        self.assertTrue(text.startswith("CAMP AGUINALDO, Quezon City - The Armed Forces"))
        self.assertTrue(text.endswith("Col Baclor added."))
        self.assertIn("The report turned out to be positive", text)

    def test_a_dateline_only_in_the_intro_does_not_repeat_the_opening_paragraph(self):
        # The measured current-CMS defect: the intro carries "CAMP AGUINALDO,
        # Quezon City -- " and the body starts after it, so the intro is not a
        # prefix of the body but the body's first paragraph is inside the intro.
        intro = ("<p>CAMP AGUINALDO, Quezon City -- The Armed Forces of the "
                 "Philippines completed the exercise.</p>")
        body = ("<p>The Armed Forces of the Philippines completed the "
                "exercise.</p><p>Second paragraph of the release.</p>")
        text, how = ph.assemble_text(intro, body)
        self.assertEqual(how, "intro+body")
        self.assertEqual(text.count("completed the exercise"), 1)
        self.assertTrue(text.startswith("CAMP AGUINALDO, Quezon City --"))
        self.assertTrue(text.endswith("Second paragraph of the release."))

    def test_a_trailing_intro_paragraph_already_in_the_body_is_not_repeated(self):
        intro = ("<p>First paragraph unique to the introduction.</p>"
                 "<p>The shared paragraph that also opens the body.</p>")
        body = ("<p>The shared paragraph that also opens the body.</p>"
                "<p>The remainder of the article.</p>")
        text, _ = ph.assemble_text(intro, body)
        self.assertEqual(text.count("The shared paragraph"), 1)
        self.assertEqual(text.split("\n\n"), [
            "First paragraph unique to the introduction.",
            "The shared paragraph that also opens the body.",
            "The remainder of the article."])

    def test_a_short_repeated_line_is_not_treated_as_overlap(self):
        text, how = ph.assemble_text("<p>Photos by PAO</p><p>Intro text here.</p>",
                                     "<p>Photos by PAO</p><p>Body text here now.</p>")
        self.assertEqual(text.count("Photos by PAO"), 2)

    def test_the_real_migrated_item_is_unchanged_by_the_overlap_rule(self):
        d = S.detail_obj(1211)
        text, how = ph.assemble_text(d["intro_html"], d["body_html"])
        self.assertEqual(how, "intro+body")
        self.assertEqual(len(text.split("\n\n")),
                         len(ph.html_to_text(d["intro_html"]).split("\n\n"))
                         + len(ph.html_to_text(d["body_html"]).split("\n\n")))

    def test_intro_only_and_body_only_and_neither(self):
        self.assertEqual(ph.assemble_text("<p>I</p>", ""), ("I", "intro"))
        self.assertEqual(ph.assemble_text("", "<p>B</p>"), ("B", "body"))
        self.assertEqual(ph.assemble_text("", ""), ("", "none"))

    def test_the_fingerprint_ignores_the_view_counter(self):
        d = S.detail_obj(1384)
        e = dict(d, hits=d["hits"] + 500, updated_at="2027-01-01T00:00:00+08:00")
        self.assertEqual(ph.revision_fingerprint(d), ph.revision_fingerprint(e))

    def test_the_fingerprint_moves_when_the_slug_moves(self):
        d = S.detail_obj(1384)
        self.assertNotEqual(ph.revision_fingerprint(d),
                            ph.revision_fingerprint(dict(d, slug="renamed")))

    def test_the_fingerprint_moves_when_the_text_or_title_moves(self):
        d = S.detail_obj(1384)
        base = ph.revision_fingerprint(d)
        self.assertNotEqual(base, ph.revision_fingerprint(
            dict(d, body_html=d["body_html"] + "<p>Correction.</p>")))
        self.assertNotEqual(base, ph.revision_fingerprint(dict(d, title="Retitled")))


class TestPolicy(unittest.TestCase):
    """The robots position, case by case. See the adapter docstring."""

    def discover(self, session):
        a = S.adapter(session)
        return a, a.discover(WIDE)

    def test_both_hosts_robots_are_read_on_every_discovery(self):
        sess = S.session_for()
        self.discover(sess)
        self.assertIn(ph.ROBOTS_WWW, sess.calls)
        self.assertIn(ph.ROBOTS_API, sess.calls)
        self.discover(sess)
        self.assertEqual(sess.calls.count(ph.ROBOTS_WWW), 2)
        self.assertEqual(sess.calls.count(ph.ROBOTS_API), 2)

    def test_a_404_on_the_api_hosts_robots_is_no_rules_not_a_refusal(self):
        a, r = self.discover(S.session_for())
        self.assertEqual(r.status, st.OK)
        self.assertEqual(a.observed["api_robots_status"], 404)
        self.assertEqual(a.observed["www_robots_status"], 200)

    def test_the_x_robots_tag_is_recorded_not_obeyed_as_a_refusal(self):
        a, r = self.discover(S.session_for())
        self.assertEqual(r.status, st.OK)
        self.assertEqual(a.observed["api_x_robots_tag"], "noindex, nofollow")

    def test_a_403_on_the_api_hosts_robots_is_a_hard_failure(self):
        a, r = self.discover(S.session_for(robots_api_status=403,
                                           robots_api="Forbidden"))
        self.assertEqual(r.status, st.AUTH_FAILURE)
        self.assertEqual(r.references, [])

    def test_a_403_on_the_www_robots_is_a_hard_failure(self):
        a, r = self.discover(S.session_for(robots_www_status=403,
                                           robots_www="Forbidden"))
        self.assertEqual(r.status, st.AUTH_FAILURE)

    def test_a_challenge_page_on_robots_is_recorded_as_a_challenge(self):
        a, r = self.discover(S.session_for(
            robots_api_status=403, robots_api=S.CHALLENGE_HTML))
        self.assertEqual(r.status, st.ACCESS_CHALLENGED)

    def test_a_robots_5xx_means_the_policy_could_not_be_read(self):
        a, r = self.discover(S.session_for(robots_api_status=503,
                                           robots_api="down"))
        self.assertEqual(r.status, st.LISTING_FAILURE)

    def test_a_disallow_on_the_api_host_stops_before_any_listing_request(self):
        sess = S.session_for(robots_api_status=200,
                             robots_api=S.ROBOTS_DENY_ARTICLES)
        a, r = self.discover(sess)
        self.assertEqual(r.status, st.AUTH_FAILURE)
        self.assertFalse([c for c in sess.calls if c.startswith(ph.LIST_URL)])

    def test_a_disallow_on_the_www_host_stops_the_run(self):
        sess = S.session_for(robots_www=S.ROBOTS_DENY_ALL)
        a, r = self.discover(sess)
        self.assertEqual(r.status, st.AUTH_FAILURE)
        self.assertFalse([c for c in sess.calls if c.startswith(ph.LIST_URL)])

    def test_a_robots_transport_error_is_a_status_not_an_exception(self):
        sess = S.session_for(raise_on={"api.afp.mil.ph/robots.txt": S.Boom})
        a, r = self.discover(sess)
        self.assertEqual(r.status, st.LISTING_FAILURE)


class TestDiscovery(unittest.TestCase):

    def test_the_real_first_page_yields_references_with_hint_dates(self):
        sess = S.FakeSession(pages={
            S.page_url(1): (S.FIX / "list_page_default.json").read_bytes()})
        a = S.adapter(sess)
        r = a.discover(WIDE)
        self.assertEqual(r.status, st.OK)
        self.assertEqual(len(r.references), 12)
        self.assertEqual(r.references[0].hint_published_date, "2026-09-15")
        self.assertTrue(all(x.url.startswith("https://www.afp.mil.ph/news/")
                            for x in r.references))
        self.assertEqual(a.observed["api_reported_count"], 1076)

    def test_pagination_follows_next_and_stops_on_the_real_last_page(self):
        first = (S.FIX / "list_page_default.json").read_bytes()
        last = (S.FIX / "list_page_last.json").read_bytes()
        sess = S.FakeSession(pages={S.page_url(1): first,
                                    "https://api.afp.mil.ph/articles/?page=2": last})
        a = S.adapter(sess)
        r = a.discover(WIDE)
        self.assertEqual(r.status, st.OK)
        self.assertEqual(a.observed["list_pages"], 2)
        self.assertEqual(a.observed["listed_items"], 20)
        self.assertEqual(a.observed["listing_end"], "next_null")
        self.assertEqual(len(r.references), 20)

    def test_the_real_invalid_page_404_ends_the_list_and_is_not_a_failure(self):
        first = (S.FIX / "list_page_default.json").read_bytes()
        sess = S.FakeSession(pages={S.page_url(1): first})   # page 2 -> real 404
        a = S.adapter(sess)
        r = a.discover(WIDE)
        self.assertEqual(r.status, st.OK)
        self.assertEqual(a.observed["listing_end"], "invalid_page")

    def test_the_api_total_does_not_stand_in_for_what_was_listed(self):
        first = (S.FIX / "list_page_default.json").read_bytes()
        a = S.adapter(S.FakeSession(pages={S.page_url(1): first}))
        a.discover(WIDE)
        self.assertEqual(a.observed["api_reported_count"], 1076)
        self.assertEqual(a.observed["listed_items"], 12)
        self.assertTrue(a.observed["count_mismatch"])

    def test_a_matching_count_is_not_a_mismatch(self):
        a = S.adapter(S.session_for())
        a.discover(WIDE)
        self.assertFalse(a.observed["count_mismatch"])

    def test_a_404_on_the_first_page_is_a_listing_failure(self):
        a = S.adapter(S.FakeSession())
        r = a.discover(WIDE)
        self.assertEqual(r.status, st.LISTING_FAILURE)

    def test_a_next_link_off_the_permitted_host_is_refused_not_followed(self):
        page = S.list_page(S.real_list_from_details((1384,)),
                           next_url="https://evil.test/articles/?page=2")
        sess = S.FakeSession(pages={S.page_url(1): page})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.DISALLOWED_REDIRECT)
        self.assertNotIn("https://evil.test/articles/?page=2", sess.calls)

    def test_a_looping_next_link_is_a_failure_not_an_endless_walk(self):
        url = S.page_url(1)
        page = S.list_page(S.real_list_from_details((1384,)), next_url=url)
        r = S.adapter(S.FakeSession(pages={url: page})).discover(WIDE)
        self.assertEqual(r.status, st.LISTING_FAILURE)
        self.assertIn("did not terminate", r.error_detail)

    def test_a_listing_longer_than_the_page_cap_is_a_failure(self):
        pages = {}
        for n in range(1, 6):
            pages[S.page_url(n)] = S.list_page(
                S.real_list_from_details((1384,)),
                next_url="https://api.afp.mil.ph/articles/?page_size=100&page=%d" % (n + 1))
        a = S.adapter(S.FakeSession(pages=pages), max_pages=3)
        r = a.discover(WIDE)
        self.assertEqual(r.status, st.LISTING_FAILURE)
        self.assertEqual(a.observed["listing_end"], "truncated")

    def test_an_edge_challenge_instead_of_a_listing_is_recorded_and_not_retried(self):
        sess = S.FakeSession(pages={S.page_url(1): S.FakeResponse(
            S.CHALLENGE_HTML, 200, {"Content-Type": "text/html"})})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.ACCESS_CHALLENGED)
        self.assertEqual(sess.calls.count(S.page_url(1)), 1)

    def test_a_403_listing_is_an_auth_failure(self):
        sess = S.FakeSession(pages={S.page_url(1): S.FakeResponse(
            b"forbidden", 403, {"Content-Type": "text/plain"})})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.AUTH_FAILURE)

    def test_a_5xx_listing_is_a_listing_failure(self):
        sess = S.FakeSession(pages={S.page_url(1): S.FakeResponse(
            b"oops", 502, {"Content-Type": "text/plain"})})
        self.assertEqual(S.adapter(sess).discover(WIDE).status,
                         st.LISTING_FAILURE)

    def test_the_spa_shell_returned_in_place_of_json_is_an_unexpected_content_type(self):
        shell = "<!doctype html><html><body><div id=root></div></body></html>"
        sess = S.FakeSession(pages={S.page_url(1): S.FakeResponse(
            shell, 200, {"Content-Type": "text/html"})})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.UNEXPECTED_CONTENT_TYPE)

    def test_a_listing_that_is_not_json_is_a_listing_failure(self):
        sess = S.FakeSession(pages={S.page_url(1): b"not json {"})
        self.assertEqual(S.adapter(sess).discover(WIDE).status,
                         st.LISTING_FAILURE)

    def test_a_listing_with_the_wrong_shape_is_a_listing_failure(self):
        sess = S.FakeSession(pages={S.page_url(1): json.dumps(
            {"items": []}).encode()})
        self.assertEqual(S.adapter(sess).discover(WIDE).status,
                         st.LISTING_FAILURE)

    def test_an_empty_results_array_is_a_shape_change_not_a_quiet_day(self):
        sess = S.FakeSession(pages={S.page_url(1): S.list_page([])})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.LISTING_FAILURE)
        self.assertIn("zero items", r.error_detail)

    def test_an_oversized_listing_page_is_refused(self):
        big = b" " * (ph.MAX_LIST_BYTES + 1)
        sess = S.FakeSession(pages={S.page_url(1): big})
        self.assertEqual(S.adapter(sess).discover(WIDE).status,
                         st.OVERSIZED_RESPONSE)

    def test_a_transport_error_on_the_listing_is_a_status_not_an_exception(self):
        sess = S.session_for(raise_on={"articles/?": S.Boom})
        r = S.adapter(sess).discover(WIDE)
        self.assertEqual(r.status, st.LISTING_FAILURE)
        self.assertIn("unreachable", r.error_detail)

    def test_a_timeout_on_the_listing_is_named_as_one(self):
        sess = S.session_for(raise_on={"articles/?": S.BoomTimeout})
        self.assertEqual(S.adapter(sess).discover(WIDE).status, st.TIMEOUT)

    def test_a_transport_error_is_retried_a_bounded_number_of_times(self):
        sess = S.session_for(raise_on={"articles/?": S.Boom})
        S.adapter(sess).discover(WIDE)
        listing_calls = [c for c in sess.calls if c.startswith(ph.LIST_URL)]
        self.assertEqual(len(listing_calls), ph.MAX_RETRIES + 1)

    def test_consecutive_requests_are_never_closer_than_the_request_interval(self):
        # A fake clock advanced only by the adapter's own sleeps, so the
        # spacing is measured, not assumed. Includes the transport-retry
        # backoff, which must not undercut the interval either.
        from unittest import mock
        clock = [1000.0]
        stamps = []
        sess = S.session_for(raise_on={"articles/?": S.Boom})
        real_get = sess.get

        def timed_get(url, timeout=None, headers=None):
            stamps.append(clock[0])
            return real_get(url, timeout=timeout, headers=headers)
        sess.get = timed_get
        a = ph.PHAfpAdapter(S.FakeSource(), session=sess, cap=0,
                            sleeper=lambda s: clock.__setitem__(0, clock[0] + s))
        with mock.patch.object(ph.time, "monotonic", lambda: clock[0]):
            a.discover(WIDE)
        self.assertGreater(len(stamps), 4)      # robots x2, then listing retries
        gaps = [b - a_ for a_, b in zip(stamps, stamps[1:])]
        self.assertGreaterEqual(min(gaps), ph.REQUEST_INTERVAL - 1e-9)

    def test_a_404_is_not_retried(self):
        sess = S.FakeSession()
        S.adapter(sess).discover(WIDE)
        self.assertEqual(len([c for c in sess.calls
                              if c.startswith(ph.LIST_URL)]), 1)

    def test_requests_are_spaced_and_identified(self):
        waits = []
        sess = S.session_for()
        headers_seen = []
        real_get = sess.get

        def spy(url, timeout=None, headers=None):
            headers_seen.append(headers)
            return real_get(url, timeout=timeout, headers=headers)
        sess.get = spy
        a = ph.PHAfpAdapter(S.FakeSource(), session=sess, cap=0,
                            sleeper=waits.append)
        a.discover(WIDE)
        self.assertTrue(headers_seen)
        for h in headers_seen:
            self.assertEqual(h["User-Agent"], ph.USER_AGENT)
        self.assertIn("ChinaMilWatch", ph.USER_AGENT)
        self.assertGreaterEqual(ph.REQUEST_INTERVAL, 2.0)


class TestWindowAndRejections(unittest.TestCase):

    def build(self, entries, **kw):
        sess = S.FakeSession(pages={S.page_url(1): S.list_page(entries)})
        a = S.adapter(sess, **kw)
        return a

    def entry(self, ident, published, **over):
        e = S.list_entry(S.detail_obj(1384))
        e.update(id=ident, slug="item-%d" % ident, title="Item %d" % ident,
                 published_at=published)
        e.update(over)
        return e

    def test_the_window_uses_the_date_in_the_stated_offset(self):
        # 00:30 on 09-15 in Manila is still 09-14 in UTC. A reader of the AFP
        # site sees the 15th, so a window for the 15th contains it and a window
        # for the 14th does not.
        entries = [self.entry(1, "2026-09-15T00:30:00+08:00")]
        a = self.build(entries)
        self.assertEqual(len(a.discover(CollectionWindow(date(2026, 9, 15), 0)
                                        ).references), 1)
        a = self.build(entries)
        r = a.discover(CollectionWindow(date(2026, 9, 14), 0))
        self.assertEqual(r.status, st.OK_NO_PUBLICATIONS)
        self.assertEqual(a.rejections[ph.R_OUTSIDE_WINDOW], 1)

    def test_lookback_reaches_back_and_never_forward(self):
        entries = [self.entry(1, "2026-09-10T10:00:00+08:00"),
                   self.entry(2, "2026-09-15T10:00:00+08:00"),
                   self.entry(3, "2026-09-20T10:00:00+08:00")]
        a = self.build(entries)
        r = a.discover(CollectionWindow(date(2026, 9, 15), lookback_days=5))
        self.assertEqual([x.url.rsplit("/", 1)[1] for x in r.references],
                         ["item-2", "item-1"])
        self.assertEqual(a.rejections[ph.R_OUTSIDE_WINDOW], 1)

    def test_selection_is_newest_first_whatever_order_the_api_used(self):
        entries = [self.entry(1, "2026-09-10T10:00:00+08:00"),
                   self.entry(3, "2026-09-14T10:00:00+08:00"),
                   self.entry(2, "2026-09-12T10:00:00+08:00")]
        r = self.build(entries).discover(WIDE)
        self.assertEqual([x.url.rsplit("/", 1)[1] for x in r.references],
                         ["item-3", "item-2", "item-1"])

    def test_a_backdated_item_deep_in_the_list_is_still_found(self):
        # The list is walked to its end and never stops at the first date that
        # falls outside the window, so an item published late but stored early
        # in the list order is not lost.
        entries = [self.entry(9, "2026-09-15T10:00:00+08:00"),
                   self.entry(8, "2024-01-01T10:00:00+08:00"),
                   self.entry(7, "2026-09-14T10:00:00+08:00")]
        r = self.build(entries).discover(
            CollectionWindow(date(2026, 9, 15), lookback_days=2))
        self.assertEqual(len(r.references), 2)

    def test_the_cap_keeps_the_newest_and_counts_the_rest(self):
        entries = [self.entry(i, "2026-09-%02dT10:00:00+08:00" % i)
                   for i in range(1, 11)]
        a = self.build(entries, cap=3)
        r = a.discover(WIDE)
        self.assertEqual([x.url.rsplit("/", 1)[1] for x in r.references],
                         ["item-10", "item-9", "item-8"])
        self.assertEqual(a.rejections[ph.R_BEYOND_CAP], 7)

    def test_an_empty_window_is_a_success_not_a_failure(self):
        a = self.build([self.entry(1, "2026-09-15T10:00:00+08:00")])
        r = a.discover(CollectionWindow(date(2020, 1, 1), 0))
        self.assertEqual(r.status, st.OK_NO_PUBLICATIONS)
        self.assertEqual(r.references, [])
        self.assertFalse(st.is_failure(r.status))

    def test_a_non_press_category_is_counted_and_rejected(self):
        a = self.build([self.entry(1, "2026-09-15T10:00:00+08:00"),
                        self.entry(2, "2026-09-15T10:00:00+08:00",
                                   category_slug="afp-logos"),
                        self.entry(3, "2026-09-15T10:00:00+08:00",
                                   category_slug="some-new-category")])
        r = a.discover(WIDE)
        self.assertEqual(len(r.references), 1)
        self.assertEqual(a.rejections[ph.R_NON_PRESS_CATEGORY], 2)

    def test_uncategorised_is_collected_because_it_holds_real_statements(self):
        a = self.build([self.entry(1, "2026-09-15T10:00:00+08:00",
                                   category_slug="uncategorised")])
        self.assertEqual(len(a.discover(WIDE).references), 1)

    def test_a_duplicate_id_or_slug_within_the_list_is_kept_once(self):
        a = self.build([
            self.entry(1, "2026-09-15T10:00:00+08:00"),
            self.entry(1, "2026-09-15T10:00:00+08:00", slug="other-slug"),
            self.entry(2, "2026-09-15T10:00:00+08:00", slug="item-1"),
        ])
        r = a.discover(WIDE)
        self.assertEqual(len(r.references), 1)
        self.assertEqual(a.rejections[ph.R_DUPLICATE_IN_LIST], 2)

    def test_each_malformed_entry_is_counted_under_exactly_one_reason(self):
        good = self.entry(1, "2026-09-15T10:00:00+08:00")
        cases = {
            ph.R_MISSING_ID: self.entry(2, "2026-09-15T10:00:00+08:00", id=None),
            ph.R_INVALID_SLUG: self.entry(3, "2026-09-15T10:00:00+08:00",
                                          slug="Not A Slug"),
            ph.R_MISSING_TITLE: self.entry(4, "2026-09-15T10:00:00+08:00",
                                           title="  "),
            ph.R_MISSING_PUBDATE: self.entry(5, "2026-09-15T10:00:00+08:00",
                                             published_at=None),
            ph.R_UNPARSEABLE_PUBDATE: self.entry(
                6, "2026-09-15T10:00:00+08:00", published_at="2026-09-15T10:00:00"),
        }
        a = self.build([good] + list(cases.values()) + ["not a dict"])
        r = a.discover(WIDE)
        self.assertEqual(len(r.references), 1)
        for reason in cases:
            if reason == ph.R_MISSING_ID:
                continue        # asserted below: two entries share this reason
            with self.subTest(reason=reason):
                self.assertEqual(a.rejections[reason], 1)
        # the id=None entry and the non-dict entry both have no id: counted,
        # never raised
        self.assertEqual(a.rejections[ph.R_MISSING_ID], 2)
        self.assertEqual(sum(a.rejections.values()), 6)

    def test_two_different_ids_with_the_same_title_and_date_stay_two_records(self):
        # The real API holds such pairs (ids 1330 and 1331, 2026-07-21).
        entries = S.real_list_from_details((1330, 1331))
        a = self.build(entries)
        r = a.discover(WIDE)
        self.assertEqual(len(r.references), 2)
        self.assertEqual(a.observed["same_title_same_date_groups"], 1)

    def test_every_rejection_reason_is_present_in_the_taxonomy(self):
        a = self.build([self.entry(1, "2026-09-15T10:00:00+08:00")])
        a.discover(WIDE)
        self.assertEqual(set(a.rejections), set(ph.REJECTION_REASONS))
        self.assertEqual(len(ph.REJECTION_REASONS), len(set(ph.REJECTION_REASONS)))

    def test_the_listed_date_range_is_reported(self):
        a = self.build([self.entry(1, "2024-10-31T10:00:00+08:00"),
                        self.entry(2, "2026-06-12T15:33:51.401316+08:00")])
        a.discover(WIDE)
        self.assertEqual(a.observed["listed_date_min"], "2024-10-31")
        self.assertEqual(a.observed["listed_date_max"], "2026-06-12")


class TestFetch(unittest.TestCase):

    def setUp(self):
        self.sess = S.session_for()
        self.a = S.adapter(self.sess)
        self.a.discover(WIDE)

    def test_the_preserved_payload_is_the_exact_response_bytes(self):
        cap = capture_for(self.a, 1384)
        self.assertEqual(cap.status, st.OK)
        raw = S.detail_bytes(1384)
        # served through json.dumps in the session, so compare to what the
        # fake actually served rather than to the file on disk
        served = self.sess.details[S.detail_obj(1384)["slug"]]
        self.assertEqual(cap.body.encode("utf-8"), served)
        self.assertEqual(cap.payload_sha256, hashlib.sha256(served).hexdigest())
        self.assertEqual(cap.payload_bytes, len(served))
        self.assertTrue(raw)   # fixture present

    def test_the_requested_url_is_the_api_route_and_the_reference_stays_canonical(self):
        cap = capture_for(self.a, 1384)
        slug = S.detail_obj(1384)["slug"]
        self.assertEqual(cap.requested_url, "https://api.afp.mil.ph/articles/%s/" % slug)
        self.assertEqual(cap.reference.url, "https://www.afp.mil.ph/news/%s" % slug)
        self.assertEqual(cap.http_status, 200)
        self.assertTrue(cap.retrieved_at)

    def test_a_404_on_an_item_is_a_fetch_failure_and_is_not_retried(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        del sess.details[slug]
        a = S.adapter(sess)
        a.discover(WIDE)
        before = len(sess.calls)
        cap = capture_for(a, 1384)
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertEqual(cap.http_status, 404)
        self.assertEqual(len(sess.calls) - before, 1)

    def test_a_403_on_an_item_is_an_auth_failure(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = S.FakeResponse(b"no", 403, {"Content-Type": "text/plain"})
        a = S.adapter(sess)
        self.assertEqual(capture_for(a, 1384).status, st.AUTH_FAILURE)

    def test_a_challenge_on_an_item_is_recorded_as_one(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = S.FakeResponse(
            S.CHALLENGE_HTML, 403, {"Content-Type": "text/html"})
        self.assertEqual(capture_for(S.adapter(sess), 1384).status,
                         st.ACCESS_CHALLENGED)

    def test_a_429_is_a_fetch_failure_and_is_not_retried_in_a_loop(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = S.FakeResponse(b"slow down", 429,
                                            {"Content-Type": "text/plain"})
        a = S.adapter(sess)
        before = len(sess.calls)
        self.assertEqual(capture_for(a, 1384).status, st.FETCH_FAILURE)
        self.assertEqual(len(sess.calls) - before, 1)

    def test_a_redirect_off_the_permitted_host_is_refused(self):
        sess = S.session_for(final_url="https://evil.test/articles/x/")
        a = S.adapter(sess)
        cap = capture_for(a, 1384)
        self.assertEqual(cap.status, st.DISALLOWED_REDIRECT)
        self.assertIsNone(cap.body)

    def test_html_in_place_of_json_is_an_unexpected_content_type(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = S.FakeResponse(
            "<html></html>", 200, {"Content-Type": "text/html"})
        self.assertEqual(capture_for(S.adapter(sess), 1384).status,
                         st.UNEXPECTED_CONTENT_TYPE)

    def test_an_oversized_detail_is_refused(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = b" " * (ph.MAX_DETAIL_BYTES + 1)
        self.assertEqual(capture_for(S.adapter(sess), 1384).status,
                         st.OVERSIZED_RESPONSE)

    def test_bytes_that_are_not_utf8_are_not_stored_lossily(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        sess.details[slug] = b'{"title": "\xff\xfe"}'
        cap = capture_for(S.adapter(sess), 1384)
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertIn("UTF-8", cap.error_detail)

    def test_a_transport_error_on_an_item_is_a_status_not_an_exception(self):
        slug = S.detail_obj(1384)["slug"]
        sess = S.session_for(raise_on={"/articles/%s/" % slug: S.Boom})
        a = S.adapter(sess)
        cap = capture_for(a, 1384)
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertEqual(len([c for c in sess.calls
                              if c.endswith("/articles/%s/" % slug)]),
                         ph.MAX_RETRIES + 1)

    def test_an_item_timeout_is_named_as_one(self):
        slug = S.detail_obj(1384)["slug"]
        sess = S.session_for(raise_on={"/articles/%s/" % slug: S.BoomTimeout})
        self.assertEqual(capture_for(S.adapter(sess), 1384).status, st.TIMEOUT)

    def test_an_off_host_reference_is_refused_before_any_request(self):
        sess = S.session_for()
        a = S.adapter(sess)
        before = len(sess.calls)
        cap = a.fetch(CandidateReference(
            "https://evil.test/news/x-y", "ph_afp_articles"))
        self.assertEqual(cap.status, st.DISALLOWED_REDIRECT)
        self.assertEqual(len(sess.calls), before)

    def test_failed_retrievals_are_recorded_for_the_run_report(self):
        sess = S.session_for()
        slug = S.detail_obj(1384)["slug"]
        del sess.details[slug]
        a = S.adapter(sess)
        a.discover(WIDE)
        capture_for(a, 1384)
        self.assertEqual(a.failed_fetches,
                         ["https://api.afp.mil.ph/articles/%s/" % slug])


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.sess = S.session_for()
        self.a = S.adapter(self.sess)
        self.a.discover(WIDE)

    def extract(self, ident):
        return self.a.extract(capture_for(self.a, ident))

    def test_a_current_cms_press_item_is_fully_normalised(self):
        r = self.extract(1384)
        self.assertEqual(r.status, st.OK)
        doc = r.documents[0]
        slug = S.detail_obj(1384)["slug"]
        self.assertEqual(doc.url, "https://www.afp.mil.ph/news/%s" % slug)
        self.assertEqual(doc.title_original,
                         "AFP Advances CHR Leadership with First Civilian Director I")
        self.assertEqual(doc.published_date, "2026-09-15")
        self.assertEqual(doc.language_tag, "en")
        x = doc.extra
        self.assertEqual(x["source_identity"], "afp:1384")
        self.assertEqual(x["published_at_original"], "2026-09-15T16:00:00+08:00")
        self.assertEqual(x["published_at_utc"], "2026-09-15T08:00:00+00:00")
        self.assertEqual(x["byline"], "pao afp")
        self.assertEqual(x["category_slug"], "news-blog")
        self.assertEqual(x["text_status"], "text")
        self.assertTrue(doc.has_usable_text)

    def test_provenance_travels_with_the_document(self):
        doc = self.extract(1384).documents[0]
        served = self.sess.details[S.detail_obj(1384)["slug"]]
        x = doc.extra
        self.assertEqual(x["capture_sha256"], hashlib.sha256(served).hexdigest())
        self.assertEqual(x["requested_url"].split("/")[2], "api.afp.mil.ph")
        self.assertTrue(x["retrieved_at"])
        self.assertEqual(x["content_sha256"],
                         hashlib.sha256(doc.text_original.encode("utf-8")).hexdigest())
        self.assertEqual(len(x["source_fingerprint"]), 64)
        self.assertTrue(x["api_created_at"])

    def test_an_image_only_statement_is_a_metadata_only_record_with_nothing_inferred(self):
        doc = self.extract(1331).documents[0]
        self.assertEqual(doc.text_original, "")
        self.assertEqual(doc.extra["text_status"], "no_text")
        self.assertEqual(doc.extra["text_composition"], "none")
        self.assertFalse(doc.has_usable_text)
        self.assertEqual(doc.published_date, "2026-07-21")
        self.assertTrue(doc.title_original.startswith("AFP Statement on Misleading"))
        self.assertTrue(doc.extra["featured_image_path"].startswith("/media/"))

    def test_a_migrated_item_keeps_both_halves_and_its_original_offset_date(self):
        doc = self.extract(1211).documents[0]
        self.assertEqual(doc.extra["text_composition"], "intro+body")
        self.assertEqual(doc.published_date, "2022-04-18")
        self.assertIsNone(doc.extra["byline"])       # the API said "None"

    def test_a_misfiled_site_page_in_uncategorised_is_collected_and_flagged(self):
        doc = self.extract(834).documents[0]
        self.assertEqual(doc.extra["category_slug"], "uncategorised")
        self.assertEqual(doc.extra["text_status"], "no_text")
        # local 2023-04-22 06:08 +08:00 is still 2023-04-21 in UTC
        self.assertEqual(doc.published_date, "2023-04-22")
        self.assertTrue(doc.extra["published_at_utc"].startswith("2023-04-21"))

    def test_a_site_furniture_category_is_refused_at_extraction_too(self):
        sess = S.session_for(details_ids=(949,))
        a = S.adapter(sess)
        cap = a.fetch(CandidateReference(
            ph.canonical_url(S.detail_obj(949)["slug"]), "ph_afp_articles"))
        r = a.extract(cap)
        self.assertEqual(r.status, st.EXTRACTION_FAILURE)
        self.assertEqual(a.rejections[ph.R_NON_PRESS_CATEGORY], 1)

    def test_the_twin_statements_have_distinct_identities(self):
        a, b = self.extract(1330).documents[0], self.extract(1331).documents[0]
        self.assertNotEqual(a.extra["source_identity"], b.extra["source_identity"])
        self.assertNotEqual(a.url, b.url)
        self.assertEqual(a.title_original, b.title_original)
        self.assertEqual(a.published_date, b.published_date)

    def refuse(self, mutate, reason=None):
        sess = S.session_for(details_ids=(1384,), mutate=mutate)
        a = S.adapter(sess)
        a.discover(WIDE)
        r = a.extract(capture_for(a, 1384))
        self.assertEqual(r.status, st.EXTRACTION_FAILURE)
        self.assertEqual(r.documents, [])
        if reason:
            self.assertEqual(a.rejections[reason], 1)
        return r

    def test_a_detail_with_a_different_id_than_the_listing_is_refused(self):
        self.refuse(lambda d: d.update(id=d["id"] + 1), ph.R_IDENTITY_MISMATCH)

    def test_a_detail_with_a_different_slug_than_the_reference_is_refused(self):
        self.refuse(lambda d: d.update(slug="another-article"),
                    ph.R_IDENTITY_MISMATCH)

    def test_a_detail_with_no_usable_id_is_refused(self):
        self.refuse(lambda d: d.update(id="abc"), ph.R_IDENTITY_MISMATCH)

    def test_an_unpublished_status_is_refused(self):
        self.refuse(lambda d: d.update(status="draft"), ph.R_NOT_PUBLISHED)

    def test_a_missing_title_is_refused(self):
        self.refuse(lambda d: d.update(title=" "), ph.R_MISSING_TITLE)

    def test_a_timestamp_with_no_offset_is_refused_not_assumed_to_be_manila_time(self):
        self.refuse(lambda d: d.update(published_at="2026-09-15T16:00:00"),
                    ph.R_UNPARSEABLE_PUBDATE)

    def test_an_absent_key_is_template_drift_and_is_named(self):
        r = self.refuse(lambda d: d.pop("body_html"))
        self.assertIn("body_html", r.error_detail)
        self.assertIn("template drift", r.error_detail)

    def test_an_empty_body_is_a_fact_but_an_absent_body_is_a_defect(self):
        # 1331 has body_html == "" and is kept; the case above has no key at
        # all and is refused. The two must never be conflated.
        self.assertEqual(self.extract(1331).status, st.OK)

    def test_a_payload_that_is_not_json_is_refused(self):
        cap = capture_for(self.a, 1384)
        cap.body = "<html>not json</html>"
        self.assertEqual(self.a.extract(cap).status, st.EXTRACTION_FAILURE)

    def test_a_json_payload_that_is_not_an_object_is_refused(self):
        cap = capture_for(self.a, 1384)
        cap.body = "[1, 2, 3]"
        self.assertEqual(self.a.extract(cap).status, st.EXTRACTION_FAILURE)

    def test_a_failed_capture_yields_no_document(self):
        cap = capture_for(self.a, 1384)
        cap.status = st.FETCH_FAILURE
        self.assertEqual(self.a.extract(cap).status, st.EXTRACTION_FAILURE)

    def test_a_list_and_detail_that_disagree_on_the_date_are_counted(self):
        def move(d):
            d["published_at"] = "2026-09-16T16:00:00+08:00"
        sess = S.session_for(details_ids=(1384,), mutate=move)
        a = S.adapter(sess)
        a.discover(WIDE)
        r = a.extract(capture_for(a, 1384))
        self.assertEqual(r.status, st.OK)
        # the document's own date wins; the disagreement is on the record
        self.assertEqual(r.documents[0].published_date, "2026-09-16")
        self.assertEqual(a.observed["list_detail_date_disagreements"], 1)


class TestContractCollect(unittest.TestCase):
    """The generic `SourceAdapter.collect()` path, end to end, offline."""

    def collect(self, sess):
        a = ph.PHAfpAdapter(S.EnabledFakeSource(), session=sess, cap=0,
                            sleeper=lambda s: None)
        return a.collect(WIDE)

    def test_a_disabled_source_collects_nothing(self):
        a = ph.PHAfpAdapter(S.FakeSource(), session=S.session_for(),
                            sleeper=lambda s: None)
        result, docs = a.collect(WIDE)
        self.assertEqual(result.status, st.SKIPPED_DISABLED)
        self.assertEqual(docs, [])

    def test_text_unavailable_is_counted_separately_from_extracted(self):
        result, docs = self.collect(S.session_for(exclude_categories=("afp-logos",)))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.extracted, len(docs))
        self.assertEqual(result.extracted, 8)
        # 1331, 1330, 1365, 834 have no text in the payload
        self.assertEqual(result.text_unavailable, 4)
        self.assertEqual(result.usable_text, 4)

    def test_a_listing_failure_is_not_reported_as_silence(self):
        result, docs = self.collect(S.FakeSession())
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertEqual(docs, [])

    def test_the_manifest_declares_a_shadow_source_that_is_not_enabled(self):
        m = json.loads((REPO_ROOT / "shadow" / "ph_afp" / "manifest.json"
                        ).read_text(encoding="utf-8"))
        src = m["sources"][0]
        self.assertFalse(src["enabled"])
        self.assertEqual(src["adapter"], "scraper.sources.ph_afp:PHAfpAdapter")
        self.assertEqual(m["desk"]["public_status"], "shadow")
        self.assertFalse(m["desk"]["active"])
        self.assertEqual(src["authority_tier"], "A")


if __name__ == "__main__":
    unittest.main()
