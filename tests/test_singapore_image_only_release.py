"""
Singapore: an image-only release no longer withholds a sound batch.

On 2026-09-28 the authorized recovery run stored nothing. The window held
`22sep26-infographic`, a page whose article is one image; its extracted "body"
was 178 characters of page furniture, under `MIN_BODY_CHARS`, so the adapter's
all-or-nothing rule withheld the ten good releases beside it.

These tests pin the repair and its limits:

  * an image-only release is stored as a text-unavailable record -- the
    ministry's own title, URL and date, an empty body, nothing read from the
    image -- and the rest of an otherwise sound batch is stored;
  * short is not the same as image-only: a release whose container holds prose
    is text, and a page whose layout is not understood is still a failure;
  * every unresolved fetch or extraction failure still withholds the whole
    batch, and the two governed holds are still never discovered;
  * the shadow collector, which calls `extract()`, is unchanged.

The fixtures in `tests/fixtures/sg_mindef_recovery/` are verbatim slices of
pages captured from mindef.gov.sg on 2026-09-29 (see the README there), and the
`content_sha256` of the three recovered releases is asserted to equal the value
the shadow collector recorded for the same release. A few filler pages are
synthetic, built in the real layout, and are named so. Everything is offline.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                          # noqa: E402
from core.collection.contract import (                            # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow)
from core.registry import SourceRegistry                           # noqa: E402
from scraper.sources import sg_mindef as sg                        # noqa: E402
from tests.integration.test_pipeline_run import PipelineRunCase   # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "sg_mindef_recovery"
BASE = "https://www.mindef.gov.sg/news-and-events/latest-releases/%s/"
SG_SLUG = "sg_mindef_releases"

INFOGRAPHIC = "22sep26-infographic"
HELD = ("15aug26-speech", "16sep26-speech")

#: content_sha256 prefixes the shadow collector recorded for the three
#: releases production missed (docs/DESK_CONSOLIDATION_AND_BRIEF_PREP_2026-09-28.md).
SHADOW_SHA = {"22sep26-nr": "10866200805d",
              "22sep26-speech": "0c40feac8102",
              "23sep26-mq": "2d0e1a352cba"}

#: The slugs the 2026-09-28 run discovers (window 09-22 .. 09-28), in the real
#: sitemap. Four are captured pages; the other seven are synthetic fillers.
CAPTURED = (INFOGRAPHIC, "22sep26-nr", "22sep26-speech", "23sep26-mq")
FILLERS = ("23sep26-nr", "24sep26-nr", "25sep26-speech", "27sep26-nr",
           "27sep26-nr2", "28sep26-mq", "28sep26-speech")
WINDOW_SLUGS = CAPTURED + FILLERS


def url(slug):
    return BASE % slug


def captured(slug):
    return (FIX / (slug + ".html")).read_text(encoding="utf-8")


def release_page(title, day="22 September 2026", lede=" ", container=""):
    """A page in the ministry's real layout (`<main>` > h1, date, lede, the
    `overflow-x-auto break-words` container, a back-to-top button)."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta property="og:title" content="%s"/></head><body><main>'
        '<h1 class="prose-display-md break-words text-base-content-strong">%s</h1>'
        '<p class="prose-label-sm-medium text-base-content">%s</p>'
        '<p class="prose-title-lg whitespace-pre-wrap text-base-content-light">%s</p>'
        '<div class="mx-auto w-full gap-10 pb-20">'
        '<div class="w-full overflow-x-auto break-words lg:max-w-[660px]">%s</div>'
        '</div><button>Back to top</button></main>'
        '<footer><h2>Ministry of Defence</h2></footer></body></html>'
        % (title, title, day, lede, container))


def para(text):
    return '<p dir="ltr" class="prose-body-base text-base-content">%s</p>' % text


IMAGE = ('<div class="mt-0"><img src="https://example.invalid/synthetic.jpg" '
         'alt="synthetic" width="100%" class="mx-auto"/></div>')
RESOURCES = ('<p dir="ltr"><b>More Resources</b></p>'
             '<p dir="ltr"><a href="/x/">A related release title</a></p>')


def filler(slug):
    """A synthetic, well-formed text release. Not a claim about any real one."""
    text = " ".join("Synthetic filler sentence %d for %s." % (i, slug)
                    for i in range(12))
    return release_page("Synthetic release %s" % slug, container=para(text))


class FakeResponse:
    def __init__(self, body="", status_code=200, url=""):
        self.text = body
        self.content = body.encode("utf-8")
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html"}
        self.url = url


