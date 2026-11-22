"""Tests fuer die Sprichwort-/Redewendung-Formel-Registry (VIBE-LXXV/LXXVI).

Pruefen das Struktur-Gate (pruefe), die CLI (main), die
Report-Erzeugung und die LXXVI-Haertefixes: ASCII-Gate ueber
ALLE Felder, KeyError-sicherer Report, GEPRUEFT_NICHT_GESPEICHERT.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller.sprichwort_formeln import (
    BEREICHE,
    DEFAULT_FORMELN,
    FELDER,
    STATUSSE,
    VERDICT_GEPRUEFT_NICHT_GESPEICHERT,
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
        "status": "ORIGINAL",
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
    eintrag["erklaerung"] = "nicht ascii: " + chr(252)
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert any("ascii" in g for g in report["fehlerhafte"][0]["gruende"])


def test_nicht_ascii_quelle_abgelehnt():
    """LXXVI-Fix: frueher passierte unicode in quelle bis zum Crash."""
    eintrag = _gueltig()
    eintrag["quelle"] = "quelle mit " + chr(252)
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    gruende = report["fehlerhafte"][0]["gruende"]
    assert "feld quelle ist nicht ascii-pure" in gruende


def test_nicht_ascii_id_abgelehnt():
    """LXXVI-Fix: auch die id ist Teil des ASCII-Gates."""
    eintrag = _gueltig()
    eintrag["id"] = "uni" + chr(252)
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    gruende = report["fehlerhafte"][0]["gruende"]
    assert "feld id ist nicht ascii-pure" in gruende


def test_status_pflichtfeld():
    eintrag = _gueltig()
    del eintrag["status"]
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert "feld status fehlt oder ist leer" in \
        report["fehlerhafte"][0]["gruende"]


def test_status_wertebereich():
    eintrag = _gueltig()
    eintrag["status"] = "GEHEIMREZEPT"
    report = pruefe([eintrag])
    assert report["verdict"] == "ABGELEHNT"
    assert any("status" in g for g in report["fehlerhafte"][0]["gruende"])


def test_registry_statusse_vollstaendig():
    for eintrag in DEFAULT_FORMELN:
        assert eintrag["status"] in STATUSSE, eintrag["id"]
    from collections import Counter
    zaehl = Counter(e["status"] for e in DEFAULT_FORMELN)
    assert zaehl["ORIGINAL"] + zaehl["ZITAT"] + \
        zaehl["PARAPHRASE"] + zaehl["SCHERZ"] == 41
    assert zaehl["PARAPHRASE"] >= 1
    assert zaehl["SCHERZ"] >= 1


def test_report_kein_keyerror_bei_fehlenden_feldern():
    """LXXVI-Fix: ungueltige Eintraege duerfen den Report nicht
    crashen, sie stehen nur in fehlerhafte, nie in eintraege."""
    unvollstaendig = {"id": "ink",
                      "redewendung": "hallo",
                      "formel": "x"}
    report = pruefe([unvollstaendig])
    assert report["verdict"] == "ABGELEHNT"
    assert report["eintraege"] == []
    text = format_text_report(report)  # darf kein KeyError werfen
    text.encode("ascii")
    assert "ABGELEHNT : ink" in text


def test_report_fehlertolerant_bei_leeren_objekten():
    report = pruefe([{}])
    text = format_text_report(report)
    assert "<ohne id>" in text
    text.encode("ascii")


def test_gueltige_ergaenzung_wird_geprueft_nicht_gespeichert():
    eintrag = _gueltig("-extra")
    report = pruefe(list(DEFAULT_FORMELN) + [eintrag])
    assert report["formeln_gesamt"] == 42
    assert report["formeln_ungueltig"] == 0
    assert len(DEFAULT_FORMELN) == 41  # Registry unveraendert
    assert len(report["eintraege"]) == 42


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


def test_main_unvollstaendige_ergaenzung_exit_1_ohne_crash(
        tmp_path, capsys):
    """LXXVI-Fix: frueher KeyError 'quelle' beim Report-Schreiben."""
    pfad = tmp_path / "erg.json"
    pfad.write_text(json.dumps({"formeln": [
        {"id": "ink2", "redewendung": "r", "formel": "f",
         "erklaerung": "e"}]}), encoding="ascii")
    code = main(["--ergaenzung", str(pfad), "--report-dir", str(tmp_path)])
    assert code == 1  # EXIT_ABGELEHNT, kein Absturz
    assert (tmp_path / "sprichwort_formeln.txt").is_file()
    text = (tmp_path / "sprichwort_formeln.txt").read_text(
        encoding="ascii")
    assert "ABGELEHNT : ink2" in text
    assert "feld quelle fehlt oder ist leer" in text


def test_main_gueltige_ergaenzung_verdict_ehrlich(tmp_path, capsys):
    """LXXVI-Fix: GEPRUEFT_NICHT_GESPEICHERT statt REGISTRIERT."""
    pfad = tmp_path / "erg.json"
    eintrag = dict(DEFAULT_FORMELN[0])
    eintrag["id"] = "extra-cli"
    pfad.write_text(json.dumps({"formeln": [eintrag]}),
                    encoding="ascii")
    code = main(["--ergaenzung", str(pfad), "--report-dir", str(tmp_path)])
    assert code == 0
    text = (tmp_path / "sprichwort_formeln.txt").read_text(
        encoding="ascii")
    assert VERDICT_GEPRUEFT_NICHT_GESPEICHERT in text
    roh = (tmp_path / "sprichwort_formeln.json").read_text(
        encoding="ascii")
    assert "GEPRUEFT_NICHT_GESPEICHERT" in roh
    out = capsys.readouterr().out
    assert "GATE != SPEICHER" in out


def test_main_nicht_ascii_quelle_ergaenzung_abgelehnt(tmp_path):
    """LXXVI-Fix: Unicode-Quelle schlaegt am Gate fehl, kein Spaet-Crash."""
    pfad = tmp_path / "erg2.json"
    eintrag = _gueltig("-uni")
    eintrag["quelle"] = "quelle-mit-" + chr(252)
    pfad.write_text(json.dumps({"formeln": [eintrag]},
                               ensure_ascii=True), encoding="ascii")
    code = main(["--ergaenzung", str(pfad), "--report-dir", str(tmp_path)])
    assert code == 1
    text = (tmp_path / "sprichwort_formeln.txt").read_text(
        encoding="ascii")
    assert "quelle ist nicht ascii-pure" in text


def test_main_exit_3_bei_ergaenzung_input_error(tmp_path, capsys):
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


def test_status_zeile_im_report():
    report = pruefe(DEFAULT_FORMELN)
    report["eintraege"] = DEFAULT_FORMELN
    text = format_text_report(report)
    assert "status      : SCHERZ" in text
    assert "status      : PARAPHRASE" in text
    assert "status      : ZITAT" in text
