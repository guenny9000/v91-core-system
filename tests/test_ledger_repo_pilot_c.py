"""Integrationstest: realer Messwert-Ledger (R3) fuer Pilot C.

Ein dokumentierter WHO-Wert: Wochenanteil der Todesfaelle in
Behandlungszentren (Woche 46, 41 Prozent). Andere Belichtung als die
DON625-Baseline, im Note dokumentiert. Der WIRKUNG-Indikator bleibt
UNKNOWN, weil kein neuerer WHO-14-Tage-Durchschnitt der Kontaktquote
verfuegbar ist. OBSERVED != ERFOLG; UNKNOWN bleibt UNKNOWN.
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

DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-c-ebola-praevention-2026.json"
LEDGER_PATH = REPO_ROOT / "docs" / "ledgers" / "pilot-c-ebola-praevention-2026.jsonl"
LEDGER_DIR = REPO_ROOT / "docs" / "ledgers"


class PilotCLedgerTests(unittest.TestCase):
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
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["seq"], 1)
        self.assertEqual(entries[0]["prev_hash"], "")
        self.assertEqual(entries[0]["value"], 41.0)
        self.assertEqual(entries[0]["role"], "RESILIENZ")

    def test_all_gates_open_trotz_wirkung_unknown(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        for gate in ("GATE_1_DATASET", "GATE_2_LEDGER",
                     "GATE_3_MATCH", "GATE_4_EVIDENZ"):
            self.assertTrue(result["gates"][gate], gate)
        self.assertTrue(result["all_gates_open"])

    def test_resilienz_beobachtet_mit_fortschritt(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        resilienz = result["indicators"][
            "Anteil der Todesfaelle in Behandlungszentren"]
        self.assertEqual(resilienz["status"], "BEOBACHTET")
        self.assertEqual(resilienz["latest"], 41.0)
        self.assertAlmostEqual(resilienz["progress"], 0.141, places=3)
        self.assertFalse(resilienz["target_reached"])

    def test_wirkung_und_kosten_bleiben_unknown(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        wirkung = result["indicators"][
            "Taeglicher Anteil gesehener Kontakte in DRC"]
        self.assertEqual(wirkung["status"], "UNKNOWN")
        self.assertIsNone(wirkung["latest"])
        kosten = result["indicators"][
            "Eingeworbene Finanzierung des Kontinentalplans"]
        self.assertEqual(kosten["status"], "UNKNOWN")
        self.assertIsNone(kosten["latest"])

    def test_pilot_c_bleibt_wirkung_unknown_ehrlich(self):
        result = assess(DATASET_PATH, LEDGER_PATH)
        self.assertEqual(result["wirkung_status"], "WIRKUNG_UNKNOWN")

    def test_evidence_reference_https_und_belichtungsdoku(self):
        ledger = MesswertLedger(LEDGER_PATH)
        entry = ledger.entries()[0]
        self.assertTrue(str(entry["source"]).startswith("https://"))
        note = str(entry["note"])
        self.assertIn("Woche 46", note)
        self.assertIn("Andere Belichtung", note)

    def test_index_zaehlt_pilot_c_ledger(self):
        result = build_index(REPO_ROOT / "docs" / "messmatrix", LEDGER_DIR)
        entry = [e for e in result["entries"]
                 if e["initiative_id"] == "pilot-c-ebola-praevention-2026"][0]
        self.assertTrue(entry["ledger_found"])
        self.assertTrue(entry["all_gates_open"])
        self.assertEqual(entry["wirkung_status"], "WIRKUNG_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