class FakeSession:
    """Serves robots, the real sitemap slice, and pages by URL."""

    def __init__(self, overrides=None, statuses=None):
        self.pages = {url(s): captured(s) for s in CAPTURED}
        self.pages.update({url(s): filler(s) for s in FILLERS})
        self.pages.update({url(k): v for k, v in (overrides or {}).items()})
        self.statuses = {url(k): v for k, v in (statuses or {}).items()}
        self.calls = []

    def get(self, target, timeout=None, headers=None):
        self.calls.append(target)
        if target == sg.ROBOTS:
            return FakeResponse("User-Agent: *\nAllow: /\n")
        if target == sg.SITEMAP:
            return FakeResponse((FIX / "sitemap.xml").read_text(encoding="utf-8"))
        if target in self.statuses:
            return FakeResponse("", self.statuses[target])
        body = self.pages.get(target)
        return FakeResponse(body, 200, target) if body is not None \
            else FakeResponse("", 404)


def adapter(session=None):
    return sg.SGMindefAdapter(SourceRegistry().get_source(SG_SLUG),
                              session=session or FakeSession(),
                              sleeper=lambda _s: None)


def recovery_window():
    """`pipeline.production_window(adapter, 2026-09-28)`: 09-22 .. 09-28."""
    return CollectionWindow(target_date=date(2026, 9, 28),
                            lookback_days=sg.SGMindefAdapter.production_lookback_days)


def capture(slug_or_html, target=None):
    body = slug_or_html if "<" in slug_or_html else captured(slug_or_html)
    target = target or url(INFOGRAPHIC)
    ref = CandidateReference(url=target, source_slug=SG_SLUG)
    return CaptureResult(ref, st.OK, target, http_status=200, body=body,
                         payload_sha256="0" * 64,
                         retrieved_at="2026-09-29T00:00:00+00:00")


def sha12(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ── The page itself ──────────────────────────────────────────────────────────

class TestTheCapturedInfographicPage(unittest.TestCase):
    """What the real 22sep26-infographic response contains."""

    def test_its_only_words_are_page_furniture_not_release_text(self):
        page = captured(INFOGRAPHIC)
        body = sg.document_body(page)
        # What the old extractor called the body: 178 characters, none of which
        # the release wrote.
        self.assertEqual(len(body), 178)
        self.assertLess(len(body), sg.MIN_BODY_CHARS)
        self.assertEqual(
            body,
            "22 September 2026 More Resources Largest ASEAN Defence Ministers’ "
            "Meeting (ADMM)-Plus Exercise in a Decade with the Participation of "
            "2,200 Personnel from 19 Countries Back to top")

    def test_its_article_container_holds_one_image_and_no_prose(self):
        evidence = sg.article_evidence(captured(INFOGRAPHIC))
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.images, 1)
        self.assertEqual(evidence.prose_chars, 0)
        self.assertTrue(evidence.is_image_only)

    def test_the_three_text_releases_are_prose_never_image_only(self):
        for slug in ("22sep26-nr", "22sep26-speech", "23sep26-mq"):
            evidence = sg.article_evidence(captured(slug))
            self.assertTrue(evidence.has_prose, slug)
            self.assertFalse(evidence.is_image_only, slug)
        # An image alone proves nothing: the news release carries ten.
        self.assertGreater(sg.article_evidence(captured("22sep26-nr")).images, 1)


# ── Classification ───────────────────────────────────────────────────────────

class TestImageOnlyRelease(unittest.TestCase):

    def test_it_is_kept_as_a_text_unavailable_record(self):
        res = adapter()._extract(capture(INFOGRAPHIC), structural=True)
        self.assertEqual(res.status, st.OK)
        doc, = res.documents
        self.assertEqual(doc.url, url(INFOGRAPHIC))
        self.assertEqual(doc.title_original, "Infographic: Ex Trident Resolve 2026")
        self.assertEqual(doc.published_date, "2026-09-22")
        self.assertEqual(doc.text_original, "")
        self.assertFalse(doc.has_usable_text)
        self.assertEqual(doc.extra["content_verdict"], "media_only")
        self.assertEqual(doc.extra["content_sha256"], hashlib.sha256(b"").hexdigest())

    def test_nothing_from_the_image_or_its_alt_text_is_stored(self):
        doc = adapter()._extract(capture(INFOGRAPHIC), structural=True).documents[0]
        blob = " ".join(str(v) for v in (doc.title_original, doc.text_original,
                                         doc.extra))
        for leaked in ("Ex Trident Resolve Infogx", ".jpg", "isomer-user-content"):
            self.assertNotIn(leaked, blob)

    def test_the_shadow_path_is_unchanged_and_still_refuses_it(self):
        # `extract()` is what scripts/shadow_collect.py calls.
        res = adapter().extract(capture(INFOGRAPHIC))
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("too short", res.error_detail)
        self.assertEqual(res.documents, [])

    def test_a_missing_title_or_slug_date_still_refuses_an_image_only_page(self):
        no_title = captured(INFOGRAPHIC).replace(
            '<meta property="og:title" content="Infographic: Ex Trident Resolve 2026"/>', "")
        no_title = no_title.replace("<h1", "<h2").replace("</h1>", "</h2>")
        res = adapter()._extract(capture(no_title), structural=True)
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertIn("no title", res.error_detail)
        dateless = url("about")
        res = adapter()._extract(capture(INFOGRAPHIC, dateless), structural=True)
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)


