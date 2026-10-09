"""Pure offline owner review gate tests. No API, SMTP or real signing secret."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.regional_reviewed_evidence import _out
from core.regional_reviewed_evidence import (
    ReviewGateError, make_manual_review_template, private_model_packet,
    sign_private_review,
    verify_private_review,
)
from tests.test_regional_weekly_inventory import make, row

SECRET = b"synthetic-tests-only-review-key-more-than-32-bytes"
SAT = "2026-10-10"
SUN = "2026-10-11"


def docket(inventory=None):
    inventory = inventory or make()
    source = inventory["production_evidence"][0]
    return {
        "schema": "ipr-regional-source-review/1",
        "week_ending": SAT,
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "reviewer": "Owner for synthetic verification",
        "reviewed_on": SUN,
        "scope": "private_model_analyst_synopsis_only",
        "decisions": [{
            "id": source["id"], "desk": source["desk"],
            "source_url": source["source_url"],
            "published_date": source["published_date"],
            "stored_text_sha256": source["stored_text_sha256"],
            "disposition": "privately_reviewed",
            "original_language_checked": True,
            "publisher_version_checked": True,
            "not_a_quote_or_full_text": True,
            "synopsis": ("The official publisher described a dated policy exchange "
                         "and its proposed workstreams; implementation is not established."),
            "limitations": ("The official announcement does not establish any "
                            "independent operational outcome."),
        }],
    }


class SourceReviewGateTests(unittest.TestCase):
    def test_explicit_signed_synopsis_packet_never_contains_original(self):
        inventory = make()
        raw = docket(inventory)
        seal = sign_private_review(raw, inventory, SECRET)
        packet = private_model_packet(inventory, seal, SECRET)
        self.assertEqual(packet["schema"],
                         "ipr-regional-private-model-candidates/1")
        self.assertEqual(len(packet["production_sources"]), 1)
        self.assertIs(packet["private_model_synopses_only"], True)
        self.assertIs(packet["publication_authorized"], False)
        self.assertIs(packet["editor_email_authorized"], False)
        self.assertIs(packet["delivery_scheduled"], False)
        self.assertTrue(packet["not_an_official_publisher_attestation"])
        self.assertTrue(packet["unreviewed_japan_vietnam_research_excluded"])
        serial = json.dumps(packet)
        self.assertNotIn("Original reported wording", serial)
        self.assertNotIn("text_original", serial)
        self.assertNotIn("text_english", serial)
        self.assertNotIn(SECRET.decode(), serial)

    def test_template_prefills_only_pins_and_zero_human_approvals(self):
        inventory = make()
        template = make_manual_review_template(
            inventory, [42, 47], reviewer="Manual reviewer",
            reviewed_on=SUN)
        self.assertEqual([x["id"] for x in template["decisions"]], [42, 47])
        for item in template["decisions"]:
            self.assertEqual(item["disposition"], "awaiting_human_review")
            self.assertFalse(item["original_language_checked"])
            self.assertFalse(item["publisher_version_checked"])
            self.assertFalse(item["not_a_quote_or_full_text"])
            self.assertEqual(item["synopsis"], "")
            self.assertEqual(item["limitations"], "")
            self.assertEqual(len(item["stored_text_sha256"]), 64)
        with self.assertRaises(ReviewGateError):
            sign_private_review(template, inventory, SECRET)
        with self.assertRaises(ReviewGateError):
            make_manual_review_template(inventory, [42, 42],
                                        reviewer="Manual reviewer",
                                        reviewed_on=SUN)
        with self.assertRaises(ReviewGateError):
            make_manual_review_template(inventory, ["JP-W41-01"],
                                        reviewer="Manual reviewer",
                                        reviewed_on=SUN)

    def test_noninteractive_template_command_is_private_and_unsigned(self):
        from scripts.regional_reviewed_evidence import run
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "unsigned.json"
            argv = ["template", "--week-ending", SAT, "--as-of", SAT,
                    "--review-local-day", SUN, "--ids", "42,47",
                    "--reviewer", "Human analyst", "--out", str(destination)]
            with patch("scripts.regional_reviewed_evidence.inspect",
                       return_value=make()), patch("sys.stdin.isatty",
                       return_value=False):
                self.assertEqual(run(argv), 0)
            saved = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["decisions"]), 2)
            self.assertTrue(all(not d["original_language_checked"]
                                for d in saved["decisions"]))
            self.assertEqual(os.stat(destination).st_mode & 0o777, 0o600)
            with patch("scripts.regional_reviewed_evidence.inspect",
                       return_value=make()), self.assertRaises(SystemExit):
                run(argv)  # Cannot overwrite existing output.

    def test_no_auto_source_use_signoff_from_inventory(self):
        with self.assertRaises(ReviewGateError):
            private_model_packet(make(), {}, SECRET)
        with self.assertRaises(ReviewGateError):
            sign_private_review(docket(), make(), b"short-secret")

    def test_seal_detects_any_authority_or_citation_tampering(self):
        inventory = make()
        sealed = sign_private_review(docket(inventory), inventory, SECRET)
        cases = [
            lambda x: x["review"].update(reviewer="A different editor"),
            lambda x: x["review"]["decisions"][0].update(
                synopsis="A fabricated signed commitment was completed."),
            lambda x: x["review"]["decisions"][0].update(
                source_url="https://attacker.invalid/changed"),
            lambda x: x["review"].update(scope="publication_allowed"),
            lambda x: x.update(hmac_sha256="0"*64),
        ]
        for change in cases:
            signed = copy.deepcopy(sealed)
            change(signed)
            with self.subTest(signed=signed), self.assertRaises(ReviewGateError):
                verify_private_review(signed, inventory, SECRET)

    def test_stale_corpus_snapshot_rejects_old_review(self):
        prior = make()
        sealed = sign_private_review(docket(prior), prior, SECRET)
        changed = make(rows=[row(42, "china", text_original="New representation " * 50),
                             row(47, "singapore")])
        self.assertNotEqual(prior["source_metadata_digest_sha256"],
                            changed["source_metadata_digest_sha256"])
        with self.assertRaisesRegex(ReviewGateError, "snapshot"):
            private_model_packet(changed, sealed, SECRET)

    def test_partial_week_and_missing_sunday_marker_block_signing(self):
        not_ready = make(as_of="2026-10-08", review_day="2026-10-08",
                         marker="")
        unsigned = docket(not_ready)
        with self.assertRaisesRegex(ReviewGateError, "reporting week"):
            sign_private_review(unsigned, not_ready, SECRET)
        not_ready = make(marker="")
        with self.assertRaisesRegex(ReviewGateError, "reporting week"):
            sign_private_review(docket(not_ready), not_ready, SECRET)

    def test_unreviewed_and_held_id_cannot_be_signed(self):
        # Keep a second usable China record so Sunday readiness itself is
        # green: this must fail specifically on the held ID, not on the week.
        r = make(rows=[row(42, "china", text_original="short"),
                       row(50, "china"), row(47, "singapore")])
        d = docket(r)
        held = d["decisions"][0]
        held["id"] = 42
        with self.assertRaises(ReviewGateError):
            sign_private_review(d, r, SECRET)

    def test_reject_research_id_and_forged_production_pointer(self):
        inventory = make()
        for ident in ("JP-W41-01", 9999, True, -1):
            d = docket(inventory)
            d["decisions"][0]["id"] = ident
            with self.subTest(ident=ident), self.assertRaises(ReviewGateError):
                sign_private_review(d, inventory, SECRET)

    def test_reject_missing_primary_review_and_full_text_claim(self):
        inventory = make()
        for key in ("original_language_checked", "publisher_version_checked",
                    "not_a_quote_or_full_text"):
            d = docket(inventory)
            d["decisions"][0][key] = False
            with self.subTest(key=key), self.assertRaises(ReviewGateError):
                sign_private_review(d, inventory, SECRET)

    def test_reviewer_date_bounds_and_source_provenance(self):
        inventory = make()
        for day in ("2026-10-09", "2026-10-12", "10/11/2026"):
            d = docket(inventory)
            d["reviewed_on"] = day
            with self.subTest(day=day), self.assertRaises(ReviewGateError):
                sign_private_review(d, inventory, SECRET)
        for field, value in (("published_date", "2026-10-05"),
                             ("desk", "vietnam"),
                             ("stored_text_sha256", "f" * 64)):
            d = docket(inventory)
            d["decisions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ReviewGateError):
                sign_private_review(d, inventory, SECRET)

    def test_duplicate_decisions_and_unbounded_or_tiny_notes(self):
        inventory = make()
        d = docket(inventory)
        d["decisions"].append(copy.deepcopy(d["decisions"][0]))
        with self.assertRaises(ReviewGateError):
            sign_private_review(d, inventory, SECRET)
        for synopsis in ("short", "x" * 900, "Invalid\ncontrol"):
            d = docket(inventory)
            d["decisions"][0]["synopsis"] = synopsis
            with self.subTest(synopsis=synopsis[:10]), self.assertRaises(ReviewGateError):
                sign_private_review(d, inventory, SECRET)

    def test_strict_fields_and_signed_payload_binding(self):
        inventory = make()
        d = docket(inventory)
        d["claims_publication_ready"] = True
        with self.assertRaises(ReviewGateError):
            sign_private_review(d, inventory, SECRET)
        d = docket(inventory)
        d["decisions"][0]["source_body"] = "Do this!"
        with self.assertRaises(ReviewGateError):
            sign_private_review(d, inventory, SECRET)
        d = docket(inventory)
        sealed = sign_private_review(d, inventory, SECRET)
        with self.assertRaises(ReviewGateError):
            private_model_packet(inventory, sealed, b"another-secret" + b"Z" * 40)

    def test_private_review_output_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "review.json"
            victim = Path(root) / "must-not-create.json"
            dest.symlink_to(victim)
            with self.assertRaisesRegex(ReviewGateError, "must be new"):
                _out(dest, {"private": True})
            self.assertTrue(dest.is_symlink())
            self.assertFalse(victim.exists())

    def test_private_review_output_failing_fdopen_closes_and_unlinks(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "review.json"
            raw_close = os.close
            raw_open = os.open
            captured = []

            def capture_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                captured.append(fd)
                return fd

            with patch("scripts.regional_reviewed_evidence.os.open",
                       side_effect=capture_open), patch(
                    "scripts.regional_reviewed_evidence.os.fdopen",
                    side_effect=OSError("test fdopen failure")), patch(
                    "scripts.regional_reviewed_evidence.os.close",
                    wraps=raw_close) as closed:
                with self.assertRaisesRegex(OSError, "test fdopen failure"):
                    _out(dest, {"private": True})
            self.assertFalse(dest.exists())
            self.assertEqual(len(captured), 1)
            closed.assert_called_once_with(captured[0])

    def test_private_review_output_does_not_delete_replaced_path(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "review.json"
            original = Path(root) / "independent-owner-note.txt"
            original.write_text("OTHER", encoding="utf-8")
            raw_close = os.close

            def swap_then_fail(fd, *args, **kwargs):
                dest.unlink()
                os.link(original, dest)
                raise OSError("test replaced review output")

            with patch("scripts.regional_reviewed_evidence.os.fdopen",
                       side_effect=swap_then_fail), patch(
                    "scripts.regional_reviewed_evidence.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "test replaced review output"):
                    _out(dest, {"private": True})
            self.assertEqual(dest.read_text(encoding="utf-8"), "OTHER")
            self.assertEqual(original.read_text(encoding="utf-8"), "OTHER")

    def test_private_review_output_json_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "review.json"
            with self.assertRaises(TypeError):
                _out(dest, {"unserializable": object()})
            self.assertFalse(dest.exists())

    def test_coverage_roster_not_a_quota(self):
        inventory = make()
        docket_one = docket(inventory)
        packet = private_model_packet(
            inventory, sign_private_review(docket_one, inventory, SECRET),
            SECRET)
        self.assertEqual(len({r["desk"] for r in packet["production_sources"]}), 1)
        self.assertEqual(len(packet["production_sources"]), 1)
        # Selection of a lead is a separate editorial process, not an
        # approval of a one-desk publicly numbered Brief.


if __name__ == "__main__":
    unittest.main()
