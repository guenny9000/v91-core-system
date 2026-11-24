"""Tests fuer die TOCTOU-Race-Behbung in controller/mess_pilot.py
(PilotLog.append unter _exclusive_log_lock, 25.11.2026).

Vorher (Probe am unveraenderten Modul, 8 Threads am selben Log):
7 von 8 Appends mit Fehler, Kette anschliessend ungueltig
('prev_hash falsch'). Nachher: 8/8 sauber, seq 1..8 eindeutig,
verify() ok. WIRKUNG_NUR_AUS_MESSUNG: dieser Test ist die
dauerhafte Regressionssonde fuer genau dieses Verhalten.
LOCK != VEROEDERUNG: ohne Lock waere der Befund wieder da.
"""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from controller.mess_pilot import PilotLog, verify


class PilotLogRaceTests(unittest.TestCase):
    def test_concurrent_appends_seq_eindeutig_kette_gueltig(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "race.jsonl"
            ledger = PilotLog(log, host_id="race-test-host")
            errors = []
            seqs = []

            def write(job_id: int) -> None:
                try:
                    e = ledger.append(
                        "VB-ENERGIE-01", "OK", float(job_id), "kW",
                        timestamp_utc="2026-11-25T12:%02d:00Z" % job_id)
                    seqs.append(e["seq"])
                except Exception as ex:  # Fehler sammeln, nie still
                    errors.append("%s: %s" % (job_id, ex))

            threads = [threading.Thread(target=write, args=(i,))
                       for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], "parallele appends fehlerhaft: %s"
                             % errors)
            self.assertEqual(sorted(seqs), list(range(1, 9)),
                             "seq-Duplikate oder Luecken: %s" % sorted(seqs))
            report = verify(log)
            self.assertTrue(report["ok"], "Kette nach Rennen ungueltig: %s"
                            % report)
            self.assertEqual(report["entries"], 8)

    def test_lock_datei_enthaelt_keine_protokolldaten(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "race.jsonl"
            ledger = PilotLog(log, host_id="race-test-host")
            for i in range(3):
                ledger.append("VB-SYS-01", "OK", float(i), "percent",
                              timestamp_utc="2026-11-25T13:%02d:00Z" % i)
            lock = Path(tmp) / "race.jsonl.lock"
            self.assertTrue(lock.is_file(),
                            "Lock-Begleitdatei fehlt (Sperre wirkungslos?)")
            self.assertEqual(lock.read_text(encoding="utf-8").strip(), "",
                             "LOCK_DATEI != LOG_DATEI: Lock-Datei muss leer "
                             "bleiben (ISOLATE_NOT_DESTROY)")
            lines = [ln for ln in log.read_text(
                encoding="utf-8").split("\n") if ln.strip()]
            self.assertEqual(len(lines), 3,
                             "Protokoll enthaelt nur die echten Eintraege")
            seqs = [json.loads(ln)["seq"] for ln in lines]
            self.assertEqual(seqs, [1, 2, 3])

    def test_sequentielle_appends_unveraendert(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "seq.jsonl"
            ledger = PilotLog(log, host_id="seq-test-host")
            for i in range(5):
                ledger.append("VB-NETZ-01", "OK", float(i), "ms",
                              timestamp_utc="2026-11-25T14:%02d:00Z" % i)
            report = verify(log)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["entries"], 5)


if __name__ == "__main__":
    unittest.main()
