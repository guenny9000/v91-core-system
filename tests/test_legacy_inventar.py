"""
Tests fuer das MAX-BEST Legacy-Inventar (VIBE-LXXVII).

Pruefen das Struktur-Gate (pruefe), die CLI (main), die
Report-Erzeugung und die Kern-Invarianten aus Issue #276:
UNKNOWN != PASS, read-only (INVENTAR != REMEDIATION),
ASCII-Gate ueber ALLE Felder, KEINE_STUMME_KORREKTUR.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller.kreislauf_status import KreislaufInputError
from controller.legacy_inventar import (
    EVIDENZ_STATUSSE,
    FELDER,
    KATEGORIEN,
    LIFECYCLES,
    VERDICT_ABGELEHNT,
    VERDICT_INVENTARISIERT,
    pruefe,
    format_text_report,
    lade_inventar,
    main,
)


def _gueltig(id_extra=""):
    return {
        "id": "inv-test%s" % id_extra,
        "komponente": "v91 core laufzeit",
        "kategorie": "SOFTWARE",
        "owner": "betreiber",
        "evidenz_status": "OBSERVED",
        "evidenz_quelle": "betriebsaufzeichnung",
        "evidenz_zeitpunkt": "2026-11-22",
        "lifecycle": "SUPPORTED",
        "kritischer_dienst": "NEIN",
        "grenzen": "nur test",
    }


def test_inventar_komplett_gueltig():
    report = pruefe([_gueltig()])
    assert report["verdict"] == VERDICT_INVENTARISIERT
    assert report["eintraege_gueltig"] == 1
    assert report["eintraege_ungueltig"] == 0
    assert report["eintraege"][0]["id"] == "inv-test"
    assert "fehlerhafte" not in report


def test_ids_eindeutig_erzwungen():
    report = pruefe([_gueltig(), _gueltig()])
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert "mehrfach vergeben" in "; ".join(report["fehlerhafte"][0]["gruende"])


def test_leere_liste_abgelehnt():
    assert pruefe([])["verdict"] == VERDICT_ABGELEHNT


def test_bare_json_konstante_abgelehnt():
    report = pruefe([True, 7, None])
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert len(report["fehlerhafte"]) == 3
    for fehler in report["fehlerhafte"]:
        assert fehler["id"] == "<ohne id>"


def test_nicht_objekt_abgelehnt():
    report = pruefe(["text-eintrag"])
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert "kein json-objekt" in "; ".join(report["fehlerhafte"][0]["gruende"])


def test_fehlendes_feld_abgelehnt():
    eintrag = _gueltig()
    del eintrag["owner"]
    report = pruefe([eintrag])
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert "owner" in report["fehlerhafte"][0]["gruende"][0]


def test_leeres_objekt_mit_gruenden():
    report = pruefe([{}])
    assert report["verdict"] == VERDICT_ABGELEHNT
    gruende = report["fehlerhafte"][0]["gruende"]
    assert len(gruende) >= len(FELDER)
    assert report["fehlerhafte"][0]["id"] == "<fehlt>"


def test_non_ascii_in_id_und_quelle_abgelehnt():
    for feld in ("id", "evidenz_quelle"):
        eintrag = _gueltig()
        eintrag[feld] = "bae\xe4r"
        report = pruefe([eintrag])
        assert report["verdict"] == VERDICT_ABGELEHNT, feld
        assert any("non-ascii" in g for g in report["fehlerhafte"][0]["gruende"]), feld


def test_wertebereiche_erzwungen():
    for feld, bereich in (("kategorie", KATEGORIEN),
                          ("lifecycle", LIFECYCLES),
                          ("evidenz_status", EVIDENZ_STATUSSE),
                          ("kritischer_dienst", ("JA", "NEIN"))):
        eintrag = _gueltig()
        eintrag[feld] = "KEIN_WERT"
        report = pruefe([eintrag])
        assert report["verdict"] == VERDICT_ABGELEHNT, feld
        assert any("wertebereichs" in g for g in report["fehlerhafte"][0]["gruende"]), feld


def test_unknown_evidenz_kein_lifecycle():
    eintrag = _gueltig()
    eintrag["evidenz_status"] = "UNKNOWN"
    assert pruefe([eintrag])["verdict"] == VERDICT_ABGELEHNT
    eintrag["lifecycle"] = "UNKNOWN"
    report = pruefe([eintrag])
    assert report["verdict"] == VERDICT_INVENTARISIERT


def test_claim_und_disputed_kein_lifecycle():
    for status in ("CLAIM", "DISPUTED"):
        eintrag = _gueltig()
        eintrag["evidenz_status"] = status
        report = pruefe([eintrag])
        assert report["verdict"] == VERDICT_ABGELEHNT, status
        assert any("UNKNOWN != PASS" in g
                   for g in report["fehlerhafte"][0]["gruende"]), status


def test_kritischer_dienst_warnung():
    eintrag = _gueltig()
    eintrag["kritischer_dienst"] = "JA"
    eintrag["lifecycle"] = "ISOLATE"
    report = pruefe([eintrag])
    assert report["verdict"] == VERDICT_INVENTARISIERT
    assert len(report["warnungen"]) == 1
    assert "ISOLATE_NOT_DESTROY" in report["warnungen"][0]


def test_verteilungen_korrekt():
    eintraege = [_gueltig("a"), _gueltig("b"), _gueltig("c")]
    eintraege[1]["lifecycle"] = "REPLACE"
    eintraege[2]["evidenz_status"] = "VERIFIED"
    report = pruefe(eintraege)
    assert report["lifecycle_verteilung"]["SUPPORTED"] == 2
    assert report["lifecycle_verteilung"]["REPLACE"] == 1
    assert report["evidenz_verteilung"]["VERIFIED"] == 1


def test_report_deterministisch_ascii():
    report = pruefe([_gueltig()])
    text = format_text_report(report)
    text.encode("ascii")
    assert text == format_text_report(json.loads(json.dumps(report)))
    assert "verdict: INVENTARISIERT" in text


def test_report_fehlertolerant_ohne_crash():
    text = format_text_report({"verdict": VERDICT_ABGELEHNT})
    assert "<fehlt>" in text
    text2 = format_text_report({"fehlerhafte": [{}]})
    assert "<ohne id>" in text2


def test_lade_inventar_fail_closed():
    pfad = Path(tempfile.mkdtemp()) / "inv.json"
    pfad.write_text("{\"id\": 1}", "utf-8")
    try:
        lade_inventar(pfad)
        assert False, "KreislaufInputError erwartet"
    except KreislaufInputError:
        pass
    pfad2 = pfad.with_name("inv2.json")
    pfad2.write_text(json.dumps([_gueltig()]), encoding="utf-8")
    assert lade_inventar(pfad2)[0]["id"] == "inv-test"


def test_lade_inventar_keine_liste():
    pfad = Path(tempfile.mkdtemp()) / "inv.json"
    pfad.write_text("{\"a\": 1}", encoding="utf-8")
    try:
        lade_inventar(pfad)
        assert False
    except KreislaufInputError as exc:
        assert "keine liste" in str(exc)


def test_cli_valid_exit0_und_report_dir():
    d = Path(tempfile.mkdtemp())
    inv = d / "inv.json"
    inv.write_text(json.dumps([_gueltig()]), encoding="utf-8")
    out = d / "reports"
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([str(inv), "--report-dir", str(out)])
    assert code == 0
    assert "INVENTARISIERT" in buf.getvalue()
    assert (out / "legacy_inventar.txt").is_file()
    geladen = json.loads((out / "legacy_inventar.json").read_text(encoding="ascii"))
    assert geladen["verdict"] == VERDICT_INVENTARISIERT


def test_cli_invalid_exit1():
    d = Path(tempfile.mkdtemp())
    inv = d / "inv.json"
    inv.write_text(json.dumps([{"bad": 1}]), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([str(inv)])
    assert code == 1
    assert "ABGELEHNT" in buf.getvalue()


def test_cli_input_error_exit3():
    d = Path(tempfile.mkdtemp())
    buf = io.StringIO()
    code = main([str(d / "fehlt.json")])
    assert code == 3
