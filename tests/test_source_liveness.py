"""
The health gate's exemption list must not shelter a source that is still alive.

Background (2026-09-20). `xinhua_mil` was listed in
`scripts/check_source_liveness.py:KNOWN_INERT` with the reason "documented stub
— listing page requires JS rendering; returns [] by design". That was true when
it was written. PR #56 replaced the stub with a real server-rendered collector,
and by 2026-09-20 the source was discovering, fetching and extracting on every
daily run. The exemption stayed behind.

An entry in KNOWN_INERT is not cosmetic: `classify()` returns INERT before any
threshold is consulted, so an exempted source can never be UNHEALTHY. A
producing source left in that list is precisely the blindness the gate was
built to remove — Xinhua could have gone dark for a month and the run would
still have printed "All non-inert sources are producing."

Stale exemptions are quiet by nature; nobody re-reads a list that never fires.
So this file re-derives the claim from the tracked corpus on every run: any
source still producing inside its own silence threshold must not be classified
INERT, whatever the list says.

Offline. The tracked database is read through `reconcile_db.read_only`, which
copies it to scratch, so nothing here touches the tracked file or the network.
"""

from __future__ import annotations

import sys
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import check_source_liveness as liveness            # noqa: E402

TRACKED = REPO_ROOT / "pla_watch.db"


def as_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


class ProducingSourcesAreNeverExempt(unittest.TestCase):
    """The regression: a live source must be gated like every other one."""

    def setUp(self):
        if not TRACKED.exists():
            self.skipTest("tracked database not present")
        self.rows = [r for r in liveness.rows(TRACKED, None)]
        if not self.rows:
            self.skipTest("no active sources in the tracked database")

    def corpus_high_water_mark(self):
        """The newest collection date in the corpus, used as 'today'.

        Anchoring to the corpus rather than to the wall clock keeps this test
        meaningful as the committed database ages: `date.today()` would drift
        past every threshold and quietly stop asserting anything.
        """
        seen = [as_date(r[3]) for r in self.rows if r[3]]
        if not seen:
            self.skipTest("no collected articles in the tracked database")
        return max(seen)

    def test_no_source_producing_within_its_threshold_is_inert(self):
        today = self.corpus_high_water_mark()

        for slug, name, total, last_seen in self.rows:
            if not total or last_seen is None:
                continue
            threshold = liveness.SILENCE_THRESHOLD_DAYS.get(
                slug, liveness.DEFAULT_MAX_SILENT_DAYS
            )
            days_silent = (today - as_date(last_seen)).days
            if days_silent > threshold:
                continue                      # genuinely quiet; not our subject

            state, _days, detail = liveness.classify(
                slug, total, last_seen, today, liveness.DEFAULT_MAX_SILENT_DAYS
            )
            self.assertNotEqual(
                state, "INERT",
                f"{slug} ({name}) is producing — {total} article(s), most "
                f"recent {last_seen}, {days_silent}d before the corpus's own "
                f"{today} — yet the gate exempts it from every recency "
                f"threshold: {detail!r}. Remove it from KNOWN_INERT in "
                f"scripts/check_source_liveness.py; a live source has to be "
                f"checked like any other, or its death goes unnoticed.",
            )

    def test_xinhua_mil_is_not_marked_inert(self):
        """The specific entry this file was written for."""
        self.assertNotIn("xinhua_mil", liveness.KNOWN_INERT)

    def test_xinhua_mil_has_actually_produced_articles(self):
        """Keeps the assertion above honest rather than vacuous.

        If Xinhua ever stops appearing in the corpus, this fails and someone
        decides deliberately — repair the adapter, or document the silence —
        instead of the exemption drifting back in unexamined.
        """
        row = next((r for r in self.rows if r[0] == "xinhua_mil"), None)
        self.assertIsNotNone(
            row, "xinhua_mil is not an active source in the tracked database")
        self.assertGreater(
            row[2], 0,
            "xinhua_mil is active but has collected nothing; the liveness gate "
            "should now be reporting it UNHEALTHY rather than INERT")


class ExemptionMechanismStillWorks(unittest.TestCase):
    """KNOWN_INERT is empty today, so pin the behaviour it is meant to have.

    Without this, a refactor could break INERT entirely and no test would
    notice — and the next genuinely inert source would be reported UNHEALTHY
    forever, which is how a gate gets switched off.
    """

    def test_a_listed_slug_is_reported_inert_with_its_reason(self):
        reason = "documented: upstream retired the section, tracked in ISSUE-1"
        with unittest.mock.patch.dict(
            liveness.KNOWN_INERT, {"some_source": reason}, clear=False
        ):
            state, days, detail = liveness.classify(
                "some_source", 0, None, as_date("2026-09-20"), 7)
        self.assertEqual(state, "INERT")
        self.assertIsNone(days)
        self.assertEqual(detail, reason)

    def test_an_unlisted_silent_source_is_unhealthy(self):
        state, days, _detail = liveness.classify(
            "some_source", 12, "2026-08-01", as_date("2026-09-20"), 7)
        self.assertEqual(state, "UNHEALTHY")
        self.assertEqual(days, 50)


if __name__ == "__main__":
    unittest.main()
