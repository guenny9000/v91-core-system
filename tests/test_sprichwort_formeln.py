"""Tests fuer die Sprichwort-/Redewendung-Formel-Registry (VIBE-LXXV).

Pruefen das Struktur-Gate (pruefe), die CLI (main) und die
Report-Erzeugung. Keine Stumme Korrektur: jedes Fehlverhalten
muss sichtbar abgelehnt werden.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller.sprichwort_formeln import (
    BEREICHE,
    DEFAULT_FORMELN,
    FELDER,
    KreislaufInputError,
    format_text_report,
    lade_ergaenzung,
    main,
    pruefe,
)


def _gueltig(id_extra=""):
    return {
        "id": "test-formel%s" % id_extra,
        "redewendung": "Wer misst, misst Mist",
        "formel": "x = 1",
        "erklaerung": "test",
        "quelle": "test",
        "bereich": "SPRICHWORT",
        "grenzen": "nur test",
    }


def test_registry_komplett_gueltig():
    report = pruefe(DEFAULT_FORMELN)
    assert report["formeln_gesamt"] == 41
    assert report["formeln_ungueltig"] == 0
    assert report["verdict"] == "REGISTRIERT"
    assert report["formeln_gueltig"] == 41


def test_ids_eindeutig():
    ids = [eintrag["id"] for eintrag in DEFAULT_FORMELN]
    assert len(ids) == len(set(ids))


def test_leere_liste_abgelehnt():
    assert pruefe([])["verdict"] == "ABGELEHNT"


def test_doppelte_id_abgelehnt():
    report = pruefe([_gueltig(), _gueltig()])
    assert report["verdict"] == "ABGELEHNT"
    gruende = report["fehlerhafte"][0]["gruende"]
    assert any("doppelte id" in g for g in gruende)


def test_fehlendes_feld_abgelehnt():
    eintrag = _gueltig()
    del eintrag["grenzen"]
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert "feld grenzen fehlt oder ist leer" in \
        report["fehlerhafte"][0]["gruende"]


def test_falscher_bereich_abgelehnt():
    eintrag = _gueltig()
    eintrag["bereich"] = "ESOTERIK"
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert any("bereich" in g for g in report["fehlerhafte"][0]["gruende"])


def test_nicht_objekt_abgelehnt():
    report = pruefe(["kein objekt"])
    assert report["verdict"] == "ABGELEHNT"
    assert report["fehlerhafte"][0]["id"] == "<kein objekt>"


def test_nicht_ascii_abgelehnt():
    eintrag = _gueltig()
    eintrag["erklaerung"] = "mit Umlaut: ae, oe direct? use umlaut"
    eintrag["erklaerung"] = "nicht ascii: " + chr(252)
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert any("ascii" in g for g in report["fehlerhafte"][0]["gruende"])


def test_gueltige_ergaenzung_wird_geprueft_nicht_gespeichert():
    eintrag = _gueltig("-extra")
    report = pruefe(list(DEFAULT_FORMELN) + [eintrag])
    assert report["formeln_gesamt"] == 42
    assert report["formeln_ungueltig"] == 0
    assert len(DEFAULT_FORMELN) == 41  # Registry unveraendert


def test_ergaenzung_json_load_ok(tmp_path):
    pfad = tmp_path / "extra.json"
    pfad.write_text(
        json.dumps({"formeln": [_gueltig("-file")]}), encoding="ascii")
    assert lade_ergaenzung(pfad)[0]["id"] == "test-formel-file"


def test_ergaenzung_ohne_formeln_liste_abgelehnt(tmp_path):
    pfad = tmp_path / "schlecht.json"
    pfad.write_text(json.dumps({"eintrage": []}), encoding="ascii")
    try:
        lade_ergaenzung(pfad)
        raise AssertionError("KreislaufInputError erwartet")
    except KreislaufInputError:
        pass


def test_ergaenzung_nan_abgelehnt(tmp_path):
    pfad = tmp_path / "nan.json"
    pfad.write_text('{"formeln": [NaN]}', encoding="ascii")
    try:
        lade_ergaenzung(pfad)
        raise AssertionError("KreislaufInputError erwartet")
    except KreislaufInputError:
        pass


def test_main_exit_0_mit_default(capsys, tmp_path):
    code = main(["--report-dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "REGISTRIERT" in out
    assert (tmp_path / "sprichwort_formeln.txt").is_file()
    assert (tmp_path / "sprichwort_formeln.json").is_file()


def test_main_exit_1_bei_ergaenzung_input_error(tmp_path, capsys):
    code = main(["--ergaenzung", str(tmp_path / "fehlt.json")])
    ausgabe = capsys.readouterr().err
    assert "INPUT_ERROR" in ausgabe
    assert code == 3


def test_report_deterministisch_und_ascii():
    report = pruefe(DEFAULT_FORMELN)
    report["eintraege"] = DEFAULT_FORMELN
    text = format_text_report(report)
    assert text == format_text_report(report)
    text.encode("ascii")


def test_grenzen_stehen_im_report():
    report = pruefe(DEFAULT_FORMELN)
    assert "ANALOGIE != BEWEIS" in format_text_report(report)
