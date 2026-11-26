"""
Tests: Alarm-Outbox Restore-Drill (Issue #520-Rest).
Self-contained: nur tempfile, keine Netzwerk-/Runner-Abhaengigkeiten.
Pinnt das Doku-Dokument docs/V91-ALARM-OUTBOX-RESTORE-DRILL-2026-11-26.md.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import alarm_outbox_restore_drill as drill  # noqa: E402
from controller.alarm_outbox import (  # noqa: E402
    AlarmOutboxError,
    create_event,
    event_id_from,
    record_transition,
)

NOW = datetime.datetime(2026, 11, 26, 7, 0, 0, tzinfo=datetime.timezone.utc)
DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "V91-ALARM-OUTBOX-RESTORE-DRILL-2026-11-26.md"


def _fixture(tmp: str, events: int = 2) -> pathlib.Path:
    path = pathlib.Path(tmp) / "v91_alarm_outbox.jsonl"
    for index in range(events):
        eid = event_id_from(f"ledger::quelle-{index}", "versorgung", "2026-11-26T07:00:00Z")
        create_event(path, {
            "event_id": eid,
            "source_ref": f"ledger::quelle-{index}",
            "severity": "WARNUNG",
            "begruendung": f"quell-ereignis {index}",
        }, NOW)
    return path


class RestoreDrillTests(unittest.TestCase):
    def test_pass_mit_gesunden_ereignissen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp)
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["verdict"], "PASS")
            self.assertEqual(result["events_geprueft"], 2)
            self.assertEqual(
                list(result["sonden"].values()),
                ["PASS", "PASS", "PASS", "PASS"],
            )

    def test_quelle_bleibt_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp)
            lines_before = path.read_text()
            drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(path.read_text(), lines_before)

    def test_dedup_nach_restore_verhindert_doppelversand(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp, events=1)
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["sonden"]["dedup"], "PASS")

    def test_zustandstreue_mit_uebergang(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp, events=1)
            eid = event_id_from("ledger::quelle-0", "versorgung", "2026-11-26T07:00:00Z")
            record_transition(path, eid, "RETRY_VERPLANT", NOW, retry_count=3)
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["verdict"], "PASS")
            self.assertEqual(result["sonden"]["zustandstreue"], "PASS")

    def test_fail_closed_gegen_truncierte_kopie(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp)
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["sonden"]["fail_closed"], "PASS")

    def test_einzelnes_ereignis_ohne_uebergaenge_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "v91_alarm_outbox.jsonl"
            create_event(path, {
                "event_id": event_id_from("l", "v", "t"),
                "source_ref": "l",
                "severity": "INFO",
                "begruendung": "leer-demo",
            }, NOW)
            # Nur die Ereigniszeile, ohne Uebergaenge: Drill muss PASS bleiben (1 Event).
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["verdict"], "PASS")

    def test_fehlende_quelle_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AlarmOutboxError):
                drill.run_restore_drill(pathlib.Path(tmp) / "gibt-es-nicht.jsonl", NOW)

    def test_now_muss_timezone_aware_sein(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp)
            with self.assertRaises(AlarmOutboxError):
                drill.run_restore_drill(path, "2026-11-26T07:00:00")

    def test_result_schema_version_pinned(self):
        self.assertEqual(drill.SCHEMA_RESULT, "v91.alarm_outbox_restore_drill.result.v1")

    def test_grenzen_ehrlich_gespeichert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _fixture(tmp)
            result = drill.run_restore_drill(path, NOW, workdir=pathlib.Path(tmp) / "w")
            self.assertEqual(result["grenzen"]["scripted_vs_installed"], "SCRIPTED != INSTALLED")
            self.assertEqual(result["grenzen"]["hardware"], "NICHT_GEPRUEFT (kein Betrieb auf Betreiber-Hardware in diesem Lauf)")

    def test_cli_self_check_pass(self):
        proc = subprocess.run(
            [sys.executable, "-m", "controller.alarm_outbox_restore_drill", "--self-check"],
            cwd=str(pathlib.Path(__file__).resolve().parents[1]),
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["self_check"], "PASS")
        self.assertEqual(payload["echter_betriebs_restore"], "NICHT_GEPRUEFT")

    def test_cli_ohne_argumente_exit_2(self):
        proc = subprocess.run(
            [sys.executable, "-m", "controller.alarm_outbox_restore_drill"],
            cwd=str(pathlib.Path(__file__).resolve().parents[1]),
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)


class RestoreDrillDokuTests(unittest.TestCase):
    def test_doku_existiert(self):
        self.assertTrue(DOC.exists(), f"doku fehlt: {DOC}")

    def test_doku_pins(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in (
            "DRILL != ECHTER BETRIEBS-RESTORE",
            "SCRIPTED != INSTALLED",
            "read-only",
            "BEREITS_BEKANNT",
            "fail-closed",
            "ISOLATE_NOT_DESTROY",
            "REUSE",
            "NICHT_GEPRUEFT",
        ):
            self.assertIn(phrase, text)

    def test_doku_ascii_pure(self):
        text = DOC.read_text(encoding="utf-8")
        non_ascii = [c for c in text if ord(c) > 127]
        self.assertEqual(non_ascii, [])

    def test_doku_verweist_auf_520_und_quellmodul(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("#520", text)
        self.assertIn("alarm_outbox.py", text)


if __name__ == "__main__":
    unittest.main()
