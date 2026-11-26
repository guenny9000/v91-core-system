"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests fuer controller/dependency_audit.py (Issue #591).
Self-contained: ausschliesslich stdlib + tempfile, KEIN Netz.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from controller.dependency_audit import (  # noqa: E402
    DependencyAuditError,
    audit,
    collect_py_imports,
    main,
    parse_requirements,
)


def _repo_schreiben(wurzel: str, requirements: str, dateien: dict | None = None) -> str:
    os.makedirs(wurzel, exist_ok=True)
    req = os.path.join(wurzel, "requirements.txt")
    with open(req, "w", encoding="utf-8") as fh:
        fh.write(requirements)
    for relativ, inhalt in (dateien or {}).items():
        pfad = os.path.join(wurzel, relativ)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as fh:
            fh.write(inhalt)
    return req


class ParseRequirementsTest(unittest.TestCase):
    def test_kommentare_und_leerzeilen_ignoriert(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = _repo_schreiben(
                os.path.join(tmp, "r"),
                "# Kommentar\n\nnumpy>=1.26,<2.0\n",
            )
            ergebnis = parse_requirements(req)
            self.assertEqual(len(ergebnis), 1)
            self.assertEqual(ergebnis[0].name, "numpy")

    def test_versionsspezifikationen_werden_abgetrennt(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = _repo_schreiben(os.path.join(tmp, "r"), "cryptography>=42.0,<47.0 ; python_version>='3.11'\n")
            ergebnis = parse_requirements(req)
            self.assertEqual(ergebnis[0].name, "cryptography")
            self.assertEqual(ergebnis[0].spezifikation, "cryptography>=42.0,<47.0 ; python_version>='3.11'")

    def test_r_option_folgt_zieldatei(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            os.makedirs(wurzel)
            with open(os.path.join(wurzel, "base.txt"), "w", encoding="utf-8") as fh:
                fh.write("pytest>=8.0\n")
            req = _repo_schreiben(wurzel, "-r base.txt\n")
            ergebnis = parse_requirements(req)
            self.assertEqual([r.name for r in ergebnis], ["pytest"])

    def test_fehlende_datei_fail_closed(self):
        with self.assertRaises(DependencyAuditError):
            parse_requirements("/nicht/vorhanden/requirements.txt")

    def test_r_ohne_ziel_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = _repo_schreiben(os.path.join(tmp, "r"), "-r\n")
            with self.assertRaises(DependencyAuditError):
                parse_requirements(req)

    def test_ungueltige_option_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = _repo_schreiben(os.path.join(tmp, "r"), "-e git+https://example.invalid/x.git\n")
            with self.assertRaises(DependencyAuditError):
                parse_requirements(req)

    def test_ungueltiger_name_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = _repo_schreiben(os.path.join(tmp, "r"), "paket mit leerzeichen>=1\n")
            with self.assertRaises(DependencyAuditError):
                parse_requirements(req)


class CollectImportsTest(unittest.TestCase):
    def test_import_und_from_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(
                wurzel,
                "numpy>=1.26\n",
                {
                    "a.py": "import numpy\nfrom cryptography.hazmat import x\n",
                    "b.py": "from numpy import linalg\n",
                    "c.py": "import redis.asyncio as r\n",
                },
            )
            funde = collect_py_imports(wurzel)
            self.assertIn("numpy", funde)
            self.assertIn("cryptography", funde)
            self.assertIn("redis", funde)
            self.assertEqual(len(set(funde["numpy"])), 2)

    def test_relativer_from_import_zaehlt_nicht_als_fremdpaket(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(wurzel, "x>=1\n", {"m.py": "from . import lokal\nimport x\n"})
            funde = collect_py_imports(wurzel)
            self.assertNotIn(". import lokal", str(funde))
            self.assertIn("x", funde)

    def test_syntaxfehler_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(wurzel, "x>=1\n", {"kaputt.py": "def (:\n"})
            with self.assertRaises(DependencyAuditError):
                collect_py_imports(wurzel)

    def test_git_und_pycache_werden_ausgespart(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(wurzel, "x>=1\n", {"x.py": "import x\n"})
            os.makedirs(os.path.join(wurzel, ".git"))
            with open(os.path.join(wurzel, ".git", "hook.py"), "w", encoding="utf-8") as fh:
                fh.write("import boese\n")
            funde = collect_py_imports(wurzel)
            self.assertNotIn("boese", funde)


class AuditVerdikteTest(unittest.TestCase):
    def test_genutzt_und_nicht_gefunden(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(
                wurzel,
                "numpy>=1.26\nredis>=5.0\n",
                {"mod.py": "import numpy\n", "README.md": "redis wird in Doku erwaehnt\n"},
            )
            bericht = audit(wurzel)
            verdikte = {b["paket"]: b for b in bericht["befunde"]}
            self.assertEqual(verdikte["numpy"]["verdikt"], "GENUTZT")
            self.assertEqual(verdikte["redis"]["verdikt"], "NICHT_GEFUNDEN_IN_PY")
            self.assertIn("NICHT_GEFUNDEN != UNGENUTZT", verdikte["redis"]["notiz"])
            # HINWEIS != NUTZUNG: README-Nennung ist kein Nutzungsnachweis
            self.assertIn("README.md", verdikte["redis"]["hinweise_nicht_py"][0])
            self.assertEqual(verdikte["redis"]["anzahl_import_fundstellen"], 0)

    def test_import_override_erkannt(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(wurzel, "pillow>=10\n", {"bild.py": "import PIL.Image\n"})
            bericht = audit(wurzel)
            self.assertEqual(bericht["befunde"][0]["verdikt"], "GENUTZT")

    def test_grenzen_im_bericht(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            _repo_schreiben(wurzel, "numpy>=1.26\n", {"m.py": "import numpy\n"})
            bericht = audit(wurzel)
            for grenze in ("REPORT != DELETE", "NICHT_GEFUNDEN != UNGENUTZT", "HINWEIS != NUTZUNG"):
                self.assertIn(grenze, bericht["grenzen"])

    def test_fundstellen_gedeckelt(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "r")
            dateien = {"m%02d.py" % i: "import numpy\n" for i in range(30)}
            _repo_schreiben(wurzel, "numpy>=1.26\n", dateien)
            bericht = audit(wurzel)
            self.assertEqual(len(bericht["befunde"][0]["import_fundstellen"]), 20)
            self.assertEqual(bericht["befunde"][0]["anzahl_import_fundstellen"], 20)


class CliTest(unittest.TestCase):
    def test_self_check_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(wurzel, "pkg"))
            with open(os.path.join(wurzel, "requirements.txt"), "w", encoding="utf-8") as fh:
                fh.write("numpy>=1.26\nredis>=5.0\n")
            with open(os.path.join(wurzel, "pkg", "mod.py"), "w", encoding="utf-8") as fh:
                fh.write("import numpy\n")
            exit_code = main(["--path", wurzel])
            self.assertEqual(exit_code, 0)

    def test_self_check_flag_exit_null(self):
        self.assertEqual(main(["--self-check"]), 0)

    def test_messfehler_exit_eins(self):
        self.assertEqual(main(["--path", "/nicht/vorhanden/ganz/sicher"]), 1)


if __name__ == "__main__":
    unittest.main()
