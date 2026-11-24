"""
V91-Sonden fuer die Standard-Intake-Dokumentation docs/V91-KERN-BRIDGE-INTAKE.md.

Diese Tests verriegeln die DOKUMENTIERTE Verkettung gegen das echte
Verhalten von kern_bridge und uas_record (Sonden vor Behauptung):
der Bridge-Intake und die UAS-Validierung sind getrennte Stufen.
AUFGENOMMEN != VERIFIZIERT, INTAKE != VALIDIERUNG, und eine
UAS-formgueltige Nutzlast wird von der Blocklist NICHT begnadigt
(FORM != VERHALTEN). KEINE Dopplung zu tests/test_kern_bridge.py:
dort stehen Ledger- und Gate-Basispruefungen, hier stehen die
Verkettungs-Hypothesen, die der Doku fehlten.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import kern_bridge as kb
from controller import uas_record as ur
from controller.uas_contract import _min_record


def _issue_body(body: str, number: int = 1) -> dict:
    return {"number": number, "title": "kern", "body": body}


def _wrap(text: str) -> str:
    """Echte Uebergabe-Huelle: Template-Marker um die Nutzlast."""
    return kb.HANDOVER_MARKER + "\n" + text + "\n" + kb.HANDOVER_END_MARKER


class GateConstantsTest(unittest.TestCase):
    """Die Doku-Tabelle nennt drei feste Zustaende: gegen Code verriegelt."""

    def test_documented_gate_names_exist(self):
        self.assertEqual(kb.GATE_ACCEPTED, "ACCEPTED_ISOLATED")
        self.assertEqual(kb.GATE_BLOCKED, "BLOCKED_PATTERN")
        self.assertEqual(kb.GATE_MISSING_MARKER, "MISSING_HANDOVER_MARKER")

    def test_missing_marker_beats_nothing_but_blocked_wins(self):
        self.assertEqual(kb.gate_payload("ohne marker"), kb.GATE_MISSING_MARKER)
        # Blocklist prueft VOR dem Marker (dokumentiert: BLOCKED isoliert)
        self.assertEqual(kb.gate_payload(_wrap("os.system('x')")), kb.GATE_BLOCKED)


class IntakeVsValidationTest(unittest.TestCase):
    """Sonde 1: Intake-Accept schliesst UAS-Ungueltigkeit NICHT aus."""

    def test_accepted_but_not_uas_valid(self):
        payload = _wrap("nur ein freier text, kein schema")
        self.assertEqual(kb.gate_payload(payload), kb.GATE_ACCEPTED)
        ok, errors = ur.validate_record({"schema_version": "113.0.0",
                                         "kaputt": True})
        self.assertFalse(ok)
        self.assertTrue(errors)  # INTAKE != VALIDIERUNG (belegt, nicht nur behauptet)

    def test_uas_valid_payload_also_intake_accepted(self):
        record = _min_record()
        self.assertEqual(kb.gate_payload(_wrap(json.dumps(record))),
                         kb.GATE_ACCEPTED)
        ok, _ = ur.validate_record(record)
        self.assertTrue(ok)  # beide Stufen koennEN gleichzeitig gruen sein

    def test_uas_validity_does_not_excuse_blocklist(self):
        """FORM != VERHALTEN: Schema-Konformitaet begnadigt keine Muster."""
        record = _min_record(hypothesis="os.system('x')")
        ok, _ = ur.validate_record(record)
        self.assertTrue(ok)  # Hypothese-Text ist fuer den Validator frei
        self.assertEqual(kb.gate_payload(_wrap(json.dumps(record))),
                         kb.GATE_BLOCKED)

    def test_plain_uas_without_wrap_still_validated_not_gated_in(self):
        # Ohne Marker bleibt MISSING_HANDOVER_MARKER - Dokument-Zeile 2
        record = _min_record()
        self.assertEqual(kb.gate_payload(json.dumps(record)),
                         kb.GATE_MISSING_MARKER)


class ChainProbeTest(unittest.TestCase):
    """Sonde 2: der dokumentierte Ketten-Lauf Intake -> Ledgerrille."""

    def test_full_chain_intake_dedup_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = pathlib.Path(tmp) / "inbox.jsonl"
            issues = [_issue_body(_wrap("kern alpha")), _issue_body(_wrap("kern beta"))]
            r1 = kb.collect_kerns(ledger, fetch=lambda repo, label: issues)
            self.assertEqual(r1["records_new"], 2)
            self.assertEqual(r1["gate_counts"][kb.GATE_ACCEPTED], 2)
            r2 = kb.collect_kerns(ledger, fetch=lambda repo, label: issues)
            self.assertEqual(r2["records_new"], 0)
            self.assertEqual(r2["records_known"], 2)
            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            rec = json.loads(lines[0])
            self.assertEqual(rec["gate_status"], kb.GATE_ACCEPTED)
            self.assertEqual(rec["sha256"],
                             hashlib.sha256(_wrap("kern alpha").encode()).hexdigest())

    def test_honesty_limits_travel_with_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = pathlib.Path(tmp) / "inbox.jsonl"
            r = kb.collect_kerns(ledger, fetch=lambda repo, label: [])
            self.assertIn("AUFGENOMMEN != VERIFIZIERT",
                          r["honesty_limits"])


if __name__ == "__main__":
    unittest.main()
