"""Tests: docs/V91-EWIGBETRIEB-INSTALLATION-OPERATOR.md (Operator-Checkliste).

Doku-pinnende Tests: alle referenzierten Bausteine muessen real
existieren, damit die Checkliste keine Phantom-Pfade beschreibt
(DOKUMENT != BETRIEB, SCRIPTED != INSTALLED; ein referenzierter Pfad
in dieser Doku ist ein Existenversprechen gegenueber dem Betreiber).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "V91-EWIGBETRIEB-INSTALLATION-OPERATOR.md"

class EwigbetriebOperatorDocTests(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC.is_file())

    def test_referenced_os_files_exist(self):
        raw = DOC.read_text(encoding="utf-8")
        for rel in [
            "v99/os/windows/V91-Cycle-Task.xml",
            "v99/os/systemd/v91-cycle.service",
            "v99/os/systemd/v91-cycle.timer",
            "v99/os/launchd/com.v91.cycle.plist",
            "docs/V91-LOCAL-EMERGENCY-STOP.md",
        ]:
            self.assertIn(rel, raw, f"doc must reference {rel}")
            self.assertTrue((REPO_ROOT / rel).is_file(),
                            f"referenced file missing: {rel}")

    def test_honest_status_header(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("DOKUMENTIERT - NICHT INSTALLIERT", raw)
        self.assertIn("SCRIPTED != INSTALLED", raw)
        # Timer-Paradigma gepinnt (kein Dauerschleifen-Prozess)
        self.assertIn("main.py --max-cycles 1", raw)

    def test_no_running_claims(self):
        raw = DOC.read_text(encoding="utf-8").lower()
        self.assertNotIn("already running", raw)
        self.assertNotIn("laeuft bereits", raw)
        self.assertNotIn("\t", DOC.read_text(encoding="utf-8"))

    def test_fail_closed_keys_pinned(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("V91_MEASUREMENT_STORE_KEY", raw)
        self.assertIn("V91_EMERGENCY_KEY", raw)

    def test_deinstallation_is_reversible(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("Deinstallation", raw)
        self.assertIn("ISOLATE_NOT_DESTROY", raw)


if __name__ == "__main__":
    unittest.main()
