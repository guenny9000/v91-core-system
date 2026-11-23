"""Tests fuer controller/rebound_verlagerung.py (VIBE-LXXXCV)."""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller.rebound_verlagerung import (
    EXIT_BEFUND,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    Raum,
    bewerte_verlagerung,
    check_datei,
    format_text_report,
    load_massnahme,
    main,
)
from controller.rebound_conflict_check import ReboundConflictError


def _wirkung(kategorie="kohle_emissionen", raum="INLAND",
             richtung="REDUCES", evidenz="BEHOERDE 2026, S. 3"):
    return {
        "kategorie": kategorie,
        "raum": raum,
        "richtung": richtung,
        "evidenz": evidenz,
    }


def _massnahme(wirkungen=None):
    if wirkungen is None:
        wirkungen = [_wirkung()]
    return {
        "massnahme_id": "US-KOHLE-AUSLAUF",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": wirkungen,
    }


def test_load_gueltig():
    data = load_massnahme(json.dumps(_massnahme()))
    assert data["massnahme_id"] == "US-KOHLE-AUSLAUF"
    assert data["wirkungen"][0].raum == Raum.INLAND


def test_load_rejects_bare_nan():
    raw = json.dumps(_massnahme()).replace('"richtung": "REDUCES"', '"richtung": NaN')
    assert "NaN" in raw
    with pytest.raises(ReboundConflictError):
        load_massnahme(raw)


def test_load_rejects_wurzel_liste():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps([1]))


def test_load_rejects_leere_wirkungen():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps({
            "massnahme_id": "X",
            "ziel_kategorie": "y",
            "wirkungen": [],
        }))


def test_load_rejects_unbekannten_raum():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps(_massnahme(
            wirkungen=[_wirkung(raum="MOND")],
        )))


def test_load_rejects_unbekannte_richtung():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps(_massnahme(
            wirkungen=[_wirkung(richtung="VENICHTET")],
        )))


def test_load_rejects_leere_evidenz():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps(_massnahme(
            wirkungen=[_wirkung(evidenz=" ")],
        )))


def test_load_rejects_nicht_ascii_kategorie():
    with pytest.raises(ReboundConflictError):
        load_massnahme(json.dumps(_massnahme(
            wirkungen=[_wirkung(kategorie="Ämission")],
        ), ensure_ascii=False))


def test_verlagert_wenn_ausland_steigt():
    report = bewerte_verlagerung({
        "massnahme_id": "US-KOHLE-AUSLAUF",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": [
            _wirkung(raum="INLAND", richtung="REDUCES"),
            _wirkung(raum="AUSLAND", richtung="INCREASES"),
        ],
    })
    assert report["verdict"] == "VERLAGERT_NICHT_VERMIEDEN"
    assert len(report["verlagert_belege"]) == 1


def test_raum_unbekannt_ist_nicht_entscheidbar():
    report = bewerte_verlagerung({
        "massnahme_id": "X",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": [
            _wirkung(raum="INLAND", richtung="REDUCES"),
            _wirkung(raum="RAUM_UNBEKANNT", richtung="INCREASES"),
        ],
    })
    assert report["verdict"] == "NICHT_ENTSCHEIDBAR"
    assert report["raum_unbekannt_belege"]


def test_inlandsicht_nur_vermieden_sichtbar():
    report = bewerte_verlagerung(_massnahme())
    assert report["verdict"] == "VERMIEDEN_SICHTBAR"
    assert "VERMIEDEN != GLOBAL" in report["begruendung"]


def test_ohne_zielsicht_nicht_entscheidbar():
    report = bewerte_verlagerung({
        "massnahme_id": "X",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": [_wirkung(kategorie="andere_kategorie")],
    })
    assert report["verdict"] == "NICHT_ENTSCHEIDBAR"


def test_querwirkungen_werden_gefuehrt():
    report = bewerte_verlagerung({
        "massnahme_id": "X",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": [
            _wirkung(raum="INLAND", richtung="REDUCES"),
            _wirkung(kategorie="sozial", raum="AUSLAND", richtung="INCREASES"),
        ],
    })
    assert report["verdict"] == "VERMIEDEN_SICHTBAR"
    assert len(report["querwirkungen"]) == 1
    assert report["querwirkungen"][0][0] == "sozial"


def test_check_datei_exit_0(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps(_massnahme()), encoding="utf-8")
    report, code = check_datei(f)
    assert code == EXIT_OK


def test_check_datei_exit_1_bei_verlagerung(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps(_massnahme(wirkungen=[
        _wirkung(raum="INLAND", richtung="REDUCES"),
        _wirkung(raum="AUSLAND", richtung="INCREASES"),
    ])), encoding="utf-8")
    report, code = check_datei(f)
    assert code == EXIT_BEFUND


def test_check_datei_exit_3_bei_defekt(tmp_path):
    f = tmp_path / "m.json"
    f.write_text("{ kaputt", encoding="utf-8")
    report, code = check_datei(f)
    assert code == EXIT_INPUT_ERROR


def test_main_erfolg(tmp_path, capsys):
    f = tmp_path / "m.json"
    f.write_text(json.dumps(_massnahme()), encoding="utf-8")
    code = main([str(f)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "VERDICT: VERMIEDEN_SICHTBAR" in out


def test_main_input_error(tmp_path, capsys):
    f = tmp_path / "m.json"
    f.write_text("{}", encoding="utf-8")
    code = main([str(f)])
    assert code == EXIT_INPUT_ERROR
    assert "INPUT_ERROR" in capsys.readouterr().out


def test_report_ascii():
    report = bewerte_verlagerung(_massnahme())
    text = format_text_report(report)
    assert all(ord(c) < 127 for c in text)


def test_us_kohle_beispiel_des_fremdberichts(tmp_path):
    """Der Fall des Office-Agenten: Inlandsreduktion + Exportanstieg."""
    f = tmp_path / "us.json"
    f.write_text(json.dumps({
        "massnahme_id": "US-KOHLE-7PCT",
        "ziel_kategorie": "kohle_emissionen",
        "wirkungen": [
            _wirkung(raum="INLAND", richtung="REDUCES",
                     evidenz="Inlandsstatistik -7% 2026"),
            _wirkung(raum="AUSLAND", richtung="INCREASES",
                     evidenz="Exportstatistik +15% 2026"),
        ],
    }), encoding="utf-8")
    report, code = check_datei(f)
    assert code == EXIT_BEFUND
    assert report["verdict"] == "VERLAGERT_NICHT_VERMIEDEN"
