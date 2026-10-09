"""Fail-closed bounded Daily browser prerequisite, without executing collection."""
from __future__ import annotations

import re
import unittest

from tests.test_workflow_contract import (
    index_of, step_blocks, step_names, workflow_text,
)


def steps():
    return dict(step_blocks(workflow_text()))


class DailyBrowserPreflightTimeout(unittest.TestCase):
    def test_browser_is_still_normal_playwright_dependency_install(self):
        self.assertIn("playwright install chromium --with-deps",
                      steps()["Install Playwright browser"])
        self.assertNotIn("continue-on-error: true",
                         steps()["Install Playwright browser"])

    def test_browser_install_has_bounded_step_timeout(self):
        block = steps()["Install Playwright browser"]
        matches = re.findall(r"(?m)^\s+timeout-minutes:\s*(\d+)\s*$", block)
        self.assertEqual(len(matches), 1,
                         "browser prerequisite must have exactly one timeout")
        self.assertGreaterEqual(int(matches[0]), 5)
        self.assertLessEqual(int(matches[0]), 20)

    def test_browser_install_is_skipped_when_daily_guard_skips(self):
        block = steps()["Install Playwright browser"]
        self.assertIn(
            "if: steps.timecheck.outputs.should_run == 'true'", block)
        self.assertNotIn("always()", block)
        self.assertNotIn("!cancelled()", block)

    def test_browser_timeout_happens_before_any_production_work(self):
        names = step_names(workflow_text())
        browser = index_of(names, "Install Playwright browser")
        for later in (
            "Apply database migrations",
            "Verify database schema and invariants",
            "Run offline test suite",
            "Run pipeline",
            "Validate rendered output",
            "Commit updated database and site output",
            "Deploy to GitHub Pages",
            "Record successful run",
            "Health gate",
        ):
            with self.subTest(later=later):
                self.assertLess(browser, index_of(names, later))

    def test_pipeline_and_publication_require_successful_prior_steps(self):
        all_steps = steps()
        for name in (
            "Apply database migrations",
            "Run offline test suite",
            "Run pipeline",
            "Validate rendered output",
            "Commit updated database and site output",
            "Deploy to GitHub Pages",
            "Record successful run",
        ):
            with self.subTest(step=name):
                block = all_steps[name]
                self.assertIn(
                    "if: steps.timecheck.outputs.should_run == 'true'", block)
                # GitHub Actions injects success() into conditions that omit
                # all status functions, so these steps fail closed following
                # a failed or timed-out Playwright prerequisite.
                self.assertNotRegex(block, r"\b(?:always|failure|cancelled|success)\s*\(")
                self.assertNotIn("continue-on-error:", block)

    def test_success_marker_stays_after_deploy(self):
        names = step_names(workflow_text())
        self.assertLess(index_of(names, "Run pipeline"),
                        index_of(names, "Validate rendered output"))
        self.assertLess(index_of(names, "Validate rendered output"),
                        index_of(names, "Deploy to GitHub Pages"))
        self.assertLess(index_of(names, "Deploy to GitHub Pages"),
                        index_of(names, "Record successful run"))

    def test_failure_persistence_cannot_publish_site_or_mark_success(self):
        all_steps = steps()
        persist = all_steps["Persist scraped articles (if pipeline failed)"]
        self.assertIn("failure()", persist)
        self.assertIn("steps.pipeline.outcome == 'failure'", persist)
        self.assertNotIn("git add pla_watch.db output/", persist)
        success_marker = all_steps["Record successful run"]
        self.assertNotIn("failure()", success_marker)
        self.assertNotIn("always()", success_marker)


if __name__ == "__main__":
    unittest.main()
