"""Guarded Japan Coast Guard scheduled qualification is inert by default."""
import unittest
from datetime import datetime, date, timezone
from pathlib import Path

from core.shadow_schedule import (
    scheduled_slot_date, resolve_target_date, ScheduleError,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/jcg_guarded_daily_shadow.yml"
MANUAL = ROOT / ".github/workflows/japan_jcg_shadow_manual.yml"


class JCGDailyQualifications(unittest.TestCase):
    def test_disabled_without_explicit_owner_repository_variable(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("vars.JCG_SHADOW_DAILY_ENABLED == 'true'", source)
        self.assertIn("github.event_name == 'schedule'", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("    - cron: '13 19 * * *'", source)
        self.assertNotIn("workflow_dispatch:", source)
        self.assertIn("group: japan-jcg-manual-shadow", source)
        self.assertIn("cancel-in-progress: false", source)

    def test_scheduled_attempt_never_bootstraps_or_changes_production(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("git ls-remote --exit-code --heads", source)
        self.assertIn("test -f state/clock.json", source)
        self.assertIn("test -s state/shadow.db", source)
        self.assertIn("assert clock[\"desk\"] == \"japan_jcg\"", source)
        self.assertNotIn("git init", source)
        self.assertNotIn("--orphan", source)
        self.assertNotIn("--force", source)
        self.assertNotIn("desks/japan/manifest.json", source)
        self.assertNotIn("pla_watch.db", source)
        self.assertNotIn("output/", source)
        self.assertNotIn("smtp", source.lower())
        self.assertIn("git push origin", source)
        self.assertIn('test -z "$(git -C repo status --porcelain)"', source)

    def test_schedule_passes_source_date_to_existing_runner(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--desk japan_jcg", source)
        self.assertIn("--lookback-days 9 --cap 20", source)
        self.assertIn("--event-name schedule", source)
        self.assertIn("--cron-utc 19:13", source)
        self.assertIn('--run-attempt "$GITHUB_RUN_ATTEMPT"', source)
        self.assertIn("--run-id", source)
        self.assertNotIn("--target-date", source)
        self.assertIn("shadow/japan-jcg", source)
        self.assertNotIn("/captures/", source.split("path:", 1)[-1])

    def test_nominal_slot_survives_utc_midnight_delay(self):
        when = datetime(2026, 10, 9, 1, 23, tzinfo=timezone.utc)
        self.assertEqual(scheduled_slot_date(when, "19:13"),
                         date(2026, 10, 8))
        target, prov = resolve_target_date(
            when, "schedule", "19:13", None, "1")
        self.assertEqual(target, date(2026, 10, 8))
        self.assertEqual(prov, "schedule-slot")
        with self.assertRaises(ScheduleError):
            resolve_target_date(when, "schedule", "19:13", None, "2")

    def test_manual_rescue_remains_separate_and_requires_explicit_date(self):
        source = MANUAL.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", source)
        self.assertNotIn("  schedule:", source)
        self.assertIn("TARGET_DATE_INPUT", source)
        day, prov = resolve_target_date(
            datetime(2026, 10, 9, 23, tzinfo=timezone.utc),
            "workflow_dispatch", None, "2026-10-08", "1")
        self.assertEqual(day, date(2026, 10, 8))
        self.assertEqual(prov, "explicit")

    def test_original_source_is_not_archive_complete_without_pdf(self):
        source = (ROOT / "shadow/jp_jcg/manifest.json").read_text(encoding="utf-8")
        self.assertIn("shadow", source)
        self.assertIn("jp_jcg_press_en", source)
        self.assertIn("linked PDFs", source)
        self.assertFalse((ROOT / "desks/japan/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
