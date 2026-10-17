"""Korea legacy public writer guard: fail closed on a private cutover attempt."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import check_korea_public_shadow_writer as guard

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "korea_shadow_writer_policy.json"
WORKFLOW = ROOT / ".github/workflows/indonesia_korea_shadow.yml"


class KoreaPublicWriterCutoverGuardTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def assess(self, data=None, *, stage="pre_collect"):
        return guard.assess("korea", guard.STATE_BRANCH,
                            self.policy if data is None else data, stage=stage)

    def test_default_legacy_collection_and_push_are_only_operational_mode(self):
        for stage in ("pre_collect", "pre_public_push"):
            report = self.assess(stage=stage)
            self.assertTrue(report["legacy_public_writer_permitted"])
            for field in ("private_repo_access_verified", "source_custody_migrated",
                          "source_retention_rights_approved", "owner_cutover_authorized",
                          "korea_production_admission_authorized",
                          "sunday_ai_email_or_publication_authorized"):
                self.assertIs(report[field], False)

    def test_proposed_private_cutover_blocks_legacy_public_writer(self):
        changes = (
            ("mode", "private"), ("mode", "dual_writer"),
            ("mode", "private_cutover"),
            ("state_branch", "archive/korea-policy-briefing"),
            ("day_zero_utc", "2026-10-06T19:00:00+00:00"),
            ("day_zero_run_id", "manual-reset"),
            ("private_writer_active", True),
            ("private_copy_verified", True),
            ("private_restore_verified", True),
            ("private_cutover_authorized", True),
            ("production_admission_authorized", True),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                changed = dict(self.policy, **{field: value})
                for stage in ("pre_collect", "pre_public_push"):
                    with self.assertRaises(guard.WriterHold):
                        self.assess(changed, stage=stage)

    def test_extra_fields_missing_fields_and_type_confusions_fail(self):
        with self.assertRaises(guard.WriterHold):
            self.assess(dict(self.policy, transfer_approved=True))
        for field in ("private_writer_active", "private_cutover_authorized"):
            with self.assertRaises(guard.WriterHold):
                self.assess(dict(self.policy, **{field: 0}))
        for field in ("day_zero_run_id", "schema"):
            changed = dict(self.policy)
            changed.pop(field)
            with self.assertRaises(guard.WriterHold):
                self.assess(changed)

    def test_indonesia_unchanged(self):
        for stage in ("pre_collect", "pre_public_push"):
            result = guard.assess("indonesia", guard.INDONESIA_BRANCH,
                                  None, stage=stage)
            self.assertTrue(result["indonesia_unchanged"])
            self.assertFalse(result["korea_cutover_authorized"])
            with self.assertRaises(guard.WriterHold):
                guard.assess("indonesia", guard.STATE_BRANCH, None, stage=stage)
        with self.assertRaises(guard.WriterHold):
            guard.assess("other", guard.STATE_BRANCH, {}, stage="pre_collect")

    def test_policy_file_rejects_malformed_or_symlinked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mode.json"
            path.write_text(json.dumps(self.policy), encoding="utf-8")
            result = guard.check_file(str(path), desk="korea",
                                      branch=guard.STATE_BRANCH,
                                      stage="pre_collect")
            self.assertTrue(result["legacy_public_writer_permitted"])
            path.write_text('{"mode":"private"}', encoding="utf-8")
            with self.assertRaises(guard.WriterHold):
                guard.check_file(str(path), desk="korea", branch=guard.STATE_BRANCH,
                                 stage="pre_collect")
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(guard.WriterHold):
                guard.check_file(str(path), desk="korea", branch=guard.STATE_BRANCH,
                                 stage="pre_collect")
            path.unlink()
            path.symlink_to(POLICY)
            with self.assertRaises(guard.WriterHold):
                guard.check_file(str(path), desk="korea", branch=guard.STATE_BRANCH,
                                 stage="pre_collect")

    def test_cli_hold_receipt_excludes_paths_or_source_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid-private-policy.json"
            path.write_text(json.dumps(dict(self.policy, mode="private")))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                rc = guard.main(["--policy", str(path), "--desk", "korea",
                                 "--state-branch", guard.STATE_BRANCH,
                                 "--stage", "pre_public_push"])
            self.assertEqual(rc, 2)
            receipt = json.loads(output.getvalue())
            self.assertEqual(receipt["status"], "HOLD")
            self.assertIs(receipt["legacy_public_writer_permitted"], False)
            self.assertNotIn(str(path), output.getvalue())

    def test_workflow_guard_order_and_preserved_korea_cadence(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        for item in ("47 17 * * *", "state_branch=shadow/korea-policy-briefing"):
            self.assertIn(item, raw)
        for retired in ("17 17 * * *", "state_branch=shadow/indonesia-kemhan",
                        "candidate-shadow-indonesia-", "DESK_INPUT=indonesia"):
            self.assertNotIn(retired, raw)
        self.assertIn("SHADOW_CRON_UTC=$cron_utc", raw)
        self.assertEqual(raw.count("scripts/check_korea_public_shadow_writer.py"), 2)
        self.assertEqual(raw.count("--stage pre_collect"), 1)
        self.assertEqual(raw.count("--stage pre_public_push"), 1)
        first = raw.index("Fail closed on Korea public writer policy before source access")
        source = raw.index("- name: Check out isolated state")
        self.assertLess(first, source)
        push = raw.split("- name: Publish successful state to its explicit branch")[1]
        self.assertLess(push.index("--stage pre_public_push"),
                        push.index('git push origin "HEAD:refs/heads/$STATE_BRANCH"'))
        self.assertIn('if [ "$SHADOW_DESK" = korea ]; then', push)
        self.assertIn("env.SHADOW_DESK == 'korea'", raw)


if __name__ == "__main__":
    unittest.main()
