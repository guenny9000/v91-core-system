"""Tests: controller/wirkungs_assessment.py (R4, Modul-Schritt 6)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from controller.messwerte_ingest import MesswertLedger, load_dataset  # noqa: E402
from controller.wirkungs_assessment import (  # noqa: E402
    WirkungsAssessmentError,
    assess,
    main,
)

INDICATORS = [
    {
        "role": "WIRKUNG",
        "name": "Geschuetzte Flaeche",
        "unit": "ha",
        "baseline": 100.0,
        "target": 1000.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2030-12-31T00:00:00Z"},
        "method": "Flaechenerfassung nach Foerdergeometrie",
        "verifier": "Foerderstatistik",
        "uncertainty": 10.0,
        "alternative_comparison": "Ohne Programm bleibt die Flaeche ungeschuetzt",
    },
    {
        "role": "KOSTEN",
        "name": "Verausgabte Mittel",
        "unit": "EUR",
        "baseline": 0.0,
        "target": 500000.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2030-12-31T00:00:00Z"},
        "method": "Haushaltsfuehrung",
        "verifier": "Bundeshaushalt",
        "uncertainty": 1000.0,
    },
    {
        "role": "RESILIENZ",
        "name": "Netzunabhaengige Messstellen",
        "unit": "Stellen",
        "baseline": 0.0,
        "target": 10.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2030-12-31T00:00:00Z"},
        "method": "Messstellenregister",
        "verifier": "Register",
        "uncertainty": 0.0,
    },
]


def dataset(path: Path) -> Path:
    record = {
        "initiative_id": "test-initiative-2026",
        "description": "Test Initiative Wirkungs-Assessment",
        "watcher": "natur",
        "maturity": "R2",
        "indicators": INDICATORS,
        "multiplier": None,
        "sources": [{"publisher": "Test", "url": "https://example.org",
                     "used_for": "Test"}],
    }
    path.write_text(json.dumps(record, ensure_ascii=True, indent=2) + "\n")
    return path


def append(ledger: MesswertLedger, record, indicator, value, measured_at,
           source="https://example.org/messung", initiative="test-initiative-2026"):
    return ledger.append({
        "initiative_id": initiative,
        "indicator": indicator,
        "value": value,
        "measured_at": measured_at,
        "source": source,
        "measured_by": "Testpilot",
    }, record)


class WirkungsAssessmentTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.dataset_path = dataset(self.tmp / "matrix.json")
        self.record = load_dataset(self.dataset_path)
        self.ledger_path = self.tmp / "ledger.jsonl"

    def test_gates_open_wirkung_beobachtet(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertTrue(result["all_gates_open"])
        self.assertEqual(result["wirkung_status"], "WIRKUNG_BEOBACHTET")
        slot = result["indicators"]["Geschuetzte Flaeche"]
        self.assertEqual(slot["status"], "WIRKUNG_BEOBACHTET")
        self.assertAlmostEqual(slot["progress"], 0.5)

    def test_ziel_erreicht(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 1000.0,
               "2028-01-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path)
        slot = result["indicators"]["Geschuetzte Flaeche"]
        self.assertTrue(slot["target_reached"])
        self.assertEqual(slot["status"], "ZIEL_ERREICHT")
        self.assertEqual(slot["progress"], 1.0)

    def test_kein_messwert_unknown(self):
        result = assess(self.dataset_path, self.ledger_path)
        self.assertTrue(result["all_gates_open"])
        self.assertEqual(result["wirkung_status"], "WIRKUNG_UNKNOWN")
        for slot in result["indicators"].values():
            self.assertEqual(slot["status"], "UNKNOWN")
            self.assertFalse(slot["target_reached"])

    def test_kosten_ohne_ziel_beobachtet(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Verausgabte Mittel", 100000.0,
               "2027-01-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path)
        slot = result["indicators"]["Verausgabte Mittel"]
        self.assertEqual(slot["status"], "BEOBACHTET")
        self.assertFalse(slot["target_reached"])
        self.assertAlmostEqual(slot["progress"], 0.2)

    def test_kaputte_kette_schliesst_tor_2(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["value"] = 9999.0
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_2_LEDGER"])
        self.assertFalse(result["all_gates_open"])
        self.assertEqual(result["wirkung_status"], "UNBEWERTET_GESCHLOSSENES_TOR")
        self.assertTrue(any("chain broken" in reason
                           for reason in result["closed_reasons"]))

    def test_fremde_initiative_schliesst_tor_3(self):
        ledger = MesswertLedger(self.ledger_path)
        with self.assertRaises(Exception):
            append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
                   "2027-06-01T00:00:00Z", initiative="andere-initiative")
        self.assertEqual(ledger.entries(), [])
        result = assess(self.dataset_path, self.ledger_path)
        self.assertTrue(result["all_gates_open"])

    def test_unbekannter_indikator_schliesst_tor_3(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["indicator"] = "Unbekannter Indikator"
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_3_MATCH"])
        self.assertFalse(result["all_gates_open"])

    def test_messzeit_vor_baseline_schliesst_tor_4(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["measured_at"] = "2025-01-01T00:00:00Z"
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_4_EVIDENZ"])
        self.assertTrue(any("before baseline_at" in reason
                            for reason in result["closed_reasons"]))

    def test_messzeit_nach_zieltermin_schliesst_tor_4(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["measured_at"] = "2031-01-01T00:00:00Z"
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_4_EVIDENZ"])
        self.assertTrue(any("after target_at" in reason
                            for reason in result["closed_reasons"]))

    def test_ungueltige_evidenz_schliesst_tor_4(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["source"] = "keine-referenz"
        entry["entry_hash"] = json.dumps(
            {k: v for k, v in entry.items() if k != "entry_hash"},
            sort_keys=True, ensure_ascii=False) and __import__("hashlib").sha256(
            json.dumps({k: v for k, v in entry.items() if k != "entry_hash"},
                       sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_4_EVIDENZ"])
        self.assertTrue(any("invalid evidence reference" in reason
                            for reason in result["closed_reasons"]))

    def test_ungueltiges_dataset_schliesst_tor_1(self):
        broken = self.tmp / "broken.json"
        record = json.loads(self.dataset_path.read_text())
        record["watcher"] = "kein-watcher"
        broken.write_text(json.dumps(record))
        result = assess(broken, self.ledger_path)
        self.assertFalse(result["gates"]["GATE_1_DATASET"])
        self.assertFalse(result["all_gates_open"])

    def test_as_of_ignoriert_spaeltere_messwerte(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 200.0,
               "2026-06-01T00:00:00Z")
        append(ledger, self.record, "Geschuetzte Flaeche", 800.0,
               "2028-06-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path,
                        as_of="2027-01-01T00:00:00Z")
        slot = result["indicators"]["Geschuetzte Flaeche"]
        self.assertEqual(slot["latest"], 200.0)
        self.assertAlmostEqual(slot["progress"], (200.0 - 100.0) / 900.0)
        result_full = assess(self.dataset_path, self.ledger_path)
        self.assertEqual(result_full["indicators"]["Geschuetzte Flaeche"]
                         ["latest"], 800.0)

    def test_fortschritt_negativ_begrenzt(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 50.0,
               "2027-01-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path)
        slot = result["indicators"]["Geschuetzte Flaeche"]
        self.assertEqual(slot["progress"], 0.0)
        self.assertEqual(slot["status"], "WIRKUNG_BEOBACHTET")

    def test_torpflicht_bleibt(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Geschuetzte Flaeche", 550.0,
               "2027-06-01T00:00:00Z")
        lines = self.ledger_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["value"] = 600.0
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        self.ledger_path.write_text("\n".join(lines) + "\n")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertEqual(result["indicators"]["Geschuetzte Flaeche"]["status"],
                         "UNKNOWN")

    def test_parameter_typen(self):
        with self.assertRaises(WirkungsAssessmentError):
            assess("kein-pfad", self.ledger_path)
        with self.assertRaises(WirkungsAssessmentError):
            assess(self.dataset_path, "kein-pfad")

    def test_pilot_a_repo_mitfahrtest(self):
        ledger = MesswertLedger(self.ledger_path)
        append(ledger, self.record, "Netzunabhaengige Messstellen", 12.0,
               "2029-12-01T00:00:00Z")
        result = assess(self.dataset_path, self.ledger_path)
        self.assertTrue(result["all_gates_open"])
        self.assertEqual(result["indicators"]["Netzunabhaengige Messstellen"]
                         ["status"], "ZIEL_ERREICHT")

    def test_real_echte_repo_pilotmatrix(self):
        matrix = REPO / "docs/messmatrix/pilot-b-geothermie-pullach-2026.json"
        if not matrix.exists():
            self.skipTest("pilot matrix not in checkout")
        record = load_dataset(matrix)
        ledger = MesswertLedger(self.ledger_path)
        name = record["indicators"][0]["name"]
        ledger.append({
            "initiative_id": record["initiative_id"],
            "indicator": name,
            "value": 5,
            "measured_at": "2027-01-01T00:00:00Z",
            "source": "https://example.org/test",
        }, record)
        result = assess(matrix, self.ledger_path)
        self.assertTrue(result["all_gates_open"])
        self.assertEqual(result["initiative_id"],
                         "pilot-b-geothermie-pullach-2026")

    def test_cli_exit_codes(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "controller/wirkungs_assessment.py"),
             "--dataset", str(self.dataset_path),
             "--ledger", str(self.ledger_path)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["wirkung_status"], "WIRKUNG_UNKNOWN")
        proc_bad = subprocess.run(
            [sys.executable, str(REPO / "controller/wirkungs_assessment.py"),
             "--dataset", str(self.tmp / "fehlt.json"),
             "--ledger", str(self.ledger_path)],
            capture_output=True, text=True)
        self.assertEqual(proc_bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
