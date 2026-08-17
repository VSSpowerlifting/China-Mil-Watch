"""
The pull-request workflow must stay offline, read-only and inert.

`.github/workflows/pr_offline_checks.yml` runs on pull requests, which means it
executes code the repository has not yet reviewed: `pip install` reads the PR's
`requirements.txt`, and the suite is the PR's own test code. What keeps that
safe is entirely a property of the workflow file — its trigger, its permissions,
the absence of any secret, the absence of a persisted checkout credential, and
the order of its steps. Those properties are asserted here so they cannot be
relaxed by accident.

On the trigger, precisely: `pull_request` runs the workflow definition taken
from the PR's merge commit, with the permissions the file declares.
`pull_request_target` instead runs the definition from the BASE branch in the
base repository's context, where a token and secrets can be available. That is
not dangerous in itself; the hazard is the combination of a privileged context
with checking out or executing PR-controlled code. This workflow sidesteps it:
`pull_request`, explicit read-only permissions, no secrets, no persisted
credential.

These tests inspect YAML *structure*, not substrings. A substring test for
`"pull_request"` also matches `pull_request_target`, so the distinction that
matters most is exactly the one a substring cannot draw.

`_parse` is not a YAML parser. It reads the block-subset these workflow files
use — block mappings, block sequences, sequences of mappings, literal and
folded block scalars (`|`, `>`, `|-`, `>-`, `|+`, `>+`), quote-aware trailing
comments, and scalars typed as quoted string, bool or int. It does NOT support
flow collections, anchors, aliases, tags, multiple documents, or multi-line
plain scalars. It fails closed: anything it does not understand, content left
over after the document, or a duplicate mapping key raises `YamlSubsetError`
rather than being silently dropped or overwritten. `TestTheReaderItself` pins
that behaviour, because a reader that quietly returned less would turn every
assertion below vacuously green.

One trap worth naming: in YAML 1.1 an unquoted `on` is the boolean true, so a
real loader returns the key `True` for a workflow's trigger block, not `"on"`.
This reader does no such coercion — it keeps the literal key — and
`test_the_trigger_key_is_read_literally` asserts that, so the tests below can
say `doc["on"]` and mean it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOW_DIR / "pr_offline_checks.yml"

# Workflows already in the repository, used only to discover which actions and
# versions are established here. Deliberately not a digest and not an
# exhaustive list of what may exist: adding a legitimate workflow is normal
# work and is not this module's business.
ESTABLISHED_WORKFLOWS = (
    "daily_update.yml",
    "deploy_output_only.yml",
    "generate_pla_watch_draft.yml",
)

# Commands whose presence would mean this job is no longer offline and inert.
# Matched against the text of every `run:` body and every `uses:` value.
FORBIDDEN_COMMANDS = {
    "collection pipeline": r"\bpipeline\.py\b",
    "database migration": r"\bmigrations\.cli\b|\bmigrations/cli\b",
    "database reconciliation": r"\breconcile_db\.py\b",
    "source liveness / collection": r"\bcheck_source_liveness\.py\b",
    "site generation": r"\bsite/generator\.py\b|\bgenerate_pla_watch\b|\brerender_pla_watch\b",
    "scraping backfill": r"\bbackfill_\w+\.py\b",
    "playwright browser install": r"\bplaywright\s+install\b",
    "git commit": r"\bgit\s+commit\b",
    "git push": r"\bgit\s+push\b",
    "git tag": r"\bgit\s+tag\b",
    "gh CLI": r"(^|[^\w-])gh\s+(pr|api|release|workflow|auth)\b",
    "secret reference": r"secrets\.",
    "pages deployment": r"actions-gh-pages",
}


# ── a block-YAML subset reader (stdlib only, fails closed) ─────────────────

class YamlSubsetError(ValueError):
    """The input used a construct this reader does not implement."""


def _strip_comment(line: str) -> str:
    """Remove a trailing `#` comment, respecting quotes."""
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _parse(text: str):
    lines = text.split("\n")

    def indent_of(i: int) -> int:
        return len(lines[i]) - len(lines[i].lstrip(" "))

    def skip_blank(i: int) -> int:
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "" or stripped.startswith("#"):
                i += 1
            else:
                return i
        return i

    def block_scalar(i: int, parent_indent: int):
        """Literal/folded block: every deeper line, verbatim and dedented."""
        body = []
        while i < len(lines):
            if lines[i].strip() == "":
                body.append("")
                i += 1
                continue
            if indent_of(i) <= parent_indent:
                break
            body.append(lines[i])
            i += 1
        while body and body[-1] == "":
            body.pop()
        widths = [len(b) - len(b.lstrip(" ")) for b in body if b.strip()]
        base = min(widths) if widths else 0
        return "\n".join(b[base:] if b.strip() else "" for b in body), i

    def parse_node(i: int, minimum: int):
        i = skip_blank(i)
        if i >= len(lines) or indent_of(i) < minimum:
            return None, i
        if lines[i].lstrip().startswith("- "):
            return parse_seq(i, indent_of(i))
        return parse_map(i, indent_of(i))

    def parse_pair(i: int, indent: int):
        """One `key: …` at `indent`. Returns (key, value, next_index)."""
        body = _strip_comment(lines[i]).strip()
        if ":" not in body:
            raise YamlSubsetError("not a mapping entry: %r" % lines[i])
        key, _, rest = body.partition(":")
        key, rest = key.strip().strip("\"'"), rest.strip()
        i += 1
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            value, i = block_scalar(i, indent)
        elif rest == "":
            value, i = parse_node(i, indent + 1)
        else:
            value = _scalar(rest)
        return key, value, i

    def parse_map(i: int, indent: int):
        result = {}
        while True:
            i = skip_blank(i)
            if i >= len(lines) or indent_of(i) != indent:
                break
            if _strip_comment(lines[i]).strip().startswith("- "):
                break
            key, value, i = parse_pair(i, indent)
            if key in result:
                # Silently keeping the last wins is how a guard stops guarding:
                # a second `permissions:` would quietly replace the first.
                raise YamlSubsetError("duplicate mapping key: %r" % key)
            result[key] = value
        return result, i

    def parse_seq(i: int, indent: int):
        items = []
        while True:
            i = skip_blank(i)
            if i >= len(lines) or indent_of(i) != indent:
                break
            body = _strip_comment(lines[i]).strip()
            if not body.startswith("- "):
                break
            inner = body[2:].strip()
            item_indent = indent + 2
            if ":" in inner and inner[0] not in "\"'":
                # A mapping whose first key sits on the dash line.
                lines[i] = " " * item_indent + inner
                key, value, i = parse_pair(i, item_indent)
                entry = {key: value}
                rest, i = parse_map(i, item_indent)
                clash = set(rest) & set(entry)
                if clash:
                    raise YamlSubsetError(
                        "duplicate mapping key: %r" % sorted(clash)[0])
                entry.update(rest)
                items.append(entry)
            else:
                items.append(_scalar(inner))
                i += 1
        return items, i

    doc, end = parse_map(skip_blank(0), 0)
    end = skip_blank(end)
    if end < len(lines):
        # Anything still here was not consumed — trailing garbage, a top-level
        # sequence, an unexpected indent. Returning `doc` anyway would mean
        # asserting against a document that is not the file.
        raise YamlSubsetError(
            "unconsumed content at line %d: %r" % (end + 1, lines[end]))
    return doc


def load_workflow() -> dict:
    return _parse(WORKFLOW.read_text(encoding="utf-8"))


def steps_of(doc: dict) -> list:
    return doc["jobs"]["offline-checks"]["steps"]


def run_bodies(doc: dict):
    """Every `run:` script in the workflow."""
    return [s["run"] for job in doc["jobs"].values()
            for s in job["steps"] if "run" in s]


def uses_values(doc: dict):
    return [s["uses"] for job in doc["jobs"].values()
            for s in job["steps"] if "uses" in s]


def index_of(doc: dict, predicate) -> int:
    for n, step in enumerate(steps_of(doc)):
        if predicate(step):
            return n
    raise AssertionError("no step matched")


class TestTheReaderItself(unittest.TestCase):
    """If the reader degrades, every assertion below turns vacuously green."""

    def test_the_workflow_file_exists(self):
        self.assertTrue(WORKFLOW.is_file(), "%s is missing" % WORKFLOW)

    def test_it_reads_this_file_correctly(self):
        doc = load_workflow()
        self.assertIsInstance(doc, dict)
        self.assertEqual(doc["name"], "PR offline checks")
        job = doc["jobs"]["offline-checks"]
        self.assertEqual(job["runs-on"], "ubuntu-latest")
        self.assertIsInstance(job["steps"], list)
        self.assertGreaterEqual(len(job["steps"]), 5)
        for step in job["steps"]:
            self.assertIsInstance(step, dict)
            self.assertIn("name", step)

    def test_the_trigger_key_is_read_literally(self):
        """
        YAML 1.1 makes an unquoted `on` the boolean true. A loader that did
        that would key this document by True, and `doc["on"]` would raise.
        Pin the behaviour rather than depend on it silently.
        """
        doc = load_workflow()
        self.assertIn("on", doc, "the trigger block must be keyed by the "
                                 "string 'on', not coerced to a boolean")
        self.assertNotIn(True, doc)

    def test_it_rejects_a_line_it_cannot_read(self):
        with self.assertRaises(YamlSubsetError):
            _parse("jobs:\n  build:\n    steps:\n      - just-a-scalar: x\n"
                   "        and then a line with no colon\n")

    def test_it_rejects_trailing_indented_garbage(self):
        """Unconsumed content must raise, not be dropped on the floor."""
        with self.assertRaises(YamlSubsetError) as ctx:
            _parse("name: fine\npermissions:\n  contents: read\n"
                   "    stray: deeper-than-anything\n")
        self.assertIn("unconsumed", str(ctx.exception))

    def test_it_rejects_a_trailing_top_level_sequence(self):
        with self.assertRaises(YamlSubsetError) as ctx:
            _parse("name: fine\n- unexpected\n- sequence\n")
        self.assertIn("unconsumed", str(ctx.exception))

    def test_it_rejects_a_duplicate_mapping_key(self):
        """
        Last-wins would let a second `permissions:` block silently replace a
        read-only one, and every permission assertion would still pass.
        """
        with self.assertRaises(YamlSubsetError) as ctx:
            _parse("permissions:\n  contents: read\n"
                   "permissions:\n  contents: write\n")
        self.assertIn("duplicate", str(ctx.exception))

    def test_it_rejects_a_duplicate_key_inside_a_sequence_item(self):
        with self.assertRaises(YamlSubsetError) as ctx:
            _parse("steps:\n  - name: a\n    run: one\n    run: two\n")
        self.assertIn("duplicate", str(ctx.exception))


class TestNothingUnexpectedIsDeclared(unittest.TestCase):
    """
    Fail-closed parsing only rejects what it cannot READ. A key that lands at a
    valid indent is valid YAML and gets absorbed silently — a real loader does
    the same. So the shape of the document has to be asserted separately, or an
    appended `container:`, `services:`, or `continue-on-error:` would simply
    become part of the job.
    """

    TOP_LEVEL = {"name", "on", "permissions", "concurrency", "jobs"}
    JOB = {"runs-on", "timeout-minutes", "steps"}
    STEP = {"name", "id", "uses", "with", "run", "if"}

    def test_the_document_declares_only_the_expected_top_level_keys(self):
        self.assertEqual(set(load_workflow()), self.TOP_LEVEL)

    def test_the_job_declares_only_the_expected_keys(self):
        doc = load_workflow()
        self.assertEqual(set(doc["jobs"]), {"offline-checks"})
        self.assertEqual(set(doc["jobs"]["offline-checks"]), self.JOB)

    def test_no_step_declares_an_unexpected_key(self):
        """
        `continue-on-error: true` is the one that matters: on the protection
        step it would turn a detected modification into a green run.
        """
        for step in steps_of(load_workflow()):
            with self.subTest(step=step["name"]):
                unexpected = set(step) - self.STEP
                self.assertEqual(unexpected, set(),
                                 "unexpected step key(s): %s" % sorted(unexpected))

    def test_no_step_is_allowed_to_fail_silently(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("continue-on-error", raw)


class TestTrigger(unittest.TestCase):

    def test_it_triggers_on_pull_requests_to_main_and_nothing_else(self):
        """
        Exact equality, not membership: `["main", "develop"]` also contains
        "main", and would silently widen the job to a branch nobody reviewed
        this workflow against.
        """
        triggers = load_workflow()["on"]
        self.assertIn("pull_request", triggers)
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])

    def test_it_covers_exactly_the_activity_types_that_change_the_diff(self):
        """
        Sorted equality rather than membership: it catches an added type (a
        `closed` event runs the job on merge, for nothing) and a duplicated
        one, without pinning the order in which they happen to be written.
        """
        types = load_workflow()["on"]["pull_request"]["types"]
        self.assertEqual(
            sorted(types),
            sorted(["opened", "synchronize", "reopened", "ready_for_review"]))

    def test_it_has_no_other_trigger(self):
        """
        `pull_request_target` would run the base branch's workflow definition
        in the base repository's context, where a token and secrets can be
        available; the rest would make this workflow run outside review.
        """
        triggers = load_workflow()["on"]
        self.assertEqual(set(triggers), {"pull_request"},
                         "only a pull_request trigger is permitted here")
        for forbidden in ("push", "schedule", "workflow_dispatch",
                          "pull_request_target", "workflow_run",
                          "repository_dispatch", "release"):
            self.assertNotIn(forbidden, triggers)


class TestPermissions(unittest.TestCase):

    def test_the_token_is_read_only(self):
        self.assertEqual(load_workflow()["permissions"], {"contents": "read"})

    def test_no_job_widens_its_own_permissions(self):
        for name, job in load_workflow()["jobs"].items():
            with self.subTest(job=name):
                self.assertNotIn("permissions", job,
                                 "a job-level permissions block would "
                                 "override the read-only default")

    def test_no_step_carries_an_environment_secret(self):
        doc = load_workflow()
        for job in doc["jobs"].values():
            for step in job["steps"]:
                self.assertNotIn("env", step,
                                 "steps here need no environment; an env "
                                 "block is how a secret would arrive")
            self.assertNotIn("env", job)
        self.assertNotIn("env", doc)

    def test_checkout_does_not_persist_credentials(self):
        """
        The default writes the job token into .git/config, where this PR's own
        test code could read it. Nothing here needs git auth.
        """
        doc = load_workflow()
        checkouts = [s for s in steps_of(doc)
                     if s.get("uses", "").startswith("actions/checkout")]
        self.assertEqual(len(checkouts), 1)
        self.assertIs(checkouts[0]["with"]["persist-credentials"], False)

    def test_checkout_does_not_pin_a_writable_ref(self):
        """
        `ref: main` would check out the base branch instead of the PR, so the
        job would validate something the reviewer is not looking at.
        """
        for step in steps_of(load_workflow()):
            if step.get("uses", "").startswith("actions/checkout"):
                self.assertNotIn("ref", step.get("with") or {})


class TestItRunsTheRealChecks(unittest.TestCase):
    """The commands must be the repository's own, not weakened variants."""

    OFFLINE_SUITE = "python -m unittest discover -s tests -t . -v"
    VALIDATOR = "python scripts/validate_output.py"

    def test_it_runs_the_full_offline_suite(self):
        self.assertIn(self.OFFLINE_SUITE, run_bodies(load_workflow()))

    def test_it_runs_the_production_validator(self):
        self.assertIn(self.VALIDATOR, run_bodies(load_workflow()))

    def test_those_are_the_commands_the_daily_run_uses(self):
        """
        Cross-check against the production workflow, so renaming the suite or
        the validator in one place and not the other is caught here rather
        than by a green PR check that ran nothing.
        """
        daily = (WORKFLOW_DIR / "daily_update.yml").read_text(encoding="utf-8")
        self.assertIn("run: %s" % self.OFFLINE_SUITE, daily)
        self.assertIn("run: %s" % self.VALIDATOR, daily)

    def test_the_suite_is_not_narrowed_to_a_subset(self):
        for body in run_bodies(load_workflow()):
            if "unittest" in body:
                self.assertIn("discover", body,
                              "the PR job must run the whole suite")
                for narrowing in ("-k ", "--failfast", "tests.test_"):
                    self.assertNotIn(narrowing, body)

    def test_the_validator_is_not_given_a_softening_flag(self):
        for body in run_bodies(load_workflow()):
            if "validate_output.py" in body:
                self.assertEqual(body.strip(), self.VALIDATOR)

    def test_it_uses_the_governed_python_and_install_convention(self):
        doc = load_workflow()
        setup = [s for s in steps_of(doc)
                 if s.get("uses", "").startswith("actions/setup-python")]
        self.assertEqual(len(setup), 1)
        self.assertEqual(str(setup[0]["with"]["python-version"]), "3.9")
        self.assertIn("pip install -r requirements.txt", run_bodies(doc))

    def test_it_uses_only_first_party_actions_already_in_use(self):
        established = set()
        for name in ESTABLISHED_WORKFLOWS:
            path = WORKFLOW_DIR / name
            if path.is_file():
                established.update(re.findall(
                    r"uses:\s*(\S+)", path.read_text(encoding="utf-8")))
        for used in uses_values(load_workflow()):
            with self.subTest(action=used):
                self.assertTrue(used.startswith("actions/"),
                                "third-party action introduced: %s" % used)
                self.assertIn(used, established,
                              "action/version not already used by this "
                              "repository: %s" % used)


