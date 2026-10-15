"""An already published and owner-approved Brief may appear on the Vietnam desk."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader

from core import published_desk_editorials as editorials


class ApprovedPermanentVietnamResearch(unittest.TestCase):
    def test_already_published_vietnam_brief_and_unchanged_other_desks(self):
        rows = editorials.published_desk_editorials("vietnam")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "What Is Being Built in Laos?")
        self.assertEqual(rows[0]["route"], "briefs/what-is-being-built-in-laos.html")
        self.assertEqual(rows[0]["issue_number"], 18)
        self.assertEqual(rows[0]["editorial_status"], "approved")
        self.assertNotIn("body_paragraphs", rows[0])
        self.assertNotIn("publisher_references", rows[0])
        for country in ("philippines", "indonesia", "japan", "korea",
                        "singapore", "china", "us-indopacific"):
            self.assertEqual(editorials.published_desk_editorials(country), [])

    def test_render_and_approved_source_bindings_are_explicit(self):
        root = editorials.ROOT
        source = (root / "site/preview/generate_preview.py").read_text()
        template = (root / "site/preview/templates/desk.html").read_text()
        Environment(loader=FileSystemLoader(str(root / "site/preview/templates")),
                    autoescape=True).parse(template)
        self.assertIn("published_editorials=published_desk_editorials(desk.slug)", source)
        self.assertIn("Published analysis from this desk", template)
        self.assertIn("{{ item.route }}", template)
        self.assertIn("{{ item.dek }}", template)
        self.assertIn("already approved and published through", template)
        self.assertIn("automated source", template)
        self.assertNotIn("original_api_response_utf8", template)
        self.assertNotIn("state/shadow.db", template)

    def test_no_registry_or_public_record_activation(self):
        root = editorials.ROOT
        reg = json.loads((root / "desks/registry.json").read_text())
        row = next(x for x in reg["desks"] if x["slug"] == "vietnam")
        self.assertEqual(row["status"], "shadow")
        self.assertFalse(row["has_production_records"])
        self.assertTrue(row["public"])

    def test_approval_manuscript_source_and_public_page_pinned(self):
        root = editorials.ROOT
        with tempfile.TemporaryDirectory() as td:
            scratch = Path(td)
            (scratch / "briefs").mkdir()
            (scratch / "output/briefs").mkdir(parents=True)
            source = root / "briefs/what-is-being-built-in-laos.json"
            shutil.copyfile(source, scratch / "briefs" / source.name)
            page = scratch / "output/briefs/what-is-being-built-in-laos.html"
            page.write_text("published", encoding="utf-8")
            with patch.object(editorials, "ROOT", scratch):
                self.assertEqual(len(editorials.published_desk_editorials("vietnam")), 1)
                document = json.loads((scratch / "briefs" / source.name).read_text())
                cases = (
                    ("approval", lambda x: x["approval"].update(approved_by="Unsigned")),
                    ("status", lambda x: x.update(editorial_status="draft")),
                    ("digest", lambda x: x.update(manuscript_sha256="0"*64)),
                    ("issue", lambda x: x.update(issue_number=99)),
                    ("source", lambda x: x.update(publisher_references=[])),
                )
                for case, mutate in cases:
                    with self.subTest(case=case):
                        changed = json.loads(json.dumps(document))
                        mutate(changed)
                        (scratch / "briefs" / source.name).write_text(
                            json.dumps(changed), encoding="utf-8")
                        with self.assertRaises(editorials.DeskEditorialError):
                            editorials.published_desk_editorials("vietnam")
                (scratch / "briefs" / source.name).write_text(
                    json.dumps(document), encoding="utf-8")
                page.unlink()
                with self.assertRaises(editorials.DeskEditorialError):
                    editorials.published_desk_editorials("vietnam")

    def test_country_release_remains_manually_guarded(self):
        path = editorials.ROOT / ".github/workflows/country_research_render_only_release.yml"
        source = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("approved_main_sha:", source)
        self.assertIn("if: inputs.publish", source)
        self.assertIn("guard_country_research_output_scope", source)
        self.assertNotIn("\n  schedule:", source)
        self.assertNotIn("\n  push:", source)


if __name__ == "__main__":
    unittest.main()
