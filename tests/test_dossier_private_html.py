"""Standalone fictional HTML review prototype; no site templates or live data."""
from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import sqlite3
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from core.dossier_contract import dossier_content_digest
from core.dossier_private_html import PRIVATE_BANNER, render_private_dossier_html
from core.dossier_private_view import PrivateDossierViewHold
from tests.test_dossier_publication import fake_archive, fake_authority, fake_dossier
from tests.test_dossier_private_view import (
    fictional_revision_two, fictional_archive_for,
)


def render(doc=None, archive=None, auth=None, previous=None):
    d = fake_dossier() if doc is None else doc
    report = fake_archive(d) if archive is None else archive
    packet = fake_authority(d) if auth is None else auth
    return render_private_dossier_html(
        d, report, synthetic_authority=packet, previous_sidecar=previous
    )


class Structure(HTMLParser):
    """Capture literal HTML elements and attributes without browsing or IO."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class FictionalPrivateHTMLTests(unittest.TestCase):
    def test_synthetic_html_is_inert_and_watermarked(self):
        page = render()
        self.assertTrue(page.startswith("<!doctype html><html lang=\"en\">"))
        self.assertGreaterEqual(page.count(PRIVATE_BANNER), 2)
        self.assertIn("FICTIONAL PRIVATE DOSSIER PREVIEW", page)
        self.assertIn('name="robots" content="noindex,nofollow,noarchive,nosnippet"', page)
        self.assertIn('name="referrer" content="no-referrer"', page)

    def test_csp_denies_all_non_inline_styles(self):
        page = render()
        parser = Structure()
        parser.feed(page)
        csp = [
            attrs["content"] for tag, attrs in parser.elements
            if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"
        ]
        self.assertEqual(len(csp), 1)
        self.assertIn("default-src 'none'", csp[0])
        self.assertIn("base-uri 'none'", csp[0])
        self.assertIn("form-action 'none'", csp[0])
        self.assertIn("style-src 'unsafe-inline'", csp[0])

    def test_zero_scripts_external_hyperlinks_and_media(self):
        parser = Structure()
        parser.feed(render())
        tags = [tag for tag, _ in parser.elements]
        for forbidden in ("script", "iframe", "img", "form", "link", "base", "video"):
            self.assertNotIn(forbidden, tags)
        for tag, attrs in parser.elements:
            for key, value in attrs.items():
                self.assertFalse(key.startswith("on"))
                if key in ("href", "src", "action"):
                    self.assertTrue(value.startswith("#"), (tag, key, value))

    def test_all_internal_links_have_real_targets(self):
        parser = Structure()
        parser.feed(render())
        ids = {attrs["id"] for _, attrs in parser.elements if "id" in attrs}
        links = [attrs["href"][1:] for tag, attrs in parser.elements
                 if tag == "a" and "href" in attrs]
        self.assertGreaterEqual(len(links), 7)
        self.assertTrue(set(links) <= ids, set(links) - ids)

    def test_authored_prose_is_displayed_and_html_escaped(self):
        d = fake_dossier()
        d["overview"] = "Fictional & limited statement with \"quoted\" text."
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        page = render(d)
        self.assertIn("Fictional &amp; limited statement", page)
        self.assertIn("&quot;quoted&quot;", page)
        self.assertNotIn("Fictional & limited statement", page)

    def test_original_source_body_and_review_receipt_are_never_output(self):
        content = render()
        for forbidden in (
            "Fake Alpha original", "Fake Beta original",
            "synthetic-editor-review-does-not-grant-permission",
            "source_use_decision_ref", "editorial_admission_ref",
            "stored_original_sha256", "model_screening",
            "https://example.org/",
        ):
            self.assertNotIn(forbidden, content)

    def test_supporting_and_counterevidence_are_distinguishable(self):
        d = fake_dossier()
        claim = d["sections"][1]["claims"][0]
        claim["source_record_ids"] = [900001]
        claim["counterevidence_ids"] = [900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        text = render(d)
        self.assertIn("Supporting sources", text)
        self.assertIn("Counterevidence", text)
        self.assertIn('href="#source-900001"', text)
        self.assertIn('href="#source-900002"', text)

    def test_no_contradiction_is_not_presented_as_consensus(self):
        self.assertIn("not evidence of consensus or completeness", render())

    def test_date_basis_stays_attributed_not_asserted_as_actual_event(self):
        d = fake_dossier()
        d["sections"][0]["claims"][0]["event_period"] = {
            "start": "2026-09-12", "end": "2026-09-13",
            "basis": "planned", "date_basis": "Fictional ministry announcement",
        }
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        page = render(d)
        self.assertIn("Date basis: planned", page)
        self.assertIn("Fictional ministry announcement", page)

    def test_no_css_or_js_network_dependencies(self):
        page = render()
        self.assertIn("<style>", page)
        self.assertNotIn("@import", page)
        self.assertNotIn("url(", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<link", page)
        self.assertNotIn("fetch(", page)

    def test_small_screen_and_print_semantics_are_self_contained(self):
        page = render()
        self.assertIn("@media(max-width:820px)", page)
        self.assertIn("@media print", page)
        self.assertIn('class="skip" href="#main"', page)
        self.assertIn('aria-label="On this fictional dossier"', page)
        self.assertIn('<main id="main">', page)
        self.assertIn('<nav aria-label="On this fictional dossier">', page)

    def test_invalid_archive_prevents_html_creation(self):
        archive = fake_archive(fake_dossier())
        archive["content_sha256"] = "0" * 64
        with self.assertRaises(PrivateDossierViewHold):
            render(archive=archive)

    def test_draft_never_enters_html(self):
        d = fake_dossier()
        d["editorial_status"] = "draft"
        d.pop("approval")
        with self.assertRaises(PrivateDossierViewHold):
            render(d)

    def test_real_record_id_cannot_be_disguised_by_fictional_slug(self):
        d = fake_dossier()
        d["sources"][0]["record_id"] = 4428
        d["sections"][0]["claims"][0]["source_record_ids"] = [4428]
        d["sections"][1]["claims"][0]["source_record_ids"] = [4428, 900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        with self.assertRaises(PrivateDossierViewHold):
            render(d)

    def test_real_source_hostname_refuses_preview(self):
        d = fake_dossier()
        d["sources"][0]["url"] = "https://www.mod.gov.sg/article"
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        with self.assertRaises(PrivateDossierViewHold):
            render(d)

    def test_b13_saved_cli_report_is_not_a_render_authorization(self):
        cli_report = {"schema": "ipr-dossier-private-review/1",
                      "eligible_for_publication": False, "dossiers": []}
        with self.assertRaises(PrivateDossierViewHold):
            render(archive=cli_report)

    def test_two_editions_show_only_fictional_historical_comparison(self):
        before, after, packet = fictional_revision_two()
        page = render(after, fictional_archive_for(after), packet, previous=before)
        self.assertIn("Compared with fictional revision 1", page)
        self.assertIn("Revision 2", page)
        self.assertIn("structurally compared drafts", page)
        self.assertNotIn("authentic historical release", page)

    def test_unacknowledged_thematic_relocation_refuses_html(self):
        before, after, packet = fictional_revision_two()
        a = after["sections"][0]["claims"][0]
        b = after["sections"][1]["claims"][0]
        after["sections"][0]["claims"] = [b]
        after["sections"][1]["claims"] = [a]
        after["approval"]["content_sha256"] = dossier_content_digest(after)
        packet = fake_authority(after)
        packet["history_checked"] = True
        with self.assertRaises(PrivateDossierViewHold):
            render(after, fictional_archive_for(after), packet, previous=before)

    def test_data_and_review_packet_never_mutated(self):
        d = fake_dossier()
        a = fake_archive(d)
        auth = fake_authority(d)
        originals = copy.deepcopy((d, a, auth))
        render(d, a, auth)
        self.assertEqual((d, a, auth), originals)

    def test_rendering_same_revision_is_byte_deterministic(self):
        d = fake_dossier()
        a = fake_archive(d)
        p = fake_authority(d)
        self.assertEqual(render(d, a, p),
                         render(copy.deepcopy(d), copy.deepcopy(a), copy.deepcopy(p)))

    def test_real_synthetic_sqlite_to_standalone_html_no_originals_or_writes(self):
        from core.dossier_sources import reconcile_dossier_sources
        from tests.test_dossier_contract import approved
        from tests.test_dossier_sources import BODIES, fake_registry, synthetic_sqlite

        with tempfile.TemporaryDirectory() as dirname:
            database = Path(dirname) / "imaginary.db"
            synthetic_sqlite(database)
            d = approved()
            for src in d["sources"]:
                src["stored_original_sha256"] = hashlib.sha256(
                    BODIES[src["record_id"]].encode("utf-8")
                ).hexdigest()
            d["approval"]["content_sha256"] = dossier_content_digest(d)
            archive = reconcile_dossier_sources(d, database, registry=fake_registry())
            auth = fake_authority(d)
            auth["claim_ids"] = sorted(c["id"] for sec in d["sections"] for c in sec["claims"])
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            page = render(d, archive, auth)
            self.assertIn(PRIVATE_BANNER, page)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            self.assertNotIn(BODIES[900001], page)
            self.assertFalse(Path(str(database) + "-wal").exists())
            self.assertFalse(Path(str(database) + "-shm").exists())


if __name__ == "__main__":
    unittest.main()
