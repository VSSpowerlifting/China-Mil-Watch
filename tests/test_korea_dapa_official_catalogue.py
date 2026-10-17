"""Offline DAPA catalogue contract: official metadata cannot confer publication."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import io

from scripts import qualify_korea_dapa_official_catalogue as sut


def official():
    # Synthetic schema.org JSON based on published official catalogue fields.
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "방위사업청_보도자료",
        "alternateName": "방위사업청_보도자료_20260910",
        "description": "Untrusted description cannot authorize source text.",
        "url": sut.OFFICIAL_URL,
        "creator": {"@type": "Organization", "name": sut.DAPA},
        "encodingFormat": "HWPX",
        "license": sut.ATTRIBUTION_LICENSE,
        "datasetTimeInterval": "연간",
        "dateCreated": "2026-09-12",
        "datePublished": "2026-09-12",
        "dateModified": "2026-09-12",
    }


class DapaOfficialCatalogueContracts(unittest.TestCase):
    def test_exact_pinned_official_identity_is_metadata_only(self):
        result = sut.qualify(official())
        self.assertEqual(result["status"], "OFFICIAL_DAPA_CATALOGUE_METADATA_ONLY")
        self.assertEqual(result["individual_articles_verified"], 0)
        self.assertEqual(result["individual_source_identities_verified"], 0)
        for forbidden in ("publication_authorized",
                          "article_collection_enabled",
                          "document_body_reuse_cleared",
                          "third_party_media_cleared",
                          "declared_rows_independently_verified",
                          "original_hwp_bytes_verified"):
            self.assertIs(result[forbidden], False)

    def test_fake_issuer_and_domain_always_hold(self):
        for field, value in (
            ("url", "https://dapa-datasets.example/unsafe"),
            ("url", "https://www.data.go.kr.evil.example/data/15118819/fileData.do"),
            ("url", "https://www.data.go.kr/data/15118819/fileData.do?download=1"),
            ("name", "Agency reports"),
            ("alternateName", "방위사업청_보도자료_20260911"),
            ("@type", "CreativeWork"),
        ):
            with self.subTest(field=field):
                item = official()
                item[field] = value
                with self.assertRaises(sut.CatalogueHold):
                    sut.qualify(item)
        item = official()
        item["creator"]["name"] = "국방부"
        with self.assertRaisesRegex(sut.CatalogueHold, "issuer_unverified"):
            sut.qualify(item)

    def test_licence_or_source_version_changes_require_requalification(self):
        for name, value in (
            ("license", "CC0"),
            ("license", "공공저작물 : 제 4유형"),
            ("dateModified", "2026-10-17"),
            ("dateCreated", "2026-09-11"),
            ("encodingFormat", "PDF"),
            ("datasetTimeInterval", "매일"),
        ):
            with self.subTest(field=name):
                item = official()
                item[name] = value
                with self.assertRaises(sut.CatalogueHold):
                    sut.qualify(item)

    def test_absent_and_malformed_source_can_never_qualify(self):
        for bad in ([], None, "", 699, {"@type": "Dataset"}, dict(official(), creator=[])):
            with self.subTest(value=type(bad).__name__):
                with self.assertRaises(sut.CatalogueHold):
                    sut.qualify(bad)

    def test_catalogue_descriptions_and_count_claims_confer_no_article_rights(self):
        item = official()
        item["description"] = "699 sources licensed for immediate unrestricted publication"
        item["numberOfRecords"] = 699
        result = sut.qualify(item)
        self.assertEqual(result["individual_articles_verified"], 0)
        self.assertFalse(result["document_body_reuse_cleared"])
        self.assertNotIn("numberOfRecords", result)

    def test_local_file_is_read_only_and_source_bytes_not_printed(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "metadata.json"
            raw = json.dumps(official(), ensure_ascii=False).encode()
            src.write_bytes(raw)
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(sut.main(["--metadata-file", str(src)]), 0)
            result = json.loads(buf.getvalue())
            self.assertFalse(result["publication_authorized"])
            self.assertEqual(src.read_bytes(), raw)
            self.assertFalse((Path(temp) / "metadata.json.new").exists())

    def test_malicious_or_oversize_inputs_are_held_without_body_leaks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad = root / "source.json"
            bad.write_text('{"name": "PRIVATE FAKE PRESS TITLE"', encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(sut.main(["--metadata-file", str(bad)]), 2)
            self.assertNotIn("PRIVATE", buf.getvalue())
            bad.write_bytes(b"a" * (sut.MAX_INPUT_BYTES + 1))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sut.main(["--metadata-file", str(bad)]), 2)
            link = root / "symlink.json"
            link.symlink_to(bad)
            with self.assertRaisesRegex(sut.CatalogueHold, "file_invalid"):
                sut.read_local_metadata(link)

    def test_no_network_collection_workflow_or_publication_effect(self):
        from pathlib import Path
        code = (Path(__file__).resolve().parents[1] /
                "scripts/qualify_korea_dapa_official_catalogue.py").read_text()
        for prohibited in ("urllib.request", "requests.get", "requests.post",
                           "subprocess", "httpx", "pla_watch.db", "gh-pages",
                           "output/korea"):
            self.assertNotIn(prohibited, code)


if __name__ == "__main__":
    unittest.main()
