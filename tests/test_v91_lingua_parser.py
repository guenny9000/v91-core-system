"""Tests fuer den V91-LINGUA Referenzparser (Stufe 3, Schritt 2,
docs/V91-LINGUA-GRAMMATIK.md). Kodex-Muster: Doku existiert und ist
klein und ASCII-pure, Subordination an GRAMMATIK/KERN/Anhang
gepinnt, Beispiel des KERNs pariert, Sicherheitsblock atomar,
Determinismus, PFLICHT-NEGATIVE TESTS (beschaedigt, unvollstaendig,
gefaelscht, widerspruechlich muessen zuverlaessig scheitern),
KEIN Netz im Modulkern, KEINE Befugnis aus Sprache, self-check CLI
ehrlich NICHT_GEPRUEFT."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.lingua_parser import (  # noqa: E402
    EXAMPLE,
    LinguaParseError,
    MANDATORY_KEYS,
    parse,
    validate,
)
import controller.lingua_parser as lingua_modul  # noqa: E402

DOC = ROOT / "docs" / "V91-LINGUA-GRAMMATIK.md"
KERN = ROOT / "docs" / "V91-LINGUA-KERN.md"
ANHANG = ROOT / "docs" / "V91-LINGUA-SICHERHEITS-ANHANG.md"

MINIMAL = "TASK:042\nSTATE:VER\nEVID:2/4 ::ledger/x\nNEXT:HOLD\n"


class V91LinguaParserPositiveTests(unittest.TestCase):
    def test_beispiel_aus_kern_pariert(self):
        ergebnis = parse(EXAMPLE)
        self.assertEqual(ergebnis["task"], "042")
        self.assertEqual(ergebnis["state"], "UNV")
        self.assertEqual(ergebnis["evid"], {"n": 0, "m": 4, "beleg": "offen"})
        self.assertEqual(ergebnis["next"], "VERIFY")
        self.assertEqual(ergebnis["goal"], "SECURITY")
        self.assertEqual(ergebnis["action"], "AUDIT")
        self.assertEqual(ergebnis["gate"], "HOLD")
        self.assertEqual(ergebnis["befugnis"], "KEINE")
        self.assertEqual(ergebnis["schema"], "lingua.parser.v1")

    def test_minimalnachricht_pariert(self):
        ergebnis = parse(MINIMAL)
        self.assertEqual(ergebnis["task"], "042")
        self.assertEqual(ergebnis["state"], "VER")
        self.assertEqual(ergebnis["evid"]["n"], 2)
        self.assertEqual(ergebnis["next"], "HOLD")
        self.assertNotIn("version", ergebnis)

    def test_sicherheitsblock_vollstaendig_pariert(self):
        nachricht = (
            "VERSION:1\nFROM:AGENT-A\nTO:AGENT-B\n"
            "TIME:2026-11-26T10:00:00Z\nMSGID:MSG-17\n"
            "TASK:A-1\nSTATE:UNK\nEVID:2/2 ::b\nNEXT:REPORT\n"
        )
        ergebnis = parse(nachricht)
        self.assertEqual(ergebnis["version"], 1)
        self.assertEqual(ergebnis["from"], "AGENT-A")
        self.assertEqual(ergebnis["to"], "AGENT-B")
        self.assertEqual(ergebnis["msgid"], "MSG-17")

    def test_evid_leerzeichen_nur_in_positionssyntax(self):
        self.assertTrue(validate("TASK:A\nSTATE:VER\nEVID:2/4::x\nNEXT:HOLD")["gueltig"])
        self.assertTrue(validate("TASK:A\nSTATE:VER\nEVID:2/4 ::x\nNEXT:HOLD")["gueltig"])
        self.assertTrue(validate("TASK:A\nSTATE:VER\nEVID:2/4:: x\nNEXT:HOLD")["gueltig"])

    def test_determinismus(self):
        a = json.dumps(parse(EXAMPLE), sort_keys=True)
        b = json.dumps(parse(EXAMPLE), sort_keys=True)
        self.assertEqual(a, b)

    def test_validate_ok(self):
        ergebnis = validate(EXAMPLE)
        self.assertTrue(ergebnis["gueltig"])
        self.assertEqual(ergebnis["ergebnis"]["next"], "VERIFY")


class V91LinguaParserNegativTests(unittest.TestCase):
    """NEGATIVE TESTS SIND PFLICHT (Anhang #572): beschaedigte,
    unvollstaendige, gefaelschte und widerspruechliche Nachrichten
    muessen ZUVERLAESSIG SCHEITERN. KEINE stille Reparatur."""

    def _fail(self, text, code):
        ergebnis = validate(text)
        self.assertFalse(ergebnis["gueltig"], text)
        self.assertEqual(ergebnis["code"], code, text)
        self.assertTrue(len(ergebnis["grund"]) > 0)
        return ergebnis

    def test_e01_input_keine_zeichenkette(self):
        with self.assertRaises(LinguaParseError) as ctx:
            parse(42)
        self.assertEqual(ctx.exception.code, "E01")

    def test_e02_cr_und_nicht_ascii_beschaedigen(self):
        self._fail("TASK:A\r\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E02")
        self._fail(
            "TASK:\u00c4\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E02"
        )

    def test_e03_leere_nachricht(self):
        self._fail("", "E03")

    def test_e04_leerzeile_innen(self):
        self._fail("TASK:A\n\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E04")
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD\n\n", "E04")

    def test_e05_zeile_ohne_doppelpunkt(self):
        self._fail("TASK A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E05")

    def test_e06_schluesselmuster(self):
        self._fail("task:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E06")
        self._fail("T ASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E06")

    def test_e07_unbekannter_schluessel_gefaelscht(self):
        self._fail("AUTH:JA\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E07")

    def test_e08_doppelter_schluessel(self):
        self._fail("TASK:A\nTASK:B\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E08")

    def test_e09_wert_leer(self):
        self._fail("TASK:\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E09")

    def test_e10_doppelpunkt_im_wert(self):
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:VER:IFY", "E10")

    def test_e11_pflichtfelder_fehlen(self):
        voll = ["TASK:A", "STATE:VER", "EVID:2/4 ::b", "NEXT:HOLD"]
        for feld in MANDATORY_KEYS:
            rest = [zeile for zeile in voll if not zeile.startswith(feld + ":")]
            self._fail("\n".join(rest), "E11")

    def test_e12_werte_ungueltig(self):
        base = "TASK:A\nSTATE:%s\nEVID:1/1 ::b\nNEXT:HOLD"
        for wert in ("WAGLICH", "BELEGT", "VERIFIZIERT"):
            self._fail(base % wert, "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:FLY", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nGATE:START\nNEXT:HOLD", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nGOAL:REICHTUM\nNEXT:HOLD", "E12")
        self._fail("TASK:-1\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E12")
        self._fail("TASK:A B\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD\nVERSION:x", "E12")

    def test_e12_evid_muster(self):
        self._fail("TASK:A\nSTATE:VER\nEVID:2/2\nNEXT:HOLD", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:2/2 ::\nNEXT:HOLD", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:2/4 ::a b\nNEXT:HOLD", "E12")
        self._fail("TASK:A\nSTATE:VER\nEVID:2/4 ::  x\nNEXT:HOLD", "E12")

    def test_e13_evid_bereich_widerspruechlich(self):
        self._fail("TASK:A\nSTATE:VER\nEVID:5/4 ::b\nNEXT:HOLD", "E13")

    def test_e14_zeit_ungueltig(self):
        base = "TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD\nTIME:%s"
        for wert in (
            "2026-02-30T10:00:00Z",
            "2026-11-26T25:00:00Z",
            "2026-11-26 10:00:00Z",
            "26.11.2026",
        ):
            self._fail(base % wert, "E14")

    def test_e15_sicherheitsblock_nur_teilweise(self):
        self._fail("TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD\nVERSION:1", "E15")
        self._fail(
            "TASK:A\nSTATE:VER\nEVID:1/1 ::b\nNEXT:HOLD\nFROM:AGENT-A", "E15"
        )

    def test_kein_teilergebnis_bei_fehler(self):
        ergebnis = validate("TASK:A\nSTATE:VER")
        self.assertNotIn("ergebnis", ergebnis)
        self.assertTrue(ergebnis["zeile"] >= 0)
        self.assertTrue(len(ergebnis["grund"]) > 0)


class V91LinguaParserGrenzenTests(unittest.TestCase):
    def test_kein_netz_im_modulkern(self):
        quelle = pathlib.Path(lingua_modul.__file__).read_text(encoding="utf-8")
        for verboten in (
            "import socket",
            "import requests",
            "http.client",
            "urllib",
            "subprocess",
        ):
            self.assertNotIn(verboten, quelle, verboten)

    def test_self_check_cli(self):
        proc = subprocess.run(
            [sys.executable, "-m", "controller.lingua_parser", "--self-check"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["self_check"], "PASS")
        self.assertEqual(out["befugnis"], "KEINE")
        self.assertEqual(out["signaturpruefung"], "NICHT_IMPLEMENTIERT")
        self.assertEqual(out["modelltests"], "NICHT_GEPRUEFT")
        self.assertEqual(out["kooperation"], "OFFEN")

    def test_grammatik_doku_pins(self):
        self.assertTrue(DOC.is_file(), "Grammatik fehlt")
        self.assertLess(DOC.stat().st_size, 8 * 1024)
        text = DOC.read_text(encoding="utf-8")
        self.assertEqual([], [c for c in text if ord(c) > 127])
        for schluessel in (
            "TASK",
            "STATE",
            "EVID",
            "NEXT",
            "GOAL",
            "ACTION",
            "GATE",
            "VERSION",
            "FROM",
            "TO",
            "TIME",
            "MSGID",
        ):
            self.assertIn(schluessel, text, schluessel)
        for code in range(1, 16):
            self.assertIn("E%02d" % code, text)
        for nadel in (
            "SPRACHE SCHAFFT KEINE BEFUGNIS",
            "NEGATIVE TESTS SIND PFLICHT",
            "SIGNATUR",
            "NICHT_IMPLEMENTIERT",
            "MODELLTESTS",
            "KOOPERATION",
            "OFFEN",
            "fail-closed",
        ):
            self.assertIn(nadel, text, nadel)

    def test_status_nachtraege_in_kern_und_anhang(self):
        kern = KERN.read_text(encoding="utf-8")
        anhang = ANHANG.read_text(encoding="utf-8")
        self.assertIn("V91-LINGUA-GRAMMATIK", kern)
        self.assertIn("V91-LINGUA-GRAMMATIK", anhang)


if __name__ == "__main__":
    unittest.main()
