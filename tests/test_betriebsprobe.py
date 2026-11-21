"""
Tests fuer scripts/v91_betriebsprobe.py (VIBE-XLVIII Phase 6):
Anforderungen: ohne echtes Ed25519-Backend verweigert die Probe
(REQUIREMENTS_MISSING, STUB != ECHT, KEIN Schein-Report); mit echtem
Backend (CI): vollstaendiger Durchlauf PROBE_PASSED mit allen Stufen
PASS, Report-Datei schreiben, --keep haelt Beweisverzeichnis, ohne
--keep wird aufgeraeumt (PROBE != BETRIEB bleibt dokumentiert).
"""
import importlib.util
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import v91_betriebsprobe

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None


class ProbeHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_probe(self, argv=None):
        buf_out = StringIO()
        argv = argv or []
        with mock.patch("sys.stdout", buf_out):
            code = v91_betriebsprobe.main([str(a) for a in argv])
        out = buf_out.getvalue().strip()
        payload = json.loads(out) if out else {}
        return code, payload


class RequirementsTests(ProbeHarness):
    def test_without_real_backend_probe_refuses(self):
        code, payload = self.run_probe([])
        if HAS_CRYPTO:
            self.skipTest("Backend vorhanden; Verweigerungspfad braucht CI-Gegenprobe nicht")
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "REQUIREMENTS_MISSING")
        self.assertIn("STUB != ECHT", payload["honesty"])
        self.assertNotIn("PROBE_PASSED", payload["status"])

    def test_report_file_written_even_on_refusal(self):
        report_file = self.tmp_path / "archiv" / "probe.json"
        code, _ = self.run_probe(["--report", report_file])
        self.assertTrue(report_file.is_file())
        data = json.loads(report_file.read_text(encoding="utf-8"))
        if HAS_CRYPTO:
            self.assertEqual(code, 0)
            self.assertEqual(data["status"], "PROBE_PASSED")
        else:
            self.assertEqual(code, 2)
            self.assertEqual(data["status"], "REQUIREMENTS_MISSING")

    def test_missing_backend_reason_recorded(self):
        if HAS_CRYPTO:
            self.skipTest("Backend vorhanden; Fehlgrund-Test nur ohne cryptography")
        _, payload = self.run_probe([])
        self.assertEqual(payload["backend"], "cryptography_module_missing")


@unittest.skipUnless(HAS_CRYPTO, "echtes Ed25519-Backend nicht verfuegbar (STUB != ECHT, SKIP != PASS)")
class FullProbeTests(ProbeHarness):
    def test_full_probe_passes_all_stages(self):
        code, payload = self.run_probe([])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PROBE_PASSED")
        stages = {s["stage"]: s["status"] for s in payload["stages"]}
        self.assertEqual(
            stages,
            {
                "KEYGEN": "PASS",
                "LIFECYCLE": "PASS",
                "WATCHDOG": "PASS",
                "INTEGRITY": "PASS",
            },
        )
        self.assertIn("PROBE != BETRIEB", payload["honesty"])

    def test_keep_preserves_probe_dir(self):
        workdir = self.tmp_path / "probebase"
        workdir.mkdir()
        code, payload = self.run_probe(["--keep", "--workdir", workdir])
        self.assertEqual(code, 0)
        kept = Path(payload["probe_dir"])
        self.assertTrue(kept.is_dir())
        self.assertTrue((kept / "probe-ledger.jsonl").is_file())
        self.assertTrue(kept.name.startswith("v91-probe-"))

    def test_default_run_cleans_up(self):
        workdir = self.tmp_path / "probebase"
        workdir.mkdir()
        code, payload = self.run_probe(["--workdir", workdir])
        self.assertEqual(code, 0)
        leftovers = list(workdir.glob("v91-probe-*"))
        self.assertEqual(leftovers, [])
        self.assertFalse(Path(payload["probe_dir"]).exists())

    def test_report_file_matches_run(self):
        report_file = self.tmp_path / "probe-report.json"
        code, payload = self.run_probe(["--report", report_file])
        self.assertEqual(code, 0)
        data = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], payload["status"])
        self.assertEqual(len(data["stages"]), len(payload["stages"]))


if __name__ == "__main__":
    unittest.main()
