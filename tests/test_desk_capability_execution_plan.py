"""No-network validation of cross-desk ROADMAP, never actual desk readiness."""
from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.validate_desk_capability_plan import (
    ROOT, DEFAULT_PLAN, DEFAULT_BINDINGS, DEFAULT_REGISTRY,
    PlanInvalid, main, validate,
)


class DeskCapabilityPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(DEFAULT_PLAN.read_text(encoding="utf-8"))
        cls.bindings = json.loads(DEFAULT_BINDINGS.read_text(encoding="utf-8"))
        cls.registry = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))

    def case(self):
        return copy.deepcopy(self.plan)

    def test_actual_sources_and_registry_reconcile_without_acting(self):
        report = validate(self.case(), bindings=self.bindings, registry=self.registry)
        self.assertEqual(report["state"], "structure_valid_only_not_operational_evidence")
        self.assertGreaterEqual(report["work_packages"], 15)
        self.assertEqual(sum(report["wave_counts"].values()), report["work_packages"])
        self.assertEqual(len(report["topological_order"]), report["work_packages"])
        self.assertIn("VN-01", report["topological_order"])
        self.assertIn("JP-01", report["topological_order"])
        self.assertIn("KR-01", report["topological_order"])
        self.assertLess(report["topological_order"].index("VN-01"),
                        report["topological_order"].index("VN-06"))
        for key in ("execution_permitted", "source_admission_permitted",
                    "desk_promotion_permitted", "publishing_permitted"):
            self.assertIs(report[key], False)
        self.assertNotIn("ready_for_production", str(report).lower())

    def test_every_task_is_a_plan_not_a_fake_review(self):
        plan = self.case()
        self.assertTrue(all(x["status"] == "planned_not_verified" for x in plan["tasks"]))
        self.assertTrue(all(x["executable_effect"] == "none" for x in plan["tasks"]))
        self.assertEqual({x["scope"] for x in plan["tasks"]},
                         {"regional", "vietnam", "japan", "korea"})
        self.assertTrue(all(x["human_decision_required"] for x in plan["tasks"]
                            if x["gate"] in ("qualify", "decide", "verify")))
        self.assertIsNone(next(x for x in plan["tasks"]
                               if x["scope"] == "korea")["registry_desk"])
        self.assertNotIn("korea", {x["slug"] for x in self.registry["desks"]})

    def test_invalid_dependencies_cycles_and_wrong_wave_refused(self):
        for mutation in ("unknown", "cycle", "self", "future", "duplicate"):
            p = self.case()
            nodes = {x["id"]: x for x in p["tasks"]}
            if mutation == "unknown":
                nodes["VN-07"]["dependencies"].append("VN-99")
            elif mutation == "cycle":
                nodes["REG-01"]["dependencies"].append("VN-07")
            elif mutation == "self":
                nodes["VN-01"]["dependencies"].append("VN-01")
            elif mutation == "future":
                nodes["REG-01"]["dependencies"].append("KR-01")
            else:
                nodes["VN-01"]["dependencies"].append("REG-01")
            with self.subTest(mutation=mutation), self.assertRaises(PlanInvalid):
                validate(p, bindings=self.bindings, registry=self.registry)

    def test_no_fake_approval_promotion_or_source_registration(self):
        cases = (
            ("status", "qualified"),
            ("executable_effect", "enable_collector"),
            ("human_decision_required", False),
            ("gate", "activated"),
            ("registry_desk", "vietnam"),
        )
        for key, value in cases:
            p = self.case()
            subject = next(x for x in p["tasks"] if x["id"] == "KR-03")
            subject[key] = value
            with self.subTest(key=key), self.assertRaises(PlanInvalid):
                validate(p, bindings=self.bindings, registry=self.registry)

        for field, value in [
            ("declared_source_slugs", ["vn_mod_invented"]),
            ("declared_source_slugs", ["jp_mod_news_ja"]),
            ("proposed_source_families", ["vn_mps_foreign_affairs_vi"]),
            ("proposed_source_families", ["https://bad.example/a"]),
        ]:
            p = self.case()
            next(x for x in p["tasks"] if x["id"] == "VN-05")[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PlanInvalid):
                validate(p, bindings=self.bindings, registry=self.registry)

    def test_no_missing_issue_or_underdescribed_exit(self):
        for key, value in [
            ("issue", 0), ("acceptance", "ship it"),
            ("stop_if", "looks fine"), ("wave", 200),
            ("dependencies", "REG-01"),
        ]:
            p = self.case()
            next(x for x in p["tasks"] if x["id"] == "VN-01")[key] = value
            with self.subTest(key=key), self.assertRaises(PlanInvalid):
                validate(p, bindings=self.bindings, registry=self.registry)

    def test_registry_source_map_is_not_reinvented(self):
        bad_binding = copy.deepcopy(self.bindings)
        bad_binding["sources"].append(copy.deepcopy(bad_binding["sources"][0]))
        with self.assertRaises(PlanInvalid):
            validate(self.case(), bindings=bad_binding, registry=self.registry)
        missing = copy.deepcopy(self.registry)
        missing["desks"] = [x for x in missing["desks"] if x["slug"] != "vietnam"]
        with self.assertRaises(PlanInvalid):
            validate(self.case(), bindings=self.bindings, registry=missing)

    def test_cli_returns_planning_only_and_writes_no_output(self):
        refs = (ROOT / "pla_watch.db", ROOT / "desks/registry.json",
                ROOT / "config/shadow_source_workflow_bindings.json")
        before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
                  for p in refs if p.exists()}
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["--json"]), 0)
        report = json.loads(buffer.getvalue())
        self.assertFalse(report["execution_permitted"])
        self.assertFalse(report["publishing_permitted"])
        after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
                 for p in refs if p.exists()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
