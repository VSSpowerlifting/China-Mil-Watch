"""
Source-liveness expectations must be derived, not hand-maintained.

The defect (2026-09-20). Xinhua Military was rewritten from a stub into a
working adapter on 2026-09-16 and delivered four new articles in the
2026-09-20 daily run. `scripts/check_source_liveness.py` still listed it in a
hand-maintained `KNOWN_INERT` dictionary whose stated reason — "returns [] by
design" — had been false for four days. INERT sources are exempt from every
recency threshold, so the one gate that exists to notice a source dying was
structurally blind to this one. Nothing failed; that is the point.

The repair is not a corrected list. It is the removal of the list: whether a
source may be silent now comes from the adapter's own offline `healthcheck()`
(NOT_IMPLEMENTED for a class declaring `IS_STUB`, SKIPPED_DISABLED for one the
manifest disables) and how long it may be silent comes from the manifest's
`silence_threshold_days`. Both already existed and were already correct about
Xinhua while the script's copy was wrong.

Offline: no network, no model calls. The live-corpus tests open the tracked
database read-only through `scripts.reconcile_db.read_only`, which copies.
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import SourceHealthResult         # noqa: E402
from core.registry import get_registry                          # noqa: E402
import scripts.check_source_liveness as liveness                # noqa: E402

TODAY = date(2026, 9, 20)


class FakeSource:
    def __init__(self, slug, silence_threshold_days=None, enabled=True):
        self.slug = slug
        self.silence_threshold_days = silence_threshold_days
        self.enabled = enabled


class FakeRegistry:
    """Just enough registry to drive `expectations()` without importing
    adapters or reading manifests."""

    def __init__(self, results, sources):
        self._results = results
        self._sources = {s.slug: s for s in sources}

    def healthcheck_all(self):
        return self._results

    def get_source(self, slug):
        return self._sources.get(slug)


def expectation_for(slug, status, detail=None, threshold=None):
    reg = FakeRegistry(
        [SourceHealthResult(slug, status, detail)],
        [FakeSource(slug, silence_threshold_days=threshold)],
    )
    return liveness.expectations(reg)[slug]


# ── The list is gone ──────────────────────────────────────────────────────────

class TheHandMaintainedListsAreGone(unittest.TestCase):

    def test_known_inert_no_longer_exists(self):
        """A second copy of a fact is a second chance to be wrong about it."""
        self.assertFalse(
            hasattr(liveness, "KNOWN_INERT"),
            "KNOWN_INERT is back. Inertness is declared by IS_STUB on the "
            "adapter and by `enabled` in the desk manifest; a source must not "
            "be exemptable by being named in this script.",
        )

    def test_hardcoded_threshold_table_no_longer_exists(self):
        self.assertFalse(
            hasattr(liveness, "SILENCE_THRESHOLD_DAYS"),
            "SILENCE_THRESHOLD_DAYS is back. Thresholds belong to the desk "
            "manifest, which core.collection.health already reads.",
        )

    def test_the_script_names_no_source_slug(self):
        """No per-source special case may be reintroduced as a literal."""
        source = (REPO_ROOT / "scripts" / "check_source_liveness.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        slugs = set(get_registry().slugs)
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        # Docstrings explain the history, so only executable code is scanned.
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        offenders = sorted((literals - docstrings) & slugs)
        self.assertEqual(
            [], offenders,
            "check_source_liveness.py special-cases %s by name" % offenders,
        )


# ── Xinhua specifically ───────────────────────────────────────────────────────

class XinhuaIsAWorkingSource(unittest.TestCase):

    def test_the_adapter_does_not_declare_itself_a_stub(self):
        from scraper.sources.xinhua_mil import XinhuaMilScraper
        self.assertFalse(getattr(XinhuaMilScraper, "IS_STUB", False))

    def test_the_registry_healthcheck_reports_it_collectible(self):
        result = next(
            r for r in get_registry().healthcheck_all()
            if r.source_slug == "xinhua_mil"
        )
        self.assertNotEqual(st.NOT_IMPLEMENTED, result.status)
        self.assertFalse(st.is_failure(result.status))

    def test_derived_expectation_is_not_inert(self):
        expected = liveness.expectations()["xinhua_mil"]
        self.assertFalse(expected.inert)
        self.assertFalse(expected.broken)

    def test_a_recent_result_passes(self):
        """The 2026-09-20 shape: collected on the day the run covers."""
        state, days, detail = liveness.classify(
            "xinhua_mil", 1, TODAY.isoformat(), TODAY, 7,
            liveness.expectations()["xinhua_mil"],
        )
        self.assertEqual("HEALTHY", state)
        self.assertEqual(0, days)
        self.assertIn("threshold", detail)

    def test_unexplained_silence_is_now_unhealthy(self):
        """Before the repair this returned INERT for any date at all."""
        silent_for = liveness.expectations()["xinhua_mil"].threshold + 1
        last_seen = date.fromordinal(TODAY.toordinal() - silent_for)
        state, days, _ = liveness.classify(
            "xinhua_mil", 1, last_seen.isoformat(), TODAY, 7,
            liveness.expectations()["xinhua_mil"],
        )
        self.assertEqual("UNHEALTHY", state)
        self.assertEqual(silent_for, days)

    def test_it_is_judged_by_the_same_standard_as_its_peers(self):
        """Same corpus shape, same verdict, for every implemented China source."""
        expected = liveness.expectations()
        peers = [s for s in get_registry().slugs_for_desk("china")
                 if not expected[s].inert and not expected[s].broken]
        self.assertIn("xinhua_mil", peers)

        verdicts = set()
        for slug in peers:
            silent_for = (expected[slug].threshold or 7) + 1
            last_seen = date.fromordinal(TODAY.toordinal() - silent_for)
            state, days, _ = liveness.classify(
                slug, 1, last_seen.isoformat(), TODAY, 7, expected[slug],
            )
            self.assertEqual(silent_for, days)
            verdicts.add(state)
        self.assertEqual({"UNHEALTHY"}, verdicts)


# ── Declared stubs still work ─────────────────────────────────────────────────

class DeclaredStubsAreStillExempt(unittest.TestCase):

    def test_a_not_implemented_adapter_is_inert(self):
        expected = expectation_for("someday_mil", st.NOT_IMPLEMENTED,
                                   "documented stub — no working path")
        self.assertTrue(expected.inert)
        state, days, detail = liveness.classify(
            "someday_mil", 0, None, TODAY, 7, expected)
        self.assertEqual("INERT", state)
        self.assertIsNone(days)
        self.assertIn("stub", detail)

    def test_a_manifest_disabled_source_is_inert(self):
        expected = expectation_for("paused_mil", st.SKIPPED_DISABLED,
                                   "disabled in desk manifest")
        self.assertTrue(expected.inert)
        state, _, detail = liveness.classify(
            "paused_mil", 0, None, TODAY, 7, expected)
        self.assertEqual("INERT", state)
        self.assertIn("disabled", detail)

    def test_an_inert_source_never_fails_the_gate(self):
        expected = expectation_for("someday_mil", st.NOT_IMPLEMENTED)
        state, _, _ = liveness.classify(
            "someday_mil", 0, None, TODAY, 7, expected)
        self.assertNotEqual("UNHEALTHY", state)

    def test_an_unimportable_adapter_is_unhealthy_not_inert(self):
        """The dangerous middle case: broken looks exactly like quiet."""
        expected = expectation_for("broken_mil", st.ADAPTER_ERROR,
                                   "No module named 'scraper.sources.gone'")
        self.assertFalse(expected.inert)
        self.assertTrue(expected.broken)
        state, _, detail = liveness.classify(
            "broken_mil", 900, TODAY.isoformat(), TODAY, 7, expected)
        self.assertEqual(
            "UNHEALTHY", state,
            "a source whose adapter will not import reported HEALTHY because "
            "yesterday's corpus was still warm",
        )
        self.assertIn("adapter unusable", detail)

    def test_an_undeclared_slug_is_not_exempt(self):
        """A source configuration has forgotten is still expected to produce."""
        self.assertFalse(liveness.UNDECLARED.inert)
        state, _, _ = liveness.classify(
            "orphan_mil", 0, None, TODAY, 7, liveness.UNDECLARED)
        self.assertEqual("UNHEALTHY", state)


# ── Thresholds come from the manifest ─────────────────────────────────────────

class ThresholdsComeFromTheManifest(unittest.TestCase):

    def manifest_sources(self):
        data = json.loads(
            (REPO_ROOT / "desks" / "china" / "manifest.json").read_text(
                encoding="utf-8")
        )
        return {s["slug"]: s for s in data["sources"]}

    def test_every_derived_threshold_matches_its_manifest(self):
        declared = self.manifest_sources()
        expected = liveness.expectations()
        checked = 0
        for slug, entry in declared.items():
            self.assertEqual(
                entry.get("silence_threshold_days"), expected[slug].threshold,
                "threshold for %s diverged from its manifest" % slug,
            )
            checked += 1
        self.assertEqual(len(declared), checked)

    def test_a_manifest_threshold_is_honoured_over_the_flag(self):
        expected = expectation_for("slow_mil", st.OK, threshold=21)
        state, _, detail = liveness.classify(
            "slow_mil", 10, "2026-09-05", TODAY, 7, expected)
        self.assertEqual("HEALTHY", state)          # 15d < 21d
        self.assertIn("threshold 21d", detail)

    def test_no_manifest_threshold_falls_back_to_the_flag(self):
        expected = expectation_for("plain_mil", st.OK, threshold=None)
        state, _, detail = liveness.classify(
            "plain_mil", 10, "2026-09-05", TODAY, 7, expected)
        self.assertEqual("UNHEALTHY", state)        # 15d > 7d
        self.assertIn("threshold 7d", detail)


# ── Against the live corpus ───────────────────────────────────────────────────

class TheLiveCorpusAgrees(unittest.TestCase):
    """Properties over the tracked database. Nothing here pins a count."""

    @classmethod
    def setUpClass(cls):
        cls.db = liveness.DEFAULT_DB
        if not cls.db.exists():
            raise unittest.SkipTest("tracked database not present")
        cls.rows = liveness.rows(cls.db, date.today())
        cls.expected = liveness.expectations()

    def test_no_producing_source_is_classified_inert(self):
        """The invariant the Xinhua defect violated for four days."""
        for slug, name, total, last_seen in self.rows:
            state, _, _ = liveness.classify(
                slug, total, last_seen, date.today(), 7,
                self.expected.get(slug, liveness.UNDECLARED),
            )
            if state == "INERT":
                self.assertEqual(
                    0, total,
                    "%s is classified INERT while holding articles" % name,
                )

    def test_every_live_source_is_judged(self):
        for slug, name, total, last_seen in self.rows:
            state, _, _ = liveness.classify(
                slug, total, last_seen, date.today(), 7,
                self.expected.get(slug, liveness.UNDECLARED),
            )
            self.assertIn(state, {"HEALTHY", "UNHEALTHY", "INERT"})

    def test_no_moving_corpus_count_is_frozen_in_this_file(self):
        """Guard against pinning a total that grows every day.

        A literal is suspicious when it equals a live per-source total or the
        grand total AND is not a value configuration declares (a threshold or a
        cadence), which is how 7 and 21 stay legal.
        """
        totals = {total for _slug, _name, total, _seen in self.rows}
        totals.add(sum(total for _s, _n, total, _x in self.rows))
        configured = set()
        for slug in get_registry().slugs:
            src = get_registry().get_source(slug)
            for attr in ("silence_threshold_days", "expected_cadence_days"):
                value = getattr(src, attr, None)
                if value is not None:
                    configured.add(value)

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }
        frozen = sorted((literals & totals) - configured)
        self.assertEqual(
            [], frozen,
            "these test literals equal a live corpus total and will rot: %s"
            % frozen,
        )


if __name__ == "__main__":
    unittest.main()
