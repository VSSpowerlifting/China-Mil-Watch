"""Publication boundaries and rendered fidelity for the reading architecture."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bs4 import BeautifulSoup
from core.brief_presentation import presentation_html_errors, presentation_view
from core.brief_source_linked import fingerprint, manuscript_html_errors
from scripts import author_brief, brief_presentation
from tests import test_brief_presentation as fixtures

ROOT, SLUG, ARTICLE_PATH = fixtures.ROOT, fixtures.SLUG, fixtures.ARTICLE_PATH


def renderer():
    spec = importlib.util.spec_from_file_location("presentation_test_renderer", ROOT / "site/render.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PresentationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.article = json.loads(ARTICLE_PATH.read_text())
        self.manifest = json.loads((ROOT / "briefs/presentation" / (SLUG + ".json")).read_text())
        self.fixture = fixtures.BriefPresentationTests()
        self.fixture.setUp()

    def render(self, manifest):
        from core.brief_collection import brief_view, brief_citation
        view = brief_view(SLUG, self.article, desk_names={}, state_labels={},
                          state_order=[], language_label=str)
        view["citation"] = brief_citation(view)
        view["presentation"] = presentation_view(manifest, self.article)
        return self.fixture.render(view)

    def test_exact_manuscript_citations_and_publication_identity_survive_structure(self):
        before = self.render(None)
        after = self.render(self.manifest)
        self.assertEqual(manuscript_html_errors(self.article, after), [])
        self.assertEqual(presentation_html_errors(self.manifest, after), [])
        old, new = BeautifulSoup(before, "html.parser"), BeautifulSoup(after, "html.parser")
        for selector in (".brief-byline", ".brief-meta", ".brief-author", "#s-cite", "#s-publishers"):
            old_node, new_node = old.select_one(selector), new.select_one(selector)
            if selector in ("#s-cite", "#s-publishers"):
                self.assertEqual(new_node.attrs.pop("tabindex"), "-1")
                self.assertNotIn("tabindex", old_node.attrs)
            self.assertEqual(str(old_node), str(new_node), selector)
        self.assertEqual(fingerprint(self.article), "3ff586938e7680a014a7b6b6c60449327c9d07dcb12b2f6845fc0d3749a44c57")
        self.assertEqual(self.article["issue_number"], 18)
        self.assertEqual(self.article["desks"], [])
        self.assertEqual(self.article["source_trail"], [])
        self.assertEqual(self.article["coverage_by_desk"], {})
        for index, paragraph in enumerate(self.article["body_paragraphs"], 1):
            self.assertEqual(new.select_one('[data-manuscript-paragraph="%d"]' % index).get_text(),
                             "".join(run["text"] for run in paragraph))
        self.assertTrue(manuscript_html_errors(self.article, after.replace("On October 8", "On  October 8")))
        self.assertTrue(manuscript_html_errors(self.article, after.replace('data-source="s1"', 'data-source="s2"', 1)))

    def test_output_gate_rejects_wrong_headings_boundaries_toc_and_unapproved_components(self):
        html = self.render(self.manifest)
        for broken in (
            html.replace("Introduction</h2>", "Unreviewed heading</h2>"),
            html.replace('href="#reading-identity"', 'href="#reading-aviation"'),
            html.replace('data-manuscript-paragraph="2"', 'data-manuscript-paragraph="4"'),
            html.replace('id="reading-introduction"', 'id="reading-identity"'),
            html.replace(self.manifest["central_finding"]["quote"], "Changed excerpt", 1),
        ):
            self.assertTrue(presentation_html_errors(self.manifest, broken))
        self.assertTrue(presentation_html_errors(None, html))
        self.assertEqual(presentation_html_errors(None, self.render(None)), [])

    def test_isolated_evidence_fixture_quotes_approved_text_and_passes_fidelity(self):
        fixture = json.loads((ROOT / "tests/fixtures/brief-presentation/evidence-excerpts.json").read_text())
        from core.brief_presentation import validate_presentation
        self.assertEqual(validate_presentation(fixture, self.article, slug=SLUG), [])
        html = self.render(fixture)
        self.assertIn("What the evidence establishes", html)
        self.assertIn("What remains uncertain", html)
        self.assertEqual(presentation_html_errors(fixture, html), [])
        self.assertEqual(manuscript_html_errors(self.article, html), [])
        self.assertNotIn("evidence", self.manifest)

    def test_new_source_linked_numbering_requires_an_independent_presentation_receipt(self):
        draft = copy.deepcopy(self.article)
        draft.update(editorial_status="draft", approval=None, issue_number=None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "briefs" / (SLUG + ".json")
            source.parent.mkdir()
            source.write_text(json.dumps(draft))
            self.assertTrue(author_brief.presentation_problems(source, draft))
            manifest_path = source.parent / "presentation" / source.name
            manifest_path.parent.mkdir()
            manifest_path.write_text(json.dumps(self.manifest))
            self.assertEqual(author_brief.presentation_problems(source, draft), [])
            self.assertTrue(author_brief.presentation_problems(source, draft, release=True))
            manifest_path.write_text(json.dumps(self.fixture.approved()))
            self.assertEqual(author_brief.presentation_problems(source, draft, release=True), [])
            self.assertEqual(source.read_text(), json.dumps(draft))
        self.assertEqual(author_brief.presentation_problems(ARTICLE_PATH, self.article, release=True), [])

    def test_numbering_command_refuses_unapproved_structure_without_writing_article(self):
        from types import SimpleNamespace
        draft = copy.deepcopy(self.article)
        draft.update(editorial_status="draft", approval=None, issue_number=None)
        with tempfile.TemporaryDirectory() as directory:
            briefs = Path(directory) / "briefs"
            briefs.mkdir()
            source = briefs / (SLUG + ".json")
            source.write_text(json.dumps(draft))
            before = source.read_bytes()
            args = SimpleNamespace(path=str(source), approved_by="Test-only fixture", approved_on="2026-10-13",
                                   approval_reference="Simulated only", db=str(ROOT / "pla_watch.db"))
            with mock.patch.object(author_brief, "BRIEFS_DIR", briefs), \
                    mock.patch.object(author_brief, "existing_issues", return_value=[]), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(author_brief.cmd_approve(args), 1)
            self.assertEqual(source.read_bytes(), before)

    def test_private_review_destination_and_mode_guards_fail_before_render(self):
        render = renderer()
        path = ROOT / "briefs/presentation" / (SLUG + ".json")
        for destination in (render.OUTPUT_DIR, ROOT, ROOT / "docs", ROOT.parent):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                render.render_site(output_dir=destination, review_presentation=path)
        with self.assertRaises(ValueError):
            render.render_site("legacy", review_presentation=path)
        with self.assertRaises(ValueError):
            render.render_site(review_brief=ARTICLE_PATH, review_presentation=path)

    def test_future_draft_presentation_preview_is_private_and_keeps_source_untouched(self):
        import sys
        sys.path.insert(0, str(ROOT / "site/preview"))
        import generate_preview as gp
        draft = copy.deepcopy(self.article)
        draft.update(editorial_status="draft", approval=None, issue_number=None)
        with tempfile.TemporaryDirectory() as directory:
            briefs = Path(directory) / "briefs"
            briefs.mkdir()
            source = briefs / (SLUG + ".json")
            source.write_text(json.dumps(draft))
            (briefs / "presentation").mkdir()
            manifest_path = briefs / "presentation" / source.name
            manifest_path.write_text(json.dumps(self.manifest))
            out = Path(directory) / "private-review"
            gp.build(out, gp.PUBLIC_TITLE, ROOT / "pla_watch.db",
                     snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                     briefs_dir=briefs,
                     review_presentation=ROOT / "briefs/presentation" / source.name)
            html = (out / "briefs" / (SLUG + ".html")).read_text()
            self.assertIn("Private presentation review", html)
            self.assertIn("unapproved, unnumbered and unpublished", html)
            self.assertIn('content="noindex', html)
            self.assertNotIn('rel="canonical"', html)
            self.assertNotIn("No. 18", html)
            self.assertFalse((out / "sitemap.xml").exists())
            self.assertFalse((out / "briefs/feed.xml").exists())
            self.assertEqual(manuscript_html_errors(draft, html), [])
            self.assertEqual(presentation_html_errors(self.manifest, html), [])
            self.assertEqual(json.loads(source.read_text()), draft)

    def test_helper_is_explicit_deterministic_and_does_not_approve_or_overwrite(self):
        sections = [brief_presentation.section_arg("reading-article|1|11|Article")]
        a = brief_presentation.scaffold(self.article, SLUG, sections)
        self.assertEqual(a, brief_presentation.scaffold(self.article, SLUG, sections))
        self.assertIsNone(a["approval"])
        self.assertEqual(a["status"], "draft")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(brief_presentation.main(["check", str(ROOT / "briefs/presentation" / (SLUG + ".json")), "--release"]), 2)
            self.assertEqual(brief_presentation.main(["scaffold", str(ARTICLE_PATH), "--section", "reading-article|1|11|Article"]), 2)
        media_manifest = dict(self.manifest, figures=[{"media_id": "unadmitted-image", "after_paragraph": 1}])
        with self.assertRaisesRegex(ValueError, "approved media admission"):
            brief_presentation.check_media(media_manifest, self.article, SLUG)


if __name__ == "__main__":
    unittest.main()
