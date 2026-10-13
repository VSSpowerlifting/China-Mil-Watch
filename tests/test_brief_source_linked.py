"""Editorial narrative pathway; fixtures never constitute human approval."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape
from core import brief_collection, brief_contract
from core.brief_source_linked import (CHECKS, fingerprint, manuscript_html_errors,
                                      safe_publisher_url, validate_source_linked)
from core.desk_registry import load_registry
from scripts import author_brief

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "briefs/what-is-being-built-in-laos.json"


class SourceLinkedTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(SOURCE.read_text())
        self.registry = load_registry()

    def reviewed_fixture(self):
        value = copy.deepcopy(self.value)
        attestation = {"reviewed_by": "Human fixture (simulated only)",
                       "reviewed_on": "2026-10-12", "reference": "test-only attestation",
                       "fingerprint": fingerprint(value)}
        value["policy_ruling"] = dict(attestation)
        value["editorial_review"] = dict(attestation, checks={k: True for k in CHECKS})
        return value

    def render(self, value=None):
        value = value or self.value
        view = brief_collection.brief_view("fixture", value, desk_names={},
                    state_labels={}, state_order=[], language_label=str)
        view["citation"] = brief_collection.brief_citation(view)
        env = Environment(loader=ChoiceLoader([
            DictLoader({"base.html": "{% block hero %}{% endblock %}{% block content %}{% endblock %}",
                        "_atlas.html": "{% macro breadcrumb(items) %}{% endmacro %}"}),
            FileSystemLoader(ROOT / "site/preview/templates")]),
            autoescape=select_autoescape(["html"]))
        env.filters["reader_date"] = str
        env.filters["brief_prose"] = brief_collection.linked_prose
        return env.get_template("brief.html").render(brief=view)

    def test_frozen_manuscript_and_seven_associations(self):
        fields = {k: self.value[k] for k in ("title", "dek", "body_paragraphs", "manuscript_sha256")}
        fields["publisher_references"] = [{k: s[k] for k in ("id", "url")}
                                          for s in self.value["publisher_references"]]
        digest = hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, "4562e65893620126a0413ed82612290762844bb08e3e8766cae927dbaa5a2cf4")
        self.assertEqual(len(self.value["body_paragraphs"]), 11)
        self.assertEqual(len(self.value["publisher_references"]), 7)
        self.assertEqual(manuscript_html_errors(self.value, self.render()), [])

    def test_altered_omitted_reordered_duplicated_and_relinked_html_rejected(self):
        html = self.render()
        for broken in (html.replace("On October 8,", "On October 9,"),
                       html.replace('data-manuscript-paragraph="2"', 'data-omitted="2"'),
                       html.replace(self.value["publisher_references"][0]["url"], "https://example.org/other")):
            self.assertTrue(manuscript_html_errors(self.value, broken))
        changed = copy.deepcopy(self.value)
        changed["body_paragraphs"].reverse()
        self.assertTrue(manuscript_html_errors(self.value, self.render(changed)))
        changed = copy.deepcopy(self.value)
        changed["body_paragraphs"].append(changed["body_paragraphs"][0])
        self.assertTrue(manuscript_html_errors(self.value, self.render(changed)))

    def test_real_candidate_is_unapproved_and_release_held(self):
        self.assertEqual(brief_contract.validate_brief(self.value, self.registry), [])
        errors = brief_contract.validate_readiness(self.value, self.registry)
        self.assertIn("human editorial/source/rights review", " ".join(errors))
        self.assertIn("owner source-linked evidence policy ruling", " ".join(errors))
        self.assertIsNone(self.value["issue_number"])
        with self.assertRaises(brief_contract.BriefContractError):
            brief_contract.approve(self.value, collection=[], registry=self.registry,
                                   approved_by="No authority", approved_on="2026-10-12")

    def test_reviewed_fixture_uses_existing_numbering_not_desk_quotas(self):
        value = self.reviewed_fixture()
        self.assertEqual(brief_contract.validate_readiness(value, self.registry), [])
        approved = brief_contract.approve(value, collection=[{"issue_number": 15}],
                       registry=self.registry, approved_by="Fixture", approved_on="2026-10-12")
        self.assertEqual(approved["issue_number"], 16)
        self.assertEqual(approved["desks"], [])
        self.assertEqual(approved["source_trail"], [])
        with mock.patch.object(author_brief, "read_only", side_effect=AssertionError("no corpus read")):
            self.assertEqual(author_brief.readiness_problems(value, [], ROOT / "pla_watch.db"), [])

    def test_exact_version_review_and_chronology(self):
        for mutate in (
            lambda v: v["body_paragraphs"][0][0].update(text="Different prose"),
            lambda v: v.update(author_name="Different author"),
            lambda v: v["research_contributor"].update(title="Different credit"),
            lambda v: v["publisher_references"][0].update(date="2026-10-13"),
            lambda v: v["publisher_references"][3].update(temporal_role="in-window"),
            lambda v: v.update(week_ending="2026-10-11"),
            lambda v: v["editorial_review"]["checks"].update(original_language=False),
            lambda v: v["policy_ruling"].update(reviewed_on="2026-10-01"),
        ):
            value = self.reviewed_fixture()
            mutate(value)
            self.assertTrue(brief_contract.validate_readiness(value, self.registry))

    def test_missing_malformed_and_synthetic_evidence(self):
        for field, wrong in (("publisher_references", []), ("desks", ["vietnam"]),
                             ("source_trail", [{"record_id": 999999}]),
                             ("coverage_by_desk", {"vietnam": {"records": 1}}),
                             ("synthetic", True), ("body_paragraphs", "not paragraphs"),
                             ("paragraph_support", []), ("title", None),
                             ("evidence_type", "unreviewed-other-type")):
            value = copy.deepcopy(self.value)
            value[field] = wrong
            self.assertTrue(brief_contract.validate_brief(value, self.registry))
        value = copy.deepcopy(self.value)
        value["publisher_references"][0]["record_id"] = 5039
        self.assertTrue(validate_source_linked(value))
        value = copy.deepcopy(self.value)
        value["body_paragraphs"][1][1]["source"] = "missing"
        self.assertTrue(validate_source_linked(value))

    def test_safe_urls_and_escaped_prose(self):
        for url in ("javascript:alert(1)", "data:text/html,x", "https://user:pw@example.org/x",
                    "https://example.org:443/x", "https://example.org/\" onmouseover=\"x",
                    "https://example.org\\evil/x", "//example.org/x", "http://example.org/x"):
            self.assertFalse(safe_publisher_url(url), url)
            value = copy.deepcopy(self.value)
            value["publisher_references"][0]["url"] = url
            self.assertTrue(validate_source_linked(value))
        value = copy.deepcopy(self.value)
        value["body_paragraphs"][0][0]["text"] = '<script>alert(1)</script> & "text"'
        html = self.render(value)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_author_and_separate_contributor_card(self):
        html = self.render()
        self.assertIn("By <span class=\"byline-name\">Benjamin Yang</span>", html)
        self.assertIn('aria-label="Research contributor"', html)
        self.assertIn("Dylan Tanzi", html)
        self.assertIn("Lead Research Analyst", html)
        self.assertIn("Indo-Pacific Record", html)
        self.assertNotIn("0 cited records", html)
        self.assertNotIn("EDITORIAL STATUS", html)

    def test_ordinary_collection_withholds_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "fixture.json").write_text(json.dumps(self.value))
            published, withheld = brief_collection.load_briefs(Path(directory), self.registry)
            self.assertEqual(published, [])
            self.assertEqual(withheld, ["fixture"])

    def test_approved_fixture_joins_the_existing_catalog_and_feed(self):
        value = brief_contract.approve(self.reviewed_fixture(), collection=[{"issue_number": 15}],
                    registry=self.registry, approved_by="Fixture", approved_on="2026-10-12")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "fixture.json")
            path.write_text(json.dumps(value))
            catalog = brief_collection.load_collection([], self.registry, briefs_dir=Path(directory))
            self.assertEqual(len(catalog.briefs), 1)
            row = catalog.briefs[0]
            self.assertEqual(row["url"], "briefs/fixture.html")
            self.assertEqual(row["issue"], 16)
            feed = brief_collection.build_briefs_feed(catalog.briefs, origin="https://example.org")
            self.assertIn("https://example.org/briefs/fixture.html", feed)
            self.assertIn("Benjamin Yang", feed)
            self.assertEqual(manuscript_html_errors(value, self.render(value)), [])
            value["editorial_review"] = None
            path.write_text(json.dumps(value))
            with self.assertRaises(brief_collection.CollectionError):
                brief_collection.load_collection([], self.registry, briefs_dir=Path(directory))


if __name__ == "__main__":
    unittest.main()
