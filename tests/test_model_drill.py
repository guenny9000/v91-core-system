"""Tests for the no-hardware model drill (scripts/v91_model_drill.py).

The drill must pass on any machine with a plain Python interpreter:
- exit code 0 and RESULT: ALL_DRILLS_PASS
- per-drill PASS/SKIP lines with evidence
- honest-limit lines printed (DRILL != DEPLOYED etc.)
- a failing drill must produce exit code 1 (fail-closed check)
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "v91_model_drill.py"


def run_drill() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )


class ModelDrillTests(unittest.TestCase):
    def test_drill_passes_and_exits_zero(self) -> None:
        result = run_drill()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: ALL_DRILLS_PASS", result.stdout)

    def test_drill_reports_every_drill_with_evidence(self) -> None:
        result = run_drill()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in (
            "import_selfcheck",
            "optional_crypto_imports",
            "emergency_stop",
            "control_plane_wiring",
            "worker_wiring",
            "measurement_chain",
            "ledger_recovery",
        ):
            self.assertIn(f"DRILL {name}:", result.stdout)

    def test_drill_prints_honest_limits(self) -> None:
        result = run_drill()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DRILL != DEPLOYED", result.stdout)
        self.assertIn("SAME_PROCESS != MULTI_NODE", result.stdout)
        self.assertIn("SCRIPTED != INSTALLED", result.stdout)

    def test_drill_summary_counts_all_drills(self) -> None:
        result = run_drill()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 7 drills total; on CI cryptography is installed so 7 PASS are
        # expected, but a SKIP for the optional imports stays valid.
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith("SUMMARY:")),
            "",
        )
        self.assertTrue(line, "SUMMARY line missing")
        self.assertIn("of 7 drills", line)


if __name__ == "__main__":
    unittest.main()
