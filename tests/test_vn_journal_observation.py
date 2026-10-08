"""Synthetic metadata-only journal observation assembly; no HTTP or text."""
import copy
from dataclasses import dataclass
import json
import unittest

from scripts.vn_journal_window_drift import CATEGORIES, ObservationRefused, compare_observations
from scripts.vn_journal_observation import make_observation


@dataclass(frozen=True)
class Candidate:
    source_identity: str
    canonical_url: str
    category_page: str
    date_hint: str = None
    article_date_verified: bool = False
    title: str = "SYNTHETIC FIELD THAT MUST NEVER LEAK INTO OUTPUT"
    body: str = "SYNTHETIC FIELD THAT MUST NEVER LEAK INTO OUTPUT"


@dataclass(frozen=True)
class Observation:
    category_page: str
    candidates: tuple
    completeness_proven: bool = False
    pagination_verified: bool = False


def fake_observations():
    return [Observation(category, (
        Candidate("vndj-en:%d" % (27010 + i),
                  "https://tapchiqptd.vn/en/news/synthetic-heading/%d.html" % (27010 + i),
                  category, "2026-09-30"),
    )) for i, category in enumerate(CATEGORIES)]


def hashes():
    return {category: "a" * 64 for category in CATEGORIES}


def make(data=None, **updates):
    kwargs = dict(response_sha256_by_category=hashes(), observed_at="2026-10-08T01:00:00Z", observation_id="synthetic-run-one")
    kwargs.update(updates)
    return make_observation(fake_observations() if data is None else data, **kwargs)


class ObservationExportTest(unittest.TestCase):
    def test_exact_four_section_round_trip_is_valid(self):
        packet = make()
        self.assertEqual(packet["source_slug"], "vn_national_defence_journal_en")
        self.assertEqual([s["category"] for s in packet["sections"]], list(CATEGORIES))
        self.assertEqual(sum(len(s["candidates"]) for s in packet["sections"]), 4)
        text = json.dumps(packet)
        self.assertNotIn("SYNTHETIC FIELD THAT MUST NEVER LEAK", text)
        self.assertFalse(packet["source_html_retained"])
        later = make(observed_at="2026-10-09T01:00:00Z", observation_id="synthetic-run-two")
        self.assertEqual(compare_observations([packet, later])["transitions"][0]["sections"]["union"]["retained"], 4)

    def test_out_of_order_parser_results_normalized_to_fixed_category_order(self):
        self.assertEqual(make(list(reversed(fake_observations()))), make())

    def test_refuses_missing_category_and_mismatched_provenance(self):
        with self.assertRaises(ObservationRefused):
            make(fake_observations()[:-1])
        values = fake_observations()
        other = copy.deepcopy(values[1].candidates[0])
        values[1] = Observation(values[1].category_page, (other.__class__(other.source_identity, other.canonical_url, "news", other.date_hint),))
        with self.assertRaisesRegex(ObservationRefused, "provenance"):
            make(values)

    def test_refuses_fake_verified_dates(self):
        values = fake_observations()
        old = values[0].candidates[0]
        values[0] = Observation("news", (Candidate(old.source_identity, old.canonical_url, "news", old.date_hint, True),))
        with self.assertRaisesRegex(ObservationRefused, "article-verified"):
            make(values)

    def test_refuses_claims_of_historical_completeness_or_pagination(self):
        values = fake_observations()
        values[1] = Observation(values[1].category_page, values[1].candidates, True)
        with self.assertRaisesRegex(ObservationRefused, "pagination or completeness"):
            make(values)
        values = fake_observations()
        values[1] = Observation(values[1].category_page, values[1].candidates, False, True)
        with self.assertRaises(ObservationRefused):
            make(values)

    def test_refuses_missing_or_fake_digests(self):
        incomplete = hashes()
        incomplete.pop("news")
        with self.assertRaisesRegex(ObservationRefused, "four response digests"):
            make(response_sha256_by_category=incomplete)
        bad = hashes()
        bad["news"] = "not a sha256"
        with self.assertRaisesRegex(ObservationRefused, "digest"):
            make(response_sha256_by_category=bad)

    def test_refuses_nonutc_or_missing_identity(self):
        with self.assertRaisesRegex(ObservationRefused, "UTC"):
            make(observed_at="2026-10-08T08:00:00+07:00")
        with self.assertRaisesRegex(ObservationRefused, "identifier"):
            make(observation_id="")

    def test_refuses_duplicate_ids_or_identity_collision(self):
        vals = fake_observations()
        vals[0] = Observation("news", (vals[0].candidates[0], vals[0].candidates[0]))
        with self.assertRaisesRegex(ObservationRefused, "repeated identity"):
            make(vals)
        vals = fake_observations()
        vals[1] = Observation("theory-and-practice", (Candidate(vals[0].candidates[0].source_identity,
            "https://tapchiqptd.vn/en/news/conflicting-heading/27010.html", "theory-and-practice"),))
        with self.assertRaisesRegex(ObservationRefused, "two canonical"):
            make(vals)

    def test_no_clock_or_io_in_source(self):
        import inspect
        from scripts import vn_journal_observation
        code = inspect.getsource(vn_journal_observation)
        for forbidden in ("requests", "urlopen", "urllib.request", "datetime.now", "date.today", "write_text", "open("):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
