"""
Offline editorial regression tests — never calls the production model.

Two layers:

1. Hard contract checks (assertions): the summary prompt carries the
   editorial instructions the doctrine requires, the JSON schema is stable,
   and the lint catches known-bad patterns (self-test on synthetic text).

2. Archived-output report (informational): runs the lint over the eight
   representative fixtures in editorial_fixtures.json and prints findings.
   Historical text predates the current prompt and is evidence, not a
   failure; the run fails only if the fixture file itself is broken.

Run:  python3 tests/test_editorial_regression.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from editorial_lint import lint_summary  # noqa: E402

FIXTURES = ROOT / "tests" / "editorial_fixtures.json"
REQUIRED_CLASSES = {
    "operational_exercises", "political_work", "modernization",
    "taiwan_maritime_signaling", "military_diplomacy", "routine_personnel",
    "low_analytical_value", "model_flagged",
}

failures = []


def check(name, cond, detail=""):
    status = "ok " if cond else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail and not cond else ''}")
    if not cond:
        failures.append(name)


# ── 1. Prompt contract ───────────────────────────────────────────────────────
from analysis.prompts import SUMMARY_SCHEMA, build_summary_messages  # noqa: E402

msgs = build_summary_messages("TITLE_SENTINEL", "BODY_SENTINEL")
prompt = msgs[0]["content"]

check("prompt embeds title and body", "TITLE_SENTINEL" in prompt and "BODY_SENTINEL" in prompt)
check("prompt: concrete development first",
      "who did what, when, where" in prompt)
check("prompt: keeps unit designators exact", "76th Group Army" in prompt)
check("prompt: never invents Chinese text",
      "never invent, re-translate, or embellish Chinese text" in prompt)
check("prompt: bans headline restatement", "do not restate the headline" in prompt)
check("prompt: evidence vs inference",
      "Mark interpretation as interpretation" in prompt)
check("prompt: messaging not intent",
      'never "Beijing intends."' in prompt)
check("prompt: names what remains unknown",
      "what remains unknown" in prompt)
check("prompt: routine is named, not inflated",
      "not evidence of a capability shift" in prompt)
check("prompt: bans meta openers", '"This development underscores."' in prompt)
check("prompt: bans crutch verb", '"signals"' in prompt)
check("prompt: card-excerpt awareness",
      "only the opening of the summary is shown" in prompt)
check("prompt: length bound", "at most about 90 words" in prompt)
check("schema unchanged",
      SUMMARY_SCHEMA == {"type": "object",
                         "properties": {"summary": {"type": "string"}},
                         "required": ["summary"]})

# ── 2. Lint self-test on synthetic bad text ─────────────────────────────────
bad = ("The article discusses a training exercise. This signals unprecedented "
       "resolve. It is important to note the exercise. And a fourth sentence.")
found = lint_summary("Some Title", bad)
check("lint catches banned opener", any("banned opener" in f for f in found))
check("lint catches crutch construction", any("crutch" in f for f in found))
check("lint catches banned phrase", any("banned phrase" in f for f in found))
check("lint catches sentence overflow", any("sentences" in f for f in found))
check("lint passes clean text",
      lint_summary("T", "A brigade of the 76th Group Army ran an air-ground "
                        "coordination drill on 9 July. The report documents "
                        "joint-command friction the PLA has named before.") == [])
hr = lint_summary(
    "Chinese Navy Ship Formation 83 Concludes Friendly Visit To Vietnam Today",
    "Chinese navy ship formation 83 concludes friendly visit to Vietnam today "
    "after three days in Da Nang.")
check("lint catches headline restatement",
      any("restating the headline" in f for f in hr))

# ── 3. Fixture coverage + archived-output report (informational) ────────────
fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
classes = {f["fixture_class"] for f in fixtures}
check("fixture set covers all eight classes", REQUIRED_CLASSES <= classes,
      f"missing: {sorted(REQUIRED_CLASSES - classes)}")
check("fixtures carry provenance",
      all(f.get("url") and f.get("article_id") for f in fixtures))
check("exactly one model-flagged fixture",
      sum(1 for f in fixtures if f["is_significant"]) == 1)

print("\n── archived-summary lint report (informational, not a gate) ──")
for f in fixtures:
    findings = lint_summary(f.get("title_english") or "",
                            f.get("archived_summary") or "")
    tag = f["fixture_class"]
    if findings:
        print(f"  {tag}: " + "; ".join(findings))
    else:
        print(f"  {tag}: clean")

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("all contract checks passed")
