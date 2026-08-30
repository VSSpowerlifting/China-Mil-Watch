"""
No changing corpus figure may be frozen into a test or a template.

This is the regression guard for a defect that has already stopped collection
once. On 2026-08-24 a scheduled commit opened a seventeenth publication week
and two tests failed — not because anything was wrong, but because both had
written a corpus shape into an assertion. `Run offline test suite` in
`daily_update.yml` has no `continue-on-error` and precedes the pipeline, so the
next run would have failed at the test step and collected nothing.

Why this file was rewritten on 2026-08-28
-----------------------------------------
The guard used to compare EVERY integer literal in every test and template
against every currently-moving corpus figure. That is an equality scan over two
unrelated populations, and it was only ever a matter of time before they
collided. They did, on nine files at once, and every single hit was a false
positive:

  * `week.count * 100 / volume_max`      a percentage
  * `MAX_WORDS = 100`                    an editorial policy constant
  * `read_bytes()[:100]`                 a byte slice
  * `partition_refs(refs, CUTOFF, 100)`  a cap argument
  * `add_run(self.local, 100)`           a fixture run id
  * `assertGreater(len(entries), 100)`   a lower bound
  * `lookback_days=365`                  a day count
  * `re.findall(r"<h[123]...")`          a regex character class
  * an authority tier score of 100

Not one was a frozen corpus total, and the guard was failing the very workflow
step it exists to protect. A guard that cries wolf gets deleted, and deleting
this one would give back the defect it was written for.

So the equality scan is gone and the truth guarantee is not. It is now made two
ways, positively and negatively:

  POSITIVELY, by mutation. `tests/test_daily_corpus_advance.py` renders against
  a temporary corpus that differs from the real one and asserts the public
  metric surfaces state THAT corpus and not the launch pin. A figure frozen
  into any template cannot survive that, and no literal has to be guessed at.

  NEGATIVELY, and narrowly, here. Two rules, each matching the shape a frozen
  public total actually takes rather than any number that happens to be equal:

    1. Comma-grouped numerals — `"3,611"`. This is how a corpus total appears
       on a page and in an assertion about a page. Percentages, status codes,
       byte offsets, day counts and fixture ids are never written this way.

       In a Python file this rule reads the PARSE TREE, not the raw text:
       string constants only, docstrings excluded by node identity, and
       comments invisible because they are not nodes at all. Corrected
       2026-08-28 — it had been a regex over the whole file, so a comment
       reading `# Historical launch contained 3,611 records` was reported as a
       frozen total. The prose tests below did not catch it because they
       called the context scanner directly while the end-to-end path composed
       both, which is why `TestProseIsInvisibleEndToEnd` goes through
       `frozen_total_literals_from` instead. Templates and JSON configs keep
       the raw rule: they have no docstrings, no comments in this sense, and
       every number in one is content a reader sees.
    2. Bare integers in a statement that also names a corpus metric —
       `assertEqual(metrics.records, 3611)`. Whole-identifier matches only, so
       `add_run` is not `runs` and `count` is not `record_count`.

What it does NOT do
-------------------
It does not ban numbers. Governed constants stay: thirteen published editions,
a thirty-day shadow gate, the twenty-seven Japan exercise titles, the observed
publication volumes carried from research. Those are facts about the world or
about policy, and they do not move when a scraper succeeds.

`FLOOR` is unchanged at 100. The fix for the false positives was to look at
where a number sits, not to stop looking at numbers of a certain size.

Mutation-proved in both directions by `TestTheNarrowingStillCatchesTheRealThing`
and `TestTheKnownFalsePositivesAreGone`: a genuinely hardcoded public total is
still caught, and each of the nine real-world literals above is not.
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


#: Whole identifier names that mean "a quantity of corpus". Deliberately not
#: substrings and deliberately not generic: `count`, `total` and `n` appear all
#: over the suite on things that are not the corpus, and matching them is how
#: the previous version came to flag a percentage denominator. `add_run` is not
#: `runs`; `week.count` is not `record_count`.
CORPUS_IDENTIFIERS = frozenset({
    "records", "record_count", "records_total", "corpus_size", "corpus_total",
    "stored_records", "expected_records", "analyzed", "analyzed_records",
    "awaiting_screening", "not_selected", "with_original_text", "runs",
    "n_records", "methodology_metrics",
})

GROUPED = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")


def grouped_literals(text: str):
    """
    Comma-grouped numerals only: `3,611`.

    The form a corpus total takes when a reader sees it, and therefore the form
    it takes when someone freezes one into a page or into an assertion about a
    page. Nothing structural is written this way — there are no comma-grouped
    status codes, byte offsets, caps or day counts.
    """
    return {int(m.replace(",", "")) for m in GROUPED.findall(text)}


def _docstring_node_ids(tree) -> set:
    """
    The identity of every module, class and function docstring in `tree`.

    By identity, not by text: an ordinary string that happens to read like a
    docstring must still be scanned, or the exclusion becomes a way to hide a
    frozen figure inside a lookalike.
    """
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                found.add(id(body[0].value))
    return found


def grouped_literals_in_code(source: str):
    """
    Comma-grouped numerals in a Python file's EXECUTABLE strings only.

    `grouped_literals` runs a regex over raw text, which is right for a
    template or a JSON config and wrong for Python: it read comments and
    docstrings too, so

        # Historical launch contained 3,611 records

    was reported as a frozen corpus total. That contradicted this module's own
    stated contract — prose is ignored — and the prose tests did not catch it
    because they exercised `corpus_context_literals` while the end-to-end path
    also called the raw scanner. A guard whose documented behaviour and actual
    behaviour disagree is worse than one that is merely strict.

    So the source is parsed and only string constants are read. Comments are
    not AST nodes and therefore cannot be seen at all — the strongest available
    form of "invisible", because it needs no rule. Docstrings are excluded by
    node identity. What remains is the ordinary executable string, which is
    where a frozen total actually lives:

        self.assertIn("3,611", page)
    """
    tree = ast.parse(source)
    docstrings = _docstring_node_ids(tree)
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            found |= grouped_literals(node.value)
    return found


def _own_nodes(stmt):
    """
    The nodes belonging to this statement, not to statements nested inside it.

    `ast.walk` on a `ClassDef` returns the entire class, so a class that
    mentions `runs` in one method and the number 100 in another read as one
    statement doing both — which is how a `<h[123]>` regex and a percentage
    denominator ended up sharing a scope with a corpus figure. A statement's
    context is its own expressions; anything nested is its own context.
    """
    collected = []

    def visit(node, is_root=False):
        if isinstance(node, ast.stmt) and not is_root:
            return
        collected.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(stmt, is_root=True)
    return collected


def _statement_names(stmt) -> set:
    names = set()
    for child in _own_nodes(stmt):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
        elif isinstance(child, ast.keyword) and child.arg:
            names.add(child.arg)
    return names


def corpus_context_literals(source: str):
    """
    Integers written in a statement that also names a corpus metric.

    `self.assertEqual(metrics.records, 3611)` is a frozen total. `MAX_WORDS =
    100` is not, and the difference is not the number — it is what the
    statement is talking about. Docstrings are excluded the same way
    the superseded scanner did: a figure nothing asserts is not a time bomb.
    """
    tree = ast.parse(source)
    docstrings = _docstring_node_ids(tree)

    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if not (_statement_names(node) & CORPUS_IDENTIFIERS):
            continue
        for child in _own_nodes(node):
            if not isinstance(child, ast.Constant) or id(child) in docstrings:
                continue
            if isinstance(child.value, bool):
                continue
            if isinstance(child.value, int):
                found.add(child.value)
            elif isinstance(child.value, str):
                found |= grouped_literals(child.value)
    return found


def frozen_total_literals(path: Path):
    """
    Every number in `path` that looks like a frozen public corpus total.

    Python files get both rules, and both read the parse tree rather than the
    raw text, so a figure in a comment or a docstring is invisible to each.

    Everything else gets the raw comma-grouped rule: a template or a JSON
    config has no statements to read context from and no docstrings to
    exclude, and every number in one is content. The mutation proof in
    `test_daily_corpus_advance.py` covers a template that freezes a figure far
    better than any literal scan could — it renders a different corpus and
    checks the page followed it.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return grouped_literals_in_code(text) | corpus_context_literals(text)
    return grouped_literals(text)


