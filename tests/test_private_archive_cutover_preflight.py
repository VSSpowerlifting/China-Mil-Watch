"""No-network cutover preflight contract on fictional workflow source files.

Synthetic worktree only: no source originals, repository database or provider.
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.preflight_private_archive_cutover import CODE_PATHS, SCHEMA, audit, main

DAILY = """
on:
  schedule: []
jobs:
  collect:
    steps:
      - name: Success push
        run: |
          git add pla_watch.db
          git push origin main
      - name: Failure salvage
        run: |
          git add pla_watch.db output/
          git push
      - name: Site publish
        uses: peaceiris/actions-gh-pages@v3
        with:
          publish_dir: ./output
          publish_branch: gh-pages
"""
KOREA_INDO = """
jobs:
  collect:
    steps:
      - name: Preserve Korea attempt metadata only
        if: always()
        uses: actions/upload-artifact@v4
        with:
          path: |
            ${{ runner.temp }}/candidate-state/state/ledger/*.json
            ${{ runner.temp }}/candidate-state/state/clock.json
      - name: Preserve Indonesia complete attempt evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          path: |
            ${{ runner.temp }}/candidate-state/state/
            ${{ runner.temp }}/candidate-run.log
"""
PH = """
jobs:
  collect:
    steps:
      - name: Preserve run evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          path: |
            ${{ runner.temp }}/shadow-state/state/
            ${{ runner.temp }}/ph-afp-run.log
"""
VIETNAM = """
jobs:
  collect:
    steps:
      - name: Preserve complete attempt evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          path: |
            ${{ runner.temp }}/vn-ministry-state/vn_mps_foreign_affairs_vi/state/
            ${{ runner.temp }}/vn-ministry-state/vn_moit_energy_vi/state/
            ${{ runner.temp }}/vn-ministry-run.log
"""


class CutoverExposureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        entries = {
            CODE_PATHS[0]: DAILY, CODE_PATHS[1]: KOREA_INDO,
            CODE_PATHS[2]: PH, CODE_PATHS[3]: VIETNAM,
            CODE_PATHS[4]: "{{ record.text_original }}",
        }
        for relative, content in entries.items():
            file = self.root / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content, encoding="utf-8")
        (self.root / "pla_watch.db").write_bytes(b"FICTIONAL_FILENAME_ONLY")

    def tearDown(self):
        self.tmp.cleanup()

    def test_current_style_exposures_fail_closed_without_publisher_data(self):
        result = audit(self.root)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertFalse(result["cutover_ready"])
        self.assertFalse(result["private_provider_connected_and_restore_verified"])
        self.assertEqual(result["finding_count"], 7)
        found = [(v["code"], v["file"]) for v in result["findings"]]
        for expected in (
            ("public_daily_canonical_database_commit", CODE_PATHS[0]),
            ("public_daily_static_output_deployment", CODE_PATHS[0]),
            ("public_record_template_reads_full_original", CODE_PATHS[4]),
            ("canonical_database_present_in_worktree", "pla_watch.db"),
            ("actions_uploads_full_or_original_shadow_state", CODE_PATHS[1]),
            ("actions_uploads_full_or_original_shadow_state", CODE_PATHS[2]),
            ("actions_uploads_full_or_original_shadow_state", CODE_PATHS[3]),
        ):
            self.assertIn(expected, found)
        self.assertEqual(result["finding_count"], len(set(found)))

    def test_narrow_action_artifact_receipts_do_not_trigger_full_state_false_positive(self):
        for relative in CODE_PATHS[1:4]:
            path = self.root / relative
            content = path.read_text(encoding="utf-8")
            content = content.replace("/state/\n", "/state/ledger/*.json\n")
            path.write_text(content, encoding="utf-8")
        found = audit(self.root)["findings"]
        self.assertFalse(any(r["code"] == "actions_uploads_full_or_original_shadow_state"
                             for r in found))
        self.assertFalse(audit(self.root)["cutover_ready"])

    def test_explicit_raw_capture_and_database_payloads_are_detected(self):
        path = self.root / CODE_PATHS[2]
        for unsafe in ("state/shadow.db", "state/captures/*.bin",
                       "state/evidence/payloads/*.bin"):
            with self.subTest(unsafe=unsafe):
                path.write_text(PH.replace("state/\n", unsafe + "\n"),
                                encoding="utf-8")
                self.assertIn(
                    ("actions_uploads_full_or_original_shadow_state", CODE_PATHS[2]),
                    {(x["code"], x["file"]) for x in audit(self.root)["findings"]})

    def test_cannot_scan_missing_or_symlinked_code_path(self):
        file = self.root / CODE_PATHS[3]
        file.unlink()
        with self.assertRaisesRegex(ValueError, "inspected_code_missing_or_unsafe"):
            audit(self.root)
        file.symlink_to(self.root / CODE_PATHS[2])
        with self.assertRaisesRegex(ValueError, "inspected_code_missing_or_unsafe"):
            audit(self.root)

    def test_even_synthetic_fully_clean_code_tree_cannot_self_authorize_cutover(self):
        (self.root / "pla_watch.db").unlink()
        (self.root / CODE_PATHS[0]).write_text("on: workflow_dispatch\n")
        (self.root / CODE_PATHS[4]).write_text("No original bodies\n")
        for relative in CODE_PATHS[1:4]:
            (self.root / relative).write_text("on: workflow_dispatch\n")
        report = audit(self.root)
        self.assertEqual(report["finding_count"], 0)
        self.assertFalse(report["cutover_ready"])
        self.assertFalse(report["production_cutover_authorized"])
        self.assertFalse(report["remote_branch_or_artifact_custody_verified"])

    def test_no_original_or_secret_text_in_report_or_error(self):
        sample = "SYNTHETIC_SOURCE_BODY_SHOULD_NOT_LEAK_1997"
        file = self.root / CODE_PATHS[3]
        file.write_text(VIETNAM + "\n# " + sample)
        result = audit(self.root)
        self.assertNotIn(sample, repr(result))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(["--repository", str(self.root)])
        self.assertEqual(status, 2)
        self.assertNotIn(sample, out.getvalue())
        self.assertNotIn("FICTIONAL_FILENAME_ONLY", out.getvalue())

    def test_preflight_errors_fail_closed_without_leaking_paths(self):
        (self.root / CODE_PATHS[4]).unlink()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(["--repository", str(self.root)])
        self.assertEqual(status, 2)
        self.assertIn("preflight_input_invalid", out.getvalue())
        self.assertNotIn(str(self.root), out.getvalue())


if __name__ == "__main__":
    unittest.main()
