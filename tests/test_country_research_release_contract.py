"""Offline structural guard for manual metadata-only country desk release."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/country_research_render_only_release.yml"


class CountryResearchReleaseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_reviewed_merge_or_manual_exact_main_sha_release(self):
        text = self.body
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("EXPECTED_SHA:", text)
        self.assertIn('test "$ACTUAL_SHA" = "$EXPECTED_SHA"', text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("\n  push:", text)
        self.assertIn('    branches: [main]', text)
        self.assertIn('      - "research/approved_desk_research.json"', text)
        self.assertIn('      - ".github/workflows/country_research_render_only_release.yml"', text)
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("github.event_name == 'push' && github.sha || inputs.approved_main_sha", text)
        self.assertIn("github.event_name == 'push' || inputs.publish", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)

    def test_no_unreviewed_site_change_triggers_auto_publication(self):
        text = self.body
        trigger = text.split("\n  push:", 1)[1].split("\n  workflow_dispatch:", 1)[0]
        self.assertIn("branches: [main]", trigger)
        self.assertEqual(
            [line.strip().strip('- ').strip('"') for line in
             trigger.splitlines() if line.strip().startswith('- "')],
            [".github/workflows/country_research_render_only_release.yml",
             "research/approved_desk_research.json"])
        self.assertNotIn("site/preview", trigger)
        self.assertNotIn("pla_watch.db", trigger)
        self.assertNotIn("desks/registry.json", trigger)

    def test_never_collects_or_spends_model_tokens(self):
        text = self.body
        for forbidden in (
            "python pipeline.py", "ANTHROPIC_API_KEY", "shadow_collect.py",
            "scripts/shadow_collect", "actions-gh-pages@v2", "state/shadow.db:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn("python site/render.py", text)
        self.assertIn("python scripts/validate_output.py", text)
        self.assertIn("python scripts/verify_db_current.py", text)

    def test_private_source_and_public_record_are_separate(self):
        text = self.body
        self.assertIn('assert row["entries"] == []', text)
        self.assertIn('d["has_production_records"] is False', text)
        self.assertIn('d["manifest"] is None', text)
        self.assertIn('from core.public_editorial_research import load_catalog', text)
        self.assertIn('if name in editorial_desks:', text)
        self.assertIn('assert "IPR research published — official originals linked" in text', text)
        self.assertIn('assert "not a production source-text archive" in text', text)
        self.assertIn('assert "Shadow evaluation" in text', text)
        self.assertIn('assert "data-reference-list" not in text', text)
        self.assertIn('assert "8 declared" in desk_html', text)

    def test_pull_request_checks_rehearse_actual_renderer_without_deployment(self):
        text = self.body
        self.assertIn("if: github.event_name == 'pull_request'", text)
        self.assertIn("Exercise actual static release build without committing or deploying", text)
        self.assertIn("test -f output/philippines.html", text)
        self.assertIn("test -f output/vietnam.html", text)
        self.assertIn("test -f output/indonesia.html", text)
        self.assertIn("python scripts/validate_output.py", text)

    def test_isolated_full_render_stages_only_reviewed_country_artifacts(self):
        text = self.body
        command = ('python -m scripts.stage_country_research_output '
                   '--from-dir "$RUNNER_TEMP/country-render" --to-dir output')
        self.assertEqual(text.count('python site/render.py --out "$RUNNER_TEMP/country-render"'), 2)
        self.assertEqual(text.count(command), 2)
        self.assertNotIn("python site/render.py\n", text)
        self.assertIn('"scripts/stage_country_research_output.py"', text)
        self.assertIn('"tests/test_stage_country_research_output.py"', text)
        self.assertIn("tests.test_stage_country_research_output", text)

        # No write to the checked-in tree may precede the isolated build or
        # allowlist-only staging. The whole output is validated afterwards.
        for label in (
            "Exercise actual static release build without committing or deploying",
            "Build isolated site and stage only reviewed country presentation",
        ):
            section = text.split("- name: " + label, 1)[1]
            section = section.split("\n      - name:", 1)[0]
            self.assertLess(section.index("python site/render.py --out"),
                            section.index(command))
            self.assertLess(section.index(command),
                            section.index("python scripts/validate_output.py"))
        self.assertIn("python -m scripts.guard_country_research_output_scope", text)

    def test_japan_eleven_originals_are_checked_on_rendered_release_output(self):
        text = self.body
        check = "python -m scripts.guard_japan_official_reference_release"
        self.assertEqual(text.count(check), 2)
        self.assertIn('"scripts/guard_japan_official_reference_release.py"', text)
        self.assertIn('"tests/test_guard_japan_official_reference_release.py"', text)
        self.assertIn("tests.test_guard_japan_official_reference_release -v", text)
        self.assertIn("python site/render.py --out", text)
        self.assertIn("python -m scripts.stage_country_research_output", text)
        # Check the actual staged output after scratch rendering; neither
        # validating just the template nor scanning the stale committed HTML
        # certifies the source-directory publication.
        for label in (
            "Exercise actual static release build without committing or deploying",
            "Build isolated site and stage only reviewed country presentation",
        ):
            section = text.split("- name: " + label, 1)[1]
            section = section.split("\n      - name:", 1)[0]
            self.assertLess(section.index("python -m scripts.stage_country_research_output"),
                            section.index(check))
            self.assertLess(section.index(check),
                            section.index("python scripts/validate_output.py"))

    def test_japan_render_only_release_requires_jcg_index_without_source_admission(self):
        text = self.body
        self.assertIn("test -f output/japan.html", text)
        self.assertIn('japan = country["japan"]', text)
        self.assertIn('japan["manifest"] == "shadow/jp_mod/manifest.json"', text)
        self.assertIn('japan["has_production_records"] is False', text)
        self.assertIn('"https://www.mod.go.jp/j/press/news/"', text)
        self.assertIn('"https://www.mod.go.jp/j/update/index.html"', text)
        self.assertIn('"https://www.kaiho.mlit.go.jp/e/topics_archive/index.html"', text)
        self.assertIn('japan_html.count("Open official publisher index") == 3', text)
        self.assertIn('"manual October 8 Day 0" in japan_html', text)
        self.assertIn('"repository gate was observed unset or unavailable" in japan_html', text)
        self.assertIn('"30 verified scheduled MOD collection slots" in japan_html', text)
        self.assertIn('"state/shadow.db"', text)
        self.assertIn("'href=\"archive.html?desk=japan\"' not in japan_html", text)
        self.assertIn("            output/japan.html", text)
        self.assertIn("if: github.event_name == 'push' || inputs.publish", text)

    def test_scoped_staging_command_executes_without_literal_backslash(self):
        """Reproduce the exact workflow staging shell in a disposable git repo.

        A doubled YAML backslash previously passed a literal \\ to git, causing
        a 128 pathspec failure even after every pre-stage safety gate passed.
        """
        import subprocess
        import tempfile

        block = self.body.split(
            "- name: Stage only approved country research presentation files", 1
        )[1].split("python -m scripts.guard_country_research_output_scope", 1)[0]
        commands = [
            line.strip() for line in block.splitlines()
            if line.lstrip().startswith("git add -A --")
        ]
        self.assertEqual(len(commands), 1)
        command = commands[0]
        self.assertNotIn(chr(92), command, "No shell continuations in staging command")
        expected = {
            "output/philippines.html", "output/vietnam.html",
            "output/indonesia.html", "output/japan.html", "output/desks.html",
            "output/desk-references.js", "output/desk-references.css",
        }
        self.assertEqual(set(command.split()[4:]), expected)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in expected | {"output/analysis.html"}:
                out = root / path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("baseline", encoding="utf-8")
            def git(*args):
                return subprocess.run(["git", *args], cwd=root,
                                      capture_output=True, text=True, check=True)
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            git("add", "-A")
            git("commit", "-qm", "baseline")
            for filename in ("output/japan.html", "output/desks.html",
                             "output/analysis.html"):
                (root / filename).write_text("updated", encoding="utf-8")
            subprocess.run(["bash", "-e", "-c", command], cwd=root,
                           check=True, capture_output=True, text=True)
            self.assertEqual(set(git("diff", "--cached", "--name-only").stdout.splitlines()),
                             {"output/japan.html", "output/desks.html"})
            self.assertEqual(git("diff", "--name-only").stdout.strip(),
                             "output/analysis.html")

    def test_db_immutability_and_safe_publishing(self):
        text = self.body
        self.assertIn("sha256sum -c", text)
        self.assertIn("git diff --exit-code -- pla_watch.db", text)
        self.assertNotIn("git add -A -- output/\n", text)
        self.assertIn("git add -A --", text)
        self.assertIn("output/japan.html output/desks.html", text)
        self.assertIn("python -m scripts.guard_country_research_output_scope", text)
        # Rehearsal + pre-stage + post-stage. Nothing else may reach Pages.
        self.assertEqual(
            text.count("python -m scripts.guard_country_research_output_scope"), 3
        )
        self.assertIn("Fail closed on unrelated staged or pre-existing generated drift", text)
        self.assertIn("scripts/guard_country_research_output_scope.py", text)
        self.assertIn("tests/test_country_research_output_scope.py", text)
        self.assertIn("git fetch origin main", text)
        self.assertIn("git push origin HEAD:main", text)
        self.assertIn("cname: indopacificrecord.org", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("group: daily-update", text)


if __name__ == "__main__":
    unittest.main()