class TestGenuineShortTextIsNotImageOnly(unittest.TestCase):

    def test_the_real_short_release_extracts_as_text(self):
        # 23sep26-mq is 391 characters: short, and real prose.
        for structural in (False, True):
            res = adapter()._extract(capture("23sep26-mq", url("23sep26-mq")),
                                     structural=structural)
            doc, = res.documents
            self.assertEqual(len(doc.text_original), 391)
            self.assertEqual(sha12(doc.text_original), SHADOW_SHA["23sep26-mq"])
            self.assertNotIn("content_verdict", doc.extra)
            self.assertTrue(doc.has_usable_text)

    def test_a_synthetic_release_under_the_floor_is_kept_as_text(self):
        # SYNTHETIC. No real Singapore prose release is under 200 characters
        # (the shortest stored is 258), so this is built in the real layout.
        page = release_page("Synthetic short statement",
                            container=para("A short synthetic statement."))
        self.assertLess(len(sg.document_body(page)), sg.MIN_BODY_CHARS)
        doc, = adapter()._extract(capture(page, url("22sep26-nr")),
                                  structural=True).documents
        self.assertIn("A short synthetic statement.", doc.text_original)
        self.assertNotIn("content_verdict", doc.extra)
        # The shadow path keeps refusing it, as before.
        self.assertEqual(
            adapter().extract(capture(page, url("22sep26-nr"))).status,
            st.EXTRACTION_FAILURE)

    def test_an_image_with_a_caption_is_text_not_image_only(self):
        page = release_page("Synthetic captioned image", container=(
            IMAGE + para("Personnel disembark during the exercise.")))
        doc, = adapter()._extract(capture(page, url("22sep26-nr")),
                                  structural=True).documents
        self.assertNotIn("content_verdict", doc.extra)
        self.assertIn("Personnel disembark", doc.text_original)

    def test_a_lede_is_prose(self):
        page = release_page("Synthetic image with a lede",
                            lede="The lede is the release's own sentence.",
                            container=IMAGE + RESOURCES)
        doc, = adapter()._extract(capture(page, url("22sep26-nr")),
                                  structural=True).documents
        self.assertNotIn("content_verdict", doc.extra)

    def test_a_paragraph_that_mixes_words_and_a_link_is_prose(self):
        page = release_page("Synthetic mixed paragraph", container=(
            IMAGE + '<p>Read the <a href="/x/">full release</a> here.</p>'))
        evidence = sg.article_evidence(page)
        self.assertTrue(evidence.has_prose)
        self.assertFalse(evidence.is_image_only)


class TestExtractionDefectsStillFail(unittest.TestCase):

    def check(self, page, expect):
        res = adapter()._extract(capture(page, url("22sep26-nr")), structural=True)
        self.assertEqual(res.status, st.EXTRACTION_FAILURE)
        self.assertEqual(res.documents, [])
        self.assertIn(expect, res.error_detail)

    def test_a_stub_with_no_article_container(self):
        self.check("<h1>A release</h1><p>short</p>", "too short")

    def test_an_error_page_is_not_a_release(self):
        self.check("<html><body><h1>Page not found</h1><p>Sorry.</p></body></html>",
                   "too short")

    def test_an_image_outside_the_container_is_not_evidence(self):
        # The layout changed under us: the image is not in the article
        # container, and the container is gone. That is drift, not a picture.
        page = ('<h1 class="prose-display-md">A release</h1><div>'
                '<img src="https://example.invalid/a.jpg" alt=""/></div>')
        self.check(page, "too short")

    def test_a_container_with_neither_prose_nor_an_image(self):
        page = release_page("Synthetic empty container", container=RESOURCES)
        self.check(page, "neither prose nor an image")

    def test_furniture_alone_does_not_make_an_image_a_record_when_the_image_is_absent(self):
        page = release_page("Synthetic no image", container="")
        self.check(page, "neither prose nor an image")

    def test_a_body_at_or_above_the_floor_is_extracted_as_before(self):
        # Long pages never reach the structural branch: both paths agree
        # byte for byte, and match the shadow collector's recorded hashes.
        for slug in ("22sep26-nr", "22sep26-speech"):
            a = adapter()._extract(capture(slug, url(slug)), structural=False)
            b = adapter()._extract(capture(slug, url(slug)), structural=True)
            self.assertEqual(a.documents[0].text_original, b.documents[0].text_original)
            self.assertEqual(sha12(b.documents[0].text_original), SHADOW_SHA[slug])
            self.assertNotIn("content_verdict", b.documents[0].extra)


