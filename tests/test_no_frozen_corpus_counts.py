"""
No changing corpus figure may be frozen into a test or a template.

This is the regression guard for a defect that has already stopped collection
once. On 2026-08-24 a scheduled commit opened a seventeenth publication week
and two tests failed — not because anything was wrong, but because both had
written a corpus shape into an assertion. `Run offline test suite` in
`daily_update.yml` has no `continue-on-error` and precedes the pipeline, so the
next run would have failed at the test step and collected nothing.

The lesson generalises past those two tests: any literal equal to a quantity
that moves when collection succeeds is a time bomb with a fuse of unknown
length. So this walks the test suite and the candidate's templates, and fails on
any literal matching a currently-moving corpus figure.

What it does NOT do
-------------------
It does not ban numbers. Governed constants stay: thirteen published editions,
a thirty-day shadow gate, the twenty-seven Japan exercise titles, the observed
publication volumes carried from research. Those are facts about the world or
about policy, and they do not move when a scraper succeeds.

The check is scoped to figures at or above `FLOOR`. Below that, a literal is
far more likely to be a structural constant — a column count, a page size, an
index — that happens to collide with a small corpus quantity, and a guard that
cries wolf gets deleted. The quantities that actually move fast are all large.

Mutation-proved: replacing `"{:,}".format(self.corpus_size)` with the literal
`"3,499"` in `test_preview_prototype.py` fails
`test_no_test_freezes_a_moving_corpus_figure`.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.viewmodel import PublicView                            # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
TESTS_DIR = REPO_ROOT / "tests"
TEMPLATES_DIR = REPO_ROOT / "site" / "preview" / "templates"

#: Below this, a bare integer is far more likely to be a structural constant
#: than a corpus figure, and a false positive here costs more than the miss.
FLOOR = 100

#: This file necessarily contains the machinery for talking about these
#: figures; it must not police itself into failure.
EXEMPT_FILES = ("test_no_frozen_corpus_counts.py",)


def moving_figures() -> dict:
    """
    Every corpus quantity that changes when a collection run succeeds.

    Read at test time from the database, so the guard tracks the corpus rather
    than restating it — which would be the very defect it exists to catch.
    """
    view = PublicView(TRACKED_DB)
    metrics = view.methodology_metrics()
    figures = {
        "stored records": metrics.records,
        "analyzed records": metrics.analyzed,
        "records awaiting screening": metrics.awaiting_screening,
        "records not selected": metrics.not_selected,
        "records with stored original text": metrics.with_original_text,
        "collection runs": metrics.runs,
    }
    for source in view.source_directory():
        if source.record_count:
            figures["records from %s" % source.slug] = source.record_count

    # The declared snapshot's record count is the one figure that is SUPPOSED
    # to be written down: it is hand-advanced release metadata naming one
    # frozen corpus, and `TestDeclaredSnapshot` asserts it on purpose. When the
    # snapshot is next advanced it will equal the live corpus for a while, and
    # this guard must not fire on the assertion that pins it.
    declared = _declared_snapshot_records()
    return {name: value for name, value in figures.items()
            if value >= FLOOR and value != declared}


def _declared_snapshot_records() -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gp_snapshot_probe",
        REPO_ROOT / "site" / "preview" / "generate_preview.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gp_snapshot_probe"] = module
    spec.loader.exec_module(module)
    return int(module.DECLARED_SNAPSHOT["expected_records"])


def literals(text: str):
    """Every integer literal in the text, plain or comma-grouped."""
    found = set()
    for match in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b", text):
        found.add(int(match.replace(",", "")))
    return found


def code_literals(source: str):
    """
    Numbers a Python module actually *uses*, excluding prose.

    Docstrings and comments are skipped, because a figure written there is not
    a time bomb: nothing asserts it, and nothing fails when the corpus moves.
    Scanning them made the guard fire on a test that merely narrated the run
    number of the 2026-08-25 incident — a true historical fact that happened to
    equal the day's collection-run count.

    What is NOT skipped is string constants inside expressions. A frozen figure
    most often appears as `assertIn("3,534", ...)`, which is a string, and
    dropping those would remove the guard's main tooth.
    """
    tree = ast.parse(source)

    # Collect the exact node identities of docstrings so they can be excluded
    # by identity rather than by value — an ordinary string that happens to
    # match a docstring's text must still be scanned.
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, bool):
            continue
        if isinstance(node.value, int):
            found.add(node.value)
        elif isinstance(node.value, str):
            found |= literals(node.value)
    return found


class FrozenCountCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.figures = moving_figures()

    def assert_no_frozen_figure(self, path: Path):
        source = path.read_text(encoding="utf-8")
        present = (code_literals(source) if path.suffix == ".py"
                   else literals(source))
        for name, value in self.figures.items():
            with self.subTest(figure=name):
                self.assertNotIn(
                    value, present,
                    "%s writes %d, which is the current count of %s. Derive it "
                    "from the corpus instead — this number moves the next time "
                    "collection succeeds."
                    % (path.name, value, name))


class TestTheGuardHasSomethingToGuard(FrozenCountCase):

    def test_there_are_moving_figures_to_check(self):
        """
        A guard measuring nothing passes for the wrong reason.

        Which figures are in scope is not fixed. `moving_figures()` drops any
        value equal to the declared snapshot's record count, because that one
        number is *supposed* to be written down. Immediately after a snapshot
        is advanced the stored-record count equals it, so "stored records"
        leaves the set for as long as the corpus stays where the snapshot froze
        it — the case the function's own comment anticipates. Requiring that
        particular key would make this guard fail every time a snapshot is
        accepted, which is the one moment it is least useful to break.

        So the requirement is that the guard is measuring several real,
        substantial figures — not that it is measuring one named one.
        """
        self.assertTrue(self.figures)
        self.assertGreaterEqual(len(self.figures), 4)
        self.assertTrue(all(value >= FLOOR for value in self.figures.values()))
        self.assertIn("analyzed records", self.figures)


class TestNoFrozenCorpusCounts(FrozenCountCase):

    def test_no_test_freezes_a_moving_corpus_figure(self):
        for path in sorted(TESTS_DIR.rglob("*.py")):
            if path.name in EXEMPT_FILES:
                continue
            with self.subTest(test_file=path.name):
                self.assert_no_frozen_figure(path)

    def test_no_template_freezes_a_moving_corpus_figure(self):
        for path in sorted(TEMPLATES_DIR.glob("*.html")):
            with self.subTest(template=path.name):
                self.assert_no_frozen_figure(path)

    def test_no_configuration_file_freezes_a_moving_corpus_figure(self):
        for path in (REPO_ROOT / "desks" / "registry.json",
                     REPO_ROOT / "site" / "url_transition_map.json"):
            with self.subTest(config=path.name):
                self.assert_no_frozen_figure(path)


class TestTheScanReadsCodeNotProse(unittest.TestCase):
    """
    The guard's precision, pinned in both directions.

    It fired once on a test that merely narrated the run number of the
    2026-08-25 incident, because that number happened to equal the day's
    collection-run count. A figure in prose is not a time bomb — nothing
    asserts it, and nothing fails when the corpus moves. What must keep firing
    is a figure an assertion actually depends on, including the string form
    that is how a frozen count usually appears.
    """

    SAMPLE = 3534

    def scan(self, source):
        return code_literals(source)

    def test_a_figure_in_a_module_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            '"""The corpus held %d records."""\nx = 1\n' % self.SAMPLE))

    def test_a_figure_in_a_function_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            'def f():\n    """held %d records"""\n    return 1\n' % self.SAMPLE))

    def test_a_figure_in_a_class_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            'class C:\n    """held %d records"""\n    pass\n' % self.SAMPLE))

    def test_a_figure_in_a_comment_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            '# held %d records\nx = 1\n' % self.SAMPLE))

    def test_an_integer_literal_in_code_is_still_seen(self):
        self.assertIn(self.SAMPLE, self.scan(
            'assert total == %d\n' % self.SAMPLE))

    def test_a_comma_formatted_string_in_code_is_still_seen(self):
        """The shape a frozen count actually takes: assertIn("3,534", ...)."""
        self.assertIn(self.SAMPLE, self.scan(
            'assertIn("%s", page)\n' % format(self.SAMPLE, ",")))

    def test_a_plain_string_literal_in_code_is_still_seen(self):
        self.assertIn(self.SAMPLE, self.scan(
            'assertIn("%d records", page)\n' % self.SAMPLE))

    def test_a_string_that_merely_matches_a_docstring_is_still_seen(self):
        """
        Docstrings are excluded by node identity, not by text. An ordinary
        string that happens to read like one must still be scanned, or the
        exclusion becomes a way to hide a frozen figure.
        """
        text = "held %d records" % self.SAMPLE
        source = 'def f():\n    """%s"""\n    return assertIn("%s", page)\n' % (text, text)
        self.assertIn(self.SAMPLE, self.scan(source))

    def test_booleans_are_not_counted_as_numbers(self):
        """`True` is an int subclass; counting it would make 1 a corpus figure."""
        self.assertNotIn(1, self.scan("x = True\n"))


class TestGovernedConstantsAreNotCollateralDamage(FrozenCountCase):
    """
    The other half of the rule. A guard that also removed the constants which
    are genuinely fixed would push authors toward deriving things that should
    be declared — and a derived policy threshold is worse than a frozen one.
    """

    def test_the_shadow_qualification_gate_is_still_a_declared_constant(self):
        raw = (REPO_ROOT / "desks" / "registry.json").read_text("utf-8")
        self.assertIn('"required_consecutive_days": 30', raw)

    def test_the_japan_research_figures_are_still_declared(self):
        raw = (REPO_ROOT / "desks" / "registry.json").read_text("utf-8")
        for figure in ("135", "214", "895", "27"):
            with self.subTest(figure=figure):
                self.assertIn(figure, raw)

    def test_the_published_edition_count_is_still_asserted_somewhere(self):
        raw = (TESTS_DIR / "test_desk_rollout_contract.py").read_text("utf-8")
        self.assertIn("2026-05-09", raw)


if __name__ == "__main__":
    unittest.main()
