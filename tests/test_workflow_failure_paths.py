"""
Which failures may persist the database, and which may not.

The 2026-08-14 defect (CI run 475) was not a bad command — every command in the
persist step was correct. It was a bad *predicate*: `failure()` is job-scoped, so
it was equally true when the pipeline had never run. Five pre-pipeline gates can
fail, none of them can have produced collection data, and all five reached a step
whose documented purpose is salvaging collected articles. It committed the test
residue the cleanliness gate had just rejected and pushed it as `483d154`, under
a message announcing a collection that did not happen.

String assertions cannot catch that class of bug, so these tests do two things
the rest of the contract suite does not:

  * evaluate the step's real `if:` expression against the nine job states it can
    actually be in, using a small evaluator for the GitHub expression subset the
    workflow uses; and
  * execute the step's real `run:` body in throwaway git repositories with a
    throwaway `origin`, to see what it actually commits and pushes.

Offline: no network, no GitHub, no production paths. Every repository, database
and remote here is a temporary file that is deleted again.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_workflow_contract import (                     # noqa: E402
    WORKFLOW, step_blocks, strip_comment, workflow_text,
)

PERSIST_STEP = "Persist scraped articles"
PIPELINE_STEP = "Run pipeline"


# ── Extracting a step's `if:` and `run:` ──────────────────────────────────────

def _step_source(name_fragment: str) -> str:
    """Raw text of one step, comments intact."""
    parts = re.split(r"^      - name:", workflow_text(), flags=re.M)[1:]
    for part in parts:
        if name_fragment.lower() in part.splitlines()[0].lower():
            return part
    raise AssertionError("no step matching %r" % name_fragment)


def _block_scalar(step_src: str, key: str) -> str:
    """
    The value of `key:` in a step, whether inline or a `|`/`>` block scalar.

    Written by hand rather than with PyYAML on purpose: the daily collection path
    must not grow a YAML dependency just so its tests can read it (the same trade
    test_workflow_contract.py documents).
    """
    lines = step_src.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^        %s:(.*)$" % re.escape(key), line)
        if not m:
            continue
        inline = m.group(1).strip()
        if inline and inline not in ("|", ">", "|-", ">-"):
            return inline
        body = []
        for follow in lines[i + 1:]:
            if follow.strip() == "":
                body.append("")
                continue
            if not follow.startswith("          "):
                break
            body.append(follow[10:])
        return "\n".join(body)
    raise AssertionError("step has no %r key" % key)


# ── A small evaluator for the GitHub expression subset in use ─────────────────

class ExprError(AssertionError):
    pass


def evaluate_if(expr: str, *, job_failed: bool, outputs: dict, outcomes: dict):
    """
    Evaluate a workflow `if:` expression.

    Supports exactly what the workflow uses: `&&`, `||`, parentheses, `==`, `!=`,
    single-quoted strings, `failure()`, `success()`, `always()`,
    `steps.<id>.outputs.<name>` and `steps.<id>.outcome`. Anything else raises
    rather than being quietly treated as truthy — a test that guesses about the
    predicate under test is worth nothing.

    An id that never ran yields '' for `outcome`, which is what Actions reports.
    """
    tokens = re.findall(r"\(|\)|&&|\|\||==|!=|'[^']*'|[A-Za-z0-9_.]+", expr)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def primary():
        tok = take()
        if tok == "(":
            val = or_expr()
            if take() != ")":
                raise ExprError("unbalanced parentheses in %r" % expr)
            return val
        if tok.startswith("'"):
            return tok[1:-1]
        if tok == "failure":
            _call()
            return job_failed
        if tok == "success":
            _call()
            return not job_failed
        if tok == "always":
            _call()
            return True
        if tok == "cancelled":
            _call()
            return False
        m = re.match(r"^steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)$", tok)
        if m:
            return outputs.get(m.group(1), {}).get(m.group(2), "")
        m = re.match(r"^steps\.([A-Za-z0-9_-]+)\.outcome$", tok)
        if m:
            return outcomes.get(m.group(1), "")
        m = re.match(r"^github\.([A-Za-z0-9_.]+)$", tok)
        if m:
            return outputs.get("github", {}).get(m.group(1).split(".")[-1], "")
        raise ExprError("unsupported token %r in %r" % (tok, expr))

    def _call():
        if peek() == "(":
            take()
            if take() != ")":
                raise ExprError("expected () in %r" % expr)

    def comparison():
        left = primary()
        while peek() in ("==", "!="):
            op = take()
            right = primary()
            left = (left == right) if op == "==" else (left != right)
        return left

    def and_expr():
        left = comparison()
        while peek() == "&&":
            take()
            right = comparison()
            left = bool(left) and bool(right)
        return left

    def or_expr():
        left = and_expr()
        while peek() == "||":
            take()
            right = and_expr()
            left = bool(left) or bool(right)
        return left

    value = or_expr()
    if pos != len(tokens):
        raise ExprError("trailing tokens in %r" % expr)
    return bool(value)


class TestEvaluatorIsHonest(unittest.TestCase):
    """The evaluator must not be the thing that passes the tests."""

    def test_known_expressions(self):
        cases = [
            ("failure()", True, dict(job_failed=True)),
            ("failure()", False, dict(job_failed=False)),
            ("success()", True, dict(job_failed=False)),
            ("always()", True, dict(job_failed=True)),
        ]
        for expr, expected, kw in cases:
            self.assertEqual(
                evaluate_if(expr, outputs={}, outcomes={}, **kw), expected, expr)

    def test_operator_precedence_and_parentheses(self):
        self.assertTrue(evaluate_if(
            "failure() && (steps.p.outcome == 'success' || "
            "steps.p.outcome == 'failure')",
            job_failed=True, outputs={}, outcomes={"p": "failure"}))
        self.assertFalse(evaluate_if(
            "failure() && (steps.p.outcome == 'success' || "
            "steps.p.outcome == 'failure')",
            job_failed=True, outputs={}, outcomes={"p": "skipped"}))

    def test_unknown_token_raises_rather_than_passing(self):
        with self.assertRaises(ExprError):
            evaluate_if("mystery.thing", job_failed=True, outputs={}, outcomes={})

    def test_missing_outcome_is_empty_string_not_truthy(self):
        self.assertFalse(evaluate_if(
            "steps.p.outcome == 'failure'",
            job_failed=True, outputs={}, outcomes={}))


# ── The nine job states the persist step can be in ───────────────────────────

def _persist_predicate(*, job_failed, should_run, pipeline_outcome):
    return evaluate_if(
        _block_scalar(_step_source(PERSIST_STEP), "if"),
        job_failed=job_failed,
        outputs={"timecheck": {"should_run": should_run}},
        outcomes={"pipeline": pipeline_outcome},
    )


class TestPersistEligibility(unittest.TestCase):
    """
    Each case is a real situation the daily run can be in. The comment on each
    is the reason the answer is what it is — not a restatement of the assertion.
    """

    # ── Cases 1–5: the pipeline never ran, so there is nothing to salvage ──

    def test_1_migration_apply_failure_does_not_persist(self):
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="skipped"))

    def test_2_migration_verification_failure_does_not_persist(self):
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="skipped"))

    def test_3_offline_test_failure_does_not_persist(self):
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="skipped"))

    def test_4_reconciliation_contract_failure_does_not_persist(self):
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="skipped"))

    def test_5_db_cleanliness_gate_failure_does_not_persist(self):
        """
        This is CI run 475 exactly. Under the old `failure()`-only predicate it
        was true, and the step pushed the residue the gate had just rejected.
        """
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="skipped"))

    def test_5b_an_id_that_never_ran_is_not_eligible(self):
        """Belt and braces: an unset outcome must not read as eligible."""
        self.assertFalse(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome=""))

    # ── Case 6: the pipeline ran and failed — the reason this step exists ──

    def test_6_pipeline_failure_persists(self):
        self.assertTrue(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="failure"))

    # ── Case 7: the ruling ────────────────────────────────────────────────

    def test_7_pipeline_success_then_downstream_failure_persists(self):
        """
        Output validation failing after a clean pipeline still destroys the day
        unless the database is salvaged: the normal commit carries implicit
        success() and is skipped. Salvage is database-only, so the unvalidated
        render still cannot reach production.
        """
        self.assertTrue(_persist_predicate(
            job_failed=True, should_run="true", pipeline_outcome="success"))

    # ── Case 8: nothing failed ────────────────────────────────────────────

    def test_8_successful_run_uses_the_normal_commit_path_only(self):
        self.assertFalse(_persist_predicate(
            job_failed=False, should_run="true", pipeline_outcome="success"))

    # ── Guard rails ───────────────────────────────────────────────────────

    def test_guarded_run_never_persists(self):
        for outcome in ("skipped", "", "failure", "success"):
            self.assertFalse(_persist_predicate(
                job_failed=True, should_run="false", pipeline_outcome=outcome),
                "should_run=false must never persist (outcome=%r)" % outcome)

    def test_the_old_predicate_would_fail_these_tests(self):
        """
        Proof the suite has teeth: the predicate as it stood on 2026-08-14 is
        true for the pre-pipeline cases above, so this test would fail if the
        fix were reverted to it.
        """
        old = "failure() && steps.timecheck.outputs.should_run == 'true'"
        self.assertTrue(evaluate_if(
            old, job_failed=True,
            outputs={"timecheck": {"should_run": "true"}},
            outcomes={"pipeline": "skipped"}),
            "the old predicate is supposed to be the bug — if this fails the "
            "test no longer describes run 475")

    def test_pipeline_step_has_the_id_the_predicate_depends_on(self):
        src = _step_source(PIPELINE_STEP)
        self.assertRegex(
            src, re.compile(r"^        id: pipeline\s*$", re.M),
            "the persist predicate reads steps.pipeline.outcome; without this "
            "id it silently evaluates to the empty string forever",
        )

    def test_predicate_actually_references_the_pipeline_outcome(self):
        expr = _block_scalar(_step_source(PERSIST_STEP), "if")
        self.assertIn(
            "steps.pipeline.outcome", expr,
            "persistence must be gated on proof the pipeline executed",
        )


# ── Executing the real shell body ────────────────────────────────────────────

class PersistBodyHarness(unittest.TestCase):
    """
    Runs the persist step's real `run:` body in a throwaway repository.

    `python` is shimmed to a no-op so `verify_db_current.py` does not need the
    real environment; this harness is about what the body COMMITS and PUSHES.
    That the body verifies at all, after its rebase and before its push, is
    asserted by test_workflow_contract.TestPostRebaseVerification.
    """

    body = None

    @classmethod
    def setUpClass(cls):
        cls.body = _block_scalar(_step_source(PERSIST_STEP), "run")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="persist-body-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.work = Path(self.tmp) / "repo"
        self.origin = Path(self.tmp) / "origin.git"
        self.bin = Path(self.tmp) / "bin"
        self.bin.mkdir(parents=True)
        shim = self.bin / "python"
        shim.write_text("#!/bin/sh\nexit 0\n")
        shim.chmod(0o755)

        self._git("init", "--bare", "-b", "main", str(self.origin), cwd=Path(self.tmp))
        self.work.mkdir()
        self._git("init", "-b", "main", cwd=self.work)
        self._git("config", "user.name", "seed", cwd=self.work)
        self._git("config", "user.email", "seed@example.invalid", cwd=self.work)
        (self.work / "scripts").mkdir()
        (self.work / "scripts" / "verify_db_current.py").write_text("")
        (self.work / "pla_watch.db").write_bytes(b"BASELINE")
        (self.work / "output").mkdir()
        (self.work / "output" / "index.html").write_text("baseline render")
        self._git("add", "-A", cwd=self.work)
        self._git("commit", "-m", "seed", cwd=self.work)
        self._git("remote", "add", "origin", str(self.origin), cwd=self.work)
        self._git("push", "-u", "origin", "main", cwd=self.work)

    def _git(self, *args, cwd):
        return subprocess.run(
            ("git",) + args, cwd=str(cwd), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def run_body(self, pipeline_outcome="failure"):
        env = dict(os.environ)
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        env["PIPELINE_OUTCOME"] = pipeline_outcome
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
        proc = subprocess.run(
            ["bash", "-e", "-c", self.body], cwd=str(self.work), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    def commits_on_origin(self):
        out = subprocess.run(
            ["git", "log", "--format=%s", "main"], cwd=str(self.origin),
            check=True, stdout=subprocess.PIPE).stdout.decode()
        return [line for line in out.splitlines() if line]

    def files_in_tip(self):
        out = subprocess.run(
            ["git", "show", "--name-only", "--format=", "main"],
            cwd=str(self.origin), check=True,
            stdout=subprocess.PIPE).stdout.decode()
        return sorted(f for f in out.split() if f)


class TestPersistBodyBehaviour(PersistBodyHarness):

    def test_no_database_delta_creates_no_commit(self):
        """Case 9. An unchanged database must not produce an empty, misleading
        'Persist collection' commit."""
        rc, out = self.run_body()
        self.assertEqual(rc, 0, out)
        self.assertIn("No newly scraped articles to persist.", out)
        self.assertEqual(self.commits_on_origin(), ["seed"], out)

    def test_database_delta_is_committed_and_pushed(self):
        (self.work / "pla_watch.db").write_bytes(b"BASELINE+COLLECTION")
        rc, out = self.run_body()
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.commits_on_origin()), 2, out)
        self.assertEqual(self.files_in_tip(), ["pla_watch.db"], out)

    def test_generated_output_is_never_carried_into_the_commit(self):
        """
        The whole reason the normal commit is gated on success() is that an
        unvalidated render must not publish. The salvage path must not become a
        way around that, even when output/ happens to be dirty.
        """
        (self.work / "pla_watch.db").write_bytes(b"BASELINE+COLLECTION")
        (self.work / "output" / "index.html").write_text("UNVALIDATED RENDER")
        rc, out = self.run_body()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.files_in_tip(), ["pla_watch.db"], out)
        blob = subprocess.run(
            ["git", "show", "main:output/index.html"], cwd=str(self.origin),
            check=True, stdout=subprocess.PIPE).stdout.decode()
        self.assertEqual(blob, "baseline render",
                         "the unvalidated render reached origin")

    def test_message_says_analysis_incomplete_when_the_pipeline_failed(self):
        (self.work / "pla_watch.db").write_bytes(b"BASELINE+COLLECTION")
        rc, out = self.run_body(pipeline_outcome="failure")
        self.assertEqual(rc, 0, out)
        self.assertIn("analysis incomplete", self.commits_on_origin()[0])

    def test_message_does_not_claim_analysis_failed_when_it_did_not(self):
        """
        Case 7's commit must not say 'analysis incomplete': the pipeline
        completed and a publication step failed. A wrong message here is how
        483d154 came to announce a collection that never happened.
        """
        (self.work / "pla_watch.db").write_bytes(b"BASELINE+COLLECTION")
        rc, out = self.run_body(pipeline_outcome="success")
        self.assertEqual(rc, 0, out)
        subject = self.commits_on_origin()[0]
        self.assertNotIn("analysis incomplete", subject)
        self.assertIn("a later publication step failed", subject)


# ── Parser robustness ────────────────────────────────────────────────────────

class TestCommentsCannotFoolTheParser(unittest.TestCase):
    """
    The contract suite decides whether a step pushes, rebases or verifies by
    looking for command text in its body. Prose that quotes those commands must
    therefore never survive into the body — from a whole-line comment or a
    trailing one.
    """

    SYNTHETIC = (
        "      - name: Innocent step\n"
        "        run: |\n"
        "          echo hello        # git push origin main\n"
        "          # git pull --rebase origin main\n"
        "          echo '#not-a-comment'\n"
        '          echo "### heading"\n'
    )

    def test_whole_line_comment_is_stripped(self):
        (_, body), = step_blocks(self.SYNTHETIC)
        self.assertNotIn("git pull --rebase", body)

    def test_trailing_comment_is_stripped(self):
        (_, body), = step_blocks(self.SYNTHETIC)
        self.assertNotIn("git push", body)

    def test_hash_inside_quotes_is_data_not_a_comment(self):
        (_, body), = step_blocks(self.SYNTHETIC)
        self.assertIn("'#not-a-comment'", body)
        self.assertIn('"### heading"', body)

    def test_real_workflow_keeps_its_quoted_hash(self):
        joined = "\n".join(b for _, b in step_blocks(workflow_text()))
        self.assertIn("### ❌ API account blocked", joined,
                      "a quoted hash was mistaken for a comment")

    def test_strip_comment_leaves_ordinary_lines_alone(self):
        self.assertEqual(strip_comment("  git push origin main"),
                         "  git push origin main")


# ── The tracked database must survive the suite ──────────────────────────────

TRACKED_FILENAME = "pla_watch.db"

#: Names that, in this repository, denote the repository root.
ROOT_NAMES = frozenset({"REPO_ROOT", "ROOT_DIR", "ROOT", "PROJECT_ROOT"})

#: Names conventionally bound to the tracked database. Consulted only for names
#: this module never assigns — an imported `DB_PATH` is the tracked file; one
#: assigned locally to a temporary path is not.
IMPORTED_TRACKED_NAMES = frozenset({"DB_PATH", "TRACKED_DB", "PROD_DB"})


def _sqlite_connect_names(tree):
    """
    Every local name that reaches `sqlite3.connect`, whatever the import style.

    Returns (module_aliases, function_names) — so `sqlite3.connect`,
    `_sq.connect`, `connect` and `db_connect` are all recognised. The previous
    guard matched the literal text `sqlite3.connect(` and therefore missed the
    exact line that caused run 475 (`import sqlite3 as _sq` … `_sq.connect`).
    """
    modules, funcs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    modules.add(alias.asname or "sqlite3")
        elif isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
            for alias in node.names:
                if alias.name == "connect":
                    funcs.add(alias.asname or "connect")
    return modules, funcs


def _assignments(tree):
    """name -> [assigned value nodes]. Deliberately scope-insensitive: a test
    module that binds one name to both a temporary and the tracked path is
    already a problem worth flagging."""
    out = {}
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and node.value is not None:
                out.setdefault(t.id, []).append(node.value)
    return out


def _denotes_tracked_db(node, assigned, depth=0):
    """
    Does this expression resolve to the tracked production database?

    True for `REPO_ROOT / "pla_watch.db"`, `str(prod)`, a bare `prod` bound to
    it, an imported `DB_PATH`, and `f"file:{prod}?mode=ro"` — the URI form is
    included deliberately: DECISION_LOG 2026-08-14 records that `mode=ro`
    cannot even open this WAL database without a `-shm`, so it is not an
    escape hatch for tests either.

    False for temporary and fixture paths, which never mention the repo root.
    """
    if node is None or depth > 4:
        return False
    subtree = list(ast.walk(node))
    names = {n.id for n in subtree if isinstance(n, ast.Name)}
    consts = {c.value for c in subtree
              if isinstance(c, ast.Constant) and isinstance(c.value, str)}

    # REPO_ROOT / "pla_watch.db", in any wrapper (str(), f-string, Path()).
    if any(TRACKED_FILENAME in c for c in consts) and (names & ROOT_NAMES):
        return True
    # config.DB_PATH / dbmod.DB_PATH style module attributes.
    if any(isinstance(a, ast.Attribute) and a.attr in IMPORTED_TRACKED_NAMES
           for a in subtree):
        return True
    # Names: resolve through local assignment, else fall back to convention.
    for name in names:
        if name in assigned:
            if any(_denotes_tracked_db(v, assigned, depth + 1)
                   for v in assigned[name]):
                return True
        elif name in IMPORTED_TRACKED_NAMES:
            return True
    return False


def tracked_db_connections(source: str):
    """
    [(lineno, rendered_call)] for every sqlite3 connection in `source` whose
    target resolves to the tracked database.

    Structural, not textual: it reads imports and assignments, so it is immune
    to aliasing. It stays small on purpose — this recognises one hazard, it is
    not a static analyser.
    """
    tree = ast.parse(source)
    modules, funcs = _sqlite_connect_names(tree)
    assigned = _assignments(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        is_connect = (
            (isinstance(fn, ast.Attribute) and fn.attr == "connect"
             and isinstance(fn.value, ast.Name) and fn.value.id in modules)
            or (isinstance(fn, ast.Name) and fn.id in funcs)
        )
        if not is_connect:
            continue
        target = node.args[0] if node.args else next(
            (kw.value for kw in node.keywords if kw.arg == "database"), None)
        if _denotes_tracked_db(target, assigned):
            hits.append((node.lineno, ast.dump(fn)))
    return hits


class TestTrackedDatabaseGuardItself(unittest.TestCase):
    """
    The detector is tested before it is trusted.

    Its predecessor was a regex that matched the literal `sqlite3.connect(` and
    silently missed the aliased call that actually caused run 475 — a guard
    nobody had pointed at the code it was supposed to catch. These cases are
    that missing proof.
    """

    MUST_FLAG = {
        "the exact pre-fix line (run 475)":
            "import sqlite3 as _sq\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "con = _sq.connect(str(prod))\n",
        "plain module import":
            "import sqlite3\n"
            "con = sqlite3.connect(str(REPO_ROOT / 'pla_watch.db'))\n",
        "a different module alias":
            "import sqlite3 as sq3\n"
            "con = sq3.connect(str(REPO_ROOT / 'pla_watch.db'))\n",
        "from-import of connect":
            "from sqlite3 import connect\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "con = connect(prod)\n",
        "from-import with an alias":
            "from sqlite3 import connect as db_connect\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "con = db_connect(str(prod))\n",
        "database= keyword":
            "import sqlite3\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "con = sqlite3.connect(database=prod)\n",
        "a mode=ro URI is not an escape hatch":
            "import sqlite3\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "con = sqlite3.connect(f'file:{prod}?mode=ro', uri=True)\n",
        "indirection through a second name":
            "import sqlite3\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "target = prod\n"
            "con = sqlite3.connect(str(target))\n",
        "an imported DB_PATH":
            "import sqlite3\n"
            "from config import DB_PATH\n"
            "con = sqlite3.connect(str(DB_PATH))\n",
    }

    MUST_NOT_FLAG = {
        "the canonical scratch-copy helper":
            "from scripts.reconcile_db import _read_only\n"
            "prod = REPO_ROOT / 'pla_watch.db'\n"
            "with _read_only(str(prod)) as con:\n"
            "    pass\n",
        "an ordinary temporary database":
            "import sqlite3\n"
            "con = sqlite3.connect(str(self.db_path))\n",
        "a tempfile path that happens to share the filename":
            "import sqlite3\n"
            "copy = Path(tmp) / 'pla_watch.db'\n"
            "con = sqlite3.connect(str(copy))\n",
        "a fixture database":
            "import sqlite3\n"
            "con = sqlite3.connect(str(FIXTURES / 'legacy.db'))\n",
        "a locally reassigned DB_PATH pointing at a temp file":
            "import sqlite3\n"
            "DB_PATH = tmp / 'scratch.db'\n"
            "con = sqlite3.connect(DB_PATH)\n",
        "merely naming the file in an assertion":
            "self.assertIn('pla_watch.db', block)\n"
            "self.assertEqual(REPO_ROOT / 'pla_watch.db', TRACKED)\n",
        "hashing the tracked file without connecting":
            "import hashlib\n"
            "TRACKED = REPO_ROOT / 'pla_watch.db'\n"
            "digest = hashlib.sha256(TRACKED.read_bytes()).hexdigest()\n",
        "a docstring mentioning the path":
            "'''connects to REPO_ROOT / \"pla_watch.db\" — or it used to.'''\n",
    }

    def test_flags_every_unsafe_import_style(self):
        for label, src in self.MUST_FLAG.items():
            with self.subTest(case=label):
                self.assertTrue(
                    tracked_db_connections(src),
                    "guard missed an unsafe connection: %s" % label)

    def test_does_not_flag_safe_code(self):
        for label, src in self.MUST_NOT_FLAG.items():
            with self.subTest(case=label):
                self.assertEqual(
                    tracked_db_connections(src), [],
                    "guard falsely flagged safe code: %s" % label)


class TestTrackedDatabaseIsNotOpenedForWriting(unittest.TestCase):
    """
    The regression that produced run 475's residue. The tracked database is
    WAL-mode, so a plain `sqlite3.connect()` is not a read: it creates -wal/-shm
    and can checkpoint pages back into the file.
    """

    TRACKED = REPO_ROOT / "pla_watch.db"

    def test_no_test_connects_to_the_tracked_database(self):
        offenders = []
        for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
            try:
                hits = tracked_db_connections(
                    path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                self.fail("%s does not parse: %s" % (path, exc))
            offenders += ["%s:%d" % (path.relative_to(REPO_ROOT), line)
                          for line, _ in hits]
        self.assertEqual(
            offenders, [],
            "these tests connect to the tracked database; read a scratch copy "
            "via reconcile_db._read_only instead: %s" % offenders)

    def test_repeated_runs_leave_the_tracked_database_byte_identical(self):
        if not self.TRACKED.exists():
            self.skipTest("production database not present")
        import hashlib
        from tests.test_pipeline_compat import TestNeutralLanguagePersistence

        digest = lambda: hashlib.sha256(self.TRACKED.read_bytes()).hexdigest()
        before = digest()
        loader = unittest.TestLoader()
        for _ in range(3):
            suite = loader.loadTestsFromTestCase(TestNeutralLanguagePersistence)
            with open(os.devnull, "w") as sink:
                result = unittest.TextTestRunner(
                    stream=sink, verbosity=0).run(suite)
            self.assertTrue(result.wasSuccessful())
            self.assertEqual(
                digest(), before,
                "the tracked database changed while its own tests ran")


if __name__ == "__main__":
    unittest.main(verbosity=2)