# ── The batch ────────────────────────────────────────────────────────────────

class TestRecoveryBatch(unittest.TestCase):
    """`collect()` over the 2026-09-28 recovery window."""

    def collect(self, **kw):
        session = FakeSession(**kw)
        result, docs = adapter(session).collect(recovery_window())
        return session, result, docs

    def test_the_whole_window_is_stored_including_the_three_missed_releases(self):
        session, result, docs = self.collect()
        self.assertEqual(result.status, st.OK)
        self.assertEqual((result.references_discovered, result.fetched,
                          result.extracted, result.failed_fetches), (11, 11, 11, 0))
        self.assertEqual(result.text_unavailable, 1)
        self.assertEqual(result.usable_text, 10)
        self.assertEqual({d.url for d in docs}, {url(s) for s in WINDOW_SLUGS})

        by_slug = {sg.release_slug(d.url): d for d in docs}
        for slug, want in SHADOW_SHA.items():
            self.assertEqual(sha12(by_slug[slug].text_original), want, slug)
        self.assertEqual(by_slug[INFOGRAPHIC].text_original, "")
        self.assertEqual([s for s, d in by_slug.items() if not d.has_usable_text],
                         [INFOGRAPHIC])
        self.assertIn("1 of 11 parsed page(s) carried no usable text",
                      result.error_detail)

    def test_the_two_held_records_are_not_discovered_or_requested(self):
        # The real sitemap slice lists both, and a wide window would reach both.
        wide = CollectionWindow(target_date=date(2026, 9, 28), lookback_days=90)
        session = FakeSession()
        session.pages.update({url(s): filler(s) for s in
                              ("19sep26-nr", "23sep26-nr")})
        result, docs = adapter(session).collect(wide)
        text = (FIX / "sitemap.xml").read_text(encoding="utf-8")
        for slug in HELD:
            self.assertIn(url(slug), text)
            self.assertNotIn(url(slug), session.calls)
            self.assertNotIn(url(slug), {d.url for d in docs})
        self.assertFalse(sg.HELD_RELEASE_SLUGS - set(HELD))

    def test_a_held_record_leaking_into_the_results_still_withholds_the_batch(self):
        session = FakeSession()
        leaked = adapter(session)
        original = leaked.discover

        def discover_with_leak(window):
            res = original(window)
            res.references.append(CandidateReference(
                url=url(HELD[1]), source_slug=SG_SLUG))
            return res
        leaked.discover = discover_with_leak
        session.pages[url(HELD[1])] = filler(HELD[1])
        result, docs = leaked.collect(recovery_window())
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(docs, [])
        self.assertIn("held record(s) present", result.error_detail)

    def test_a_fetch_failure_still_withholds_everything(self):
        _, result, docs = self.collect(statuses={"22sep26-nr": 500})
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(docs, [])
        self.assertIsNone(result.text_unavailable)
        self.assertIn("whole batch withheld", result.error_detail)

    def test_an_extraction_defect_still_withholds_everything(self):
        stub = "<h1>A release</h1><p>short</p>"
        _, result, docs = self.collect(overrides={"24sep26-nr": stub})
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(docs, [])
        self.assertIn("1 of 11 discovered reference(s) failed", result.error_detail)

    def test_an_unreadable_layout_beside_the_image_only_release_withholds_too(self):
        # The image-only release is not a licence for other short pages.
        drift = release_page("Synthetic drift", container="")
        _, result, docs = self.collect(overrides={"27sep26-nr": drift})
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(docs, [])

    def test_the_image_only_release_alone_is_a_clean_run(self):
        session = FakeSession()
        one = CollectionWindow(target_date=date(2026, 9, 22), lookback_days=0)
        # Only the infographic is fetchable and listed for that day; the other
        # two 22 September slugs are also discovered, so drop them.
        for slug in ("22sep26-nr", "22sep26-speech"):
            session.pages[url(slug)] = filler(slug)
        result, docs = adapter(session).collect(one)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.text_unavailable, 1)
        self.assertEqual(len(docs), 3)


