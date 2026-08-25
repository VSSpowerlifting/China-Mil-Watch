"""
README is the clean-clone entry point: it is what a maintainer reads before
anything else exists to read. Every operational claim it makes is therefore
checked here against the artifact that actually decides the answer — the
workflow file, the tracked source tree — rather than against a constant copied
into the test. A claim that drifts away from its own governing artifact fails.

Why these five and not a prose review: each one, when wrong, sends a maintainer
somewhere the repository does not go. `docs/ARCHITECTURE_AND_PUBLISHING.md` §4
is the governing statement for the CI facts; where README and that document
disagree, that document is right and README is the defect.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
DAILY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily_update.yml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


class TestReadmeDescribesTheSiteGeneratorHonestly(unittest.TestCase):
    """
    `site/generator.py` is not a stub. It renders the daily site on every
    successful scheduled run, and CLAUDE.md lists it as a standing operator
    command. README once annotated it "Not yet implemented", which tells a
    maintainer the opposite of the truth about the one component that produces
    the published site.
    """

    def test_the_generator_exists_and_is_substantial(self):
        gen = REPO_ROOT / "site" / "generator.py"
        self.assertTrue(gen.exists(), "site/generator.py is missing")
        self.assertIn("def generate_site", gen.read_text(encoding="utf-8"))

    def test_readme_does_not_call_the_generator_unimplemented(self):
        text = readme_text()
        for match in re.finditer(r"^.*site/generator\.py.*$", text, re.M):
            line = match.group(0)
            self.assertNotRegex(
                line, r"(?i)not\s+(yet\s+)?implemented",
                "README calls site/generator.py unimplemented; it renders the "
                "published site on every scheduled run")

    def test_no_line_near_the_generator_command_claims_it_is_missing(self):
        # The annotation lived on the line above the command, so check the
        # whole fenced block the command appears in.
        text = readme_text()
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            if "site/generator.py" in block:
                self.assertNotRegex(
                    block, r"(?i)not\s+(yet\s+)?implemented",
                    "the README block containing site/generator.py still "
                    "describes it as unimplemented")


class TestReadmeScheduleMatchesTheWorkflow(unittest.TestCase):
    """
    The daily workflow runs five scheduled windows and lets the scheduling
    guard admit one per New York day. A README naming a single wall-clock hour
    describes a workflow this repository does not contain, and sends anyone
    debugging a missed run to look at the wrong time.
    """

    def cron_hours(self):
        crons = re.findall(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]",
                           DAILY_WORKFLOW.read_text(encoding="utf-8"), re.M)
        self.assertTrue(crons, "no cron entries found in daily_update.yml")
        return crons, sorted({int(c.split()[1]) for c in crons})

    def test_the_workflow_really_has_several_windows(self):
        crons, _ = self.cron_hours()
        self.assertGreater(
            len(crons), 1,
            "this test assumes multiple scheduled windows; if the workflow "
            "moved to a single cron, README may legitimately name one time")

    def test_readme_does_not_name_an_hour_the_workflow_never_uses(self):
        _, hours = self.cron_hours()
        text = readme_text()
        claimed = re.findall(r"(\d{1,2}):(\d{2})\s*UTC", text)
        for hh, _mm in claimed:
            self.assertIn(
                int(hh), hours,
                "README claims the pipeline runs at %s:00 UTC, but "
                "daily_update.yml schedules only hours %s"
                % (hh, ", ".join(str(h) for h in hours)))


class TestReadmePythonPrerequisiteMatchesCI(unittest.TestCase):
    """
    Every workflow pins one Python version, and
    `docs/ARCHITECTURE_AND_PUBLISHING.md` §4 states the constraint explicitly:
    keep the validator and generator compatible with it. A README naming a
    higher floor invites a contributor to use syntax CI cannot run.
    """

    def ci_versions(self):
        found = set()
        for wf in sorted(WORKFLOW_DIR.glob("*.yml")):
            found.update(re.findall(r"python-version:\s*['\"]?([0-9.]+)",
                                    wf.read_text(encoding="utf-8")))
        self.assertTrue(found, "no python-version pin found in any workflow")
        return found

    def test_ci_pins_a_single_python_version(self):
        self.assertEqual(
            len(self.ci_versions()), 1,
            "workflows disagree about the Python version; README cannot name "
            "one until they agree")

    def test_readme_prerequisite_is_not_above_what_ci_runs(self):
        ci = sorted(self.ci_versions())[0]
        ci_tuple = tuple(int(p) for p in ci.split("."))
        text = readme_text()
        claimed = re.findall(r"Python\s+(\d+)\.(\d+)", text)
        self.assertTrue(claimed, "README states no Python prerequisite")
        for major, minor in claimed:
            self.assertLessEqual(
                (int(major), int(minor)), ci_tuple,
                "README requires Python %s.%s but CI runs %s; the floor must "
                "not exceed the version the project is actually tested on"
                % (major, minor, ci))


class TestReadmeCarriesNoUnresolvedPlaceholder(unittest.TestCase):
    """
    `tests/test_user_agent_identity.py` already refuses an unreplaced
    `[username]` in the collector identity, on the ruling that advertising an
    address which does not resolve is worse than advertising none. The same
    ruling applies to the clone URL a maintainer is told to run.
    """

    def test_no_bracketed_placeholder_survives_in_readme(self):
        for match in re.finditer(r"\[(?:username|name|your[^\]]*)\]",
                                 readme_text(), re.I):
            self.fail("README still contains the placeholder %r; it appears "
                      "in a command a maintainer is told to run"
                      % match.group(0))

    def test_readme_names_the_real_repository(self):
        self.assertIn("VSSpowerlifting/China-Mil-Watch", readme_text(),
                      "README does not name the repository it lives in")


class TestReadmePublishedUrlMatchesTheDeployStep(unittest.TestCase):
    """
    The deploy step sets a CNAME. That domain, not a github.io path, is where
    the site actually answers.
    """

    def cname(self):
        m = re.search(r"^\s*cname:\s*(\S+)",
                      DAILY_WORKFLOW.read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(m, "the deploy step sets no cname")
        return m.group(1)

    def test_readme_names_the_cname_domain(self):
        self.assertIn(self.cname(), readme_text(),
                      "README does not name the domain the deploy step sets")

    def test_readme_does_not_advertise_a_github_io_path(self):
        self.assertNotRegex(
            readme_text(), r"github\.io/pla-watch",
            "README advertises a github.io path; the site is served from the "
            "CNAME the deploy step sets")


if __name__ == "__main__":
    unittest.main(verbosity=2)
