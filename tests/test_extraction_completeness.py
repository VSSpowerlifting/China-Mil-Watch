"""
Extraction completeness, per document and per source run.

The defect this pins is a vocabulary problem with real reader-facing
consequences. `SourceRunResult.extracted` counted documents the *parser
returned a structure for*, not documents that yielded usable text, and the
Coverage page rendered that number under the heading "Read". A source that
fetched 34 pages and produced 33 articles plus one empty shell reported
"34 read" and status `ok`.

The corpus shows this is not hypothetical: 44 records hold a zero-character
body while carrying a complete title, canonical URL, publication date and
content hash. They are **metadata-only records** — the item is known to exist
and to have been published, and its text was not captured.

What must be true
-----------------
  * empty or whitespace-only text is never "usable text extracted";
  * a metadata-only record is still stored, because its metadata is real;
  * one empty document does not turn an otherwise good run into an outage;
  * a run where nothing usable was obtained is a failure, not an `ok`;
  * a parser exception is never laundered into empty-string success;
  * historical rows, which predate the measurement, report "not measured"
    rather than a fabricated zero.

Everything here uses synthetic fixtures. Nothing pins a moving corpus figure,
opens the tracked database for writing, or reaches the network.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import (                          # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow, ExtractedDocument,
    SourceRunResult,
)

BODY = "解放军报讯　某旅近日组织实战化训练，锤炼部队快速反应能力。" * 4


class PARSER_RAISED:
    """
    Plan sentinel for "the parser blew up on this page".

    A distinct type, not a status string: every collection status is a `str`,
    and using one as a sentinel made the stub treat `"extraction_failure"` as a
    document body — which is exactly the confusion this suite exists to prevent,
    committed in the test harness instead of the code.
    """


class _Source:
    slug = "fixture_source"
    desk_id = "china"
    enabled = True
    language_tag = "zh-Hans"


def _doc(text, url="http://example.test/1"):
    return ExtractedDocument(
        url=url, source_slug="fixture_source",
        title_original="标题", text_original=text,
        published_date="2026-08-26", language_tag="zh-Hans",
        raw={"url": url, "source_slug": "fixture_source",
             "title_original": "标题", "text_original": text,
             "published_date": "2026-08-26"},
    )


class TestUsableTextIsNotJustAParsedStructure(unittest.TestCase):
    """The per-document predicate everything else is built on."""

    def test_a_real_body_is_usable(self):
        self.assertTrue(_doc(BODY).has_usable_text)

    def test_an_empty_body_is_not_usable(self):
        self.assertFalse(_doc("").has_usable_text)

    def test_a_whitespace_only_body_is_not_usable(self):
        for blank in (" ", "\n", "\t\t", "  \n  \r\n ", "　", " "):
            with self.subTest(body=repr(blank)):
                self.assertFalse(_doc(blank).has_usable_text)

    def test_a_short_but_real_body_is_usable(self):
        """
        Shortness is not emptiness. The corpus holds 26 bodies under 50
        characters that are genuine, and a length threshold here would silently
        discard them.
        """
        self.assertTrue(_doc("短讯：演习结束。").has_usable_text)

    def test_the_document_keeps_its_metadata_when_text_is_unusable(self):
        d = _doc("")
        self.assertEqual(d.url, "http://example.test/1")
        self.assertEqual(d.title_original, "标题")
        self.assertEqual(d.published_date, "2026-08-26")


class TestARunResultSeparatesParsedFromUsable(unittest.TestCase):

    def test_text_unavailable_defaults_to_not_measured(self):
        """
        `None`, not 0. A row written before this measurement existed did not
        observe zero unusable documents — it observed nothing, and reporting a
        confident zero for it would invent a fact.
        """
        self.assertIsNone(SourceRunResult(source_slug="s", status=st.OK)
                          .text_unavailable)

    def test_usable_is_derived_and_never_exceeds_extracted(self):
        r = SourceRunResult(source_slug="s", status=st.OK,
                            extracted=10, text_unavailable=3)
        self.assertEqual(r.usable_text, 7)
        self.assertLessEqual(r.usable_text, r.extracted)

    def test_usable_is_unknown_when_the_run_predates_the_measurement(self):
        r = SourceRunResult(source_slug="s", status=st.OK, extracted=10)
        self.assertIsNone(r.usable_text)

    def test_a_result_cannot_claim_more_unusable_than_it_parsed(self):
        with self.assertRaises(ValueError):
            SourceRunResult(source_slug="s", status=st.OK,
                            extracted=2, text_unavailable=3)

    def test_a_negative_unusable_count_is_refused(self):
        with self.assertRaises(ValueError):
            SourceRunResult(source_slug="s", status=st.OK,
                            extracted=2, text_unavailable=-1)


class _StubAdapter:
    """
    The real `LegacyScraperAdapter.collect()` driven over synthetic documents.

    Only discovery, fetch and extract are stubbed — the counting, status
    selection and error wording under test are the production ones.
    """

    def __init__(self, docs_or_status):
        from adapters.legacy import LegacyScraperAdapter
        from core.collection.contract import DiscoveryResult, ExtractionResult
        self._plan = docs_or_status
        self.adapter = LegacyScraperAdapter.__new__(LegacyScraperAdapter)
        self.adapter.slug = "fixture_source"
        self.adapter.source = _Source()
        # `failed_fetches` is a read-only property that reads through to the
        # wrapped scraper, so the stub supplies the scraper rather than the
        # property — keeping the production accessor in the path under test.
        class _Scraper:
            failed_fetches = []
        self.adapter._scraper = _Scraper()
        refs = [CandidateReference(url="http://example.test/%d" % i,
                                   source_slug="fixture_source")
                for i in range(len(self._plan))]
        self.adapter.discover = lambda w: DiscoveryResult(
            "fixture_source", st.OK, refs)

        def _fetch(ref):
            return CaptureResult(reference=ref, status=st.OK,
                                 requested_url=ref.url, body="<html></html>")
        self.adapter.fetch = _fetch
        self._i = iter(self._plan)

        def _extract(capture):
            item = next(self._i)
            if item is PARSER_RAISED:
                return ExtractionResult(
                    "fixture_source", st.EXTRACTION_FAILURE, [],
                    error_detail="parser raised: Boom: nope")
            return ExtractionResult("fixture_source", st.OK, [_doc(item)])
        self.adapter.extract = _extract

    def run(self):
        from datetime import date
        return self.adapter.collect(CollectionWindow(
            target_date=date(2026, 8, 26)))


class TestOneEmptyDocumentIsAGapNotAnOutage(unittest.TestCase):

    def test_all_usable_is_a_clean_ok_with_no_gap(self):
        result, docs = _StubAdapter([BODY, BODY, BODY]).run()
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.extracted, 3)
        self.assertEqual(result.text_unavailable, 0)
        self.assertEqual(result.usable_text, 3)
        self.assertEqual(len(docs), 3)

    def test_one_empty_among_many_stays_ok_and_reports_the_gap(self):
        result, docs = _StubAdapter([BODY, "", BODY]).run()
        self.assertEqual(result.status, st.OK,
                         "a single unusable document turned a good run into "
                         "an outage")
        self.assertEqual(result.extracted, 3)
        self.assertEqual(result.text_unavailable, 1)
        self.assertEqual(result.usable_text, 2)
        self.assertIn("no usable text", (result.error_detail or "").lower())

    def test_the_metadata_only_document_is_still_returned_for_storage(self):
        """Discarding it would lose a real, dated, canonical-URL fact."""
        _result, docs = _StubAdapter([BODY, "", BODY]).run()
        self.assertEqual(len(docs), 3)
        empty = [d for d in docs if not d.has_usable_text]
        self.assertEqual(len(empty), 1)
        self.assertTrue(empty[0].url)
        self.assertTrue(empty[0].title_original)

    def test_whitespace_only_counts_as_unavailable_too(self):
        result, _docs = _StubAdapter([BODY, "   \n  ", BODY]).run()
        self.assertEqual(result.text_unavailable, 1)
        self.assertEqual(result.usable_text, 2)


class TestNoUsableTextAtAllIsAFailure(unittest.TestCase):

    def test_every_document_empty_is_an_extraction_failure(self):
        result, docs = _StubAdapter(["", "", ""]).run()
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertTrue(st.is_failure(result.status))
        self.assertEqual(result.extracted, 3)
        self.assertEqual(result.text_unavailable, 3)
        self.assertEqual(result.usable_text, 0)
        self.assertEqual(len(docs), 3, "the metadata was still captured")

    def test_that_failure_is_not_reported_as_nothing_published(self):
        """
        `ok_no_publications` means the source had nothing to offer. A source
        that offered three documents we could not read is the opposite claim.
        """
        result, _ = _StubAdapter(["", "", ""]).run()
        self.assertNotEqual(result.status, st.OK_NO_PUBLICATIONS)
        self.assertNotEqual(result.status, st.OK_ALL_DUPLICATES)

    def test_a_parser_exception_is_not_laundered_into_empty_success(self):
        result, docs = _StubAdapter([PARSER_RAISED]).run()
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(result.extracted, 0)
        self.assertEqual(docs, [])
        self.assertEqual(result.text_unavailable, 0,
                         "a page that never parsed is not a page that parsed "
                         "without text")

    def test_a_parser_exception_beside_a_good_document_stays_ok(self):
        result, docs = _StubAdapter([BODY, PARSER_RAISED]).run()
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.extracted, 1)
        self.assertEqual(result.usable_text, 1)
        self.assertEqual(len(docs), 1)


class TestTheStoredRowCarriesTheMeasurement(unittest.TestCase):
    """Round-trip through the real schema on a temporary database."""

    def setUp(self):
        import tempfile, shutil
        self.dir = Path(tempfile.mkdtemp(prefix="extraction-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db = self.dir / "t.db"

    def _migrated(self):
        from migrations.runner import apply_all
        conn = sqlite3.connect(str(self.db))
        conn.executescript((REPO_ROOT / "storage" / "schema.sql")
                           .read_text(encoding="utf-8"))
        apply_all(conn)
        return conn

    def test_the_column_exists_after_migration(self):
        conn = self._migrated()
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(source_run_results)")}
        conn.close()
        self.assertIn("text_unavailable", cols)

    def test_a_historical_row_reads_back_as_not_measured(self):
        """A row inserted without the column keeps NULL, never 0."""
        conn = self._migrated()
        conn.execute("INSERT INTO scrape_runs (id, status) VALUES (1, 'completed')")
        conn.execute(
            "INSERT INTO source_run_results "
            "(scrape_run_id, source_slug, status, extracted) VALUES (1,'s','ok',5)")
        conn.commit()
        value = conn.execute(
            "SELECT text_unavailable FROM source_run_results").fetchone()[0]
        conn.close()
        self.assertIsNone(value)

    def test_a_measured_row_round_trips(self):
        conn = self._migrated()
        conn.execute("INSERT INTO scrape_runs (id, status) VALUES (1, 'completed')")
        conn.execute(
            "INSERT INTO source_run_results "
            "(scrape_run_id, source_slug, status, extracted, text_unavailable) "
            "VALUES (1,'s','ok',5,2)")
        conn.commit()
        row = conn.execute(
            "SELECT extracted, text_unavailable FROM source_run_results").fetchone()
        conn.close()
        self.assertEqual(tuple(row), (5, 2))


class TestTheCoverageSurfaceTellsThemApart(unittest.TestCase):
    """
    The reader-facing half. A number is only honest if its heading is.
    """

    TEMPLATE = REPO_ROOT / "site" / "preview" / "templates" / "coverage.html"

    def template(self):
        return self.TEMPLATE.read_text(encoding="utf-8")

    def test_parsed_and_text_read_are_separate_columns(self):
        html = self.template()
        self.assertIn('<th scope="col" class="num">Parsed</th>', html)
        self.assertIn('<th scope="col" class="num">Text read</th>', html)

    def test_the_old_conflated_heading_is_gone(self):
        """
        "Read" over the parse count was the whole defect: it told a reader the
        text had been read when only the page had been parsed.
        """
        self.assertNotIn('class="num">Read</th>', self.template())

    def test_the_table_explains_the_difference_in_plain_language(self):
        html = self.template()
        self.assertIn("reachable but unreadable", html)
        self.assertIn("not measured", html)

    def test_an_unmeasured_run_is_not_rendered_as_zero(self):
        html = self.template()
        block = html.split('data-label="Text read"', 1)[1].split("</td>", 1)[0]
        self.assertIn("usable_text is not none", block)
        self.assertIn("not measured", block)

    def test_the_view_model_degrades_when_the_column_is_absent(self):
        """
        The renderer must work against a database that has not run migration
        0006 yet — which is the tracked database between this change merging
        and the first production run. Absent means unmeasured, not broken.
        """
        source = (REPO_ROOT / "core" / "viewmodel.py").read_text(encoding="utf-8")
        self.assertIn("_has_text_unavailable", source)
        self.assertIn("NULL AS text_unavailable", source)


class TestTheViewModelReportsHonestly(unittest.TestCase):

    def _view(self, **kw):
        from core.viewmodel import RunResultView
        base = dict(source_slug="s", status=st.OK, is_failure=False,
                    extracted=10)
        base.update(kw)
        return RunResultView(**base)

    def test_a_measured_run_reports_usable_text(self):
        v = self._view(text_unavailable=3)
        self.assertEqual(v.usable_text, 7)
        self.assertTrue(v.extraction_measured)
        self.assertTrue(v.has_extraction_gap)

    def test_a_clean_measured_run_reports_no_gap(self):
        v = self._view(text_unavailable=0)
        self.assertEqual(v.usable_text, 10)
        self.assertTrue(v.extraction_measured)
        self.assertFalse(v.has_extraction_gap)

    def test_an_unmeasured_run_reports_neither(self):
        v = self._view()
        self.assertIsNone(v.usable_text)
        self.assertFalse(v.extraction_measured)
        self.assertFalse(v.has_extraction_gap)


class TestTheMigrationIsIdempotentAndByteStable(unittest.TestCase):

    def setUp(self):
        import tempfile, shutil, hashlib
        self.dir = Path(tempfile.mkdtemp(prefix="m0006-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db = self.dir / "t.db"
        self._hash = lambda: hashlib.sha256(self.db.read_bytes()).hexdigest()

    def _fresh(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript((REPO_ROOT / "storage" / "schema.sql")
                           .read_text(encoding="utf-8"))
        conn.commit(); conn.close()

    def _apply(self):
        from migrations.runner import apply_all
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA journal_mode=DELETE")
        try:
            return apply_all(conn)
        finally:
            conn.commit(); conn.close()

    def test_it_applies_once_and_then_reports_itself_applied(self):
        self._fresh()
        first = self._apply()
        self.assertIn("0006", first["applied"])
        second = self._apply()
        self.assertNotIn("0006", second["applied"])
        self.assertIn("0006", second["skipped"])

    def test_a_second_run_changes_no_bytes(self):
        """
        The migration adds a column and writes no row. Re-running it on an
        already-migrated database must therefore not move the file — the
        property `test_migration_byte_stability` pins for the whole chain.
        """
        self._fresh(); self._apply()
        before = self._hash()
        self._apply()
        self.assertEqual(self._hash(), before)

    def _pre_migration_row(self):
        """
        A `source_run_results` row that exists BEFORE 0006 runs.

        This is the shape that matters: the migration must not touch rows it
        finds. Inserting after the migration would test nothing, because a
        backfill only ever sees what was already there.
        """
        self._fresh()
        from migrations.runner import apply_all
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA journal_mode=DELETE")
        # Bring the schema up to 0005 only, so 0004's table exists and 0006
        # has genuinely not run yet.
        import migrations.runner as runner
        for m in sorted(runner.discover(), key=lambda x: x.version):
            if m.version >= "0006":
                continue
            if not m.module.is_already_applied(conn):
                m.module.up(conn)
        conn.execute("INSERT INTO scrape_runs (id, status) VALUES (1,'completed')")
        conn.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, status, "
            "extracted) VALUES (1,'legacy_source','ok',4)")
        conn.commit(); conn.close()

    def test_a_row_that_predates_the_migration_stays_unmeasured(self):
        """
        The historical-honesty guarantee. A run recorded before this column
        existed observed nothing about usable text; stamping 0 on it asserts
        that it read every document it parsed, which the corpus disproves — 44
        records with a complete title, URL and date sit behind a zero-length
        body, and they came from exactly those runs.
        """
        self._pre_migration_row()
        self._apply()
        conn = sqlite3.connect(str(self.db))
        value = conn.execute(
            "SELECT text_unavailable FROM source_run_results "
            " WHERE source_slug = 'legacy_source'").fetchone()[0]
        conn.close()
        self.assertIsNone(
            value,
            "the migration backfilled a historical row: it now claims that run "
            "read every document it parsed, which nothing recorded")

    def test_the_migration_writes_no_row_data_at_all(self):
        """
        Stronger than the row check: the migration must add a column and touch
        no data. Everything except the schema must be byte-identical.
        """
        self._pre_migration_row()
        conn = sqlite3.connect(str(self.db))
        before = conn.execute(
            "SELECT scrape_run_id, source_slug, status, extracted, fetched, "
            "       references_discovered, duplicates, new_documents "
            "  FROM source_run_results ORDER BY id").fetchall()
        conn.close()
        self._apply()
        conn = sqlite3.connect(str(self.db))
        after = conn.execute(
            "SELECT scrape_run_id, source_slug, status, extracted, fetched, "
            "       references_discovered, duplicates, new_documents "
            "  FROM source_run_results ORDER BY id").fetchall()
        conn.close()
        self.assertEqual(before, after)

    def test_a_row_written_after_the_migration_can_be_measured(self):
        """The other direction: new rows carry a real number, not NULL."""
        self._fresh(); self._apply()
        conn = sqlite3.connect(str(self.db))
        conn.execute("INSERT INTO scrape_runs (id, status) VALUES (1,'completed')")
        conn.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, status, "
            "extracted, text_unavailable) VALUES (1,'s','ok',4,1)")
        conn.commit()
        self.assertEqual(conn.execute(
            "SELECT text_unavailable FROM source_run_results").fetchone()[0], 1)
        conn.close()

    def test_a_database_without_the_table_is_left_alone(self):
        """
        Migration 0004 owns `source_run_results`. This one must be a no-op on a
        database that legitimately predates it, not a hard failure that stops
        the whole chain on a table it does not own.
        """
        import migrations.versions.m0006_source_run_text_unavailable as m
        conn = sqlite3.connect(":memory:")
        self.assertTrue(m.is_already_applied(conn))
        m.up(conn)   # must not raise
        conn.close()


if __name__ == "__main__":
    unittest.main()
