"""Tests: docs/V91-IDENTITAET-VERANTWORTUNG-KODEX.md (Identitaet = Verantwortung).

Doku-pinnende Tests: Der Kodex ordnet jeden Grundsatz einem REAL existierenden
Modul zu (ein abgebildetes Modul ist ein Existenzversprechen gegenueber dem
Betreiber). Ehrlichkeit ist selbst gepinnt: Kopf, Wurzelregel, NICHT_KODIERT-
Eintrag, keine Tabs, ASCII-pure.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "V91-IDENTITAET-VERANTWORTUNG-KODEX.md"

GRUNDSAETZE = [
    "Wahrhaftigkeit",
    "Verantwortung",
    "Dankbarkeit",
    "Demut",
    "Schutz",
    "Hilfsbereitschaft",
    "Selbstbestimmung",
    "Verlaesslichkeit",
    "Gerechtigkeit",
    "Besonnenheit",
]

MODULES = [
    "controller/node_identity.py",
    "controller/agent_quorum.py",
    "controller/quorum_decision.py",
    "controller/decision_dossier.py",
    "controller/governance_gate.py",
    "controller/quorum_ledger.py",
    "controller/fiction_scan.py",
    "controller/enforcement.py",
    "controller/emergency_stop.py",
    "controller/person_dignity_gate.py",
    "controller/support_consent_gate.py",
    "controller/update_gate.py",
    "controller/ledger.py",
]


class IdentitaetVerantwortungKodexTests(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC.is_file())

    def test_all_ten_principles_present(self):
        raw = DOC.read_text(encoding="utf-8")
        for g in GRUNDSAETZE:
            self.assertIn(g, raw, f"Grundsatz fehlt: {g}")

    def test_mapped_modules_exist(self):
        raw = DOC.read_text(encoding="utf-8")
        for rel in MODULES:
            self.assertIn(rel, raw, f"Kodex muss {rel} abbilden")
            self.assertTrue((REPO_ROOT / rel).is_file(),
                            f"abgebildetes Modul fehlt: {rel}")

    def test_honesty_rules_pinned(self):
        raw = DOC.read_text(encoding="utf-8")
        for needle in [
            "KODEX != IMPLEMENTATION",
            "CLAIM != EVIDENCE",
            "SIGNATUR != WAHRHEIT",
            "NICHT_KODIERT",
            "KEINE TOETUNG",
            "SCRIPTED != INSTALLED",
            "MATRIZ != WIRKUNG",
        ]:
            self.assertIn(needle, raw)

    def test_rejected_human_impact_pinned(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertIn("REJECTED_HUMAN_IMPACT", raw)
        self.assertIn("human_impact >= 0.5", raw)

    def test_ascii_pure_no_tabs(self):
        raw = DOC.read_text(encoding="utf-8")
        self.assertNotIn("\t", raw)
        for ch in raw:
            self.assertLess(ord(ch), 128, f"non-ascii char {ch!r}")


if __name__ == "__main__":
    unittest.main()
