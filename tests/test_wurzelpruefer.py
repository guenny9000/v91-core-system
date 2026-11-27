"""
Tests fuer controller/wurzelpruefer.py (7-Kriterien-Wurzelpruefung
mit Hash-Ketten-Protokoll, REUSE controller/ledger.py).

Fail-closed-Pins:
- BELEGT ohne Evidenz wird NICHT_GEPRUEFT (CLAIM != EVIDENCE).
- Fehlende Kriterien sind NICHT_GEPRUEFT, das Verdikt bleibt
  UNVOLLSTAENDIG (UNKNOWN != PASS, kein Default-PASS).
- PROBLEM (insbesondere beim Kriterium Schaden) blockiert.
- Manipulierte Kette verweigert den Start (HASH_KETTE != WORM,
  tamper-EVIDENT).
- Unbekannte Kriterien/Schluessel werden abgelehnt, nicht still
  ueberlesen.
Alle Tests sind self-contained (tempfile, kein /tmp-Festpfad,
kein Netz).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller.ledger import verify_chain
from controller.wurzelpruefer import (
    KRITERIEN,
    WurzelprueferError,
    main,
    pruefe,
    protokolliere,
)


def assessment_alle(status, evidenz="quelle-1"):
    return {
        "kriterien": {
            name: {"status": status, "evidenz": evidenz} for name in KRITERIEN
        }
    }


class WurzelprueferTest(unittest.TestCase):
    def test_alle_belegt_mit_evidenz_bestanden(self):
        ergebnis = pruefe(assessment_alle("BELEGT"))
        self.assertEqual(ergebnis["verdikt"], "BESTANDEN")
        self.assertEqual(ergebnis["pruefstatus"], {
            "bestanden": 7, "probleme": 0, "ungeprueft": 0})

    def test_belegt_ohne_evidenz_wird_nicht_geprueft(self):
        ergebnis = pruefe(assessment_alle("BELEGT", evidenz="  "))
        self.assertEqual(ergebnis["verdikt"], "UNVOLLSTAENDIG")
        self.assertEqual(ergebnis["pruefstatus"]["ungeprueft"], 7)

    def test_fehlendes_kriterium_ist_nicht_geprueft(self):
        ergebnis = pruefe({"kriterien": {}})
        self.assertEqual(ergebnis["verdikt"], "UNVOLLSTAENDIG")
        self.assertEqual(ergebnis["pruefstatus"]["ungeprueft"], 7)
        self.assertEqual(len(ergebnis["kriterien"]), 7)

    def test_schaden_problem_blockiert(self):
        a = assessment_alle("BELEGT")
        a["kriterien"]["schaden"] = {"status": "PROBLEM",
                                    "evidenz": "schaeden-nachweis"}
        ergebnis = pruefe(a)
        self.assertEqual(ergebnis["verdikt"], "BLOCKIERT")

    def test_anderes_problem_blockiert_auch(self):
        a = assessment_alle("BELEGT")
        a["kriterien"]["transparenz"] = {"status": "PROBLEM",
                                         "evidenz": "ins black box"}
        self.assertEqual(pruefe(a)["verdikt"], "BLOCKIERT")

    def test_blockiert_schlaegt_unvollstaendig(self):
        a = assessment_alle("NICHT_GEPRUEFT")
        a["kriterien"]["schaden"] = {"status": "PROBLEM", "evidenz": "b"}
        self.assertEqual(pruefe(a)["verdikt"], "BLOCKIERT")

    def test_unzulaessiger_status_fail_closed(self):
        a = assessment_alle("BELEGT")
        a["kriterien"]["nutzen"] = {"status": "PASSED", "evidenz": "x"}
        with self.assertRaises(WurzelprueferError):
            pruefe(a)

    def test_unbekanntes_kriterium_abgelehnt(self):
        a = assessment_alle("BELEGT")
        a["kriterien"]["wohlwollen"] = {"status": "BELEGT", "evidenz": "x"}
        with self.assertRaises(WurzelprueferError):
            pruefe(a)

    def test_kein_objekt_fail_closed(self):
        with self.assertRaises(WurzelprueferError):
            pruefe([])
        with self.assertRaises(WurzelprueferError):
            pruefe({"kriterien": 5})


class ProtokollKetteTest(unittest.TestCase):
    def test_protokoll_haengt_an_und_kette_gueltig(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_pfad = str(Path(tmp) / "wurzelpruefer_ledger.jsonl")
            ergebnis = pruefe(assessment_alle("BELEGT"))
            record = protokolliere(ergebnis, ledger_pfad, "2026-11-27T00:00:00Z")
            self.assertEqual(record["seq"], 0)
            report = verify_chain(ledger_pfad)
            self.assertTrue(report["chain_valid"], report)
            self.assertEqual(report["records_checked"], 1)
            gespeichert = json.loads(
                Path(ledger_pfad).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(gespeichert["payload"]["verdikt"], "BESTANDEN")

    def test_mehrere_laeufe_seq_lueckenlos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_pfad = str(Path(tmp) / "wurzelpruefer_ledger.jsonl")
            for i in range(3):
                protokolliere(pruefe(assessment_alle("BELEGT")),
                              ledger_pfad, f"2026-11-27T00:0{i}:00Z")
            report = verify_chain(ledger_pfad)
            self.assertTrue(report["chain_valid"], report)
            self.assertEqual(report["records_checked"], 3)

    def test_manipulierte_kette_verweigert_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_pfad = str(Path(tmp) / "wurzelpruefer_ledger.jsonl")
            protokolliere(pruefe(assessment_alle("BELEGT")),
                          ledger_pfad, "2026-11-27T00:00:00Z")
            zeilen = Path(ledger_pfad).read_text(encoding="utf-8").splitlines()
            rec = json.loads(zeilen[0])
            rec["payload"]["verdikt"] = "BESTANDEN"  # scheinbar harmlos
            rec["payload"]["pruefstatus"]["bestanden"] = 42  # Verfaelschung
            zeilen[0] = json.dumps(rec, sort_keys=True)
            Path(ledger_pfad).write_text("\n".join(zeilen) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                protokolliere(pruefe(assessment_alle("BELEGT")),
                              ledger_pfad, "2026-11-27T00:01:00Z")


class CliTest(unittest.TestCase):
    def test_cli_bestanden_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            a_pfad = Path(tmp) / "assessment.json"
            a_pfad.write_text(json.dumps(assessment_alle("BELEGT")),
                              encoding="utf-8")
            ledger_pfad = str(Path(tmp) / "ledger.jsonl")
            rc = main(["--assessment", str(a_pfad), "--ledger", ledger_pfad,
                       "--timestamp-utc", "2026-11-27T00:00:00Z"])
            self.assertEqual(rc, 0)
            self.assertTrue(verify_chain(ledger_pfad)["chain_valid"])

    def test_cli_blockiert_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = assessment_alle("BELEGT")
            a["kriterien"]["schaden"] = {"status": "PROBLEM", "evidenz": "b"}
            a_pfad = Path(tmp) / "assessment.json"
            a_pfad.write_text(json.dumps(a), encoding="utf-8")
            rc = main(["--assessment", str(a_pfad),
                       "--ledger", str(Path(tmp) / "ledger.jsonl"),
                       "--timestamp-utc", "2026-11-27T00:00:00Z"])
            self.assertEqual(rc, 1)

    def test_cli_unvollstaendig_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            a_pfad = Path(tmp) / "assessment.json"
            a_pfad.write_text(json.dumps({"kriterien": {}}), encoding="utf-8")
            rc = main(["--assessment", str(a_pfad),
                       "--ledger", str(Path(tmp) / "ledger.jsonl"),
                       "--timestamp-utc", "2026-11-27T00:00:00Z"])
            self.assertEqual(rc, 2)

    def test_cli_self_check_ehrlich_unvollstaendig(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = main(["--self-check", "--ledger",
                       str(Path(tmp) / "ledger.jsonl")])
            self.assertEqual(rc, 2)  # NICHT_GEPRUEFT ist der ehrliche Status

    def test_cli_verify_leere_kette_ok_manipulation_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_pfad = str(Path(tmp) / "ledger.jsonl")
            self.assertEqual(main(["--verify", "--ledger", ledger_pfad]), 0)
            protokolliere(pruefe(assessment_alle("BELEGT")),
                          ledger_pfad, "2026-11-27T00:00:00Z")
            zeilen = Path(ledger_pfad).read_text(encoding="utf-8").splitlines()
            rec = json.loads(zeilen[0])
            rec["hash"] = "f" * 64
            zeilen[0] = json.dumps(rec, sort_keys=True)
            Path(ledger_pfad).write_text("\n".join(zeilen) + "\n", encoding="utf-8")
            self.assertEqual(main(["--verify", "--ledger", ledger_pfad]), 3)

    def test_cli_unlesbares_assessment_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            a_pfad = Path(tmp) / "kaputt.json"
            a_pfad.write_text("{kein json", encoding="utf-8")
            rc = main(["--assessment", str(a_pfad),
                       "--ledger", str(Path(tmp) / "ledger.jsonl")])
            self.assertEqual(rc, 2)


class KanonPinTest(unittest.TestCase):
    def test_kriterien_kanon_7_festgesperrt(self):
        self.assertEqual(KRITERIEN, (
            "leistungsfaehigkeit", "nutzen", "schaden", "ressourcen",
            "transparenz", "sicherheit", "verbesserung"))

    def test_reihenfolge_schaden_vor_transparenz(self):
        # Dauerprotokoll-Prioritaet: Menschenleben/Schaden zuerst bewertet
        self.assertLess(KRITERIEN.index("schaden"),
                        KRITERIEN.index("transparenz"))


if __name__ == "__main__":
    unittest.main()
