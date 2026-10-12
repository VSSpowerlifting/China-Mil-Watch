"""Private Indonesia review queue: public metadata only, explicit non-approval."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from core.indonesia_official_index import load as load_links
from scripts.prepare_indonesia_reference_review_queue import (
    DISPOSITIONS, HELD_PATH, QueueError, destination, prepare,
    spreadsheet_value, write,
)


def record(url, title, pub, sha="a" * 40):
    return {
        "country": "indonesia",
        "institution": "Indonesia Ministry of Defense — Kemhan Berita",
        "source_slug": "id_kemhan_news",
        "identity": "kemhan:" + urlsplit(url).path,
        "url": url, "title": title, "published_date": pub,
        "first_seen_run": "37533271730-1",
        "state_commit": sha,
        "review_status": "not_human_reviewed_for_public_use",
    }


def fake_report(rows):
    return {
        "schema": "ipr-private-shadow-desk-reader/1",
        "status": "private_research_not_source_admitted",
        "desk_filter": "indonesia", "query": "", "truncated": False,
        "source_body_text_exported": False,
        "human_source_review_completed": False,
        "public_release_authorized": False,
        "sources": [{"source_slug": "id_kemhan_news",
                     "state_commit": "a" * 40,
                     "stored_records": len(rows)}],
        "matched_total": len(rows), "results": rows,
    }


class IndonesiaPrivateQueueTests(unittest.TestCase):
    def setUp(self):
        self.public = load_links()
        rows = [record(x["source_url"], x["title_original"], x["published_date"])
                for x in self.public]
        rows += [
            record("https://www.kemhan.go.id" + HELD_PATH,
                   "Kunker ke Kaltara, Menhan Sjafrie Tinjau Yonif TP 880 Banuanta",
                   "2026-10-02"),
            record("https://www.kemhan.go.id/2026/10/11/source-candidate.html",
                   "Calon berita resmi untuk tinjauan", "2026-10-11"),
        ]
        self.report = fake_report(rows)

    def test_queue_separates_public_navigation_hold_and_new_candidates(self):
        packet = prepare(self.report, self.public)
        self.assertEqual(packet["stored_originals"], len(self.public) + 2)
        self.assertEqual(packet["counts"], dict(zip(DISPOSITIONS, (len(self.public), 1, 1))))
        self.assertFalse(packet["public_renderer_consumes_queue"])
        self.assertFalse(packet["independent_human_review_completed"])
        self.assertTrue(all(not x["independent_human_review_complete"] for x in packet["rows"]))
        self.assertTrue(all("body" not in x and "capture_sha256" not in x
                            for x in packet["rows"]))

    def test_refuses_body_or_forged_human_review_or_bad_provenance(self):
        cases = [
            lambda d: d["results"][0].update(text_original="unlicensed source body"),
            lambda d: d["results"][0].update(review_status="human_approved"),
            lambda d: d["results"][0].update(url="https://evil.example/forged"),
            lambda d: d["results"][0].update(source_slug="id_kemhan_press"),
            lambda d: d.update(human_source_review_completed=True),
            lambda d: d.update(public_release_authorized=True),
            lambda d: d.update(truncated=True),
            lambda d: d["sources"][0].update(stored_records=11),
            lambda d: d["results"].pop(),
        ]
        for change in cases:
            d = copy.deepcopy(self.report)
            change(d)
            with self.subTest(change=change), self.assertRaises(QueueError):
                prepare(d, self.public)

    def test_refuses_published_title_mismatch_missing_held_or_duplicate(self):
        cases = [
            lambda d: d["results"][0].update(title="Wrong publisher title"),
            lambda d: d["results"][0].update(published_date="2026-10-08"),
            lambda d: d["results"].__setitem__(8, d["results"][9]),
            lambda d: d["results"][9].update(url=d["results"][0]["url"]),
        ]
        for change in cases:
            d = copy.deepcopy(self.report)
            change(d)
            with self.subTest(change=change), self.assertRaises(QueueError):
                prepare(d, self.public)

    def test_eight_published_links_are_not_human_reviews_or_corpus_rows(self):
        packet = prepare(self.report, self.public)
        linked = [x for x in packet["rows"] if x["disposition"] == DISPOSITIONS[0]]
        held = [x for x in packet["rows"] if x["disposition"] == DISPOSITIONS[1]]
        self.assertEqual(len(linked), len(self.public))
        self.assertEqual(len(held), 1)
        self.assertEqual({x["official_url"] for x in linked},
                         {x["source_url"] for x in self.public})
        self.assertTrue(all(not x["independent_human_review_complete"]
                            and not x["publisher_body_reuse_authorized"]
                            and not x["eligible_for_public_corpus"]
                            for x in packet["rows"]))
        self.assertFalse(packet["source_reuse_approved"])
        self.assertFalse(packet["public_corpus_admitted"])

    def test_refuses_stale_four_link_pilot_or_forged_public_metadata(self):
        with self.assertRaises(QueueError):
            prepare(self.report, self.public[:4])
        doubled = copy.deepcopy(self.public)
        doubled[-1] = copy.deepcopy(doubled[0])
        with self.assertRaises(QueueError):
            prepare(self.report, doubled)
        augmented = copy.deepcopy(self.public)
        augmented[0]["text_original"] = "unexpected publisher body"
        with self.assertRaises(QueueError):
            prepare(self.report, augmented)
        substituted = copy.deepcopy(self.public)
        substituted[-1] = {
            **substituted[-1],
            "source_url": self.report["results"][-1]["url"],
            "title_original": self.report["results"][-1]["title"],
            "published_date": self.report["results"][-1]["published_date"],
        }
        # A valid-looking archived government original still cannot replace a
        # link selected in the separately reviewed bounded public directory.
        with self.assertRaises(QueueError):
            prepare(self.report, substituted)
        tampered = copy.deepcopy(self.public)
        tampered[0]["language"] = "en"
        with self.assertRaises(QueueError):
            prepare(self.report, tampered)

    def test_emits_private_json_csv_and_count_receipt(self):
        with tempfile.TemporaryDirectory(prefix="ipr-id-queue-") as td:
            root = Path(td)
            output = root / "private"
            self.assertEqual(spreadsheet_value("=HYPERLINK(1,2)"), "'=HYPERLINK(1,2)")
            self.assertEqual(spreadsheet_value("judul biasa"), "judul biasa")
            packet = prepare(self.report, self.public)
            receipt = write(packet, output)
            self.assertEqual(receipt["stored_originals"], len(self.public) + 2)
            self.assertTrue((output / "review_queue.json").exists())
            self.assertEqual(len(list(csv.DictReader(
                (output / "review_queue.csv").open(encoding="utf-8")))), len(self.public) + 2)
            count = json.loads((output / "COUNT_ONLY_RECEIPT.json").read_text())
            self.assertEqual(count["counts"][DISPOSITIONS[2]], 1)
            self.assertNotIn("rows", count)
            with self.assertRaises(QueueError):
                write(packet, output)
            with self.assertRaises(QueueError):
                destination(Path("relative-review-queue"))


if __name__ == "__main__":
    unittest.main()
