"""Tests fuer controller/v91_solar_eval.py (3-Wege-Gate: Messreihe-Ledger-Manifest).

Kernprinzipien: UNKNOWN != PASS (fehlende Daten => UNVERIFIZIERT,
KEINE erfundenen Kennzahlen), Manipulation wird NIE still akzeptiert
(tamper-EVIDENT), STATUS-Manifest wird nur aus verifizierter
Evidenz abgeleitet (SCRIPTED != INSTALLED)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.ledger import HashChainLedger, compute_hash  # noqa: E402
from controller import v91_solar_eval as se  # noqa: E402


def _write_series(path: Path, watts=(0, 120, 300)) -> None:
    lines = []
    for i, watt in enumerate(watts):
        lines.append(json.dumps({
            "schema": se.SERIES_SCHEMA,
            "timestamp": f"2026-11-25T12:{i * 15:02d}:00+01:00",
            "watt": watt,
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _linked_ledger(path: Path, series_path: Path) -> None:
    ledger = HashChainLedger(str(path))
    ledger.append(
        {"kind": "SOLAR_EVAL_SERIES", "series_digest": se._sha256_file(series_path)},
        timestamp="2026-11-25T12:59:00+01:00",
    )


class SolarEvalSeriesTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fehlende_reihe_unverifiziert(self):
        result = se.evaluate(self.tmp_path / "gibt_es_nicht.jsonl")
        self.assertEqual(result["status"], "UNVERIFIZIERT")
        self.assertEqual(result["summary"], None)  # KEINE erfundenen Zahlen
        self.assertIn("SERIES_UNAVAILABLE", result["reason"])

    def test_valide_reihe_ohne_ledger_unverifiziert(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        result = se.evaluate(series)
        self.assertEqual(result["status"], "UNVERIFIZIERT")
        self.assertIn("LEDGER_UNVERWEISEN", result["reason"])
        self.assertEqual(result["summary"]["n_samples"], 3)

    def test_ledger_ohne_eintrag_unverifiziert(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        empty = self.tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        result = se.evaluate(series, empty)
        self.assertEqual(result["status"], "UNVERIFIZIERT")
        self.assertIn("LEDGER_EINTRAG_FEHLT", result["reason"])
        self.assertFalse(result["ledger_verified"])

    def test_verlinkte_reihe_verifiziert(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series, watts=(10, 20, 40))
        ledger_path = self.tmp_path / "ledger.jsonl"
        _linked_ledger(ledger_path, series)
        result = se.evaluate(series, ledger_path)
        self.assertEqual(result["status"], "VERIFIZIERT")
        self.assertTrue(result["ledger_verified"])
        s = result["summary"]
        self.assertEqual(s["n_samples"], 3)
        self.assertAlmostEqual(s["mean_watt"], (10 + 20 + 40) / 3)
        self.assertEqual(s["max_watt"], 40)

    def test_fremder_digest_nicht_verifiziert(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        ledger_path = self.tmp_path / "ledger.jsonl"
        ledger = HashChainLedger(str(ledger_path))
        ledger.append(
            {"kind": "SOLAR_EVAL_SERIES", "series_digest": "f" * 64},
            timestamp="2026-11-25T13:00:00+01:00",
        )
        result = se.evaluate(series, ledger_path)
        self.assertEqual(result["status"], "UNVERIFIZIERT")

    def test_manipulierter_ledger_erkannt(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        ledger_path = self.tmp_path / "ledger.jsonl"
        _linked_ledger(ledger_path, series)
        original = ledger_path.read_text(encoding="utf-8")
        rec = json.loads(original)
        rec["payload"]["kind"] = "GEFAELSCHT"
        gefaelscht = json.dumps(rec, sort_keys=True) + "\n"
        ledger_path.write_text(gefaelscht, encoding="utf-8")
        result = se.evaluate(series, ledger_path)
        self.assertEqual(result["status"], "MANIPULIERT")
        self.assertIn("LEDGER_MANIPULIERT", result["reason"])

    def test_invalid_watt_fail_closed(self):
        series = self.tmp_path / "s.jsonl"
        series.write_text(json.dumps({
            "schema": se.SERIES_SCHEMA, "timestamp": "2026-11-25T12:00:00+01:00", "watt": -5,
        }) + "\n", encoding="utf-8")
        with self.assertRaises(se.SolarEvalError):
            se.load_series(series)

    def test_non_finite_watt_fail_closed(self):
        series = self.tmp_path / "non_finite.jsonl"
        for watt in (float("nan"), float("inf"), float("-inf")):
            series.write_text(json.dumps({
                "schema": se.SERIES_SCHEMA,
                "timestamp": "2026-11-25T12:00:00+01:00",
                "watt": watt,
            }) + "\n", encoding="utf-8")
            with self.subTest(watt=repr(watt)):
                with self.assertRaises(se.SolarEvalError):
                    se.load_series(series)

    def test_timestamp_without_timezone_fail_closed(self):
        series = self.tmp_path / "naive_timestamp.jsonl"
        series.write_text(json.dumps({
            "schema": se.SERIES_SCHEMA,
            "timestamp": "2026-11-25T12:00:00",
            "watt": 12,
        }) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(se.SolarEvalError, "TIMESTAMP_TIMEZONE_REQUIRED"):
            se.load_series(series)

    def test_manifest_nur_aus_verifizierter_evidenz(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        manifest = self.tmp_path / "manifest.json"
        result = se.evaluate(series)  # UNVERIFIZIERT
        se.write_manifest(result, manifest)
        on_disk = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["status"], "UNVERIFIZIERT")
        self.assertEqual(on_disk["schema"], se.MANIFEST_SCHEMA)

    def test_gate_exit_codes_drei_stufig(self):
        series = self.tmp_path / "s.jsonl"
        _write_series(series)
        self.assertEqual(se.evaluate(series)["status"], "UNVERIFIZIERT")
        ledger_path = self.tmp_path / "ledger.jsonl"
        _linked_ledger(ledger_path, series)
        self.assertEqual(se.evaluate(series, ledger_path)["status"], "VERIFIZIERT")
        self.assertEqual(se.EXIT_VERIFIZIERT, 0)
        self.assertNotEqual(se.EXIT_UNVERIFIZIERT, 0)

    def test_self_check_laeuft_ohne_reale_daten(self):
        report = se.self_check()
        self.assertEqual(report["self_check"], "PASS")
        self.assertEqual(report["reale_messreihe"], "NICHT_GEPRUEFT")

    def test_modul_traegt_agathon_header(self):
        content = Path(se.__file__).read_text(encoding="utf-8")
        self.assertIn("V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)", content)
        self.assertIn("STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)", content)


if __name__ == "__main__":
    unittest.main()
