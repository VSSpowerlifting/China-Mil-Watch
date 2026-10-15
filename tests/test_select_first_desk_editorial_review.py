"""Synthetic gates for a *real-docket-input-only* seven-original editorial handoff."""
import copy
import unittest

from scripts.select_first_desk_editorial_review import (
    AFP_IDS, AFP_PIN, AFP_PACKET, EXPECTED_AFP_BATCHES, ID_COUNTS,
    ID_PIN, ID_URLS, ReviewHold, read_json, select,
)


def fixtures():
    packet = read_json(AFP_PACKET)
    originals = {x["id"]: x for x in packet["records"]}
    afp_batches = []
    for index, (day, run, sha, count) in enumerate(EXPECTED_AFP_BATCHES):
        rows = []
        if index == 0:
            for source_id in AFP_IDS:
                source = originals[source_id]
                rows.append({
                    "source_identity": source_id,
                    "title_original": source["title"],
                    "source_url": source["source_url"],
                    "published_date": source["published_at_original"][:10],
                    "text_sha256": source["content_sha256"],
                    "capture_sha256": source["capture_sha256"],
                    "review_status": "not_started",
                    "body_status": "text",
                    "extraction_review_priority": "ordinary_fidelity_review",
                    "human_review_authenticated": False,
                })
        for n in range(count - len(rows)):
            identity = "afp:" + str(8000 + index * 100 + n)
            rows.append({
                "source_identity": identity,
                "title_original": "Synthetic unsigned AFP original",
                "source_url": "https://www.afp.mil.ph/news/synthetic-" + identity[4:],
                "published_date": "2026-10-01",
                "text_sha256": "1" * 64,
                "capture_sha256": "2" * 64,
                "review_status": "not_started",
                "body_status": "text",
                "extraction_review_priority": "ordinary_fidelity_review",
                "human_review_authenticated": False,
            })
        afp_batches.append({
            "target_date": day, "run_id": run,
            "historical_state_commit": sha,
            "new_records": count, "records": rows,
        })
    afp = {
        "protocol": "ipr_ph_afp_metadata_review_docket_v1",
        "source": "philippines_afp_shadow",
        "total_source_records": 22,
        "body_unavailable_records": 0,
        "batches": afp_batches,
        "source_bodies_or_raw_api_responses_included": False,
        "human_review_completed": False,
        "source_reuse_approved": False,
        "production_eligible": False,
        "weekly_ai_writer_eligible": False,
        "automated_review_decisions": 0,
    }

    def indo_row(url, status, n):
        return {
            "publication_date": "2026-10-14",
            "title_original": "Contoh judul asli " + str(n),
            "official_url": url,
            "source_identity": "kemhan:" + url.split("www.kemhan.go.id", 1)[1],
            "first_seen_run": "38634144819-1",
            "disposition": status,
            "independent_human_review_complete": False,
            "publisher_body_reuse_authorized": False,
            "eligible_for_public_corpus": False,
        }

    id_rows = [indo_row(url, "new_source_review_candidate", n)
               for n, url in enumerate(ID_URLS)]
    for n in range(12):
        id_rows.append(indo_row(
            "https://www.kemhan.go.id/2026/10/14/synthetic-new-" + str(n) + ".html",
            "new_source_review_candidate", n + 3))
    for n in range(15):
        id_rows.append(indo_row(
            "https://www.kemhan.go.id/2026/10/14/synthetic-indexed-" + str(n) + ".html",
            "official_link_already_public_not_reviewed", n + 15))
    id_rows.append(indo_row(
        "https://www.kemhan.go.id/2026/10/02/synthetic-held.html",
        "hold_publisher_geography_inconsistent", 30))
    indonesia = {
        "schema": "ipr-indonesia-private-review-queue/1",
        "state_commit": ID_PIN,
        "source_family": "id_kemhan_news",
        "stored_originals": 31, "counts": dict(ID_COUNTS),
        "public_renderer_consumes_queue": False,
        "independent_human_review_completed": False,
        "source_reuse_approved": False,
        "public_corpus_admitted": False,
        "rows": id_rows,
    }
    return afp, indonesia, packet


