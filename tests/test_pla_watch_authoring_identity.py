"""
The PLA Watch keeps its history when the project changes its name.

The project was renamed on 2026-08-27: China Mil Watch became Indo-Pacific
Record. Editions 1-13 were published under the predecessor name and keep it;
edition 14 onward are Indo-Pacific Record. The series name, The PLA Watch, is
unchanged throughout and is not era-dependent.

The specific regression these tests exist for: editions 1 and 2 store no author
fields at all. They rendered the historical identity only because
`scripts/generate_pla_watch.py`'s module constants were still stale, so
correcting those constants would have silently rebranded two published editions
with nothing failing. Identity is now resolved by era in
`core/edition_identity.py`, and these tests hold that line.

Nothing here calls Anthropic, fetches a URL, runs collection, or writes into
the tracked `output/` tree. Render tests use temporary directories.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.edition_identity import (                                # noqa: E402
    ERA_CURRENT, ERA_HISTORICAL, LAST_HISTORICAL_ISSUE, RENAME_DATE,
    RETROSPECTIVE_LABEL, SERIES_NAME, TIMING_REGULAR, TIMING_RETROSPECTIVE,
    TIMINGS, IdentityError, current_identity_fields, era_for, parse_timing,
    resolve_identity)

POSTS = REPO_ROOT / "output" / "the-pla-watch" / "posts"
HISTORICAL_NAME = "China Mil Watch"
CURRENT_NAME = "Indo-Pacific Record"


def sidecar(name):
    return json.loads((POSTS / f"{name}.json").read_text(encoding="utf-8"))


class TestTheRenameBoundary(unittest.TestCase):

    def test_edition_13_resolves_historical(self):
        self.assertEqual(era_for(sidecar("2026-08-08")), ERA_HISTORICAL)
        self.assertEqual(resolve_identity(sidecar("2026-08-08"))["publication"],
                         HISTORICAL_NAME)

    def test_edition_1_stores_no_author_fields_and_still_resolves_historical(self):
        """
        The regression. No. 1 carries none of the author keys, so before the
        contract it inherited whatever the generator's constants said.
        """
        sc = sidecar("2026-05-09")
        for key in ("author_name", "author_title", "author_bio", "author_links"):
            self.assertNotIn(key, sc, "fixture assumption changed")
        ident = resolve_identity(sc)
        self.assertEqual(ident["era"], ERA_HISTORICAL)
        self.assertEqual(ident["publication"], HISTORICAL_NAME)
        self.assertIn(HISTORICAL_NAME, ident["author_title"])

    def test_every_published_edition_resolves_historical(self):
        for path in sorted(POSTS.glob("*.json")):
            sc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(edition=sc.get("issue_number")):
                self.assertEqual(resolve_identity(sc)["publication"],
                                 HISTORICAL_NAME)

    def test_edition_14_resolves_to_indo_pacific_record(self):
        ident = resolve_identity({"issue_number": 14, "date": "2026-08-15"})
        self.assertEqual(ident["era"], ERA_CURRENT)
        self.assertEqual(ident["publication"], CURRENT_NAME)

    def test_the_boundary_is_the_issue_number_not_the_covered_week(self):
        """
        No. 14 covers a week that *precedes* the rename. The publisher is the
        one publishing it, not the one that existed during the week described —
        a date test would put No. 14 under the retired name.
        """
        self.assertLess(date(2026, 8, 15), RENAME_DATE)
        self.assertEqual(
            resolve_identity({"issue_number": 14, "date": "2026-08-15"})["publication"],
            CURRENT_NAME)
        self.assertEqual(
            resolve_identity({"issue_number": LAST_HISTORICAL_ISSUE,
                              "date": "2026-08-08"})["publication"],
            HISTORICAL_NAME)

    def test_an_explicit_publication_wins_over_inference(self):
        self.assertEqual(
            resolve_identity({"issue_number": 2, "publication": CURRENT_NAME})["era"],
            ERA_CURRENT)
        self.assertEqual(
            resolve_identity({"issue_number": 99, "publication": HISTORICAL_NAME})["era"],
            ERA_HISTORICAL)

    def test_an_unknown_publication_is_refused(self):
        with self.assertRaises(IdentityError):
            resolve_identity({"issue_number": 14, "publication": "Some Other Outlet"})

    def test_the_series_name_is_not_era_dependent(self):
        for sc in ({"issue_number": 1}, {"issue_number": 14}):
            self.assertEqual(resolve_identity(sc)["series_name"], SERIES_NAME)
            self.assertEqual(SERIES_NAME, "The PLA Watch")


class TestAuthorIdentity(unittest.TestCase):

    def test_stored_historical_author_metadata_is_respected(self):
        sc = sidecar("2026-07-11")
        self.assertIn(HISTORICAL_NAME, sc["author_title"])
        self.assertEqual(resolve_identity(sc)["author_title"], sc["author_title"])

    def test_new_author_defaults_drop_the_incoming_wording(self):
        fields = current_identity_fields()
        self.assertNotIn("incoming", fields["author_bio"].lower())
        self.assertNotIn(HISTORICAL_NAME, fields["author_bio"])
        self.assertNotIn(HISTORICAL_NAME, fields["author_title"])

    def test_new_author_identity_matches_the_about_page(self):
        """Derived from output/about.html, not invented."""
        fields = current_identity_fields()
        self.assertIn("Creator and Editor", fields["author_title"])
        self.assertIn(CURRENT_NAME, fields["author_title"])
        self.assertIn("studies International Affairs", fields["author_bio"])
        self.assertIn("George Washington University", fields["author_bio"])

    def test_historical_defaults_keep_the_predecessor_identity(self):
        ident = resolve_identity({"issue_number": 1})
        self.assertIn(HISTORICAL_NAME, ident["author_title"])
        self.assertIn(HISTORICAL_NAME, ident["author_links"])

    def test_new_author_links_point_at_the_current_publication(self):
        self.assertIn(CURRENT_NAME, current_identity_fields()["author_links"])


class TestPublicationTiming(unittest.TestCase):

    def test_allowed_values_are_exactly_two(self):
        self.assertEqual(set(TIMINGS), {TIMING_REGULAR, TIMING_RETROSPECTIVE})

    def test_absent_timing_is_regular(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertEqual(parse_timing(value), TIMING_REGULAR)

    def test_historical_sidecars_lacking_timing_remain_accepted(self):
        for path in sorted(POSTS.glob("*.json")):
            sc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(edition=sc.get("issue_number")):
                self.assertNotIn("publication_timing", sc)
                self.assertFalse(resolve_identity(sc)["is_retrospective"])

    def test_unknown_timing_values_are_refused(self):
        for bad in ("backdated", "Retrospective", "REGULAR", "late", "true", 1, []):
            with self.subTest(value=bad):
                with self.assertRaises(IdentityError):
                    parse_timing(bad)

    def test_retrospective_produces_a_label(self):
        ident = resolve_identity({"issue_number": 14,
                                  "publication_timing": TIMING_RETROSPECTIVE})
        self.assertTrue(ident["is_retrospective"])
        self.assertEqual(ident["retrospective_label"], RETROSPECTIVE_LABEL)

    def test_edition_type_is_independent_of_timing(self):
        """
        Timing says when the edition was written; edition_type says what the
        week held. Neither may be read off the other.
        """
        for etype in ("significant", "routine"):
            for timing in TIMINGS:
                with self.subTest(edition_type=etype, timing=timing):
                    ident = resolve_identity({"issue_number": 14,
                                              "edition_type": etype,
                                              "publication_timing": timing})
                    self.assertEqual(ident["is_retrospective"],
                                     timing == TIMING_RETROSPECTIVE)
        # And the resolver never invents or rewrites edition_type.
        self.assertNotIn("edition_type", resolve_identity({"issue_number": 14}))

    def test_current_identity_fields_records_the_timing(self):
        self.assertEqual(current_identity_fields()["publication_timing"],
                         TIMING_REGULAR)
        self.assertEqual(
            current_identity_fields(TIMING_RETROSPECTIVE)["publication_timing"],
            TIMING_RETROSPECTIVE)
        with self.assertRaises(IdentityError):
            current_identity_fields("whenever")


class TestGeneratorWiring(unittest.TestCase):
    """The generator's constants must come from the contract, not literals."""

    SRC = (REPO_ROOT / "scripts" / "generate_pla_watch.py").read_text(encoding="utf-8")
    RERENDER = (REPO_ROOT / "scripts" / "rerender_pla_watch.py").read_text(encoding="utf-8")

    def test_neither_script_hard_codes_the_predecessor_author_identity(self):
        for name, src in (("generate", self.SRC), ("rerender", self.RERENDER)):
            with self.subTest(script=name):
                self.assertNotIn("Principal Analyst, China Mil Watch", src)
                self.assertNotIn("principal analyst at China Mil Watch", src)
                self.assertNotIn("incoming ", src)

    def test_the_rerenderer_has_no_duplicate_identity_fallback(self):
        """
        The old `except ImportError` block re-declared the predecessor identity,
        so an import failure silently rebranded every edition it touched.
        """
        self.assertNotIn("except ImportError", self.RERENDER)

    def test_the_generator_exposes_a_retrospective_flag(self):
        self.assertIn('"--retrospective"', self.SRC)

    def test_the_sidecar_records_identity_explicitly(self):
        self.assertIn("current_identity_fields(timing)", self.SRC)


