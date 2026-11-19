"""Tests fuer controller.mess_pilot: Rohdaten-Writer des Mess-Piloten
Alsfeld/Vogelsberg (Runbook PR #214, Issue #101). Fail-closed,
SHA-256-Kette, seq-Monotonie, Status-Wortschatz, Pre-/Post-Check."""
import json
import tempfile
import unittest
from pathlib import Path

from controller.mess_pilot import (
    STATUSES,
    MessPilotError,
    PilotLog,
    validate_reading,
    verify,
    main,
)


class ValidateReadingTests(unittest.TestCase):
    def test_unbekannter_messpunkt_fail_closed(self):
        with self.assertRaises(MessPilotError):
            validate_reading("VB-NEIN-01", "OK", 1.0, "ms")

    def test_unbekannter_status_fail_closed(self):
        with self.assertRaises(MessPilotError):
            validate_reading("VB-NETZ-01", "GUZZLE", 1.0, "ms")

    def test_falsche_einheit_fail_closed(self):
        with self.assertRaises(MessPilotError):
            validate_reading("VB-NETZ-01", "OK", 1.0, "kWh")

    def test_unknown_traegt_keinen_wert(self):
        with self.assertRaises(MessPilotError):
            validate_reading("VB-NETZ-01", "UNKNOWN", 5.0, "ms")

    def test_out_of_range_wird_status_nicht_exception(self):
        status, value = validate_reading("VB-SYS-01", "OK", 250.0, "percent")
        self.assertEqual(status, "OUT_OF_RANGE")
        self.assertEqual(value, 250.0)

    def test_sensor_missing_ohne_wert_ok(self):
        status, value = validate_reading("VB-UMWELT-01",
                                         "SENSOR_MISSING", None, "degC")
        self.assertEqual(status, "SENSOR_MISSING")
        self.assertIsNone(value)


class PilotLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = PilotLog(self.tmp / "raw" / "pilot.jsonl")

    def test_append_verkettet_seq_und_hash(self):
        e1 = self.log.append("VB-NETZ-01", "OK", 18.4, "ms",
                             timestamp_utc="2026-11-20T01:00:00Z")
        e2 = self.log.append("VB-NETZ-01", "OK", 20.1, "ms",
                             timestamp_utc="2026-11-20T01:15:00Z")
        self.assertEqual(e1["seq"], 1)
        self.assertEqual(e2["seq"], 2)
        self.assertEqual(e2["prev_hash"], e1["entry_hash"])
        self.assertTrue(e1["entry_hash"].startswith("sha256:"))

    def test_unknown_eintrag_ohne_wert_wird_gespeichert(self):
        e = self.log.append("VB-ENERGIE-01", "UNKNOWN", None, "kW",
                            timestamp_utc="2026-11-20T01:00:00Z")
        self.assertEqual(e["status"], "UNKNOWN")
        self.assertIsNone(e["value"])

    def test_verify_gruen_neu(self):
        self.log.append("VB-SYS-01", "OK", 42.0, "percent",
                        timestamp_utc="2026-11-20T01:00:00Z")
        self.log.append("VB-SYS-01", "ERROR", None, "percent",
                        timestamp_utc="2026-11-20T01:15:00Z",
                        error_code="IO_READ")
        result = verify(self.log.path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["entries"], 2)
        self.assertEqual(result["statuses"]["ERROR"], 1)

    def test_korrupte_letzte_zeile_markiert_bruch(self):
        self.log.append("VB-NETZ-01", "OK", 10.0, "ms",
                        timestamp_utc="2026-11-20T01:00:00Z")
        with open(self.log.path, "a", encoding="utf-8") as fh:
            fh.write("{kaputte zeile\n")
        entry = self.log.append("VB-NETZ-01", "OK", 11.0, "ms",
                               timestamp_utc="2026-11-20T02:00:00Z")
        self.assertTrue(entry.get("chain_break_detected"))
        result = verify(self.log.path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["chain_breaks"], 1)

    def test_manipulation_in_der_mitte_schlaegt_verify(self):
        self.log.append("VB-NETZ-01", "OK", 10.0, "ms",
                        timestamp_utc="2026-11-20T01:00:00Z")
        self.log.append("VB-NETZ-01", "OK", 11.0, "ms",
                        timestamp_utc="2026-11-20T01:15:00Z")
        lines = self.log.path.read_text(encoding="utf-8").split("\n")
        first = json.loads(lines[0])
        first["value"] = 99.0
        lines[0] = json.dumps(first)
        self.log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = verify(self.log.path)
        self.assertFalse(result["ok"])
        self.assertFalse(result["chain_ok"])

    def test_seq_luecke_schlaegt_verify(self):
        import copy
        from controller.mess_pilot import _entry_hash
        self.log.append("VB-NETZ-01", "OK", 10.0, "ms",
                        timestamp_utc="2026-11-20T01:00:00Z")
        e1 = json.loads(self.log.path.read_text(
            encoding="utf-8").strip().split("\n")[0])
        second = copy.deepcopy(e1)
        second["seq"] = 7  # Luecke: 1 -> 7
        second["prev_hash"] = e1["entry_hash"]
        second["entry_hash"] = _entry_hash(
            {k: v for k, v in second.items() if k != "entry_hash"})
        with open(self.log.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(second, sort_keys=True,
                                separators=(",", ":")) + "\n")
        result = verify(self.log.path)
        self.assertFalse(result["seq_ok"])

    def test_status_woerterbuch_alle_da(self):
        self.assertEqual(STATUSES, frozenset({
            "OK", "UNKNOWN", "ERROR", "DEGRADED", "OFFLINE",
            "NOT_CONFIGURED", "SENSOR_MISSING", "OUT_OF_RANGE"}))

    def test_verify_fehlende_datei_fail_closed(self):
        result = verify(self.tmp / "gibt-es-nicht.jsonl")
        self.assertFalse(result["ok"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "raw" / "pilot.jsonl"

    def test_cli_append_dann_verify_exit_0(self):
        rc1 = main(["append", "--log", str(self.log),
                    "--metric", "VB-NETZ-01", "--status", "OK",
                    "--value", "18.4", "--unit", "ms",
                    "--timestamp-utc", "2026-11-20T01:00:00Z"])
        rc2 = main(["verify", "--log", str(self.log)])
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)

    def test_cli_ungueltiger_status_exit_2(self):
        rc = main(["append", "--log", str(self.log),
                   "--metric", "VB-NETZ-01", "--status", "NOPE",
                   "--timestamp-utc", "2026-11-20T01:00:00Z"])
        self.assertEqual(rc, 2)

    def test_cli_verify_manipuliert_exit_2(self):
        main(["append", "--log", str(self.log),
              "--metric", "VB-SYS-01", "--status", "OK",
              "--value", "42.0", "--unit", "percent",
              "--timestamp-utc", "2026-11-20T01:00:00Z"])
        text = self.log.read_text(encoding="utf-8")
        self.log.write_text(text.replace("42.0", "13.0"), encoding="utf-8")
        rc = main(["verify", "--log", str(self.log)])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
