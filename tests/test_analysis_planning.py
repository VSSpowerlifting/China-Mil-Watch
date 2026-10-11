"""Differential selection against the pre-extraction Daily algorithm."""
from dataclasses import replace
from datetime import datetime, timezone
import random
import unittest

from core.analysis_plan import Candidate, Policy, build_plan, revalidate


def candidate(i, lane="unscored", **kw):
    values = dict(record_id=i, source_slug="fictional", desk_id="china",
                  url="https://fictional.invalid/%d" % i, lane=lane,
                  title="FICTIONAL fixture", body="FICTIONAL source text",
                  scraped_at="2026-10-10 00:00:00")
    values.update(kw)
    return Candidate(**values)


class PlannerTests(unittest.TestCase):
    def plan(self, rows, policy=None):
        return build_plan(rows, policy or Policy("2026-10-11T00:00:00Z"),
                          code_identity="code", pricing_identity="prices")

    def test_legacy_differential_order_rounding_cutoff_spillover(self):
        rng = random.Random(268)
        for _ in range(90):
            cap, reserve = rng.randint(1, 55), rng.choice([0, .1, .3, .5, 1])
            rows = []
            for lane in ("new", "pending", "unscored"):
                for j in range(rng.randint(0, 70)):
                    rows.append(candidate(len(rows) + 1, lane,
                                          scraped_at=rng.choice([None, "2026-09-26", "2026-09-27"]),
                                          body=rng.choice(["FICTIONAL body", "\u2003\n\t"])))
            new = [r for r in rows if r.lane == "new" and r.body.strip()]
            pending = [r for r in rows if r.lane == "pending" and r.body.strip()]
            unscored = [r for r in rows if r.lane == "unscored" and r.body.strip()]
            live = [r for r in unscored if (r.scraped_at or "")[:10] >= "2026-09-27"]
            archive = [r for r in unscored if (r.scraped_at or "")[:10] < "2026-09-27"]
            backlog = pending + live + archive
            slots = min(len(backlog), max(1, round(cap * reserve))) if backlog else 0
            nt = new[:cap - slots]
            expected = nt + backlog[:cap - len(nt)]
            p = self.plan(rows, Policy("2026-10-11T00:00:00Z", cap, reserve))
            self.assertEqual(p["selected_ids"], [r.record_id for r in expected])
            self.assertEqual(p["counts"]["stored"], p["counts"]["eligible"] + p["counts"]["held"])

    def test_holds_do_not_consume_slots_and_reports_exclude_text(self):
        rows = [candidate(1, desk_id="singapore"), candidate(2, body="\u2003"),
                candidate(3, processing_state="paused"), candidate(4, processing_state="terminal"),
                candidate(5, analyzed_at="2026-10-01"), candidate(6, passed_relevance=0), candidate(7)]
        p = self.plan(rows)
        self.assertEqual(p["selected_ids"], [7])
        self.assertEqual(p["counts"]["held"], 6)
        self.assertNotIn("FICTIONAL source text", str(p))
        self.assertNotIn("https://", str(p))

    def test_age_policy_only_reorders_backlog_at_equal_cap(self):
        rows = [candidate(1, "new"), candidate(2, "pending"),
                candidate(3, scraped_at="2026-01-01"), candidate(4, scraped_at=None)]
        p = Policy("2026-10-11T00:00:00Z", cap=2)
        self.assertEqual(self.plan(rows, p)["selected_ids"], [1, 2])
        self.assertEqual(self.plan(rows, replace(p, mode="age-aware"))["selected_ids"], [1, 3])

    def test_duplicate_missing_identity_and_stale_state_refused(self):
        c = candidate(1)
        for rows in ([c, c], [replace(c, source_slug="")], [replace(c, lane="stored")]):
            with self.assertRaises(ValueError): self.plan(rows)
        p = Policy("2026-10-11T00:00:00Z")
        plan = self.plan([c], p)
        for changed in (replace(c, body="changed"), replace(c, attempts=1), replace(c, desk_id="singapore")):
            with self.assertRaises(ValueError):
                revalidate(plan, [changed], p, code_identity="code", pricing_identity="prices")

    def test_injected_time_prices_and_config_bind_identity(self):
        c = candidate(1)
        p = Policy("2026-10-11T00:00:00Z")
        original = self.plan([c], p)
        self.assertEqual(original, self.plan([c], p))
        self.assertNotEqual(original["plan_id"], self.plan([c], replace(p, cap=54))["plan_id"])
        with self.assertRaises(ValueError): self.plan([c], replace(p, evaluated_at="2026-10-11"))
