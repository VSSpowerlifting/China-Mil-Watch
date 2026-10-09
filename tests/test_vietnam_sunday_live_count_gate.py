"""Execute the real Sunday source-count gate without a model, SMTP or publisher."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
SAT = "2026-10-10"


def gate_source():
    """Extract the same inline Python used in the Sunday job (not a copy)."""
    source = WORKFLOW.read_text(encoding="utf-8")
    start = source.index("- name: Verify refreshed exact-week research before the model call")
    end = source.index("- name: Create read-only full Saturday-ending week source scaffold", start)
    step = source[start:end]
    block = step.split("          python - <<'PY'\n", 1)[1]
    block = block.split("\n          PY\n", 1)[0]
    return textwrap.dedent(block) + "\n"


def offered_packet(root, saturday=SAT, *, malformed=False):
    if saturday == SAT:
        source = ROOT / "research/briefs_editorial_evidence" / (SAT + ".json")
        raw = source.read_bytes()
        data = json.loads(raw.decode())
        number = sum(x["desk"] == "vietnam" for x in data["items"])
    else:
        data = {
            "schema": "ipr-private-drafting-evidence/1",
            "week_ending": saturday,
            "status": "unapproved-source-linked-editorial-candidate",
            "items": [],
        }
        raw = (json.dumps(data, ensure_ascii=False) + "\n").encode()
        number = 0
    if malformed:
        raw = b'{"schema":"forged-approved-source"}\n'
    file = root / (saturday + ".json")
    file.write_bytes(raw)
    return file, number


def execute_gate(file, saturday, ready, eligible):
    env = os.environ.copy()
    env.update({
        "IPR_SUNDAY_WEEK_END": saturday,
        "IPR_SUNDAY_AS_OF": saturday,
        "PRIVATE_WEEK_PACKET": str(file),
        "PRIVATE_VN_COUNT": str(ready),
        "PRIVATE_VN_MACHINE_ELIGIBLE": str(eligible),
    })
    return subprocess.run(
        [sys.executable, "-c", gate_source()],
        cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=20, check=False,
    )


class SundayCurrentMPSCountGate(unittest.TestCase):
    def test_october_pilot_uses_real_fixture_and_accepts_exact_parity(self):
        with tempfile.TemporaryDirectory() as folder:
            path, source_count = offered_packet(Path(folder))
            self.assertGreaterEqual(source_count, 2)
            before = hashlib.sha256(path.read_bytes()).digest()
            result = execute_gate(path, SAT, source_count, source_count)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Source-audited private research roster:", result.stdout)
            self.assertIn(str(source_count) + " Vietnam items", result.stdout)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).digest())

    def test_newly_archived_eligible_mps_record_stops_model_and_mail(self):
        with tempfile.TemporaryDirectory() as folder:
            path, current = offered_packet(Path(folder))
            result = execute_gate(path, SAT, current, current + 1)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("strict pilot must account for all in-window MPS sources",
                          result.stderr)

    def test_refuses_packet_and_archived_counts_that_disagree(self):
        with tempfile.TemporaryDirectory() as folder:
            path, current = offered_packet(Path(folder))
            for ready, eligible in ((current - 1, current), (current, -1),
                                    (current, current - 1), ("abc", current)):
                with self.subTest(ready=ready, eligible=eligible):
                    result = execute_gate(path, SAT, ready, eligible)
                    self.assertNotEqual(result.returncode, 0)

    def test_future_week_can_omit_unprepared_mps_with_explicit_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            week = "2026-10-17"
            path, count = offered_packet(Path(folder), week)
            self.assertEqual(count, 0)
            result = execute_gate(path, week, 0, 3)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("3 verified MPS sources currently lack", result.stdout)
            self.assertIn("omission is NOT official silence", result.stdout)
            empty = execute_gate(path, week, 0, 0)
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertNotIn("::warning::", empty.stdout)

    def test_malformed_packet_and_wrong_week_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good, number = offered_packet(root)
            result = execute_gate(good, "2026-10-17", number, number)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing or wrong-week", result.stderr)
            broken, _ = offered_packet(root, malformed=True)
            result = execute_gate(broken, SAT, number, number)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown evidence packet fields", result.stderr)

    def test_actual_embedded_gate_has_no_network_model_or_mail(self):
        source = gate_source()
        for forbidden in ("anthropic", "smtplib", "requests", "urllib.request",
                          "git push", "openai", "subprocess", "send_packet("):
            self.assertNotIn(forbidden, source)
        self.assertIn("eligible != vn", source)
        self.assertIn("load_editorial_evidence", source)


if __name__ == "__main__":
    unittest.main()