def frozen_total_literals_from(text: str, suffix: str):
    """
    `frozen_total_literals` for a source string, so cases read as code.

    Deliberately the same composition as the file-reading path. When these two
    diverged, the prose tests passed against a scanner the real guard was not
    only using, and a comment containing `3,611` was reported as a frozen
    corpus total for a day.
    """
    if suffix == ".py":
        return grouped_literals_in_code(text) | corpus_context_literals(text)
    return grouped_literals(text)


class FrozenCountCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.figures = moving_figures()

    def assert_no_frozen_figure(self, path: Path):
        present = frozen_total_literals(path)
        for name, value in self.figures.items():
            with self.subTest(figure=name):
                self.assertNotIn(
                    value, present,
                    "%s writes %d as a corpus total, which is the current "
                    "count of %s. Derive it from the corpus instead — this "
                    "number moves the next time collection succeeds."
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

    These run against `corpus_context_literals`, which is the detector the
    guard actually uses. Each sample is written inside a statement that names a
    corpus metric, because that is the only context in which the prose rule
    now has anything to decide.
    """

    SAMPLE = 3534

    def scan(self, source):
        return corpus_context_literals(source)

    def test_a_figure_in_a_module_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            '"""The corpus held %d records."""\nrecords = f()\n' % self.SAMPLE))

    def test_a_figure_in_a_function_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            'def f():\n    """held %d records"""\n    return records\n'
            % self.SAMPLE))

    def test_a_figure_in_a_class_docstring_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            'class C:\n    """held %d records"""\n    records = f()\n'
            % self.SAMPLE))

    def test_a_figure_in_a_comment_is_ignored(self):
        self.assertNotIn(self.SAMPLE, self.scan(
            '# held %d records\nrecords = f()\n' % self.SAMPLE))

    def test_an_integer_literal_in_code_is_still_seen(self):
        self.assertIn(self.SAMPLE, self.scan(
            'assert records == %d\n' % self.SAMPLE))

    def test_a_comma_formatted_string_in_code_is_still_seen(self):
        """
        The shape a frozen count actually takes. This one is caught by the
        comma-grouped rule wherever it appears, statement context or not.
        """
        self.assertIn(self.SAMPLE, grouped_literals(
            'assertIn("%s", page)\n' % format(self.SAMPLE, ",")))

    def test_a_plain_string_literal_in_a_corpus_statement_is_seen(self):
        self.assertIn(self.SAMPLE, self.scan(
            'assertEqual(records, "%s")\n' % format(self.SAMPLE, ",")))

    def test_a_string_that_merely_matches_a_docstring_is_still_seen(self):
        """
        Docstrings are excluded by node identity, not by text. An ordinary
        string that happens to read like one must still be scanned, or the
        exclusion becomes a way to hide a frozen figure.
        """
        text = "held %s records" % format(self.SAMPLE, ",")
        source = ('def f():\n    """%s"""\n    return assertIn("%s", page)\n'
                  % (text, text))
        self.assertIn(self.SAMPLE, grouped_literals(source))

    def test_booleans_are_not_counted_as_numbers(self):
        """`True` is an int subclass; counting it would make 1 a corpus figure."""
        self.assertNotIn(1, self.scan("records = True\n"))


class TestProseIsInvisibleEndToEnd(unittest.TestCase):
    """
    The guard's stated contract, tested through the door the guard actually
    uses.

    This class exists because the contract and the code disagreed for a day.
    `TestTheScanReadsCodeNotProse` proved prose was ignored — but it called
    `corpus_context_literals` directly, while `frozen_total_literals` ALSO
    applied a raw regex to the whole file. So

        # Historical launch contained 3,611 records

    was reported as a frozen corpus total, and every prose test passed.

    Every case below goes through `frozen_total_literals_from`, which composes
    exactly what the file-reading path composes. A lower-level test cannot
    prove this property, because the defect was in the composition.
    """

    TOTAL = 3611
    GROUPED = "3,611"

    def scan(self, source):
        return frozen_total_literals_from(source, ".py")

    # ── prose: invisible ────────────────────────────────────────────────────

    def test_a_grouped_number_in_a_comment_is_ignored(self):
        """The reported defect, verbatim."""
        self.assertNotIn(self.TOTAL, self.scan(
            "# Historical launch contained %s records\nx = 1\n" % self.GROUPED))

    def test_a_grouped_number_in_a_trailing_comment_is_ignored(self):
        self.assertNotIn(self.TOTAL, self.scan(
            "x = 1  # was %s records at launch\n" % self.GROUPED))

    def test_a_grouped_number_in_a_module_docstring_is_ignored(self):
        self.assertNotIn(self.TOTAL, self.scan(
            '"""Historical launch contained %s records."""\nx = 1\n'
            % self.GROUPED))

    def test_a_grouped_number_in_a_class_docstring_is_ignored(self):
        self.assertNotIn(self.TOTAL, self.scan(
            'class C:\n    """held %s records"""\n    pass\n' % self.GROUPED))

    def test_a_grouped_number_in_a_function_docstring_is_ignored(self):
        self.assertNotIn(self.TOTAL, self.scan(
            'def f():\n    """held %s records"""\n    return 1\n'
            % self.GROUPED))

    def test_a_grouped_number_in_a_method_docstring_is_ignored(self):
        self.assertNotIn(self.TOTAL, self.scan(
            'class C:\n    def f(self):\n        """held %s records"""\n'
            '        return 1\n' % self.GROUPED))

    # ── code: still caught ──────────────────────────────────────────────────

    def test_the_same_text_in_an_executable_string_is_caught(self):
        """
        Identical words, different node. This is the pair that shows the rule
        is about where the number lives, not about what it says.
        """
        self.assertIn(self.TOTAL, self.scan(
            'note = "Historical launch contained %s records"\n' % self.GROUPED))

    def test_a_page_assertion_is_caught(self):
        self.assertIn(self.TOTAL, self.scan(
            'self.assertIn("%s", page)\n' % self.GROUPED))

    def test_a_grouped_number_in_an_f_string_is_caught(self):
        self.assertIn(self.TOTAL, self.scan(
            'msg = f"expected %s records {suffix}"\n' % self.GROUPED))

    def test_a_string_that_merely_looks_like_a_docstring_is_caught(self):
        """
        Docstrings are excluded by node identity. A string with the same text
        in an executable position is a different node and must still be read,
        or the exclusion becomes a hiding place.
        """
        text = "held %s records" % self.GROUPED
        self.assertIn(self.TOTAL, self.scan(
            'def f():\n    """%s"""\n    return assertIn("%s", page)\n'
            % (text, text)))


class TestNonPythonFilesStillReadEveryNumber(unittest.TestCase):
    """
    The AST scoping applies to Python only. A template has no docstrings and no
    comments in the Python sense — every number in one is content a reader
    sees, so the raw rule stays.
    """

    TOTAL = 3611
    GROUPED = "3,611"

    def test_a_grouped_total_in_a_template_is_caught(self):
        self.assertIn(self.TOTAL, frozen_total_literals_from(
            '<dd>%s<small>records</small></dd>\n' % self.GROUPED, ".html"))

    def test_a_grouped_total_in_a_jinja_comment_is_still_caught(self):
        """
        Deliberately NOT excluded. A Jinja comment is not executable, but it is
        also not parsed here, and a template is small enough that a number in
        one is worth a look. Erring strict on templates costs a reviewer a
        glance; erring loose costs a frozen figure on a public page.
        """
        self.assertIn(self.TOTAL, frozen_total_literals_from(
            '{# was %s records #}\n' % self.GROUPED, ".html"))

    def test_a_grouped_total_in_a_json_config_is_caught(self):
        self.assertIn(self.TOTAL, frozen_total_literals_from(
            '{"expected_records": "%s"}\n' % self.GROUPED, ".json"))

    def test_an_ungrouped_structural_number_in_a_template_is_quiet(self):
        self.assertNotIn(100, frozen_total_literals_from(
            '<span style="width: {{ (n * 100 / top) }}%"></span>\n', ".html"))


class TestTheNarrowingStillCatchesTheRealThing(unittest.TestCase):
    """
    A narrowed guard is worth nothing unless it still fires on the defect. Each
    case below is a genuinely frozen public corpus total, in the shape it
    actually appears in.
    """

    TOTAL = 3611

    def test_a_comma_grouped_total_in_a_page_assertion_is_caught(self):
        source = 'self.assertIn("%s", page)\n' % format(self.TOTAL, ",")
        self.assertIn(self.TOTAL, frozen_total_literals_from(source, ".py"))

    def test_a_comma_grouped_total_in_a_template_is_caught(self):
        markup = '<dd>%s<small>records</small></dd>\n' % format(self.TOTAL, ",")
        self.assertIn(self.TOTAL, frozen_total_literals_from(markup, ".html"))

    def test_a_bare_total_asserted_against_a_corpus_metric_is_caught(self):
        source = 'self.assertEqual(metrics.records, %d)\n' % self.TOTAL
        self.assertIn(self.TOTAL, frozen_total_literals_from(source, ".py"))

    def test_a_bare_total_assigned_to_a_corpus_name_is_caught(self):
        source = 'corpus_size = %d\n' % self.TOTAL
        self.assertIn(self.TOTAL, frozen_total_literals_from(source, ".py"))

    def test_a_frozen_analyzed_count_is_caught(self):
        source = 'self.assertEqual(analyzed_records, %d)\n' % self.TOTAL
        self.assertIn(self.TOTAL, frozen_total_literals_from(source, ".py"))

    def test_the_guard_would_have_caught_the_2026_08_24_defect(self):
        """
        The original incident: a test that froze the corpus's week count. It
        appeared as an equality against a corpus figure, which is exactly what
        rule 2 reads.
        """
        source = 'self.assertEqual(len(data["weeks"]), records)\nx = 17\n'
        self.assertIn(17, frozen_total_literals_from(
            'self.assertEqual(records, 17)\n', ".py"))
        self.assertNotIn(17, frozen_total_literals_from('x = 17\n', ".py"))


class TestTheKnownFalsePositivesAreGone(unittest.TestCase):
    """
    Every literal below is real code from this repository that the previous
    equality scan flagged, and none of them is a corpus total. If any starts
    failing again the guard has widened back into the shape that broke CI and
    would have stopped collection.

    The values 100, 123 and 365 are NOT exempted anywhere — they are ordinary
    integers here, and the guard declines to flag them because of where they
    sit, not because of what they are. A frozen total of 100, 123 or 365 in a
    corpus-metric statement is still caught, which the last case proves.
    """

    CASES = (
        ("a percentage denominator", 'width = round(week.count * 100 / volume_max, 1)\n', 100),
        ("an editorial policy cap", 'MAX_WORDS = 100\n', 100),
        ("a byte slice", 'header = self.db.read_bytes()[:100]\n', 100),
        ("a call argument cap", 'partition_refs(refs, CUTOFF, 100)\n', 100),
        ("a fixture run id", 'add_run(self.local, 100)\n', 100),
        ("a lower bound", 'self.assertGreater(len(entries), 100)\n', 100),
        ("an authority tier score", 'self.assertEqual(tier_for("gfbw"), 100)\n', 100),
        ("a lookback in days", 'window = CollectionWindow(lookback_days=365)\n', 365),
        ("a regex character class", 'headings = re.findall(r"<h[123]>(.*?)</h[123]>", html)\n', 123),
        ("a timedelta", 'cutoff = today - timedelta(days=365)\n', 365),
    )

    def test_none_of_the_real_world_literals_is_flagged(self):
        for label, source, value in self.CASES:
            with self.subTest(case=label):
                self.assertNotIn(
                    value, frozen_total_literals_from(source, ".py"),
                    "%s (%d) is being read as a frozen corpus total" % (label, value))

    def test_a_percentage_in_a_template_is_not_flagged(self):
        markup = '<span style="width: {{ (week.count * 100 / volume_max) }}%"></span>\n'
        self.assertNotIn(100, frozen_total_literals_from(markup, ".html"))

    def test_those_same_values_are_still_caught_as_corpus_totals(self):
        """The narrowing is about context, not about an exemption list."""
        for value in (100, 123, 365):
            with self.subTest(value=value):
                source = 'self.assertEqual(metrics.records, %d)\n' % value
                self.assertIn(value, frozen_total_literals_from(source, ".py"))


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