# ── Through the real pipeline and storage ────────────────────────────────────

class TestPipelineStoresTheRecovery(PipelineRunCase):
    """`pipeline.run(--date 2026-09-28 --source sg_mindef_releases
    --no-analysis)` on a temporary, migrated database."""

    def run_sg(self, session=None):
        import core.registry as reg
        session = session or FakeSession()

        class Registry(SourceRegistry):
            def get_adapter(inner, slug):
                if slug == SG_SLUG:
                    return sg.SGMindefAdapter(inner.get_source(slug),
                                              session=session,
                                              sleeper=lambda _s: None)
                return super().get_adapter(slug)

        registry = Registry()
        reg._DEFAULT = registry
        self.pipeline.get_registry = lambda refresh=False: registry
        self.pipeline.run(sources=[SG_SLUG], target_date=date(2026, 9, 28),
                          dry_run=False, no_analysis=True)
        return session

    def rows(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            return {sg.release_slug(r["url"]): dict(r) for r in con.execute(
                "SELECT a.* FROM articles a JOIN sources s ON s.id = a.source_id "
                "WHERE s.slug = ?", (SG_SLUG,))}
        finally:
            con.close()

    def test_the_recovery_stores_all_eleven_and_marks_one_text_unavailable(self):
        self.run_sg()
        rows = self.rows()
        self.assertEqual(set(rows), set(WINDOW_SLUGS))

        info = rows[INFOGRAPHIC]
        self.assertEqual(info["url"], url(INFOGRAPHIC))
        self.assertEqual(info["title_original"], "Infographic: Ex Trident Resolve 2026")
        self.assertEqual(info["published_date"], "2026-09-22")
        self.assertEqual(info["text_original"], "")
        self.assertIsNone(info["passed_relevance"])     # never screened or analysed

        for slug, want in SHADOW_SHA.items():
            self.assertEqual(sha12(rows[slug]["text_original"]), want, slug)
            self.assertIsNone(rows[slug]["passed_relevance"])

        res = self.results()[SG_SLUG]
        self.assertEqual(res["status"], st.OK)
        self.assertFalse(res["is_failure"])
        self.assertEqual((res["references_discovered"], res["fetched"],
                          res["extracted"], res["new_documents"],
                          res["duplicates"]), (11, 11, 11, 11, 0))
        self.assertEqual(res["text_unavailable"], 1)
        self.assertIn("carried no usable text", res["error_detail"])

    def test_neither_held_record_is_stored(self):
        self.run_sg()
        stored = self.rows()
        for slug in HELD:
            self.assertNotIn(slug, stored)

    def test_a_release_already_stored_is_a_duplicate_and_the_batch_still_commits(self):
        # 23sep26-mq is what the scheduled 2026-09-29 run stores first.
        self.run_sg(FakeSession(statuses={INFOGRAPHIC: 500}))     # withheld
        self.assertEqual(self.rows(), {})
        self.seed_one("23sep26-mq")
        self.run_sg()
        rows = self.rows()
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[INFOGRAPHIC]["text_original"], "")
        res = self.results()[SG_SLUG]
        self.assertEqual((res["new_documents"], res["duplicates"]), (10, 1))

    def seed_one(self, slug):
        con = sqlite3.connect(str(self.db_path))
        sid = con.execute("SELECT id FROM sources WHERE slug=?", (SG_SLUG,)).fetchone()[0]
        text = sg.document_body(captured(slug))
        con.execute(
            "INSERT INTO articles (source_id, url, title_original, text_original, "
            "published_date, content_hash, scraped_at) VALUES (?,?,?,?,?,?,datetime('now'))",
            (sid, url(slug), sg.document_title(captured(slug)), text, "2026-09-23",
             "seeded-" + slug))
        con.commit()
        con.close()

    def test_an_unresolved_failure_still_commits_nothing(self):
        self.run_sg(FakeSession(statuses={"22sep26-speech": 500}))
        self.assertEqual(self.rows(), {})
        res = self.results()[SG_SLUG]
        self.assertEqual(res["status"], st.EXTRACTION_FAILURE)
        self.assertTrue(res["is_failure"])

    def test_running_it_again_adds_nothing(self):
        self.run_sg()
        first = self.rows()
        self.run_sg()
        self.assertEqual(self.rows(), first)
        res = self.results()[SG_SLUG]
        self.assertEqual((res["new_documents"], res["duplicates"]), (0, 11))


if __name__ == "__main__":
    unittest.main()
