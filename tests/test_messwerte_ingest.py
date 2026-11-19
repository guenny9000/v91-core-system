"""Tests fuer controller.messwerte_ingest (R3): Ledger, Evidenzpflicht, fail-closed."""
import json
import tempfile
import unittest
from pathlib import Path

from controller.messwerte_ingest import (
    MesswertLedger,
    MesswerteIngestError,
    load_dataset,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DATASET = REPO_ROOT / "docs" / "messmatrix" / "pilot-b-geothermie-pullach-2026.json"


def _payload(**overrides):
    value = {
        "initiative_id": "pilot-b-geothermie-pullach-2026",
        "indicator": "Verausgabte Projektmittel Pullach Sued",
        "value": 1_250_000.0,
        "measured_at": "2026-12-01T00:00:00Z",
        "source": "https://example.org/kfw-verwendungsnachweis",
        "measured_by": "Testpruefstelle",
    }
    value.update(overrides)
    return value


def _tmp_ledger(tmp):
    return MesswertLedger(Path(tmp) / "messwerte.jsonl")


class LedgerTests(unittest.TestCase):
    def test_first_and_second_entry_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            dataset = load_dataset(REAL_DATASET)
            first = ledger.append(_payload(), dataset)
            second = ledger.append(_payload(value=2_500_000.0), dataset)
            self.assertEqual(1, first["seq"])
            self.assertEqual(2, second["seq"])
            self.assertEqual(first["entry_hash"], second["prev_hash"])
            self.assertTrue(ledger.verify_chain())

    def test_entry_carries_dataset_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            entry = ledger.append(_payload(), load_dataset(REAL_DATASET))
            self.assertEqual(entry["role"], "KOSTEN")
            self.assertEqual(entry["unit"], "EUR")
            self.assertEqual(entry["target"], 47_000_000.0)
            self.assertEqual(entry["recorded_status"], "OBSERVED")

    def test_persistence_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "messwerte.jsonl"
            ledger = MesswertLedger(path)
            ledger.append(_payload(), load_dataset(REAL_DATASET))
            reloaded = MesswertLedger(path)
            self.assertEqual(1, len(reloaded.entries()))
            self.assertTrue(reloaded.verify_chain())
            reloaded.append(_payload(value=3_000_000.0), load_dataset(REAL_DATASET))
            self.assertEqual(2, len(MesswertLedger(path).entries()))

    def test_tamper_detection_refuses_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            dataset = load_dataset(REAL_DATASET)
            ledger.append(_payload(), dataset)
            path = Path(tmp) / "messwerte.jsonl"
            lines = path.read_text().splitlines()
            entry = json.loads(lines[0])
            entry["value"] = 999_999_999.0
            path.write_text(json.dumps(entry) + "\n")
            broken = MesswertLedger(path)
            self.assertFalse(broken.verify_chain())
            with self.assertRaises(MesswerteIngestError):
                broken.append(_payload(value=1.0), dataset)


class FailClosedTests(unittest.TestCase):
    def test_initiative_id_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(initiative_id="falsche-id"),
                              load_dataset(REAL_DATASET))

    def test_unknown_indicator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(indicator="Gibt es nicht"),
                              load_dataset(REAL_DATASET))

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(source=""), load_dataset(REAL_DATASET))

    def test_structurally_invalid_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(source="vanishing:muell"),
                              load_dataset(REAL_DATASET))

    def test_ledger_reference_source_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            entry = ledger.append(_payload(source="ledger::receipt-42"),
                                  load_dataset(REAL_DATASET))
            self.assertEqual(entry["source"], "ledger::receipt-42")

    def test_boolean_value_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(value=True), load_dataset(REAL_DATASET))

    def test_negative_value_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(value=-1.0), load_dataset(REAL_DATASET))

    def test_invalid_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            with self.assertRaises(MesswerteIngestError):
                ledger.append(_payload(measured_at="morgen früh"),
                              load_dataset(REAL_DATASET))

    def test_invalid_dataset_rejected_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"initiative_id": "x"}), encoding="utf-8")
            with self.assertRaises(MesswerteIngestError):
                load_dataset(bad)


class ReportTests(unittest.TestCase):
    def test_report_counts_and_unknown_stays_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            dataset = load_dataset(REAL_DATASET)
            ledger.append(_payload(value=1_000_000.0), dataset)
            report = ledger.report(dataset)
            kosten = report["indicators"]["Verausgabte Projektmittel Pullach Sued"]
            self.assertEqual(kosten["measurement_count"], 1)
            self.assertEqual(kosten["latest"], 1_000_000.0)
            self.assertEqual(kosten["status"], "OBSERVED")
            wirkung = report["indicators"][
                "Zusaetzlich mit Tiefengeothermie-Waerme versorgte Personen"]
            self.assertEqual(wirkung["status"], "UNKNOWN")
            self.assertEqual(wirkung["measurement_count"], 0)

    def test_report_without_dataset_lists_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _tmp_ledger(tmp)
            ledger.append(_payload(), load_dataset(REAL_DATASET))
            report = ledger.report()
            self.assertEqual(report["entries_total"], 1)
            self.assertIn("Verausgabte Projektmittel Pullach Sued",
                          report["indicators"])


class CliTests(unittest.TestCase):
    def test_cli_append_verify_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "messwerte.jsonl"
            payload = json.dumps(_payload())
            code = main(["append", "--dataset", str(REAL_DATASET),
                         "--ledger", str(ledger), "--payload", payload])
            self.assertEqual(code, 0)
            code = main(["verify", "--ledger", str(ledger)])
            self.assertEqual(code, 0)
            code = main(["report", "--dataset", str(REAL_DATASET),
                         "--ledger", str(ledger)])
            self.assertEqual(code, 0)

    def test_cli_rejects_bad_payload_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "messwerte.jsonl"
            code = main(["append", "--dataset", str(REAL_DATASET),
                         "--ledger", str(ledger), "--payload", "nicht json"])
            self.assertEqual(code, 2)
            self.assertFalse(ledger.exists())


if __name__ == "__main__":
    unittest.main()