class TestItIsInert(unittest.TestCase):

    def test_no_step_runs_a_forbidden_command(self):
        doc = load_workflow()
        text = "\n".join(run_bodies(doc) + uses_values(doc))
        for label, pattern in FORBIDDEN_COMMANDS.items():
            with self.subTest(command=label):
                hit = re.search(pattern, text, re.MULTILINE)
                self.assertIsNone(
                    hit, "the PR workflow must not %s (matched %r)"
                         % (label, hit.group(0) if hit else ""))

    def test_the_whole_file_is_free_of_secret_interpolation(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("secrets.", raw)
        self.assertNotIn("GITHUB_TOKEN", raw)

    def test_it_declares_a_timeout(self):
        job = load_workflow()["jobs"]["offline-checks"]
        self.assertIsInstance(job["timeout-minutes"], int)
        self.assertLessEqual(job["timeout-minutes"], 30)

    CONCURRENCY_GROUP = "pr-offline-checks-${{ github.event.pull_request.number }}"

    def test_superseded_runs_are_cancelled_per_pull_request(self):
        """
        Exact equality, because a group that merely mentions "pull_request" can
        still be one static string shared by every PR — for example
        `pr-offline-checks-pull_request`. With `cancel-in-progress: true` that
        would make each new PR cancel the checks of every other open PR.
        """
        concurrency = load_workflow()["concurrency"]
        self.assertIs(concurrency["cancel-in-progress"], True)
        self.assertEqual(concurrency["group"], self.CONCURRENCY_GROUP)


class TestStepOrder(unittest.TestCase):
    """
    Ordering is a safety property here, not a style preference: the baseline
    must predate the first execution of anything the pull request controls.
    """

    def setUp(self):
        self.doc = load_workflow()
        self.baseline = index_of(self.doc, lambda s: s.get("id") == "baseline")
        self.install = index_of(
            self.doc, lambda s: "pip install" in s.get("run", ""))
        self.suite = index_of(
            self.doc, lambda s: "unittest" in s.get("run", ""))
        self.validator = index_of(
            self.doc, lambda s: "validate_output.py" in s.get("run", ""))
        self.guard = index_of(
            self.doc,
            lambda s: "git diff --quiet -- pla_watch.db" in s.get("run", ""))

    def test_the_baseline_is_recorded_before_dependencies_are_installed(self):
        """
        `requirements.txt` comes from the pull request, so `pip install` is the
        first point at which PR-controlled code runs. A baseline taken after it
        would measure a state the PR could already have changed.
        """
        self.assertLess(self.baseline, self.install,
                        [s["name"] for s in steps_of(self.doc)])

    def test_dependencies_are_installed_before_the_suite_and_validator(self):
        self.assertLess(self.install, self.suite)
        self.assertLess(self.install, self.validator)

    def test_the_protection_step_runs_after_the_checks(self):
        self.assertLess(self.suite, self.guard)
        self.assertLess(self.validator, self.guard)

    def test_the_protection_step_is_last(self):
        self.assertEqual(self.guard, len(steps_of(self.doc)) - 1)


class TestItProtectsProductionState(unittest.TestCase):

    def guard_step(self):
        doc = load_workflow()
        return steps_of(doc)[index_of(
            doc,
            lambda s: "git diff --quiet -- pla_watch.db" in s.get("run", ""))]

    def test_it_compares_the_database_by_content_hash(self):
        body = self.guard_step()["run"]
        self.assertIn("sha256sum pla_watch.db", body)
        self.assertIn("steps.baseline.outputs.db", body)

    def test_it_asserts_the_tracked_database_is_unchanged(self):
        self.assertIn("git diff --quiet -- pla_watch.db",
                      self.guard_step()["run"])

    def test_it_asserts_output_is_unchanged(self):
        self.assertIn("git diff --quiet -- output/", self.guard_step()["run"])

    def test_the_status_check_sees_untracked_files(self):
        """
        A diff against the index cannot see a file that was never added, and a
        new untracked file beside the database is exactly the residue worth
        catching.
        """
        self.assertIn(
            "git status --porcelain --untracked-files=all -- pla_watch.db output/",
            self.guard_step()["run"])

    def test_it_checks_for_sidecar_residue(self):
        body = self.guard_step()["run"]
        for sidecar in ("pla_watch.db-wal", "pla_watch.db-shm"):
            self.assertIn(sidecar, body)

    def test_the_baseline_step_refuses_a_checkout_carrying_sidecars(self):
        doc = load_workflow()
        baseline = steps_of(doc)[index_of(
            doc, lambda s: s.get("id") == "baseline")]
        self.assertIn("pla_watch.db-wal", baseline["run"])
        self.assertIn("sha256sum pla_watch.db", baseline["run"])

    GUARD_CONDITION = "${{!cancelled()&&steps.baseline.outcome=='success'}}"

    def test_it_runs_after_a_failing_check_but_not_after_cancellation(self):
        """
        The default `success()` would skip this step precisely when it matters
        most — a suite that failed *and* dirtied the tracked database. It must
        not run after cancellation, where a half-finished job proves nothing,
        nor when the baseline it compares against never succeeded.

        Whitespace-normalised exact equality, because asserting the two operands
        separately says nothing about the operator between them: swapping `&&`
        for `||` leaves both substrings present while changing the meaning to
        "run whenever the baseline succeeded, cancelled or not".
        """
        normalised = self.guard_step()["if"].replace(" ", "")
        self.assertEqual(normalised, self.GUARD_CONDITION)

    def test_the_removed_head_output_pseudo_check_is_absent(self):
        """
        `git rev-parse HEAD:output` reads the committed tree, which cannot
        change during a job. Comparing it before and after compared a constant
        to itself and proved nothing; keeping it would suggest coverage that
        does not exist.
        """
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("HEAD:output", raw)
        self.assertNotIn("steps.baseline.outputs.output", raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
