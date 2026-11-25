"""Tests fuer controller/trockenlauf.py (pytest-freier Trockendurchlauf-Runner).

Pinnt den DREI-Klassen-Vertrag: PASS / FAIL (echter Bestandsfehler) /
ENV_FEHLT (ImportError BEVOR irgendein Test lief = Umgebungsgrenze,
UNKNOWN != ROT), honest exit-codes, self-check, AGATHON-Header."""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location("trockenlauf", REPO / "controller" / "trockenlauf.py")
tl = importlib.util.module_from_spec(_spec)
sys.modules["trockenlauf"] = tl
_spec.loader.exec_module(tl)


class TrockenlaufRunnerTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _mod(self, name: str, source: str) -> Path:
        p = self.tmp_path / name
        p.write_text(source, encoding="utf-8")
        return p

    def test_pass_modul(self):
        p = self._mod("test_okmod.py",
                      "import unittest\nclass T(unittest.TestCase):\n"
                      "    def test_ok(self):\n        self.assertTrue(True)\n"
                      "def test_plain():\n    assert True\n")
        r = tl.run_test_file(p, self.tmp_path)
        self.assertEqual(r.verdict, tl.VERDICT_PASS)
        self.assertEqual(r.tests_run, 2)

    def test_fail_modul_ist_bestandsfehler(self):
        p = self._mod("test_badmod.py",
                      "import unittest\nclass T(unittest.TestCase):\n"
                      "    def test_boom(self):\n        self.fail('doppelt gemoppelt haelt besser')\n")
        r = tl.run_test_file(p, self.tmp_path)
        self.assertEqual(r.verdict, tl.VERDICT_FAIL)
        self.assertEqual(r.failures, 1)

    def test_importfehler_ist_env_fehlt_nicht_fail(self):
        p = self._mod("test_envmod.py", "import fehlendes_paket_xyz_123\n")
        r = tl.run_test_file(p, self.tmp_path)
        self.assertEqual(r.verdict, tl.VERDICT_ENV_FEHLT)
        self.assertEqual(r.tests_run, 0)
        self.assertTrue(any("ImportError" in d for d in r.detail))

    def test_fixture_funktion_wird_nicht_geraten(self):
        p = self._mod("test_argmod.py", "def test_mit_fixture(fix):\n    pass\n")
        r = tl.run_test_file(p, self.tmp_path)
        self.assertEqual(r.verdict, tl.VERDICT_FAIL)  # unlauffaehig ohne pytest
        self.assertTrue(any("SKIP_ARGCOUNT" in d for d in r.detail))

    def test_leeres_modul_ist_fail_nicht_pass(self):
        p = self._mod("test_leer.py", "X = 1\n")
        r = tl.run_test_file(p, self.tmp_path)
        self.assertEqual(r.verdict, tl.VERDICT_FAIL)
        self.assertTrue(any("KEINE_TESTS_GEFUNDEN" in d for d in r.detail))

    def test_directory_report_verdicts_zaehlt(self):
        self._mod("test_a.py", "import unittest\nclass T(unittest.TestCase):\n    def test(self):\n        pass\n")
        self._mod("test_b.py", "import fehlend_xyz_123\n")
        report = tl.run_directory(self.tmp_path, self.tmp_path)
        self.assertEqual(report["files_checked"], 2)
        self.assertEqual(report["verdicts"][tl.VERDICT_PASS], 1)
        self.assertEqual(report["verdicts"][tl.VERDICT_ENV_FEHLT], 1)
        self.assertEqual(report["verdicts"][tl.VERDICT_FAIL], 0)

    def test_exit_codes(self):
        self._mod("test_a.py", "import unittest\nclass T(unittest.TestCase):\n    def test(self):\n        pass\n")
        self.assertEqual(tl.main(["--tests-dir", str(self.tmp_path), "--repo-root", str(self.tmp_path)]), 0)
        self._mod("test_c.py", "import unittest\nclass T(unittest.TestCase):\n    def test(self):\n        self.fail('x')\n")
        self.assertEqual(tl.main(["--tests-dir", str(self.tmp_path), "--repo-root", str(self.tmp_path)]), 1)
        self.assertEqual(tl.main(["--tests-dir", str(self.tmp_path / "gibtsnicht"), "--repo-root", str(self.tmp_path)]), 5)

    def test_self_check(self):
        rep = tl.self_check()
        self.assertEqual(rep["self_check"], "PASS")
        self.assertEqual(rep["reine_fiktion"], "KEINE")

    def test_agathon_header(self):
        content = (REPO / "controller" / "trockenlauf.py").read_text(encoding="utf-8")
        for line in ("V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)",
                     "STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)",
                     "AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft."):
            self.assertIn(line, content)


if __name__ == "__main__":
    unittest.main()
