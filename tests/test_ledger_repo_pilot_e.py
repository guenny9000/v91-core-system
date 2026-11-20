"""Integrationstest: erster realer Messwert-Ledger (R3) fuer Pilot E.

Der Ledger enthaelt zwei dokumentierte amtliche Beobachtungen. OBSERVED ist
nicht ERFOLG: Der WIRKUNG-Wert entspricht der dokumentierten Baseline,
Fortschritt 0. SIGNATUR != WAHRHEIT; das Assessment prueft Struktur,
nicht die Wahrheit der Quelle. UNKNOWN bleibt UNKNOWN.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from controller.messwerte_ingest import (  # noqa: E402
    MesswertLedger,
    load_dataset,
)
from controller.wirkungs_assessment import assess  # noqa: E402
from controller.wirkungs_index import build_index  # noqa: E402

DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-e-ukraine-friedenssicherung-2026.json"
LEDGER_PATH = REPO_ROOT / "docs" / "ledgers" / "pilot-e-ukraine-friedenssicherung-2026.jsonl"
LEDGER_DIR = REPO_ROOT / "docs" / "ledgers"


class PilotELedgerTests(unittest.TestCase):
    def test_ledger_exists_and_is_ascii_pure(self):
        raw = LEDGER_PATH.read_text(encoding="utf-8")
        self.assertTrue(LEDGER_PATH.is_file())
        for char in raw:
            self.assertTrue(ord(char) < 128,
                            f"non-ASCII character {char!r} in ledger")

    def test_chain_unveraendert(self):
        ledger = MesswertLedger(LEDGER_PATH)
        self.assertTrue(ledger.verify_chain())
        entries = ledger.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["seq"], 1)
        self.assertEqual(entries[1]["seq"], 2)
        self.assertEqual(entries[1]["prev_hash"], entries[0]["entry_hash"])
        self.assertEqual(entries[0]["value"], 2800.0)
        self.assertEqual(entries[1]["value"], 7560000000.0)

    def test_all_gates_open_and_wirkung_beobachtet(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        for gate in ("GATE_1_DATASET", "GATE_2_LEDGER",
                     "GATE_3_MATCH", "GATE_4_EVIDENZ"):
            self.assertTrue(result["gates"][gate], gate)
        self.assertTrue(result["all_gates_open"])
        self.assertEqual(result["wirkung_status"], "WIRKUNG_BEOBACHTET")

    def test_wirkung_progress_null_nicht_erfolg(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        wirkung = result["indicators"][
            "Aus dem EU-Ukraine-Kredit ausgezahlte Finanzmittel"]
        self.assertEqual(wirkung["status"], "WIRKUNG_BEOBACHTET")
        self.assertEqual(wirkung["latest"], 7560000000.0)
        self.assertEqual(wirkung["progress"], 0.0)
        self.assertFalse(wirkung["target_reached"])

    def test_resilienz_beobachtet_kosten_unknown(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        resilienz = result["indicators"][
            "Angehoerige der Panzerbrigade 45 Litauen bis Einsatzbereitschaft"]
        self.assertEqual(resilienz["status"], "BEOBACHTET")
        self.assertEqual(resilienz["latest"], 2800.0)
        self.assertFalse(resilienz["target_reached"])
        kosten = result["indicators"][
            "Deutsche Zusage ueber den Purl-Mechanismus fuer US-Luftverteidigungswaffen"]
        self.assertEqual(kosten["status"], "UNKNOWN")
        self.assertIsNone(kosten["latest"])
        self.assertIsNone(kosten["progress"])

    def test_evidence_references_https(self):
        ledger = MesswertLedger(LEDGER_PATH)
        for entry in ledger.entries():
            self.assertTrue(str(entry["source"]).startswith("https://"))
            self.assertTrue(str(entry["measured_by"]).strip())

    def test_index_zaehlt_pilot_e_beobachtet(self):
        result = build_index(REPO_ROOT / "docs" / "messmatrix", LEDGER_DIR)
        entry = [e for e in result["entries"]
                 if e["initiative_id"] == "pilot-e-ukraine-friedenssicherung-2026"][0]
        self.assertTrue(entry["ledger_found"])
        self.assertTrue(entry["all_gates_open"])
        self.assertEqual(entry["wirkung_status"], "WIRKUNG_BEOBACHTET")

    def test_assessment_deterministisch(self):
        first = assess(DATASET_PATH, LEDGER_PATH)
        second = assess(DATASET_PATH, LEDGER_PATH)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
