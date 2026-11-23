"""Tests fuer controller/nachrichten_lagebild.py (VIBE-LXXXCIV)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller.nachrichten_lagebild import (
    LagebildError,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_VIOLATIONS,
    bewerte_bereich,
    bewerte_gesamt,
    build_lagebild,
    check_lagebildFile,
    format_text_report,
    load_lagebild,
    main,
)


def _eintrag(richtung="besser"):
    return {
        "claim": "Strommix 63,7% erneuerbar",
        "source": "electricshift 21.11.2026",
        "date": "2026-11-21",
        "richtung": richtung,
    }


def _daten(eintraege=None, richtungen=None):
    if eintraege is None:
        eintraege = [_eintrag(r) for r in (richtungen or ["besser"])]
    return {
        "bericht_id": "NL-2026-11-23",
        "bereiche": {"energie": {"eintraege": eintraege}},
    }


def test_load_gueltig():
    data = load_lagebild(json.dumps(_daten()))
    assert data["bericht_id"] == "NL-2026-11-23"


def test_load_rejects_bare_nan():
    valid = json.dumps(_daten())
    raw = valid.replace('"richtung": "besser"', '"richtung": NaN')
    assert "NaN" in raw
    with pytest.raises(LagebildError):
        load_lagebild(raw)


def test_load_wurzel_muss_objekt():
    with pytest.raises(LagebildError):
        load_lagebild(json.dumps([1, 2]))


def test_load_rejects_fehlende_richtung():
    text = json.dumps(_daten())
    text = text.replace('"richtung": "besser"', '"richtug": "besser"')
    with pytest.raises(LagebildError):
        load_lagebild(text)


def test_load_rejects_leeren_bereichsnamen():
    with pytest.raises(LagebildError):
        load_lagebild(json.dumps({
            "bericht_id": "X",
            "bereiche": {"": {"eintraege": []}},
        }))


def test_load_rejects_nicht_ascii_bereich():
    with pytest.raises(LagebildError):
        load_lagebild(json.dumps({
            "bericht_id": "X",
            "bereiche": {"Änergie": {"eintraege": []}},
        }, ensure_ascii=False))


def test_bewerte_bereich_unknown_wenn_leer():
    res = bewerte_bereich([])
    assert res["tendenz"] == "UNKNOWN"


def test_bewerte_bereich_besser():
    assert bewerte_bereich([_eintrag(), _eintrag()])["tendenz"] == "BESSER"


def test_bewerte_bereich_schlechter():
    res = bewerte_bereich([_eintrag("schlechter")])
    assert res["tendenz"] == "SCHLECHTER"


def test_bewerte_bereich_gemischt():
    res = bewerte_bereich([_eintrag("besser"), _eintrag("schlechter")])
    assert res["tendenz"] == "GEMISCHT"
    assert res["besser"] == 1 and res["schlechter"] == 1


def test_bewerte_bereich_neutral():
    assert bewerte_bereich([_eintrag("neutral")])["tendenz"] == "NEUTRAL"


def test_bewerte_bereich_ungeultige_bleiben_sichtbar():
    res = bewerte_bereich([_eintrag(), {"claim": "x"}])
    assert res["tendenz"] == "BESSER" and res["ungueltig"] == 1


def test_bewerte_gesamt_unknown_wenn_alles_unknown():
    assert bewerte_gesamt({"energie": "UNKNOWN"}) == "UNKNOWN"


def test_bewerte_gesamt_gemischt_wenn_widerspruch():
    assert bewerte_gesamt({"energie": "BESSER", "krieg": "SCHLECHTER"}) == "GEMISCHT"


def test_bewerte_gesamt_unknown_zaehlt_mit():
    value = bewerte_gesamt({"energie": "BESSER", "rest": "UNKNOWN"})
    assert value == "BESSER"


def test_gesamt_gemischt_bei_schlechter_und_besser_ueber_bereiche():
    res = build_lagebild({
        "bericht_id": "NL",
        "bereiche": {
            "energie": {"eintraege": [_eintrag("besser")]},
            "konflikt": {"eintraege": [_eintrag("schlechter")]},
        },
    })
    assert res["gesamt_tendenz"] == "GEMISCHT"


def test_gesamt_schlechter_bei_unknown_und_schlechter():
    res = build_lagebild({
        "bericht_id": "NL",
        "bereiche": {
            "energie": {"eintraege": []},
            "konflikt": {"eintraege": [_eintrag("schlechter")]},
        },
    })
    assert res["gesamt_tendenz"] == "SCHLECHTER"


def test_check_lagebildFile_exit_0(tmp_path):
    f = tmp_path / "l.json"
    f.write_text(json.dumps(_daten()), encoding="utf-8")
    report, code = check_lagebildFile(f)
    assert code == EXIT_OK and report["gesamt_tendenz"] == "BESSER"


def test_check_lagebildFile_exit_1_bei_ungueltigen(tmp_path):
    f = tmp_path / "l.json"
    f.write_text(
        json.dumps(_daten(eintraege=[_eintrag(), {"richtung": "besser"}])),
        encoding="utf-8",
    )
    report, code = check_lagebildFile(f)
    assert code == EXIT_VIOLATIONS and report["ungueltige_eintraege"] == 1


def test_check_lagebildFile_exit_3_bei_defekt(tmp_path):
    f = tmp_path / "l.json"
    f.write_text("{ kaputt", encoding="utf-8")
    report, code = check_lagebildFile(f)
    assert code == EXIT_INPUT_ERROR


def test_main_json_out_im_repo_abgewiesen(tmp_path, monkeypatch, capsys):
    f = tmp_path / "l.json"
    f.write_text(json.dumps(_daten()), encoding="utf-8")
    code = main([
        str(f),
        "--json-out",
        os.path.join(os.path.dirname(__file__), "un_erlaubt.json"),
    ])
    assert code == EXIT_INPUT_ERROR
    assert "Ragnarok-Phase-1" in capsys.readouterr().out


def test_main_erfolg(tmp_path, capsys):
    f = tmp_path / "l.json"
    f.write_text(json.dumps(_daten()), encoding="utf-8")
    code = main([str(f)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "GESAMT-TENDENZ: BESSER" in out
    assert "LAGEBILD != WAHRHEIT" in out


def test_report_ascii_und_honesty():
    report = build_lagebild(_daten())
    text = format_text_report(report)
    assert all(ord(c) < 127 for c in text)
    assert "BEWERTUNG != FAKT" in text