class TestWorkflowContract(unittest.TestCase):

    WF = (REPO_ROOT / ".github" / "workflows"
          / "generate_pla_watch_draft.yml").read_text(encoding="utf-8")

    def test_the_workflow_describes_the_saturday_convention(self):
        self.assertIn("Editions close on Saturday", self.WF)
        self.assertNotIn("next Sunday", self.WF)

    def test_the_workflow_offers_a_retrospective_boolean(self):
        self.assertRegex(self.WF, r"(?m)^      retrospective:$")
        self.assertRegex(self.WF, r"(?m)^        type: boolean$")
        self.assertRegex(self.WF, r"(?m)^        default: false$")

    def test_inputs_reach_the_shell_through_the_environment(self):
        self.assertIn("WEEK_ENDING: ${{ inputs.week_ending }}", self.WF)
        self.assertIn("RETROSPECTIVE: ${{ inputs.retrospective }}", self.WF)
        body = self.WF.split("run: |", 1)[-1]
        self.assertNotIn("${{ inputs.", body)

    def test_the_flag_is_passed_only_when_selected(self):
        """The guard, executed as shell against every input combination."""
        start = self.WF.index('set --\n')
        end = self.WF.index('python scripts/generate_pla_watch.py', start)
        guard = "\n".join(line[10:] for line in self.WF[start:end].splitlines())
        script = ("set -euo pipefail\n" + guard
                  + '\nprintf "%s" "$*"\n')

        def run(env):
            full = {"PATH": "/usr/bin:/bin"}
            full.update(env)
            out = subprocess.run(["bash", "-c", script], env=full,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            return out.stdout.strip()

        self.assertEqual(run({}), "")
        self.assertEqual(run({"WEEK_ENDING": "", "RETROSPECTIVE": "false"}), "")
        self.assertEqual(run({"WEEK_ENDING": "2026-08-15", "RETROSPECTIVE": "false"}),
                         "--week-ending 2026-08-15")
        self.assertEqual(run({"WEEK_ENDING": "2026-08-15", "RETROSPECTIVE": "true"}),
                         "--week-ending 2026-08-15 --retrospective")
        self.assertEqual(run({"RETROSPECTIVE": "true"}), "--retrospective")


class TestTemplateSurface(unittest.TestCase):

    TPL = REPO_ROOT / "site" / "templates"

    def read(self, name):
        return (self.TPL / name).read_text(encoding="utf-8")

    def test_the_citation_is_contextual_not_hard_coded(self):
        post = self.read("pla-watch-post.html")
        self.assertIn("{{ publication", post)
        self.assertNotIn(f", {HISTORICAL_NAME}, {{{{ week_ending", post)

    def test_current_site_chrome_names_indo_pacific_record(self):
        base = self.read("pla-watch-base.html")
        self.assertIn(f"{CURRENT_NAME} &rarr;", base)
        self.assertIn(f"{CURRENT_NAME} — Daily Brief", base)
        self.assertNotIn(HISTORICAL_NAME, base)

    def test_site_metadata_does_not_claim_a_sunday_cadence(self):
        base = self.read("pla-watch-base.html")
        self.assertNotIn("Published every Sunday", base)
        self.assertIn("week ending Saturday", base)

    def test_the_archive_stand_names_the_current_publication(self):
        arch = self.read("pla-watch-archive.html")
        self.assertNotIn(HISTORICAL_NAME, arch)
        self.assertIn(CURRENT_NAME, arch)

    def test_index_and_archive_cards_surface_retrospective_status(self):
        for name in ("pla-watch-index.html", "pla-watch-archive.html"):
            with self.subTest(template=name):
                text = self.read(name)
                self.assertIn("publication_timing == 'retrospective'", text)
                self.assertIn("Retrospective edition", text)

    def test_the_post_page_surfaces_retrospective_status(self):
        post = self.read("pla-watch-post.html")
        self.assertIn("is_retrospective", post)
        self.assertIn("retrospective_label", post)


class TestFixtureRenders(unittest.TestCase):
    """
    End-to-end rendering, both sides of the boundary, in a temp directory.
    Never touches the tracked output/ tree.
    """

    @classmethod
    def setUpClass(cls):
        import scripts.generate_pla_watch as gen
        cls.gen = gen

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pw-identity-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def render(self, sc):
        result = {
            "title": sc.get("title", "T"), "dek": sc.get("dek", "D"),
            "signal": "", "opening_note": "O", "what_stood_out": "W",
            "why_it_matters": "M", "what_was_routine": "R",
            "term_to_know_term": "TT", "term_to_know_explanation": "TE",
            "what_im_watching_next": "N",
            "edition_type": sc.get("edition_type", "routine"),
        }
        meta = dict(sc)
        meta.setdefault("week_start", "2026-08-09")
        meta.setdefault("week_ending", sc.get("date", "2026-08-15"))
        meta.setdefault("n_articles", 0)
        meta.setdefault("n_significant", 0)
        return self.gen.render_post(result, meta)

    def test_edition_13_renders_the_historical_masthead(self):
        html = self.render(sidecar("2026-08-08"))
        self.assertIn(HISTORICAL_NAME, html)
        self.assertIn(f"<em>{SERIES_NAME}</em>", html)
        # The masthead tag states the publishing identity of the page it is on.
        self.assertIn(f"A weekly publication of {HISTORICAL_NAME}", html)
        self.assertNotIn(f"A weekly publication of {CURRENT_NAME}", html)

    def test_a_new_edition_renders_the_current_masthead(self):
        html = self.render({"date": "2026-08-15", "issue_number": 14,
                            "title": "T", "dek": "D"})
        self.assertIn(f"A weekly publication of {CURRENT_NAME}", html)
        self.assertNotIn(f"A weekly publication of {HISTORICAL_NAME}", html)

    def test_site_chrome_stays_current_on_a_historical_page(self):
        """
        The split the rename requires: the edition's own byline, citation,
        author block and parent links are historical, while the navigation and
        footer — the site the reader is actually on — are current.
        """
        html = self.render(sidecar("2026-08-08"))
        self.assertIn(f'class="pw-nav-back">{CURRENT_NAME}', html)
        self.assertIn(f"{CURRENT_NAME} — Daily Brief", html)
        self.assertIn(f"{CURRENT_NAME} — Archive", html)

    def test_an_early_edition_remains_historical(self):
        """No. 1 — the one with no stored author fields."""
        html = self.render(sidecar("2026-05-09"))
        self.assertIn(HISTORICAL_NAME, html)

    def test_historical_citation_names_the_predecessor(self):
        html = self.render(sidecar("2026-07-11"))
        cite = re.search(r'id="pw-cite">(.*?)</div>', html, re.S).group(1)
        self.assertIn(HISTORICAL_NAME, cite)
        self.assertNotIn(CURRENT_NAME, cite)

    def test_a_post_rename_edition_renders_indo_pacific_record(self):
        html = self.render({"date": "2026-08-15", "issue_number": 14,
                            "title": "T", "dek": "D"})
        cite = re.search(r'id="pw-cite">(.*?)</div>', html, re.S).group(1)
        self.assertIn(CURRENT_NAME, cite)
        self.assertNotIn(HISTORICAL_NAME, cite)

    def test_a_new_edition_carries_no_incoming_author_wording(self):
        html = self.render({"date": "2026-08-15", "issue_number": 14,
                            "title": "T", "dek": "D"})
        self.assertNotIn("incoming", html.lower())
        self.assertIn("Creator and Editor", html)

    def test_a_retrospective_edition_shows_a_visible_label(self):
        html = self.render({"date": "2026-08-15", "issue_number": 14,
                            "title": "T", "dek": "D",
                            "publication_timing": TIMING_RETROSPECTIVE})
        self.assertIn(RETROSPECTIVE_LABEL, html)

    def test_a_regular_edition_shows_no_retrospective_label(self):
        html = self.render({"date": "2026-08-15", "issue_number": 14,
                            "title": "T", "dek": "D"})
        self.assertNotIn(RETROSPECTIVE_LABEL, html)

    def test_editions_1_to_13_never_show_a_retrospective_label(self):
        for name in ("2026-05-09", "2026-08-08"):
            with self.subTest(edition=name):
                self.assertNotIn(RETROSPECTIVE_LABEL, self.render(sidecar(name)))

    def test_the_rerenderers_current_defaults_are_not_the_predecessor(self):
        """
        A narrow check on the re-renderer's module constants only. It does NOT
        exercise the re-render path — `TestRerenderPath` below does that, and
        an earlier version of this test claimed the coverage without having it.
        """
        import scripts.rerender_pla_watch as rr
        self.assertNotIn(HISTORICAL_NAME, rr.AUTHOR_TITLE)
        self.assertNotIn("incoming", rr.AUTHOR_BIO.lower())


# ── the re-render path, exercised for real ───────────────────────────────────

class RerenderCase(unittest.TestCase):
    """
    Renders through `scripts.rerender_pla_watch._build_post_context()` and the
    real post template — the API-free path that actually rebuilds published
    pages. Nothing here writes into the tracked tree.
    """

    @classmethod
    def setUpClass(cls):
        import scripts.rerender_pla_watch as rr
        from scripts.pw_env import make_pw_env
        cls.rr = rr
        cls.env = make_pw_env()

    def context(self, sc):
        return self.rr._build_post_context(dict(sc))

    def render(self, sc):
        ctx = self.context(sc)
        return ctx, self.env.get_template("pla-watch-post.html").render(**ctx)

    def masthead_tag(self, html):
        m = re.search(r"A weekly publication of ([^<]+)", html)
        return m.group(1).strip() if m else None

    def citation(self, html):
        m = re.search(r'id="pw-cite">(.*?)</div>', html, re.S)
        return m.group(1) if m else ""


class TestRerenderPathPreservesHistoricalEditions(RerenderCase):

    def test_edition_1_rerenders_historical(self):
        """
        No. 1 stores no author fields. Before the fix this path gave it the
        current author title, masthead and citation — a silent rebrand of a
        published edition.
        """
        ctx, html = self.render(sidecar("2026-05-09"))
        self.assertEqual(ctx["publication"], HISTORICAL_NAME)
        self.assertEqual(ctx["publication_home_label"], HISTORICAL_NAME)
        self.assertEqual(ctx["series_name"], SERIES_NAME)
        self.assertIn(HISTORICAL_NAME, ctx["author_title"])
        self.assertEqual(self.masthead_tag(html), HISTORICAL_NAME)
        self.assertIn(HISTORICAL_NAME, self.citation(html))
        self.assertNotIn(CURRENT_NAME, self.citation(html))
        self.assertIn(f'>Visit {HISTORICAL_NAME}', html)

    def test_edition_13_rerenders_historical(self):
        ctx, html = self.render(sidecar("2026-08-08"))
        self.assertEqual(ctx["publication"], HISTORICAL_NAME)
        self.assertIn(HISTORICAL_NAME, ctx["author_title"])
        self.assertEqual(self.masthead_tag(html), HISTORICAL_NAME)
        self.assertIn(HISTORICAL_NAME, self.citation(html))
        self.assertNotIn(CURRENT_NAME, self.citation(html))

    def test_every_published_sidecar_rerenders_historical(self):
        for path in sorted(POSTS.glob("*.json")):
            sc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(edition=sc.get("issue_number")):
                ctx, html = self.render(sc)
                self.assertEqual(ctx["publication"], HISTORICAL_NAME)
                self.assertEqual(self.masthead_tag(html), HISTORICAL_NAME)
                self.assertIn(HISTORICAL_NAME, self.citation(html))
                self.assertNotIn(RETROSPECTIVE_LABEL, html)

    def test_site_chrome_stays_current_on_a_rerendered_historical_page(self):
        _, html = self.render(sidecar("2026-08-08"))
        self.assertIn(f'class="pw-nav-back">{CURRENT_NAME}', html)
        self.assertIn(f"{CURRENT_NAME} — Archive", html)


class TestRerenderPathHandlesNewEditions(RerenderCase):

    BASE = {"date": "2026-08-15", "issue_number": 14, "title": "T", "dek": "D",
            "week_ending": "2026-08-15", "week_start": "2026-08-09"}

    def test_a_retrospective_14_rerenders_with_every_surface(self):
        sc = dict(self.BASE, publication_timing=TIMING_RETROSPECTIVE)
        ctx, html = self.render(sc)
        self.assertEqual(ctx["publication"], CURRENT_NAME)
        self.assertTrue(ctx["is_retrospective"])
        self.assertEqual(ctx["retrospective_label"], RETROSPECTIVE_LABEL)
        self.assertEqual(ctx["publication_timing"], TIMING_RETROSPECTIVE)
        self.assertEqual(self.masthead_tag(html), CURRENT_NAME)
        self.assertIn(CURRENT_NAME, self.citation(html))
        # Every post-level retrospective surface: masthead line, badge, sidebar.
        self.assertGreaterEqual(html.count(RETROSPECTIVE_LABEL), 3)
        self.assertIn("pw-badge--retrospective", html)

    def test_a_regular_14_has_no_retrospective_surface(self):
        ctx, html = self.render(dict(self.BASE))
        self.assertFalse(ctx["is_retrospective"])
        self.assertEqual(ctx["retrospective_label"], "")
        self.assertNotIn(RETROSPECTIVE_LABEL, html)
        self.assertEqual(self.masthead_tag(html), CURRENT_NAME)

    def test_index_and_archive_badges_survive_the_rerender_path(self):
        """The cards read `publication_timing` straight off the sidecar."""
        sc = dict(self.BASE, publication_timing=TIMING_RETROSPECTIVE,
                  edition_label="Routine")
        for tpl, key in (("pla-watch-index.html", "latest_post"),
                         ("pla-watch-archive.html", "posts")):
            with self.subTest(template=tpl):
                payload = {key: (sc if key == "latest_post" else [sc]),
                           "root_path": "../", "archive_posts": []}
                html = self.env.get_template(tpl).render(**payload)
                self.assertIn(RETROSPECTIVE_LABEL, html)
                self.assertIn("pw-badge--retrospective", html)


class TestRerenderPathFailsClosedOnBadIdentity(RerenderCase):

    def test_the_context_builder_refuses_an_unknown_publication(self):
        with self.assertRaises(IdentityError):
            self.context({"date": "2026-08-15", "issue_number": 14,
                          "publication": "Some Other Outlet"})

    def test_the_context_builder_refuses_an_unknown_timing(self):
        with self.assertRaises(IdentityError):
            self.context({"date": "2026-08-15", "issue_number": 14,
                          "publication_timing": "backdated"})

    def test_validation_happens_before_any_derivative_or_write(self):
        """
        One bad sidecar must stop the run before a single HTML or cover file is
        produced, so a partial re-render cannot land.
        """
        good = dict(sidecar("2026-08-08"))
        bad = {"date": "2026-08-15", "issue_number": 14,
               "publication_timing": "whenever"}
        with self.assertRaises(IdentityError) as caught:
            self.rr.validate_sidecar_identities([good, bad])
        self.assertIn("2026-08-15", str(caught.exception))

    def test_valid_sidecars_pass_pre_validation(self):
        loaded = [json.loads(p.read_text(encoding="utf-8"))
                  for p in sorted(POSTS.glob("*.json"))]
        loaded.append({"date": "2026-08-15", "issue_number": 14,
                       "publication": CURRENT_NAME,
                       "publication_timing": TIMING_RETROSPECTIVE})
        self.rr.validate_sidecar_identities(loaded)   # must not raise

    def test_in_memory_enrichment_uses_the_editions_own_identity(self):
        """
        Index and archive cards read the byline off the in-memory sidecar. It
        may be enriched, but only from that edition's resolved identity — never
        from the module's current constants.
        """
        src = (REPO_ROOT / "scripts" / "rerender_pla_watch.py").read_text(encoding="utf-8")
        self.assertNotIn('setdefault("author_name", AUTHOR_NAME)', src)
        self.assertNotIn('setdefault("author_title", AUTHOR_TITLE)', src)
        self.assertIn('setdefault("author_name", _identity["author_name"])', src)

    def test_a_historical_sidecar_enriches_to_its_own_byline(self):
        sc = dict(sidecar("2026-05-09"))
        ident = resolve_identity(sc)
        sc.setdefault("author_title", ident["author_title"])
        self.assertIn(HISTORICAL_NAME, sc["author_title"])


class TestValidatorEnforcesTheContract(unittest.TestCase):
    """`validate_output.py` is the deploy gate; the contract has to reach it."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_output_contract", REPO_ROOT / "scripts" / "validate_output.py")
        cls.vo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.vo)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pw-validate-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.posts = self.tmp / "the-pla-watch" / "posts"
        self.posts.mkdir(parents=True)
        for page in ("index.html", "archive.html"):
            (self.tmp / "the-pla-watch" / page).write_text("", encoding="utf-8")
        (self.tmp / "the-pla-watch" / "feed.xml").write_text(
            "<?xml version='1.0'?><feed/>", encoding="utf-8")

    def write(self, name, **extra):
        sc = json.loads((POSTS / "2026-08-08.json").read_text(encoding="utf-8"))
        sc.update(extra)
        (self.posts / f"{name}.json").write_text(json.dumps(sc), encoding="utf-8")

    def check(self):
        errors, warnings = [], []
        self.vo._validate_pla_watch(self.tmp, errors, warnings)
        return errors, warnings

    def test_a_historical_sidecar_without_the_fields_is_accepted(self):
        self.write("2026-08-08")
        errors, _ = self.check()
        self.assertEqual([e for e in errors if "publication" in e], [])

    def test_valid_values_are_accepted(self):
        self.write("2026-08-08", publication=CURRENT_NAME,
                   publication_timing=TIMING_RETROSPECTIVE)
        errors, _ = self.check()
        self.assertEqual([e for e in errors if "publication" in e], [])

    def test_an_unknown_publication_is_an_error_naming_the_sidecar(self):
        self.write("2026-08-08", publication="Some Other Outlet")
        errors, _ = self.check()
        hits = [e for e in errors if "publication" in e]
        self.assertTrue(hits, "expected a publication error")
        self.assertIn("2026-08-08.json", hits[0])

    def test_an_unknown_timing_is_an_error_naming_the_sidecar(self):
        self.write("2026-08-08", publication_timing="backdated")
        errors, _ = self.check()
        hits = [e for e in errors if "publication_timing" in e]
        self.assertTrue(hits, "expected a timing error")
        self.assertIn("2026-08-08.json", hits[0])

    def test_the_validator_uses_the_contract_not_a_second_copy(self):
        src = (REPO_ROOT / "scripts" / "validate_output.py").read_text(encoding="utf-8")
        self.assertIn("core.edition_identity", src)


class TestCoverTimingIsCanonical(unittest.TestCase):
    """Cover selection, exercised with stubs. No network, no tracked writes."""

    @classmethod
    def setUpClass(cls):
        import scripts.generate_pla_watch_cover as cov
        cls.cov = cov

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pw-cover-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.calls = []

    def run_one(self, sidecar_fields, expect_raises=False):
        cov = self.cov
        path = self.tmp / "2026-08-15.json"
        sc = {"date": "2026-08-15", "issue_number": 14, "title": "T",
              "source_trail": [{"url": "https://example.invalid/a"}]}
        sc.update(sidecar_fields)
        path.write_text(json.dumps(sc), encoding="utf-8")

        calls = self.calls
        originals = {}

        def spy(name, result=None):
            def _fake(*a, **k):
                calls.append(name)
                return result
            return _fake

        for attr, result in (("_auto_fetch_source_image", None),
                             ("_first_image_in_dirs", None)):
            originals[attr] = getattr(cov, attr)
            setattr(cov, attr, spy(attr, result))
        originals["render_cover"] = cov.render_cover
        originals["render_thumbnail"] = getattr(cov, "render_thumbnail", None)
        cov.render_cover = spy("render_cover")
        if originals["render_thumbnail"] is not None:
            cov.render_thumbnail = spy("render_thumbnail")
        originals["_cover_path_for"] = cov._cover_path_for
        originals["_thumb_path_for"] = cov._thumb_path_for
        cov._cover_path_for = lambda d: self.tmp / f"{d}.png"
        cov._thumb_path_for = lambda d: self.tmp / f"{d}-thumb.png"
        originals["_prev_issue_image"] = cov._prev_issue_image
        cov._prev_issue_image = lambda d: None
        try:
            if expect_raises:
                with self.assertRaises(IdentityError):
                    cov.generate_one(path, force=True)
                return None
            cov.generate_one(path, force=True)
            return json.loads(path.read_text(encoding="utf-8"))
        finally:
            for attr, value in originals.items():
                if value is not None:
                    setattr(cov, attr, value)

    def test_retrospective_never_fetches_and_never_uses_curated(self):
        sc = self.run_one({"publication_timing": TIMING_RETROSPECTIVE})
        self.assertNotIn("_auto_fetch_source_image", self.calls)
        self.assertNotIn("_first_image_in_dirs", self.calls)
        self.assertEqual(sc["background_image_source"], "retrospective_gradient")

    def test_a_regular_edition_still_consults_both_helpers(self):
        self.run_one({})
        self.assertIn("_auto_fetch_source_image", self.calls)
        self.assertIn("_first_image_in_dirs", self.calls)

    def test_an_invalid_timing_fails_before_any_helper_or_write(self):
        self.run_one({"publication_timing": "backdated"}, expect_raises=True)
        self.assertEqual(self.calls, [],
                         "no helper or render may run before validation")

    def test_an_approved_edition_image_still_wins_for_a_retrospective(self):
        img = self.tmp / "approved.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0stub")
        sc = self.run_one({"publication_timing": TIMING_RETROSPECTIVE,
                           "media_items": [{"src": str(img)}]})
        self.assertNotEqual(sc["background_image_source"],
                            "retrospective_gradient")
        self.assertNotIn("_auto_fetch_source_image", self.calls)


class TestRetrospectiveCover(unittest.TestCase):

    SRC = (REPO_ROOT / "scripts"
           / "generate_pla_watch_cover.py").read_text(encoding="utf-8")

    def test_timing_is_validated_through_the_contract(self):
        """Behaviour is covered by TestCoverTimingIsCanonical; this pins the
        contract call so a raw string compare cannot creep back."""
        self.assertIn("parse_timing(sidecar.get(\"publication_timing\"))", self.SRC)
        self.assertIn("fetch_source_image = False", self.SRC)
        self.assertIn("allow_curated = False", self.SRC)

    def test_the_curated_fallback_is_gated(self):
        self.assertIn("if bg_path is None and allow_curated:", self.SRC)

    def test_the_background_source_is_recorded_truthfully(self):
        self.assertIn('"retrospective_gradient"', self.SRC)

    def test_a_human_supplied_edition_image_still_wins(self):
        """Priority 1 runs before the retrospective gating takes effect."""
        idx_resolve = self.SRC.index("bg_path = resolve_background_image(sidecar, exclude_path=prev_img)")
        idx_curated = self.SRC.index("if bg_path is None and allow_curated:")
        self.assertLess(idx_resolve, idx_curated)


class TestNoNetworkOrProductionWrites(unittest.TestCase):
    """
    This module must stay offline and must not touch tracked output.

    Checked against the parsed import graph rather than raw substrings: a
    substring scan of this file matches the very names it is asserting are
    absent, which is a test that can only fail.
    """

    def _imports(self):
        import ast
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
        return names

    def test_this_module_imports_nothing_network_capable(self):
        forbidden = {"anthropic", "requests", "urllib", "urllib.request",
                     "http", "http.client", "socket",
                     "scripts.fetch_article_image"}
        self.assertEqual(self._imports() & forbidden, set())

    def test_this_module_imports_only_what_it_needs(self):
        allowed = {"__future__", "json", "re", "shutil", "subprocess", "sys",
                   "tempfile", "unittest", "datetime", "pathlib",
                   "core.edition_identity", "ast", "importlib.util",
                   "scripts.generate_pla_watch", "scripts.rerender_pla_watch",
                   "scripts.generate_pla_watch_cover", "scripts.pw_env"}
        self.assertTrue(self._imports() <= allowed,
                        "unexpected import(s): %s" % sorted(self._imports() - allowed))

    def test_the_tracked_output_tree_is_never_written(self):
        """
        Fixtures are read from `output/`; every write goes to a temp directory.
        Asserted structurally: no write target in this module is derived from
        `POSTS` or from a path rooted at the repository.
        """
        import ast
        src = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("write_text", "write_bytes", "mkdir")):
                continue
            target = ast.unparse(node.func.value)
            with self.subTest(target=target):
                self.assertFalse(
                    target.startswith("POSTS") or "REPO_ROOT" in target,
                    "write target %r is inside the repository" % target)

    def test_fixtures_from_the_tracked_tree_are_only_read(self):
        """`POSTS` is inside tracked output/, and is only ever read from."""
        import ast
        self.assertTrue(POSTS.is_relative_to(REPO_ROOT / "output"))
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("write_text", "write_bytes", "mkdir")):
                self.assertNotIn("POSTS", ast.unparse(node.func.value))


if __name__ == "__main__":
    unittest.main()
