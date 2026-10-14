"""Contracts for independently reviewed Brief reading structure."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from core import brief_collection
from core.brief_presentation import (CHECKS, VERSION, load_presentation,
                                    presentation_html_errors,
                                    presentation_fingerprint,
                                    presentation_view, validate_presentation)
from core.brief_source_linked import manuscript_html_errors

ROOT = Path(__file__).resolve().parent.parent
ARTICLE_PATH = ROOT / "briefs/what-is-being-built-in-laos.json"
SLUG = "what-is-being-built-in-laos"


class BriefPresentationTests(unittest.TestCase):
    def setUp(self):
        self.article = json.loads(ARTICLE_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "briefs/presentation" / (SLUG + ".json")).read_text(encoding="utf-8"))

    def approved(self, manifest=None):
        result = copy.deepcopy(manifest or self.manifest)
        result["status"] = "approved"
        result["approval"] = {
            "reviewed_by": "Test reviewer (simulated only)",
            "reviewed_on": "2026-10-13",
            "reference": "test-only simulated receipt; not publication approval",
            "fingerprint": "",
            "checks": {name: True for name in CHECKS},
        }
        result["approval"]["fingerprint"] = presentation_fingerprint(result)
        return result

    def assertInvalid(self, manifest, message):
        errors = validate_presentation(manifest, self.article, slug=SLUG)
        self.assertTrue(any(message in error for error in errors), errors)

    def test_real_laos_manifest_is_valid_draft_and_is_withheld_from_public_load(self):
        self.assertEqual(validate_presentation(self.manifest, self.article, slug=SLUG), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (SLUG + ".json")
            path.write_text(json.dumps(self.manifest), encoding="utf-8")
            self.assertIsNone(load_presentation(path, self.article, slug=SLUG))
            self.assertEqual(load_presentation(path, self.article, slug=SLUG, review=True), self.manifest)
            with self.assertRaisesRegex(ValueError, "missing"):
                load_presentation(Path(directory) / "missing.json", self.article, slug=SLUG, review=True)

    def test_only_approved_presentation_loads_for_public_use(self):
        manifest = self.approved()
        self.assertEqual(validate_presentation(manifest, self.article, slug=SLUG), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (SLUG + ".json")
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(load_presentation(path, self.article, slug=SLUG), manifest)

    def test_public_load_withholds_stale_and_incomplete_identified_drafts(self):
        drafts = [dict(self.manifest, manuscript_fingerprint="0" * 64, sections=None),
                  {"version": VERSION, "article": SLUG, "status": "draft"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (SLUG + ".json")
            for draft in drafts:
                with self.subTest(draft=draft):
                    path.write_text(json.dumps(draft), encoding="utf-8")
                    self.assertIsNone(load_presentation(path, self.article, slug=SLUG))
                    with self.assertRaises(ValueError):
                        load_presentation(path, self.article, slug=SLUG, review=True)

    def test_public_load_still_rejects_invalid_approved_or_unclassifiable_manifests(self):
        approved = self.approved()
        approved["manuscript_fingerprint"] = "0" * 64
        manifests = [approved, None, [], "draft", {"status": "draft"},
                     dict(self.manifest, status=None), dict(self.manifest, status="unknown"),
                     dict(self.manifest, version="unknown"), dict(self.manifest, article="other")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (SLUG + ".json")
            for manifest in manifests:
                with self.subTest(manifest=manifest):
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                    for review in (False, True):
                        with self.assertRaises(ValueError):
                            load_presentation(path, self.article, slug=SLUG, review=review)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_presentation(path, self.article, slug=SLUG)

    def test_manifest_missing_unknown_and_corrupt_fields_fail_closed(self):
        for changed in (
            {key: value for key, value in self.manifest.items() if key != "sections"},
            dict(self.manifest, invented=True),
            dict(self.manifest, version=None),
            dict(self.manifest, article=[]),
            dict(self.manifest, manuscript_fingerprint=7),
            dict(self.manifest, status="pending"),
            dict(self.manifest, sections="not a list"),
            dict(self.manifest, approval={}),
        ):
            with self.subTest(changed=changed):
                self.assertTrue(validate_presentation(changed, self.article, slug=SLUG))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (SLUG + ".json")
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_presentation(path, self.article, slug=SLUG)

    def test_section_ranges_reject_gaps_overlaps_reordering_and_duplicates(self):
        for sections in (
            [dict(s) for s in self.manifest["sections"][:-1]],
            [dict(s) for s in self.manifest["sections"][:1]] +
                [dict(self.manifest["sections"][1], start=1)] + self.manifest["sections"][2:],
            list(reversed(copy.deepcopy(self.manifest["sections"]))),
            [dict(s) for s in self.manifest["sections"][:1]] * 2 + self.manifest["sections"][1:],
        ):
            changed = copy.deepcopy(self.manifest)
            changed["sections"] = sections
            self.assertInvalid(changed, "sections")

    def test_anchors_and_heading_text_are_safe_and_unique(self):
        for ident in ("reading-unsafe id", "Reading-identity", "reading-finding",
                      "reading-evidence", "reading-establishes", "reading-uncertain",
                      "reading-introduction"):
            changed = copy.deepcopy(self.manifest)
            changed["sections"][1]["id"] = ident
            self.assertInvalid(changed, "anchor")
        changed = copy.deepcopy(self.manifest)
        changed["sections"][0]["heading"] = "<script>alert(1)</script>"
        self.assertInvalid(changed, "plain text")

    def test_stale_article_binding_is_rejected(self):
        article = copy.deepcopy(self.article)
        article["body_paragraphs"][0][0]["text"] += " Unreviewed addition."
        self.assertTrue(any("binding is stale" in e for e in
                            validate_presentation(self.manifest, article, slug=SLUG)))
        self.assertTrue(any("identity differs" in e for e in
                            validate_presentation(self.manifest, self.article, slug="different-article")))

    def test_excerpts_must_be_exact_plain_text_and_use_supported_sources(self):
        paragraph = self.article["paragraph_support"][9]
        exact = self.manifest["central_finding"]["quote"]
        self.assertIn(exact, "".join(r["text"] for r in self.article["body_paragraphs"][9]))
        for quote in (exact + " invented", "<em>" + exact + "</em>", " "):
            changed = copy.deepcopy(self.manifest)
            changed["central_finding"]["quote"] = quote
            self.assertInvalid(changed, "exact approved")
        unsupported = copy.deepcopy(self.manifest)
        unsupported["central_finding"]["sources"] = ["not-a-Laos-reference"]
        self.assertInvalid(unsupported, "unsupported evidence")
        duplicate = copy.deepcopy(self.manifest)
        duplicate["central_finding"]["sources"] = [paragraph["sources"][0]] * 2
        self.assertInvalid(duplicate, "unsupported evidence")
        malformed = copy.deepcopy(self.manifest)
        malformed["central_finding"]["paragraph"] = True
        self.assertInvalid(malformed, "paragraph is invalid")

    def test_evidence_requires_both_bounded_parts_and_valid_excerpts(self):
        for evidence in ({"establishes": []}, {"establishes": [], "uncertain": []},
                         {"establishes": "text", "uncertain": []}):
            changed = copy.deepcopy(self.manifest)
            changed["evidence"] = evidence
            self.assertInvalid(changed, "evidence")

    def test_approval_requires_complete_receipt_and_digest_tracks_content(self):
        valid = self.approved()
        self.assertEqual(validate_presentation(valid, self.article, slug=SLUG), [])
        for mutate in (
            lambda value: value["approval"].pop("reference"),
            lambda value: value["approval"]["checks"].pop("media"),
            lambda value: value["approval"]["checks"].update(media=False),
            lambda value: value["approval"]["checks"].update(media=1),
            lambda value: value["approval"].update(checks="all passed"),
            lambda value: value["approval"].update(reviewed_on="not-a-date"),
            lambda value: value["approval"].update(reviewed_by=5),
            lambda value: value["approval"].update(fingerprint="0" * 64),
            lambda value: value["sections"][0].update(heading="Changed after review"),
        ):
            changed = copy.deepcopy(valid)
            mutate(changed)
            self.assertTrue(validate_presentation(changed, self.article, slug=SLUG))
        draft_with_receipt = copy.deepcopy(self.manifest)
        draft_with_receipt["approval"] = valid["approval"]
        self.assertInvalid(draft_with_receipt, "cannot carry approval")

    def test_figures_require_unique_integer_positions_and_safe_local_media_ids(self):
        cases = (
            ([{"after_paragraph": 0, "media_id": "approved-photo"}], "placement"),
            ([{"after_paragraph": len(self.article["body_paragraphs"]) + 1,
               "media_id": "approved-photo"}], "placement"),
            ([{"after_paragraph": True, "media_id": "approved-photo"}], "placement"),
            ([{"after_paragraph": 1, "media_id": "approved-photo"},
              {"after_paragraph": 1, "media_id": "another-photo"}], "duplicated"),
            ([{"after_paragraph": 1, "media_id": "../approved-photo"}], "local approved"),
            ([{"after_paragraph": 1, "media_id": "https://example.org/photo"}], "local approved"),
            ([{"after_paragraph": 1, "media_id": 42}], "local approved"),
        )
        for figures, message in cases:
            changed = copy.deepcopy(self.manifest)
            changed["figures"] = figures
            self.assertInvalid(changed, message)

    def test_optional_components_render_without_inventing_content_and_toc_matches_sections(self):
        manifest = copy.deepcopy(self.manifest)
        manifest.pop("central_finding")
        presentation = presentation_view(manifest, self.article)
        view = brief_collection.brief_view(SLUG, self.article, desk_names={}, state_labels={},
                    state_order=[], language_label=str)
        view["citation"] = brief_collection.brief_citation(view)
        view["presentation"] = presentation
        html = self.render(view)
        self.assertEqual(presentation_html_errors(manifest, html), [])
        for section in manifest["sections"]:
            self.assertIn('href="#%s"' % section["id"], html)
            self.assertIn('id="%s"' % section["id"], html)
            self.assertIn(section["heading"], html)
        self.assertNotIn("reading-finding", html)
        self.assertNotIn("reading-evidence", html)
        for index in range(1, len(self.article["body_paragraphs"]) + 1):
            self.assertEqual(html.count('data-manuscript-paragraph="%d"' % index), 1)
        for paragraph, runs in zip(self.article["body_paragraphs"],
                                   [p for s in presentation["sections"] for p in s["paragraphs"]]):
            self.assertEqual(paragraph, runs["runs"])
        unchanged = presentation_view(self.manifest, self.article)
        self.assertEqual(unchanged["central_finding"]["quote"], self.manifest["central_finding"]["quote"])
        self.assertIsNone(unchanged.get("evidence"))

    def test_figure_requires_matching_photograph_media_and_reuses_its_credit(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["figures"] = [{"after_paragraph": 1, "media_id": "laos-approved-photo"}]
        valid_media = {"kind": "photograph", "id": "laos-approved-photo", "credit": [
            {"before": "", "text": "Approved source credit", "href": "https://example.org/credit", "rel": "license noopener nofollow"}
        ], "treatment": "navy", "caption": "Admitted figure caption", "src": "image.jpg",
            "srcset": "image.webp 800w", "width": 800, "height": 500, "alt": "Approved image",
            "focus": "", "label": "Photograph", "notes": ("Toned by IPR",), "notice": ""}
        self.assertEqual(presentation_view(manifest, self.article, media=valid_media)["sections"][0]["paragraphs"][0]["figure"], valid_media)
        for media in (None, {**valid_media, "id": "different"}, {**valid_media, "kind": "plate"}):
            with self.assertRaisesRegex(ValueError, "approved media admission"):
                presentation_view(manifest, self.article, media=media)
        view = brief_collection.brief_view(SLUG, self.article, desk_names={}, state_labels={},
                    state_order=[], language_label=str)
        view["citation"] = brief_collection.brief_citation(view)
        view["presentation"] = presentation_view(manifest, self.article, media=valid_media)
        html = self.render(view)
        self.assertEqual(presentation_html_errors(manifest, html), [])
        self.assertEqual(manuscript_html_errors(self.article, html), [])
        self.assertIn("Approved source credit", html)
        self.assertIn("Admitted figure caption", html)
        self.assertEqual(html.count('data-editorial-id="laos-approved-photo"'), 1)

        wrong_media = html.replace('data-editorial-id="laos-approved-photo"',
                                   'data-editorial-id="other-approved-photo"')
        self.assertTrue(any("figure placements" in error
                            for error in presentation_html_errors(manifest, wrong_media)))
        omitted = re.sub(r'<div class="brief-reading-figure">.*?</div>', "", html, count=1, flags=re.S)
        self.assertTrue(any("figure placements" in error
                            for error in presentation_html_errors(manifest, omitted)))
        figure = re.search(r'<div class="brief-reading-figure">.*?</div>', html, re.S).group(0)
        moved = html.replace(figure, "", 1)
        paragraph_two = re.search(r'(<p data-manuscript-paragraph="2">.*?</p>)', moved, re.S)
        self.assertIsNotNone(paragraph_two)
        moved = moved[:paragraph_two.end()] + figure + moved[paragraph_two.end():]
        self.assertTrue(any("figure placements" in error
                            for error in presentation_html_errors(manifest, moved)))
        caption_paragraph = re.sub(
            r'(<div class="brief-reading-figure">.*?)(</div>)',
            r'\1<p>Unmarked figure credit paragraph</p>\2', html, count=1, flags=re.S)
        self.assertTrue(any("manuscript paragraphs" in error
                            for error in manuscript_html_errors(self.article, caption_paragraph)))

    def render(self, view):
        env = Environment(loader=ChoiceLoader([
            DictLoader({"base.html": "{% block hero %}{% endblock %}{% block content %}{% endblock %}",
                        "_atlas.html": "{% macro breadcrumb(items) %}{% endmacro %}",
                        "_article_nav.html": "{% macro issue_nav(a,b,c,d) %}{% endmacro %}"}),
            FileSystemLoader(ROOT / "site/preview/templates")]),
            autoescape=select_autoescape(["html"]))
        env.filters["reader_date"] = str
        env.filters["brief_prose"] = brief_collection.linked_prose
        return env.get_template("brief.html").render(brief=view, title="IPR",
                    collection_name="Indo-Pacific Record Briefs", briefs_feed_route="")


if __name__ == "__main__":
    unittest.main()
