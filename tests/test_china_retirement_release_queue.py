"""Guard the China cutover queue against unrelated daily updates.

GitHub Actions permits only one pending job in each concurrency group.
Because the owner release and daily_update originally shared a group, a
new daily run could replace the owner's waiting release before checkout.
The cutover is separately serialized but still requires exact live-main SHA
equality before destructive promotion and Git push.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ChinaReleaseQueueContracts(unittest.TestCase):
    def test_release_does_not_share_replaceable_daily_update_queue(self):
        release = (ROOT / ".github/workflows/china_retirement_release.yml").read_text()
        daily = (ROOT / ".github/workflows/daily_update.yml").read_text()
        self.assertRegex(release, r"group:\s*china-retirement-cutover")
        self.assertRegex(daily, r"group:\s*daily-update")
        self.assertNotRegex(release, r"group:\s*daily-update")
        self.assertIn("cancel-in-progress: false", release)

    def test_independent_queue_keeps_exact_head_pin_before_write(self):
        release = (ROOT / ".github/workflows/china_retirement_release.yml").read_text()
        self.assertIn("CHINA_RELEASE_SHA=$RELEASE_SHA", release)
        self.assertGreaterEqual(
            release.count('test "$(git rev-parse origin/main)" = "$CHINA_RELEASE_SHA"'), 2)
        self.assertLess(
            release.index("Verify current main unchanged before any destructive promotion"),
            release.index("Promote exactly verified scratch DB and rebuilt full site"))
        self.assertLess(
            release.index("Commit single reviewed corpus and full-site release"),
            release.index("git push origin HEAD:main"))

    def test_private_vault_and_default_nonpublishing_gate_remain_intact(self):
        release = (ROOT / ".github/workflows/china_retirement_release.yml").read_text()
        self.assertIn("IPR_PRIVATE_VAULT_READ_TOKEN", release)
        self.assertIn("default: false", release)
        self.assertIn("if: inputs.publish", release)
        self.assertIn("scripts.verify_china_retirement_backup_lineage", release)


if __name__ == "__main__":
    unittest.main()
