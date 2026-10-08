"""End-to-end synthetic integration: actual listing parser -> assembler contract."""
import copy
import hashlib
import json
import unittest

from scripts.vn_journal_byte_observation import make_observation_from_bytes
from scripts.vn_journal_window_drift import (
    CATEGORIES, ObservationRefused, compare_observations, validate_observation,
)


def page(category, number):
    # Body text is deliberately publisher-like but entirely invented and must
    # never survive the metadata-only assembly boundary.
    return (
        "<html><body><div class='item'>"
        "<a href='https://tapchiqptd.vn/en/news/synthetic-study/%d.html'>"
        "FABRICATED JOURNAL TITLE %s</a>"
        "<span>09/30/2026</span>"
        "<p>FABRICATED PUBLISHER PARAGRAPH MUST NOT APPEAR</p>"
        "</div></body></html>" % (number, category)
    ).encode("utf-8")


def bodies():
    return {c: page(c, 27010 + i) for i, c in enumerate(CATEGORIES)}


def times():
    return {c: "2026-10-08T01:%02d:00Z" % i for i, c in enumerate(CATEGORIES)}


def make(pages=None, instants=None, **kwargs):
    return make_observation_from_bytes(
        bodies() if pages is None else pages,
        captured_at_by_category=times() if instants is None else instants,
        observation_id=kwargs.get("observation_id", "synthetic-four-pages"),
    )


class ByteBoundSnapshotTests(unittest.TestCase):
    def test_real_parser_to_validated_assembler_end_to_end(self):
        output = make()
        self.assertEqual(output["schema"], "ipr-vndj-listing-observation/1")
        self.assertEqual(output["observed_at"], "2026-10-08T01:03:00Z")
        self.assertEqual([s["category"] for s in output["sections"]], list(CATEGORIES))
        self.assertEqual(len(validate_observation(output)[2]), 4)
        for category, section in zip(CATEGORIES, output["sections"]):
            self.assertEqual(section["response_sha256"],
                             hashlib.sha256(bodies()[category]).hexdigest())
            self.assertEqual(len(section["candidates"]), 1)
            self.assertEqual(section["candidates"][0]["date_hint"], "2026-09-30")
        self.assertFalse(output["source_html_retained"])
        self.assertFalse(output["article_text_retained"])
        self.assertFalse(output["pagination_proven"])
        self.assertFalse(output["historical_completeness_proven"])

    def test_metadata_does_not_leak_publisher_like_text(self):
        output = json.dumps(make())
        for forbidden in ("FABRICATED JOURNAL TITLE", "FABRICATED PUBLISHER PARAGRAPH",
                          "<html>", "<body>", "09/30/2026", "GMT+7"):
            self.assertNotIn(forbidden, output)

    def test_one_byte_change_alters_hash_without_claiming_new_article(self):
        first_pages = bodies()
        first = make(first_pages, observation_id="first-proof")
        second_pages = copy.deepcopy(first_pages)
        second_pages["news"] = second_pages["news"].replace(
            b"FABRICATED PUBLISHER PARAGRAPH", b"CHANGED FABRICATED PARAGRAPH")
        second = make(second_pages, observation_id="second-proof")
        self.assertNotEqual(first["sections"][0]["response_sha256"],
                            second["sections"][0]["response_sha256"])
        self.assertEqual(first["sections"][0]["candidates"],
                         second["sections"][0]["candidates"])
        self.assertNotIn("CHANGED FABRICATED PARAGRAPH", json.dumps(second))

    def test_outputs_compare_as_ordinary_v1_metadata(self):
        first = make(observation_id="run-one")
        shifted = {c: "2026-10-09T01:%02d:00Z" % i for i, c in enumerate(CATEGORIES)}
        second = make(instants=shifted, observation_id="run-two")
        diff = compare_observations([first, second])
        self.assertEqual(diff["observation_count"], 2)
        self.assertEqual(diff["transitions"][0]["sections"]["union"]["retained"], 4)
        self.assertFalse(diff["historical_completeness_proven"])
        self.assertFalse(diff["forward_collection_reliability_proven"])

    def test_refuses_missing_category_or_extra_page(self):
        missing = bodies()
        missing.pop("news")
        with self.assertRaisesRegex(ObservationRefused, "exactly four"):
            make(missing)
        extra = bodies()
        extra["fictitious"] = b"<html><body></body></html>"
        with self.assertRaisesRegex(ObservationRefused, "exactly four"):
            make(extra)

    def test_refuses_nonbyte_or_mutable_response_bodies(self):
        for value in ("<html>fabrication</html>", bytearray(page("news", 27010)), None):
            candidate = bodies()
            candidate["news"] = value
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ObservationRefused, "immutable raw bytes"):
                    make(candidate)

    def test_rejects_empty_oversized_and_nul_containing_body(self):
        from scraper.sources.vn_journal_listing import MAX_BYTES
        for payload in (b"", b"x" * (MAX_BYTES + 1), b"\x00<html></html>"):
            candidate = bodies()
            candidate["news"] = payload
            with self.subTest(length=len(payload)):
                with self.assertRaises(ObservationRefused):
                    make(candidate)

    def test_rejects_bad_utf8_before_parsing(self):
        candidate = bodies()
        candidate["news"] = b"\xff\xfe\x80"
        with self.assertRaisesRegex(ObservationRefused, "strict UTF-8"):
            make(candidate)

    def test_rejects_duplicate_response_bytes_across_categories(self):
        candidate = bodies()
        candidate["news"] = candidate["theory-and-practice"]
        with self.assertRaisesRegex(ObservationRefused, "identical responses"):
            make(candidate)

    def test_rejects_challenge_with_no_article_links(self):
        candidate = bodies()
        candidate["news"] = b"<html><body><h1>Just a moment</h1></body></html>"
        with self.assertRaises(ValueError):
            make(candidate)

    def test_rejects_missing_and_non_utc_capture_timestamps(self):
        missing = times()
        del missing["news"]
        with self.assertRaisesRegex(ObservationRefused, "capture time"):
            make(instants=missing)
        malformed = times()
        malformed["news"] = "2026-10-08T08:00:00+07:00"
        with self.assertRaisesRegex(ObservationRefused, "UTC"):
            make(instants=malformed)

    def test_rejects_long_multi_page_capture_window(self):
        excessive = times()
        excessive["news"] = "2026-10-08T00:00:00Z"
        excessive["research-and-discussion"] = "2026-10-08T01:00:00Z"
        with self.assertRaisesRegex(ObservationRefused, "bounded observation"):
            make(instants=excessive)

    def test_thirty_minute_boundary_permitted(self):
        bounded = times()
        bounded["news"] = "2026-10-08T01:00:00Z"
        bounded["research-and-discussion"] = "2026-10-08T01:30:00Z"
        self.assertEqual(make(instants=bounded)["observed_at"],
                         "2026-10-08T01:30:00Z")

    def test_no_external_io_or_system_clock_reads(self):
        import inspect
        from scripts import vn_journal_byte_observation
        code = inspect.getsource(vn_journal_byte_observation)
        for forbidden in ("requests.", "urlopen(", "datetime.now(",
                          "time.time(", "open(", "write_text(", "sqlite3"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
