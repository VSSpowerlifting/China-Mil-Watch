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


class FrozenCountCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.figures = moving_figures()

    def assert_no_frozen_figure(self, path: Path):
        present = literals(path.read_text(encoding="utf-8"))
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
        """A guard measuring nothing passes for the wrong reason."""
        self.assertTrue(self.figures)
        self.assertIn("stored records", self.figures)
        self.assertGreaterEqual(self.figures["stored records"], FLOOR)


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
