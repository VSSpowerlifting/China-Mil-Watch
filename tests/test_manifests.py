"""
Desk manifest validation tests.

The behaviour under test is that malformed configuration *fails loudly*. A
manifest defect that is silently ignored produces a source which is configured,
appears in no error, and contributes nothing — which is exactly what Xinhua
Military did for the life of the project.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.manifests import ManifestError, load_all_desks, load_manifest  # noqa: E402

CHINA_MANIFEST = REPO_ROOT / "desks" / "china" / "manifest.json"


def base_manifest() -> dict:
    return json.loads(CHINA_MANIFEST.read_text(encoding="utf-8"))


class ManifestCase(unittest.TestCase):
    def write(self, data: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(data, tmp, ensure_ascii=False)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def assertRejects(self, data: dict, *expected_fragments: str):
        with self.assertRaises(ManifestError) as ctx:
            load_manifest(self.write(data))
        message = str(ctx.exception)
        for fragment in expected_fragments:
            self.assertIn(
                fragment, message,
                "error message should mention %r; got: %s" % (fragment, message),
            )


class TestValidManifest(ManifestCase):
    def test_china_manifest_loads(self):
        cfg = load_manifest(CHINA_MANIFEST)
        self.assertEqual(cfg.desk.desk_id, "china")
        self.assertEqual(cfg.desk.public_status, "legacy")
        self.assertEqual(len(cfg.sources), 5)
        self.assertEqual(len(cfg.institutions), 4)

    def test_china_manifest_matches_production_source_slugs(self):
        """
        The manifest must describe the sources that actually exist, or syncing
        it would insert a sixth source or rename a live one.
        """
        cfg = load_manifest(CHINA_MANIFEST)
        self.assertEqual(
            sorted(s.slug for s in cfg.sources),
            ["china_mil_online", "global_times_mil", "mod_china",
             "pla_daily", "xinhua_mil"],
        )

    def test_every_source_declares_an_adapter(self):
        cfg = load_manifest(CHINA_MANIFEST)
        for src in cfg.sources:
            self.assertTrue(src.adapter, "%s has no adapter" % src.slug)
            self.assertIn(":", src.adapter)

    def test_authority_tiers_are_assigned_not_defaulted(self):
        cfg = load_manifest(CHINA_MANIFEST)
        tiers = {s.slug: s.authority_tier for s in cfg.sources}
        self.assertEqual(tiers["mod_china"], "A")       # ministry
        self.assertEqual(tiers["pla_daily"], "B")       # service media
        self.assertEqual(tiers["xinhua_mil"], "C")      # state news agency
        self.assertEqual(tiers["global_times_mil"], "D")  # state-linked

    def test_mirror_and_syndicated_sources_are_marked(self):
        cfg = load_manifest(CHINA_MANIFEST)
        by_slug = {s.slug: s for s in cfg.sources}
        self.assertEqual(by_slug["china_mil_online"].originality, "mirror")
        self.assertEqual(by_slug["xinhua_mil"].originality, "syndicated")
        self.assertTrue(by_slug["pla_daily"].is_original)

    def test_load_all_desks(self):
        configs = load_all_desks()
        self.assertIn("china", configs)


class TestRequiredFields(ManifestCase):
    def test_missing_desk_id_fails(self):
        data = base_manifest()
        del data["desk"]["desk_id"]
        self.assertRejects(data, "desk_id", "missing required field")

    def test_empty_desk_id_fails(self):
        data = base_manifest()
        data["desk"]["desk_id"] = "   "
        self.assertRejects(data, "desk_id", "empty")

    def test_missing_source_slug_fails(self):
        data = base_manifest()
        del data["sources"][0]["slug"]
        self.assertRejects(data, "slug", "missing required field")

    def test_missing_institution_id_on_source_fails(self):
        data = base_manifest()
        del data["sources"][0]["institution_id"]
        self.assertRejects(data, "institution_id")

    def test_missing_base_url_fails(self):
        data = base_manifest()
        del data["sources"][1]["base_url"]
        self.assertRejects(data, "base_url")


class TestEnums(ManifestCase):
    def test_unknown_authority_tier_fails(self):
        data = base_manifest()
        data["sources"][0]["authority_tier"] = "S"
        self.assertRejects(data, "authority_tier", "permitted: A, B, C, D")

    def test_unknown_public_status_fails(self):
        data = base_manifest()
        data["desk"]["public_status"] = "beta"
        self.assertRejects(data, "public_status", "legacy")

    def test_unknown_access_method_fails(self):
        data = base_manifest()
        data["sources"][0]["access_method"] = "carrier_pigeon"
        self.assertRejects(data, "access_method", "html")

    def test_unknown_originality_fails(self):
        data = base_manifest()
        data["sources"][0]["originality"] = "borrowed"
        self.assertRejects(data, "originality", "original")

    def test_unknown_institution_type_fails(self):
        data = base_manifest()
        data["institutions"][0]["institution_type"] = "guild"
        self.assertRejects(data, "institution_type")

    def test_unknown_calendar_fails(self):
        data = base_manifest()
        data["desk"]["default_calendar"] = "mayan"
        self.assertRejects(data, "calendar", "gregorian")


class TestDuplicates(ManifestCase):
    def test_duplicate_source_slug_fails(self):
        data = base_manifest()
        data["sources"].append(copy.deepcopy(data["sources"][0]))
        self.assertRejects(data, "duplicate source slug", "pla_daily")

    def test_duplicate_institution_id_fails(self):
        data = base_manifest()
        data["institutions"].append(copy.deepcopy(data["institutions"][0]))
        self.assertRejects(data, "duplicate institution_id")

    def test_duplicate_desk_id_across_desks_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("china", "china_copy"):
                (root / name).mkdir()
                (root / name / "manifest.json").write_text(
                    json.dumps(base_manifest(), ensure_ascii=False),
                    encoding="utf-8",
                )
            with self.assertRaises(ManifestError) as ctx:
                load_all_desks(root)
            self.assertIn("duplicate desk_id", str(ctx.exception))

    def test_slug_claimed_by_two_desks_fails(self):
        """A slug collision would merge two countries' history into one row."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "china").mkdir()
            (root / "china" / "manifest.json").write_text(
                json.dumps(base_manifest(), ensure_ascii=False), encoding="utf-8"
            )
            other = base_manifest()
            other["desk"]["desk_id"] = "elsewhere"
            other["desk"]["jurisdiction_code"] = "XX"
            (root / "elsewhere").mkdir()
            (root / "elsewhere" / "manifest.json").write_text(
                json.dumps(other, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(ManifestError) as ctx:
                load_all_desks(root)
            self.assertIn("claimed by both desk", str(ctx.exception))


class TestReferentialIntegrity(ManifestCase):
    def test_source_referencing_unknown_institution_fails(self):
        data = base_manifest()
        data["sources"][0]["institution_id"] = "cn_does_not_exist"
        self.assertRejects(data, "unknown institution_id")

    def test_institution_with_unknown_parent_fails(self):
        data = base_manifest()
        data["institutions"][1]["parent_institution_id"] = "cn_nope"
        self.assertRejects(data, "unknown parent_institution_id")

    def test_source_language_not_declared_by_desk_fails(self):
        data = base_manifest()
        data["sources"][0]["language_tag"] = "ru-RU"
        self.assertRejects(data, "supported_language_tags")


class TestLanguageTags(ManifestCase):
    def test_underscore_separator_rejected(self):
        data = base_manifest()
        data["desk"]["supported_language_tags"] = ["zh_CN", "en"]
        self.assertRejects(data, "BCP 47")

    def test_non_tag_rejected(self):
        data = base_manifest()
        data["desk"]["supported_language_tags"] = ["chinese", "en"]
        self.assertRejects(data, "primary language subtag")

    def test_empty_language_list_rejected(self):
        data = base_manifest()
        data["desk"]["supported_language_tags"] = []
        self.assertRejects(data, "non-empty list")


class TestMalformed(ManifestCase):
    def test_invalid_json_fails_with_filename(self):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        tmp.write("{ not valid json")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        with self.assertRaises(ManifestError) as ctx:
            load_manifest(Path(tmp.name))
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_missing_file_fails(self):
        with self.assertRaises(ManifestError) as ctx:
            load_manifest(Path("/nonexistent/manifest.json"))
        self.assertIn("not found", str(ctx.exception))

    def test_negative_cadence_rejected(self):
        data = base_manifest()
        data["sources"][0]["expected_cadence_days"] = -3
        self.assertRejects(data, "expected_cadence_days", "positive")

    def test_non_numeric_cadence_rejected(self):
        data = base_manifest()
        data["sources"][0]["expected_cadence_days"] = "daily"
        self.assertRejects(data, "must be a number")


if __name__ == "__main__":
    unittest.main(verbosity=2)
