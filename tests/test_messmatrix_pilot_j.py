"""Integrationstest: Pilot-J-Messmatrix-Dataset (oekologische
Arbeitspfade ohne Schubladen-Denken, natur, R1) nach Issue #268
Abschnitt 4 und Lernblock PR #232.

Das Dataset ist eine Konzeptbeschreibung (MATRIZ != WIRKUNG): Es definiert
Messkriterien, es enthaelt keine Messwerte. Kein Profil ist angelegt,
keine Stunde geleistet (IDEA != IMPLEMENTATION). UNKNOWN bleibt UNKNOWN.
Freiwilligkeit ist Grundprinzip; kein Ersatz bezahlter Stellen; keine
Zuweisung nach Diagnose oder Etikett (MENSCH != SCHUBLADE).
"""
import json
import unittest
from pathlib import Path

from v91_impact_metrics.metrics import evaluate_messmatrix

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "docs" / "messmatrix" / "pilot-j-oekologische-arbeitspfade-2026.json"


def _load_record():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


class PilotJMessmatrixTests(unittest.TestCase):
    def test_dataset_exists_and_is_ascii_pure(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertTrue(DATASET_PATH.is_file())
        for char in raw:
            self.assertTrue(ord(char) < 128,
                            f"non-ASCII character {char!r} in dataset")

    def test_evaluate_is_green(self):
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["matrix_status"], "MASSE_BESCHRIEBEN")
        self.assertEqual(sorted(result["roles_covered"]),
                         ["KOSTEN", "RESILIENZ", "WIRKUNG"])

    def test_watcher_and_maturity(self):
        result = evaluate_messmatrix(_load_record())
        self.assertEqual(result["watcher"], "natur")
        self.assertEqual(result["maturity"], "R1")

    def test_no_measured_values(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertNotIn("measured", raw)
        record = _load_record()
        for ind in record["indicators"]:
            self.assertNotIn("measured", ind)
            self.assertGreaterEqual(ind["target"], ind["baseline"])

    def test_baseline_is_zero_concept_stage(self):
        record = _load_record()
        for ind in record["indicators"]:
            self.assertEqual(ind["baseline"], 0.0)
        self.assertIn("nichts gemessen", record["description"])

    def test_voluntariness_and_no_displacement_pinned(self):
        raw = DATASET_PATH.read_text(encoding="utf-8")
        self.assertIn("freiwillig", raw)
        self.assertIn("kein Ersatz bezahlter", raw)
        self.assertIn("kein Zwang", raw)
        self.assertIn("kein Schubladen-Kriterium", raw)

    def test_no_drawer_criterion_in_resilienz_method(self):
        record = _load_record()
        resil = [i for i in record["indicators"]
                 if i["role"] == "RESILIENZ"][0]
        self.assertIn("MENSCH != SCHUBLADE", resil["method"])
        self.assertIn("NIE nach Diagnose", resil["method"])

    def test_kosten_honest_no_funds_committed(self):
        record = _load_record()
        kosten = [i for i in record["indicators"] if i["role"] == "KOSTEN"][0]
        self.assertIn("ZUSAGUNG != VERAUSGABUNG", kosten["method"])
        self.assertIn("kein Antrag gestellt", kosten["method"])

    def test_no_multiplier_fiction(self):
        record = _load_record()
        self.assertIsNone(record.get("multiplier"))
        result = evaluate_messmatrix(record)
        self.assertIsNone(result["multiplier"])
        self.assertEqual(result["multiplier_status"], "UNKNOWN")

    def test_impact_claim_never_permitted(self):
        result = evaluate_messmatrix(_load_record())
        self.assertFalse(result["impact_claim_permitted"])

    def test_primary_sources_present(self):
        record = _load_record()
        self.assertEqual(len(record["sources"]), 2)
        for src in record["sources"]:
            self.assertTrue(src["publisher"].strip())
            self.assertTrue(src["url"].startswith("https://"))
            self.assertTrue(src["used_for"].strip())


if __name__ == "__main__":
    unittest.main()
