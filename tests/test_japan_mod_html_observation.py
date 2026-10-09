"""Offline hash-only observation tests; NEVER fetches real MOD in CI."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from core.japan_mod_html_observation import (
    MAX_BYTES, MODObservationError, TARGETS, attest_packet_scope,
    observe, summarize,
)
from scripts.japan_mod_html_observation import (
    main, read_official_html, write_private,
)
from tests.test_regional_typed_research_holds import fixture

OBSERVED = "2026-10-09T16:40:00+00:00"


def source_rows():
    return fixture()[1]


def body(ident, *, include_date=True, include_title=True):
    heading = TARGETS[ident][2] if include_title else "Some unrelated article"
    day = "October 6, 2026" if include_date else "A prior event"
    return (f"<!doctype html><html lang='en'><head><title>MOD Government</title>"
            f"</head><body><main><h1>{heading}</h1><p>{day}</p>"
            f"<p>Official original page observation without copying.</p>"
            f"</main></body></html>").encode("utf-8")


def entries():
    return {ident: {"payload": body(ident), "fetched_url": item[0],
                    "content_type": "text/html; charset=utf-8"}
            for ident, item in TARGETS.items()}


class MODHTMLObservationTests(unittest.TestCase):
    def test_bounded_two_official_pages_observed_no_use_approval(self):
        report = summarize(source_rows(), entries(), OBSERVED)
        self.assertEqual(report["schema"], "ipr-japan-mod-two-html-observation/1")
        self.assertEqual(report["observation_count"], 2)
        self.assertEqual(report["expected_visible_title_and_date_count"], 2)
        self.assertEqual(len(report["items"]), 2)
        for row in report["items"]:
            self.assertTrue(row["expected_title_text_found"])
            self.assertTrue(row["expected_date_text_found"])
            self.assertEqual(row["observation_status"],
                             "NOT_REVIEWED_OBSERVATION_ONLY")
            self.assertEqual(len(row["raw_html_sha256"]), 64)
            self.assertEqual(len(row["decoded_visible_text_sha256"]), 64)
            self.assertFalse(row["editorial_model_use_authorized"])
            self.assertFalse(row["publication_authorized"])
        for key in ("model_input_authorized", "dylan_editor_email_authorized",
                    "publication_authorized", "historical_to_live_body_equality_proven",
                    "live_source_signoff_completed", "original_html_bodies_retained"):
            self.assertFalse(report[key])
        ser = json.dumps(report, ensure_ascii=False)
        for _, (url, _, title) in TARGETS.items():
            self.assertNotIn(url, ser)
            self.assertNotIn(title, ser)
        self.assertNotIn("<html", ser)

    def test_page_title_or_script_spoof_is_not_a_body_match(self):
        ident = "JP-W41-01"
        spoofed = (f"<html><head><title>{TARGETS[ident][2]} October 6, 2026"
                   f"</title><script>document.write('fake')</script>"
                   f"</head><body><p>Another subject.</p></body></html>").encode()
        result = observe(ident, spoofed, fetched_url=TARGETS[ident][0],
                         content_type="text/html", observed_utc=OBSERVED)
        self.assertFalse(result["expected_title_text_found"])
        self.assertFalse(result["expected_date_text_found"])
        self.assertIn("manual_original_check_required", result["reason"])

    def test_fingerprint_changes_when_original_html_changes(self):
        ident = "JP-W41-02"
        a = observe(ident, body(ident), fetched_url=TARGETS[ident][0],
                    content_type="text/html", observed_utc=OBSERVED)
        b = observe(ident, body(ident) + b"<!-- platform update -->",
                    fetched_url=TARGETS[ident][0],
                    content_type="text/html", observed_utc=OBSERVED)
        self.assertNotEqual(a["raw_html_sha256"], b["raw_html_sha256"])
        self.assertEqual(a["decoded_visible_text_sha256"],
                         b["decoded_visible_text_sha256"])
        self.assertFalse(b["historical_html_body_preserved_or_verified"])

    def test_wrong_host_redirect_content_type_and_encoding_fail(self):
        ident = "JP-W41-01"
        for url, ctype in (
            ("https://www.mod.go.jp.evil.example/page.html", "text/html"),
            ("http://www.mod.go.jp/redirect", "text/html"),
            (TARGETS[ident][0] + "?utm=test", "text/html"),
            (TARGETS[ident][0], "application/pdf"),
        ):
            with self.subTest(url=url, ctype=ctype), self.assertRaises(
                    MODObservationError):
                observe(ident, body(ident), fetched_url=url,
                        content_type=ctype, observed_utc=OBSERVED)
        with self.assertRaises(MODObservationError):
            observe(ident, b"\xff\xfe\x00" * 40,
                    fetched_url=TARGETS[ident][0],
                    content_type="text/html", observed_utc=OBSERVED)
        with self.assertRaises(MODObservationError):
            observe(ident, b"x" * (MAX_BYTES + 1),
                    fetched_url=TARGETS[ident][0],
                    content_type="text/html", observed_utc=OBSERVED)

    def test_research_scope_and_rights_must_remain_unapproved(self):
        original = source_rows()
        self.assertEqual(len(attest_packet_scope(original)), 3)
        for change in (
            lambda x: x[0].update(copy_scope="public"),
            lambda x: x[0].update(status="published"),
            lambda x: x[0].update(source_content_sha256="f"*64),
            lambda x: x[0].update(source_url="https://evil.example/"),
            lambda x: x[0].update(title_original="other title"),
            lambda x: x[0].update(language="ja"),
        ):
            rows = copy.deepcopy(original)
            change(rows)
            with self.subTest(change=change), self.assertRaises(
                    MODObservationError):
                summarize(rows, entries(), OBSERVED)

    def test_missing_one_page_or_untrusted_third_page_fails(self):
        sources = source_rows()
        records = entries()
        del records["JP-W41-02"]
        with self.assertRaises(MODObservationError):
            summarize(sources, records, OBSERVED)
        records = entries()
        records["JP-W41-03"] = records["JP-W41-01"]
        with self.assertRaises(MODObservationError):
            summarize(sources, records, OBSERVED)

    def test_manual_http_fetch_has_exact_url_and_no_redirect_handler(self):
        ident = "JP-W41-01"
        page = body(ident)
        response = MagicMock()
        response.status = 200
        response.geturl.return_value = TARGETS[ident][0]
        response.headers = {"Content-Type": "text/html", "Content-Encoding": "identity"}
        response.read.return_value = page
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch("scripts.japan_mod_html_observation.urllib.request.build_opener",
                   return_value=opener) as build:
            outcome = read_official_html(ident)
        self.assertEqual(outcome["payload"], page)
        self.assertEqual(outcome["fetched_url"], TARGETS[ident][0])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, TARGETS[ident][0])
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 18)
        self.assertEqual(build.call_count, 1)
        with self.assertRaises(MODObservationError):
            read_official_html("JP-W41-04")

    def test_http_redirect_and_oversized_body_refused_before_receipt(self):
        ident = "JP-W41-02"
        response = MagicMock()
        response.status = 200
        response.geturl.return_value = "https://other.mod.go.jp/"
        response.headers = {"Content-Type": "text/html"}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("scripts.japan_mod_html_observation.urllib.request.build_opener") as maker:
            maker.return_value.open.return_value = response
            with self.assertRaises(MODObservationError):
                read_official_html(ident)
            response.geturl.return_value = TARGETS[ident][0]
            response.read.return_value = b"x" * (MAX_BYTES + 1)
            with self.assertRaises(MODObservationError):
                read_official_html(ident)

    def test_output_mode_0600_exclusive_and_refuses_repo(self):
        receipt = summarize(source_rows(), entries(), OBSERVED)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "observations.json"
            write_private(out, receipt)
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(out.read_text())["observation_count"], 2)
            with self.assertRaises(ValueError):
                write_private(out, receipt)
        with self.assertRaises(ValueError):
            write_private(Path(__file__).resolve().parents[1] /
                          "DO_NOT_WRITE_MOD_OBSERVATION.json", receipt)

    def test_cli_requires_explicit_live_fetch_and_never_sends_model_email(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "observations.json"
            args = ["--fetch-live", "--out", str(out)]
            with patch("scripts.japan_mod_html_observation.load_editorial_evidence",
                       return_value=source_rows()), patch(
                       "scripts.japan_mod_html_observation.read_official_html",
                       side_effect=lambda ident: entries()[ident]) as reader, patch(
                       "scripts.sunday_editorial_handoff.send_packet") as mail:
                self.assertEqual(main(args), 0)
                self.assertEqual(reader.call_count, 2)
                mail.assert_not_called()
            report = json.loads(out.read_text())
            self.assertFalse(report["model_input_authorized"])
            self.assertFalse(report["publication_authorized"])
            with self.assertRaises(SystemExit):
                main(["--out", str(Path(d)/"not-created.json")])


if __name__ == "__main__":
    unittest.main()
