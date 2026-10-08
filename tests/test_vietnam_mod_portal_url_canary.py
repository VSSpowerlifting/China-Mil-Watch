"""Offline Vietnam MOD WCM identity canary; NEVER a publisher/source approval."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.review_vietnam_mod_portal_links import (
    MODCanaryRefused, article_identity, main, review_observations,
    visible_portal_stamp,
)

JAPAN = ("https://mod.gov.vn/en/detail?current=true&urile="
         "wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2F"
         "general-phan-van-giang-receives-japanese-ambassador-to-vietnam-2026")
COOP = ("https://mod.gov.vn/en/detail?current=true&urile="
        "wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2F"
        "vietnam-japan-defense-cooperation-yields-substantive-results")


def item(url=JAPAN, stamp="15:18 | 07/10/2026",
         title="General Phan Van Giang receives Japanese Ambassador to Vietnam"):
    return {"article_url": url, "printed_title": title, "printed_timestamp": stamp}


def packet(*items):
    return {"schema": "vn-mod-en-manual-url-observations/1", "items": list(items)}


class URLIdentityCanaryTests(unittest.TestCase):
    def test_two_official_article_example_url_shapes_are_only_unverified_leads(self):
        output = review_observations(packet(
            item(), item(COOP, "17:22 | 05/29/2026",
                         "Vietnam - Japan defense cooperation yields substantive results")))
        self.assertEqual(output["status"], "offline-metadata-only-unverified")
        self.assertEqual(len(output["items"]), 2)
        self.assertFalse(output["automated_collection_enabled"])
        self.assertFalse(output["private_model_contribution_authorized"])
        self.assertFalse(output["current_week_coverage_verified"])
        self.assertFalse(output["publisher_silence_verified"])
        for entry in output["items"]:
            self.assertFalse(entry["first_party_page_verified"])
            self.assertFalse(entry["redirect_chain_verified"])
            self.assertFalse(entry["robots_and_terms_reviewed"])
            self.assertFalse(entry["article_body_verified"])
            self.assertFalse(entry["source_use_authorized"])
            self.assertFalse(entry["eligible_for_private_model"])
            self.assertFalse(entry["eligible_for_production"])
            self.assertFalse(entry["eligible_for_publication"])
            self.assertIsNone(entry["source_content_sha256"])
            self.assertIsNone(entry["shadow_state_commit"])
        self.assertEqual(output["items"][0]["operator_supplied_date"], "2026-07-10")

    def test_percent_encoding_variants_share_one_content_identity(self):
        raw = JAPAN.replace("wcm%3Apath%3A%2F", "wcm:path:/").replace("%2F", "/")
        self.assertEqual(article_identity(raw)["source_identity"],
                         article_identity(JAPAN)["source_identity"])
        with self.assertRaisesRegex(MODCanaryRefused, "duplicate article"):
            review_observations(packet(item(JAPAN), item(raw)))

    def test_query_parameter_order_does_not_change_identity(self):
        query = JAPAN.split("?", 1)[1]
        reordered = "https://mod.gov.vn/en/detail?" + "&".join(reversed(query.split("&")))
        self.assertEqual(article_identity(reordered), article_identity(JAPAN))

    def test_host_scheme_userinfo_ports_fragments_and_redirects_fail_closed(self):
        invalid = [
            JAPAN.replace("https:", "http:"),
            JAPAN.replace("mod.gov.vn", "www.mod.gov.vn"),
            JAPAN.replace("mod.gov.vn", "mod.gov.vn.evil.example"),
            JAPAN.replace("mod.gov.vn", "mod.gov.vn:443"),
            JAPAN.replace("mod.gov.vn", "person@mod.gov.vn"),
            JAPAN + "#section",
            JAPAN + "#",
            "https://mod.gov.vn/en/news/",
            ("https://mod.gov.vn/en/news/!ut/p/z0/wcm%3Apath%3A"
             "sa-en-news-rela%2Fgeneral-phan-van-giang-receives-japanese-ambassador"),
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(MODCanaryRefused):
                article_identity(url)

    def test_unknown_identity_parameters_and_source_families_refuse(self):
        bad = [
            JAPAN + "&tracking=1",
            JAPAN + "&urile=another",
            JAPAN + "&current=false",
            JAPAN.replace("current=true", "current=1"),
            JAPAN.replace("/sa-en-news-rela/", "/sa-en-news-world/"),
            JAPAN.replace("sa-en-news-rela%2F", "sa-en-news-world%2F"),
            JAPAN.replace("sa-mod-en%2F", "sa-mod-vi%2F"),
            JAPAN.replace("sa-mod-en%2F", "sa-mod-en%252F"),
            JAPAN.replace("general-phan-van-giang", "../general-phan-van-giang"),
            JAPAN.replace("general-phan-van-giang", "General-Phan-Van-Giang"),
            JAPAN.replace("general-phan-van-giang", ""),
            JAPAN.replace("general-phan-van-giang", "another/phan-van-giang"),
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(MODCanaryRefused):
                article_identity(url)

    def test_operator_titles_dates_and_size_bounded(self):
        self.assertEqual(visible_portal_stamp("17:22 | 05/29/2026"),
                         ("2026-05-29", "17:22"))
        for stamp in ("24:00 | 05/29/2026", "17:75 | 05/29/2026",
                      "17:22 | 02/30/2026", "2026-05-29", "17:22 | 05/29/2026\n"):
            with self.subTest(stamp=stamp), self.assertRaises(MODCanaryRefused):
                visible_portal_stamp(stamp)
        for title in ("bad", "A" * 301, "Valid title but with\ninjected content"):
            with self.subTest(title=title), self.assertRaises(MODCanaryRefused):
                review_observations(packet(item(title=title)))
        with self.assertRaises(MODCanaryRefused):
            review_observations(packet(*[item(COOP) for _ in range(21)]))
        with self.assertRaises(MODCanaryRefused):
            review_observations({"schema": "vn-mod-en-manual-url-observations/1",
                                 "items": [dict(item(), source_use_authorized=True)]})

    def test_output_file_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)
            inp, out = path / "input.json", path / "out.json"
            inp.write_text(json.dumps(packet(item())), encoding="utf-8")
            self.assertEqual(main(["--input", str(inp), "--out", str(out)]), 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(data["items"][0]["eligible_for_private_model"])
            existing = out.read_bytes()
            with self.assertRaises(MODCanaryRefused):
                main(["--input", str(inp), "--out", str(out)])
            self.assertEqual(out.read_bytes(), existing)

    def test_no_transport_email_model_or_publication_apis(self):
        text = (Path(__file__).resolve().parents[1] /
                "scripts/review_vietnam_mod_portal_links.py").read_text()
        for forbidden in ("import requests", "import httpx", "urllib.request",
                          "smtplib", "anthropic", "sqlite3", "git push",
                          "send_packet(", "publish(", "DB_PATH"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
