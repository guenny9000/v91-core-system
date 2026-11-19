"""Tests: controller/wirkungs_index.py (R5, Modul-Schritt 7)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from controller.messwerte_ingest import MesswertLedger, load_dataset  # noqa: E402
from controller.wirkungs_assessment import assess  # noqa: E402
from controller.wirkungs_index import build_index, main  # noqa: E402

INDICATORS = [
    {
        "role": "WIRKUNG",
        "name": "Geschuetzte Flaeche",
        "unit": "ha",
        "baseline": 100.0,
        "target": 1000.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2030-12-31T00:00:00Z"},
        "method": "Flaechenerfassung",
        "verifier": "Foerderstatistik",
        "uncertainty": 10.0,
        "alternative_comparison": "Ohne Programm ungeschuetzt",
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
        "name": "Messstellen",
        "unit": "Stellen",
        "baseline": 0.0,
        "target": 10.0,
        "period": {"baseline_at": "2026-01-01T00:00:00Z",
                   "target_at": "2030-12-31T00:00:00Z"},
        "method": "Register",
        "verifier": "Register",
        "uncertainty": 0.0,
    },
]


def dataset(path: Path, initiative_id: str) -> Path:
    record = {
        "initiative_id": initiative_id,
        "description": "Test Initiative " + initiative_id,
        "watcher": "natur",
        "maturity": "R2",
        "indicators": INDICATORS,
        "multiplier": None,
        "sources": [{"publisher": "Test", "url": "https://example.org",
                     "used_for": "Test"}],
    }
    path.write_text(json.dumps(record, ensure_ascii=True, indent=2) + "\n")
    return path


class WirkungsIndexTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.dataset_dir = self.tmp / "matrices"
        self.ledger_dir = self.tmp / "ledgers"
        self.dataset_dir.mkdir()
        self.ledger_dir.mkdir()

    def test_leeres_ledger_verzeichnis_ist_unklar_ehrlich(self):
        a = dataset(self.dataset_dir / "pilot-eins-2026.json", "pilot-eins-2026")
        b = dataset(self.dataset_dir / "pilot-zwei-2026.json", "pilot-zwei-2026")
        result = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(result["pilots_total"], 2)
        self.assertEqual(result["ledgers_found"], 0)
        self.assertEqual(result["ledgers_missing"], 2)
        self.assertEqual(result["by_wirkung_status"]["WIRKUNG_UNKNOWN"], 2)
        self.assertEqual(result["indicators_total"], 6)
        self.assertEqual(result["indicators_unknown"], 6)
        self.assertEqual(result["indicators_observed"], 0)
        self.assertEqual(result["by_watcher"], {"natur": 2})
        self.assertTrue(result["honest_limits"])

    def test_ledger_dir_none_zieht_alle_als_offen(self):
        dataset(self.dataset_dir / "pilot-eins-2026.json", "pilot-eins-2026")
        result = build_index(self.dataset_dir, None)
        self.assertEqual(result["pilots_total"], 1)
        self.assertEqual(result["ledgers_missing"], 1)
        self.assertEqual(result["by_wirkung_status"]["WIRKUNG_UNKNOWN"], 1)

    def test_mit_ledger_zaehlt_beobachtet(self):
        matrix = dataset(self.dataset_dir / "pilot-eins-2026.json",
                         "pilot-eins-2026")
        record = load_dataset(matrix)
        ledger = MesswertLedger(self.ledger_dir / "pilot-eins-2026.jsonl")
        ledger.append({
            "initiative_id": "pilot-eins-2026",
            "indicator": "Geschuetzte Flaeche",
            "value": 550.0,
            "measured_at": "2027-06-01T00:00:00Z",
            "source": "https://example.org/messung",
        }, record)
        result = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(result["ledgers_found"], 1)
        self.assertEqual(result["by_wirkung_status"]["WIRKUNG_BEOBACHTET"], 1)
        entry = result["entries"][0]
        self.assertTrue(entry["ledger_found"])
        self.assertEqual(entry["indicators"]["Geschuetzte Flaeche"],
                         "WIRKUNG_BEOBACHTET")
        self.assertEqual(entry["indicators"]["Verausgabte Mittel"], "UNKNOWN")
        self.assertEqual(result["indicators_observed"], 1)
        self.assertEqual(result["indicators_unknown"], 2)

    def test_zielerreichung_zaehlt(self):
        matrix = dataset(self.dataset_dir / "pilot-eins-2026.json",
                         "pilot-eins-2026")
        record = load_dataset(matrix)
        ledger = MesswertLedger(self.ledger_dir / "pilot-eins-2026.jsonl")
        ledger.append({
            "initiative_id": "pilot-eins-2026",
            "indicator": "Messstellen",
            "value": 10.0,
            "measured_at": "2028-01-01T00:00:00Z",
            "source": "https://example.org/messung",
        }, record)
        result = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(result["indicators_target_reached"], 1)
        entry = result["entries"][0]
        self.assertEqual(entry["indicators"]["Messstellen"], "ZIEL_ERREICHT")

    def test_kaputte_kette_wird_geschlossenes_tor(self):
        matrix = dataset(self.dataset_dir / "pilot-eins-2026.json",
                         "pilot-eins-2026")
        record = load_dataset(matrix)
        ledger = MesswertLedger(self.ledger_dir / "pilot-eins-2026.jsonl")
        ledger.append({
            "initiative_id": "pilot-eins-2026",
            "indicator": "Geschuetzte Flaeche",
            "value": 550.0,
            "measured_at": "2027-06-01T00:00:00Z",
            "source": "https://example.org/messung",
        }, record)
        path = self.ledger_dir / "pilot-eins-2026.jsonl"
        lines = path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        entry["value"] = 999.0
        lines[0] = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        path.write_text("\n".join(lines) + "\n")
        result = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(
            result["by_wirkung_status"]["UNBEWERTET_GESCHLOSSENES_TOR"], 1)
        entry = result["entries"][0]
        self.assertFalse(entry["all_gates_open"])
        self.assertIn("chain broken", entry["closed_reason"])
        # Indikatoren bleiben UNKNOWN gezaehlt, niemals Erfolg
        self.assertEqual(result["indicators_unknown"], 3)

    def test_determinismus_zwei_laeufe_identisch(self):
        matrix = dataset(self.dataset_dir / "pilot-eins-2026.json",
                         "pilot-eins-2026")
        record = load_dataset(matrix)
        ledger = MesswertLedger(self.ledger_dir / "pilot-eins-2026.jsonl")
        ledger.append({
            "initiative_id": "pilot-eins-2026",
            "indicator": "Geschuetzte Flaeche",
            "value": 550.0,
            "measured_at": "2027-06-01T00:00:00Z",
            "source": "https://example.org/messung",
        }, record)
        first = build_index(self.dataset_dir, self.ledger_dir)
        second = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_kaputtes_dataset_fail_closed(self):
        broken = self.dataset_dir / "broken-matrix.json"
        broken.write_text(json.dumps({"initiative_id": "x",
                                       "watcher": "kein-watcher"}))
        with self.assertRaises(Exception):
            build_index(self.dataset_dir, self.ledger_dir)

    def test_dataset_ohne_watcher_fail_closed(self):
        record = {
            "initiative_id": "pilot-drei-2026",
            "description": "Test",
            "watcher": "natur",
            "maturity": "R2",
            "indicators": INDICATORS,
            "multiplier": None,
            "sources": [],
        }
        path = self.dataset_dir / "pilot-drei-2026.json"
        path.write_text(json.dumps(record))
        result = build_index(self.dataset_dir, self.ledger_dir)
        self.assertEqual(result["pilots_total"], 1)

    def test_lederes_verzeichnis_fail_closed(self):
        with self.assertRaises(Exception):
            build_index(self.tmp / "existiert-nicht", self.ledger_dir)

    def test_typen_fail_closed(self):
        with self.assertRaises(Exception):
            build_index("kein-pfad", None)
        with self.assertRaises(Exception):
            build_index(self.dataset_dir, "kein-pfad")

    def test_repo_pilot_waechter_mit_ohne_ledger(self):
        repo_dir = REPO / "docs/messmatrix"
        if not repo_dir.is_dir() or not list(repo_dir.glob("*.json")):
            self.skipTest("repo messmatrix nicht im Checkout")
        empty_ledgers = self.tmp / "empty-ledgers"
        empty_ledgers.mkdir()
        result = build_index(repo_dir, empty_ledgers)
        self.assertEqual(result["pilots_total"], 7)
        self.assertEqual(result["by_wirkung_status"]["WIRKUNG_UNKNOWN"], 7)
        self.assertEqual(result["indicators_observed"], 0)
        self.assertEqual(result["indicators_unknown"],
                         result["indicators_total"])
        self.assertEqual(sorted(result["by_watcher"]),
                         ["energie", "ernaehrung", "frieden",
                          "gesundheit", "natur", "technologie",
                          "wasser"])

    def test_cli_exit_codes(self):
        matrix = dataset(self.dataset_dir / "pilot-eins-2026.json",
                         "pilot-eins-2026")
        proc = subprocess.run(
            [sys.executable, str(REPO / "controller/wirkungs_index.py"),
             "--dataset-dir", str(self.dataset_dir),
             "--ledger-dir", str(self.ledger_dir)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["pilots_total"], 1)
        proc_bad = subprocess.run(
            [sys.executable, str(REPO / "controller/wirkungs_index.py"),
             "--dataset-dir", str(self.tmp / "fehlt"),
             "--ledger-dir", str(self.ledger_dir)],
            capture_output=True, text=True)
        self.assertEqual(proc_bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
