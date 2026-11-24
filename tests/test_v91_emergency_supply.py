"""Tests fuer scripts/v91_emergency_supply.py (Grundversorgungs-Check).

Fremdbeitrag 25.11.2026, mit zwei Korrekturen gegenueber dem Entwurf
als gepinnte Regressionen:
1. LEDGER-SCHUTZ: Der Entwurf schrieb in 'v91_bridge_inbox.jsonl'
   (kern_bridge-Ledger #496) - hierfuer gilt NO_DUPLICATE_SYSTEMS,
   der eigene Alert-Ledger darf fremde Semantik NICHT beruehren.
2. BOOL-FALLE: days_remaining: true ist bool (int-Subtyp) und wurde
   vom Entwurf als 1.0 Tage gewertet - fail-closed bleibt hier None
   (BOOLEAN != ZAHL, UNKNOWN != PASS).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v91_emergency_supply.py"
spec = importlib.util.spec_from_file_location("v91_emergency_supply", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EnvIsolation(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("EMERGENCY_MANIFEST", "EMERGENCY_LEDGER",
                                 "EMERGENCY_REQUIRED_ITEMS",
                                 "EMERGENCY_WEBHOOK_URL",
                                 "EMERGENCY_WEBHOOK_TIMEOUT_S")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run(self, env):
        for k, v in env.items():
            os.environ[k] = v
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.run_check()
        out = {}
        text = buf.getvalue().strip()
        if text:
            try:
                out = json.loads(text)
            except json.JSONDecodeError:
                out = {"raw": text}
        return rc, out


class FailClosedTests(EnvIsolation):
    def test_manifest_fehlt_unknown_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run({
                "EMERGENCY_MANIFEST": str(Path(tmp) / "none.json"),
                "EMERGENCY_LEDGER": str(Path(tmp) / "l.jsonl")})
            self.assertEqual(rc, 1)
            self.assertEqual(out["status"], "UNKNOWN")
            self.assertEqual(out["issue_count"], 4)
            self.assertTrue(out["ledger_written"])

    def test_korruptes_json_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "m.json"
            m.write_text("{broken", encoding="utf-8")
            rc, out = self._run({
                "EMERGENCY_MANIFEST": str(m),
                "EMERGENCY_LEDGER": str(Path(tmp) / "l.jsonl")})
            self.assertEqual(rc, 1)
            self.assertEqual(out["status"], "UNKNOWN")

    def test_missing_ignoriert_kein_pass(self):
        r = mod._evaluate_item("x", {"status": "not_a_known_word"})
        self.assertEqual(r["state"], "UNKNOWN")

    def test_unsupported_entry_type_unknown(self):
        r = mod._evaluate_item("x", 42)
        self.assertEqual(r["state"], "UNKNOWN")
        self.assertEqual(r["reason"], "unsupported_entry_type")

    def test_days_zero_bei_ok_ist_missing(self):
        r = mod._evaluate_item("x", {"status": "ok", "days_remaining": 0})
        self.assertEqual(r["state"], "MISSING")
        self.assertEqual(r["reason"], "zero_days_remaining")


class BoolFallenTests(EnvIsolation):
    def test_days_true_wird_nicht_als_1_0_gewertet(self):
        """Der Entwurf wertete days_remaining: true als 1.0 (float(True))."""
        r = mod._evaluate_item("x", {"status": "ok", "days_remaining": True})
        self.assertIsNone(r["days_remaining"],
                          "BOOLEAN != ZAHL: true darf kein 1.0-Tage-Wert sein")

    def test_eintrag_bool_true_ok_false_missing(self):
        self.assertEqual(mod._evaluate_item("a", True)["state"], "OK")
        self.assertEqual(mod._evaluate_item("a", False)["state"], "MISSING")


class LedgerSchutzTests(EnvIsolation):
    def test_default_ledger_nicht_kern_bridge_inbox(self):
        """NO_DUPLICATE_SYSTEMS: kern_bridge-Inbox #496 bleibt unberuehrt."""
        self.assertNotIn("bridge_inbox", str(mod.DEFAULT_LEDGER_PATH))
        self.assertEqual(mod.DEFAULT_LEDGER_PATH.name, "emergency_alerts.jsonl")

    def test_dedup_unterdrueckt_identischen_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = str(Path(tmp) / "l.jsonl")
            env = {"EMERGENCY_MANIFEST": str(Path(tmp) / "none.json"),
                   "EMERGENCY_LEDGER": led}
            rc1, out1 = self._run(dict(env))
            rc2, out2 = self._run(dict(env))
            self.assertEqual((rc1, rc2), (1, 1))
            self.assertFalse(out1["duplicate_suppressed"])
            self.assertTrue(out2["duplicate_suppressed"])
            lines = [ln for ln in Path(led).read_text(
                encoding="utf-8").split("\n") if ln.strip()]
            self.assertEqual(len(lines), 1,
                            "Dedup-Verletzung: identischer Alert zweimal")

    def test_ok_manifest_schreibt_kein_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "m_ok.json"
            m.write_text(json.dumps({
                "food": {"status": "ok", "days_remaining": 14},
                "water": {"status": "available"},
                "medical_kit": True,
                "comms": {"status": "ready"}}), encoding="utf-8")
            led = Path(tmp) / "never.jsonl"
            rc, out = self._run({
                "EMERGENCY_MANIFEST": str(m),
                "EMERGENCY_LEDGER": str(led)})
            self.assertEqual(rc, 0)
            self.assertEqual(out["status"], "OK")
            self.assertFalse(out["ledger_appended"])
            self.assertFalse(led.exists(),
                             "OK-Fall darf keinen Ledger-Eintrag erzeugen")


class WebhookTests(EnvIsolation):
    def test_invalides_schema_fail_ledger_trotzdem_geschrieben(self):
        """Netz-Ausgang nur bei gueltigem Schema; Befund-Eintrag bleibt."""
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run({
                "EMERGENCY_MANIFEST": str(Path(tmp) / "none.json"),
                "EMERGENCY_LEDGER": str(Path(tmp) / "l.jsonl"),
                "EMERGENCY_WEBHOOK_URL": "ftp://kein-https"})
            self.assertEqual(rc, 1)
            self.assertTrue(out["ledger_written"],
                            "Webhook-Fehler darf lokalen Befund nie verhindern")
            self.assertIn("invalid_webhook_scheme", out["webhook"])

    def test_webhook_bei_doppelt_unterdrueckt(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"EMERGENCY_MANIFEST": str(Path(tmp) / "none.json"),
                   "EMERGENCY_LEDGER": str(Path(tmp) / "l.jsonl"),
                   "EMERGENCY_WEBHOOK_URL": "https://example.invalid/hook"}
            self._run(dict(env))
            rc, out = self._run(dict(env))
            self.assertEqual(out["webhook"], "skipped_duplicate",
                             "Duplikat darf nie erneut senden")


if __name__ == "__main__":
    unittest.main()