class FirstEditorialSevenSourceGate(unittest.TestCase):
    def test_only_four_afp_and_three_kemhan_with_no_approval(self):
        subset = select(*fixtures())
        self.assertEqual(len(subset["philippines"]["records"]), 4)
        self.assertEqual(len(subset["indonesia"]["records"]), 3)
        self.assertEqual([r["source_id"] for r in subset["philippines"]["records"]],
                         list(AFP_IDS))
        self.assertEqual([r["publisher_url"] for r in subset["indonesia"]["records"]],
                         list(ID_URLS))
        self.assertEqual({r["state_commit"] for r in subset["philippines"]["records"]},
                         {AFP_PIN})
        self.assertEqual({r["state_commit"] for r in subset["indonesia"]["records"]},
                         {ID_PIN})
        self.assertTrue(all(r["capture_sha256_reference"] is None
                            for r in subset["indonesia"]["records"]))
        for key in ("approved_for_publication", "source_text_or_media_exported",
                    "original_version_parity_verified_by_this_script",
                    "human_review_complete", "reuse_rights_cleared",
                    "production_source_admitted"):
            self.assertIs(subset[key], False)

    def test_rejects_false_signatures_and_production_admission(self):
        for section, field in (
            (0, "human_review_completed"),
            (0, "source_reuse_approved"),
            (0, "production_eligible"),
            (1, "independent_human_review_completed"),
            (1, "source_reuse_approved"),
            (1, "public_corpus_admitted"),
        ):
            with self.subTest(section=section, field=field):
                inputs = list(fixtures())
                inputs[section][field] = True
                with self.assertRaises(ReviewHold):
                    select(*inputs)

    def test_rejects_replaced_afp_body_or_capture_digest(self):
        for field in ("text_sha256", "capture_sha256", "source_url",
                      "title_original", "body_status"):
            with self.subTest(field=field):
                inputs = list(fixtures())
                inputs[0]["batches"][0]["records"][0][field] = "changed"
                with self.assertRaises(ReviewHold):
                    select(*inputs)

    def test_rejects_stale_incomplete_or_forged_archive_roster(self):
        for section, field, value in (
            (0, "total_source_records", 21),
            (1, "stored_originals", 30),
            (1, "state_commit", "f" * 40),
        ):
            with self.subTest(section=section, field=field):
                inputs = list(fixtures())
                inputs[section][field] = value
                with self.assertRaises(ReviewHold):
                    select(*inputs)
        inputs = list(fixtures())
        inputs[0]["batches"][1]["records"].pop()
        with self.assertRaises(ReviewHold):
            select(*inputs)

    def test_rejects_missing_sanlakas_or_kemhan_references(self):
        inputs = list(fixtures())
        inputs[0]["batches"][0]["records"][0]["source_identity"] = "afp:9999"
        with self.assertRaises(ReviewHold):
            select(*inputs)
        inputs = list(fixtures())
        inputs[1]["rows"][0]["official_url"] = "https://www.kemhan.go.id/other"
        with self.assertRaises(ReviewHold):
            select(*inputs)

    def test_rejects_artifact_body_field_and_unauthorized_indonesia_row(self):
        inputs = list(fixtures())
        inputs[0]["batches"][0]["records"][0]["text_original"] = "leaked body"
        with self.assertRaises(ReviewHold):
            select(*inputs)
        inputs = list(fixtures())
        inputs[1]["rows"][0]["publisher_body_reuse_authorized"] = True
        with self.assertRaises(ReviewHold):
            select(*inputs)

    def test_rejects_altered_preexisting_source_packet(self):
        inputs = list(fixtures())
        inputs[2]["records"][0]["capture_sha256"] = "9" * 64
        with self.assertRaises(ReviewHold):
            select(*inputs)
        inputs = list(fixtures())
        inputs[2]["permissions"]["human_source_review_complete"] = True
        with self.assertRaises(ReviewHold):
            select(*inputs)


if __name__ == "__main__":
    unittest.main()
