"""Fake authenticated GitHub API only: zero network/source/capture operations."""
import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import verify_private_github_vault as vault

SRC = "VSSpowerlifting/China-Mil-Watch"
DEST = "VSSpowerlifting/ipr-source-evidence-private"


def fake_api(*, destination=None, source=None, branches=None):
    origin = source if source is not None else {
        "full_name": SRC, "private": False, "visibility": "public",
    }
    target = destination if destination is not None else {
        "full_name": DEST, "private": True, "visibility": "private",
        "archived": False, "disabled": False, "fork": False,
        "permissions": {"admin": True, "push": True, "pull": True},
    }
    values = {
        "repos/" + SRC: origin,
        "repos/" + DEST: target,
        "repos/" + DEST + "/branches?per_page=100": [] if branches is None else branches,
    }
    return values.__getitem__


class VaultPreflightTests(unittest.TestCase):
    def test_verified_private_empty_repo_is_still_not_transfer_approval(self):
        out = vault.evaluate(SRC, DEST, api=fake_api())
        self.assertEqual(out["destination_visibility_verified"], "private")
        self.assertEqual(out["destination_initial_branches"], 0)
        self.assertTrue(out["operator_repo_admin_verified"])
        for gate in ("ready_to_transfer", "source_bodies_transferred",
                     "production_cutover_authorized",
                     "cross_repo_workflow_credential_verified",
                     "independent_backup_and_restore_verified",
                     "publisher_original_retention_rights_approved",
                     "failed_attempt_capture_inventory_complete"):
            self.assertFalse(out[gate])

    def test_rejects_names_that_could_change_endpoint_or_shell_semantics(self):
        bad = (
            "", "invalid", "a/..", "a/.hidden", "a/name/path",
            "a/name?x=1", "a/name#frag", "a/${{secrets.X}}",
            "a/name\n", "a/name;rm", "a /name", "https://github.com/a/b",
        )
        for name in bad:
            with self.subTest(name=name), self.assertRaises(vault.VaultPreflightError):
                vault.evaluate(SRC, name, api=fake_api())
        with self.assertRaisesRegex(vault.VaultPreflightError, "source_is_destination"):
            vault.evaluate(SRC, SRC, api=fake_api())
        with self.assertRaisesRegex(vault.VaultPreflightError, "vault_owner_mismatch"):
            vault.evaluate(SRC, "otherowner/private-vault", api=fake_api())

    def test_fails_closed_on_public_or_unknown_visibility(self):
        for setting in (
            {"private": False},
            {"visibility": "public"},
            {"visibility": None},
            {"private": None},
        ):
            target = dict(fake_api()("repos/" + DEST), **setting)
            with self.subTest(setting=setting), self.assertRaisesRegex(
                    vault.VaultPreflightError, "vault_not_private"):
                vault.evaluate(SRC, DEST, api=fake_api(destination=target))

    def test_refuses_nonempty_wrong_identity_fork_archived_disabled_or_no_admin(self):
        base = fake_api()("repos/" + DEST)
        for mutation, code in (
            ({"full_name": "otherowner/not-our-vault"}, "vault_identity_mismatch"),
            ({"fork": True}, "vault_state_unsafe"),
            ({"archived": True}, "vault_state_unsafe"),
            ({"disabled": True}, "vault_state_unsafe"),
            ({"permissions": {"admin": False}}, "vault_owner_access_unverified"),
        ):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                    vault.VaultPreflightError, code):
                vault.evaluate(SRC, DEST, api=fake_api(destination=dict(base, **mutation)))
        with self.assertRaisesRegex(vault.VaultPreflightError, "vault_not_empty"):
            vault.evaluate(SRC, DEST, api=fake_api(branches=[{"name": "main"}]))

    def test_missing_or_wrong_source_identity_is_hold(self):
        for value, reason in (
            ({"full_name": "a/b", "private": False, "visibility": "public"},
             "source_identity_mismatch"),
            ({"full_name": SRC, "private": True, "visibility": "private"},
             "source_visibility_not_public"),
        ):
            with self.assertRaisesRegex(vault.VaultPreflightError, reason):
                vault.evaluate(SRC, DEST, api=fake_api(source=value))

    def test_malformed_identity_type_returns_a_fixed_safe_hold(self):
        for identity in (None, 7, [], {}):
            with self.subTest(identity=identity):
                src = dict(fake_api()("repos/" + SRC), full_name=identity)
                with self.assertRaisesRegex(vault.VaultPreflightError, "source_identity_mismatch"):
                    vault.evaluate(SRC, DEST, api=fake_api(source=src))
                dest = dict(fake_api()("repos/" + DEST), full_name=identity)
                with self.assertRaisesRegex(vault.VaultPreflightError, "vault_identity_mismatch"):
                    vault.evaluate(SRC, DEST, api=fake_api(destination=dest))

    def test_does_not_believe_malformed_api_or_unavailable_endpoint(self):
        with self.assertRaisesRegex(vault.VaultPreflightError, "repository_api_shape"):
            vault.evaluate(SRC, DEST, api=lambda endpoint: [])
        # An ordinary network/library ValueError yields a controlled fixed code.
        def offline(_endpoint):
            raise ValueError("Sensitive publisher and auth diagnostic")
        with self.assertRaisesRegex(vault.VaultPreflightError, "authenticated_api_unavailable") as cm:
            vault.evaluate(SRC, DEST, api=offline)
        self.assertNotIn("Sensitive", str(cm.exception))

    def test_cli_refusal_does_not_print_tokens_or_raw_errors(self):
        secret = "FICTITIOUS_SESSION_TOKEN_DO_NOT_REPRINT"
        fake = subprocess.CompletedProcess(["gh"], 1, stdout="", stderr=secret)
        with patch("subprocess.run", return_value=fake):
            with self.assertRaisesRegex(vault.VaultPreflightError, "authenticated_api_refused") as cm:
                vault._api("repos/" + DEST)
            self.assertNotIn(secret, str(cm.exception))
        with patch("subprocess.run", side_effect=FileNotFoundError("token:" + secret)):
            with self.assertRaisesRegex(vault.VaultPreflightError, "authenticated_api_unavailable") as cm:
                vault._api("repos/" + DEST)
            self.assertNotIn(secret, str(cm.exception))

    def test_real_gh_api_invocation_is_read_only_and_no_shell(self):
        json_text = json.dumps({"full_name": DEST})
        fake = subprocess.CompletedProcess(["gh"], 0, stdout=json_text, stderr="")
        with patch("subprocess.run", return_value=fake) as run:
            self.assertEqual(vault._api("repos/" + DEST)["full_name"], DEST)
        argv = run.call_args.args[0]
        self.assertEqual(argv, ["gh", "api", "--method", "GET", "--hostname",
                                "github.com", "repos/" + DEST])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertTrue(run.call_args.kwargs["timeout"] <= 30)

    def test_error_report_never_claims_created_or_migrated(self):
        with patch.object(vault, "evaluate",
                          side_effect=vault.VaultPreflightError("vault_not_private")):
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                status = vault.main(["--source", SRC, "--vault", DEST])
        report = json.loads(buf.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(report["result"], "HOLD")
        self.assertFalse(report["source_bodies_transferred"])
        self.assertFalse(report["ready_to_transfer"])


if __name__ == "__main__":
    unittest.main()
