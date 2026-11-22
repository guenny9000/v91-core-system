"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tests fuer controller/kreislauf_verbesserung.py (VIBE-LXXI).

REUSE: Status-Report-Struktur und Phasen-Definitionen aus PR #363.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.kreislauf_status import (  # noqa: E402
    BELEGT,
    NICHT_GEPRUEFT,
    PHASEN,
    KreislaufInputError,
)
from controller.kreislauf_verbesserung import (  # noqa: E402
    ABGELEHNT,
    ANGENOMMEN,
    EXIT_ABGELEHNT,
    EXIT_AKZEPTIERT,
    EXIT_INPUT_ERROR,
    VERDICT_ABGELEHNT,
    VERDICT_AKZEPTIERT,
    assess,
    format_text_report,
    load_plan,
    load_status_report,
    main,
)


def _phasen_block(verdict):
    block = {"verdict": verdict, "grund": "test"}
    if verdict == BELEGT:
        block["indikatorzahl"] = 3
    else:
        block["unvollstaendige_indikatoren"] = ["x"]
    return block


def status_report(tmp_path, offene=("PRUEFUNG", "NACHWEIS", "NUTZEN",
                                    "MONITORING", "VERBESSERUNG"),
                  initiative="pil-x-2026", fehlen=()):
    alle = ("MOEGLICHKEIT", "PRUEFUNG", "NACHWEIS", "NUTZEN",
            "MONITORING", "VERBESSERUNG")
    phasen = {
        phase: _phasen_block(NICHT_GEPRUEFT if phase in offene else BELEGT)
        for phase in alle if phase not in fehlen
    }
    report = {
        "initiative_id": initiative,
        "phasen": phasen,
        "offene_phasen": sorted(offene),
    }
    path = tmp_path / "status.json"
    path.write_text(json.dumps(report), encoding="ascii")
    return path


def massnahme(mid="m1", phase="NUTZEN", quelle="ledgers/pilot-x.jsonl",
              datum="2026-11-23", indikator="nutzwert", zielwert=10.0,
              fenster="2027-01-01/2027-12-31",
              methode="r3-ledger-je-quartal",
              verantwortung="operator"):
    return {
        "id": mid,
        "phase": phase,
        "befund": {"quelle": quelle, "datum": datum},
        "ziel": {
            "indikator": indikator,
            "zielwert": zielwert,
            "messfenster": fenster,
            "methode": methode,
        },
        "verantwortung": verantwortung,
    }


def plan_file(tmp_path, massnahmen, initiative="pil-x-2026",
              name="plan.json"):
    plan = {"initiative_id": initiative, "measures": massnahmen}
    path = tmp_path / name
    path.write_text(json.dumps(plan), encoding="ascii")
    return path


# --- load_status_report -------------------------------------------------

def test_load_status_report_ok(tmp_path):
    report = load_status_report(status_report(tmp_path))
    assert report["initiative_id"] == "pil-x-2026"
    assert report["phasen"]["NUTZEN"]["verdict"] == NICHT_GEPRUEFT


def test_load_status_report_fehlt(tmp_path):
    with pytest.raises(KreislaufInputError, match="status-report fehlt"):
        load_status_report(tmp_path / "fehlt.json")


def test_load_status_report_kein_json(tmp_path):
    path = tmp_path / "kein.json"
    path.write_text("{kaputt", encoding="ascii")
    with pytest.raises(KreislaufInputError, match="kein gueltiges JSON"):
        load_status_report(path)


def test_load_status_report_unbekannte_phase(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({
        "initiative_id": "x",
        "phasen": {"MOEGLICHKEIT": _phasen_block(BELEGT),
                   "PHANTOM": _phasen_block(BELEGT)},
    }), encoding="ascii")
    with pytest.raises(KreislaufInputError, match="unbekannte phasen"):
        load_status_report(path)


def test_load_status_report_falsches_verdict(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({
        "initiative_id": "x",
        "phasen": {p: {"verdict": "VIelleicht"}
                   for p in ("MOEGLICHKEIT", "PRUEFUNG", "NACHWEIS",
                             "NUTZEN", "MONITORING", "VERBESSERUNG")},
    }), encoding="ascii")
    with pytest.raises(KreislaufInputError, match="gueltiges verdict"):
        load_status_report(path)


# --- load_plan ----------------------------------------------------------

def test_load_plan_ok(tmp_path):
    plan = load_plan(plan_file(tmp_path, [massnahme()]))
    assert plan["measures"][0]["id"] == "m1"


def test_load_plan_ohne_initiative(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"measures": []}), encoding="ascii")
    with pytest.raises(KreislaufInputError, match="initiative_id"):
        load_plan(path)


def test_load_plan_ohne_measures(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"initiative_id": "x"}), encoding="ascii")
    with pytest.raises(KreislaufInputError, match="measures"):
        load_plan(path)


# --- assess: akzeptiert / abgelehnt --------------------------------------

def test_assess_komplette_massnahme_angenommen(tmp_path):
    report = assess(load_plan(plan_file(tmp_path, [massnahme()])),
                    load_status_report(status_report(tmp_path)))
    assert report["verdict"] == VERDICT_AKZEPTIERT
    assert report["massnahmen"][0]["status"] == ANGENOMMEN
    assert report["adressierte_offene_phasen"] == ["NUTZEN"]


def test_assess_belegte_phase_abgelehnt(tmp_path):
    report = assess(
        load_plan(plan_file(tmp_path, [massnahme(phase="MOEGLICHKEIT")])),
        load_status_report(status_report(tmp_path)))
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("keine erfundene luecke" in g
               for g in report["massnahmen"][0]["gruende"])


def test_assess_phase_nicht_im_report_abgelehnt(tmp_path):
    report = assess(
        load_plan(plan_file(tmp_path, [massnahme(phase="NACHWEIS")])),
        load_status_report(status_report(tmp_path, fehlen=("NACHWEIS",))))
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("nicht im status-report" in g
               for g in report["massnahmen"][0]["gruende"])


def test_assess_phantom_phase_abgelehnt(tmp_path):
    report = assess(
        load_plan(plan_file(tmp_path, [massnahme(phase="TRAUM")])),
        load_status_report(status_report(tmp_path)))
    assert any("nicht im kreislauf" in g
               for g in report["massnahmen"][0]["gruende"])


def test_assess_fehlende_zielfelder_gesammelt(tmp_path):
    m = massnahme()
    del m["ziel"]["messfenster"]
    del m["ziel"]["methode"]
    report = assess(load_plan(plan_file(tmp_path, [m])),
                    load_status_report(status_report(tmp_path)))
    gruende = report["massnahmen"][0]["gruende"]
    assert any("messfenster" in g for g in gruende)
    assert any("methode" in g for g in gruende)
    assert report["verdict"] == VERDICT_ABGELEHNT


def test_assess_befund_ohne_quelle_abgelehnt(tmp_path):
    m = massnahme()
    m["befund"]["quelle"] = ""
    report = assess(load_plan(plan_file(tmp_path, [m])),
                    load_status_report(status_report(tmp_path)))
    assert any("quelle" in g
               for g in report["massnahmen"][0]["gruende"])


def test_assess_ohne_verantwortung_abgelehnt(tmp_path):
    m = massnahme()
    m["verantwortung"] = ""
    report = assess(load_plan(plan_file(tmp_path, [m])),
                    load_status_report(status_report(tmp_path)))
    assert any("verantwortung" in g
               for g in report["massnahmen"][0]["gruende"])


def test_assess_doppelte_id_abgelehnt_beide(tmp_path):
    plan = load_plan(
        plan_file(tmp_path, [massnahme(mid="dup"),
                            massnahme(mid="dup", phase="PRUEFUNG")]))
    report = assess(plan, load_status_report(status_report(tmp_path)))
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert report["massnahmen"][1]["status"] == ABGELEHNT
    assert any("doppelte id" in g
               for g in report["massnahmen"][1]["gruende"])


def test_assess_leere_measures_abgelehnt(tmp_path):
    report = assess(load_plan(plan_file(tmp_path, [])),
                    load_status_report(status_report(tmp_path)))
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert report["offene_phasen_unadressiert"] == [
        "MONITORING", "NACHWEIS", "NUTZEN", "PRUEFUNG", "VERBESSERUNG"]


def test_assess_initiative_mismatch_input_error(tmp_path):
    with pytest.raises(KreislaufInputError, match="passt nicht"):
        assess(load_plan(plan_file(tmp_path, [massnahme()],
                                   initiative="andere-initiative")),
               load_status_report(status_report(tmp_path)))


def test_assess_kein_objekt_massnahme(tmp_path):
    report = assess(load_plan(plan_file(tmp_path, ["kein objekt"])),
                    load_status_report(status_report(tmp_path)))
    assert report["massnahmen"][0]["id"] == "<ohne id>"
    assert report["massnahmen"][0]["status"] == ABGELEHNT


def test_assess_mische_akzept_und_ablehnung(tmp_path):
    plan = load_plan(plan_file(tmp_path, [
        massnahme(mid="gut", phase="NUTZEN"),
        massnahme(mid="schlecht", phase="MOEGLICHKEIT"),
    ]))
    report = assess(plan, load_status_report(status_report(tmp_path)))
    assert report["massnahmen_akzeptiert"] == 1
    assert report["verdict"] == VERDICT_ABGELEHNT
    assert report["adressierte_offene_phasen"] == ["NUTZEN"]


def test_assess_unadressierte_offene_phasen_ehrlich(tmp_path):
    report = assess(
        load_plan(plan_file(tmp_path, [massnahme(phase="NUTZEN")])),
        load_status_report(status_report(tmp_path)))
    assert "PRUEFUNG" in report["offene_phasen_unadressiert"]
    assert "NUTZEN" not in report["offene_phasen_unadressiert"]


# --- reports / CLI -------------------------------------------------------

def test_format_text_report_ascii_deterministisch(tmp_path):
    report = assess(load_plan(plan_file(tmp_path, [massnahme()])),
                    load_status_report(status_report(tmp_path)))
    text = format_text_report(report)
    text.encode("ascii")
    assert text == format_text_report(report)
    assert "AKZEPTIERT" in text


def test_main_exit_0_akzeptiert(tmp_path, capsys):
    code = main([str(plan_file(tmp_path, [massnahme()])),
                 "--status-report", str(status_report(tmp_path))])
    assert code == EXIT_AKZEPTIERT
    assert "verdict    : AKZEPTIERT" in capsys.readouterr().out


def test_main_exit_1_abgelehnt(tmp_path, capsys):
    code = main([str(plan_file(tmp_path, [massnahme(phase="MOEGLICHKEIT")])),
                 "--status-report", str(status_report(tmp_path))])
    assert code == EXIT_ABGELEHNT


def test_main_exit_3_input_error(tmp_path, capsys):
    code = main([str(tmp_path / "fehlt.json"),
                 "--status-report", str(status_report(tmp_path))])
    assert code == EXIT_INPUT_ERROR
    assert "INPUT_ERROR" in capsys.readouterr().err


def test_main_report_dir_schreibt_txt_json(tmp_path):
    out = tmp_path / "out"
    code = main([str(plan_file(tmp_path, [massnahme()])),
                 "--status-report", str(status_report(tmp_path)),
                 "--report-dir", str(out)])
    assert code == EXIT_AKZEPTIERT
    text = (out / "kreislauf_verbesserung_pil-x-2026.txt")
    jsonpfad = (out / "kreislauf_verbesserung_pil-x-2026.json")
    assert text.is_file() and jsonpfad.is_file()
    text.read_text(encoding="ascii")
    daten = json.loads(jsonpfad.read_text(encoding="ascii"))
    assert daten["verdict"] == VERDICT_AKZEPTIERT


# --- Regression VIBE-LXXII: zielwert-Eingabegrenze (unabhaengige Pruefung) --

def _status(tmp_path):
    return status_report(tmp_path)


def test_regression_zielwert_text_abgelehnt(tmp_path):
    m = massnahme()
    m["ziel"]["zielwert"] = "spaeter"
    report = assess(load_plan(plan_file(tmp_path, [m])),
                    load_status_report(_status(tmp_path)))
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("zielwert" in g
               for g in report["massnahmen"][0]["gruende"])


def test_regression_zielwert_nan_abgelehnt(tmp_path):
    # NaN erreicht assess nie ueber Dateien (Loader lehnt JSON-Konstante
    # ab); der Assess-Pfad bleibt zusaetzlich selbst hart:
    plan = {"initiative_id": "pil-x-2026",
            "measures": [massnahme()]}
    plan["measures"][0]["ziel"]["zielwert"] = float("nan")
    report = assess(plan, {"initiative_id": "pil-x-2026", "phasen": {
        ph: {"verdict": NICHT_GEPRUEFT, "grund": "t"} for ph in PHASEN}})
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("zielwert" in g
               for g in report["massnahmen"][0]["gruende"])


def test_regression_zielwert_infinity_abgelehnt(tmp_path):
    plan = {"initiative_id": "pil-x-2026",
            "measures": [massnahme()]}
    plan["measures"][0]["ziel"]["zielwert"] = float("inf")
    report = assess(plan, {"initiative_id": "pil-x-2026", "phasen": {
        ph: {"verdict": NICHT_GEPRUEFT, "grund": "t"} for ph in PHASEN}})
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("zielwert" in g
               for g in report["massnahmen"][0]["gruende"])


def test_regression_zielwert_bool_abgelehnt(tmp_path):
    m = massnahme()
    m["ziel"]["zielwert"] = True
    report = assess(load_plan(plan_file(tmp_path, [m])),
                    load_status_report(_status(tmp_path)))
    assert report["massnahmen"][0]["status"] == ABGELEHNT
    assert any("zielwert" in g
               for g in report["massnahmen"][0]["gruende"])


def test_regression_zielwert_endliche_zahlen_erlaubt(tmp_path):
    for wert in (7, 10.5, 0, -3):
        m = massnahme(mid="m-%r" % wert)
        m["ziel"]["zielwert"] = wert
        report = assess(load_plan(plan_file(tmp_path, [m])),
                        load_status_report(_status(tmp_path)))
        assert report["massnahmen"][0]["status"] == ANGENOMMEN, wert


def test_regression_json_nan_in_plan_input_error(tmp_path):
    # Python json parst bare NaN; der Loader muss fail-closed sein.
    path = tmp_path / "nan_plan.json"
    path.write_text(
        '{"initiative_id": "pil-x-2026", "measures": ['
        '{"id": "m1", "phase": "NUTZEN", "befund": {"quelle": "q",'
        ' "datum": "d"}, "ziel": {"indikator": "i", "zielwert": NaN,'
        ' "messfenster": "f", "methode": "m"}, "verantwortung": "op"}]}'
        .replace('"initiative_id": "pil-x-2026"',
                 '"initiative_id": "pil-x-2026"'),
        encoding="ascii")
    with pytest.raises(KreislaufInputError, match="JSON-konstante"):
        load_plan(path)


def test_regression_json_infinity_in_plan_input_error(tmp_path):
    path = tmp_path / "inf_plan.json"
    path.write_text(
        '{"initiative_id": "pil-x-2026", "measures": ['
        '{"id": "m1", "phase": "NUTZEN", "befund": {"quelle": "q",'
        ' "datum": "d"}, "ziel": {"indikator": "i", "zielwert": Infinity,'
        ' "messfenster": "f", "methode": "m"}, "verantwortung": "op"}]}',
        encoding="ascii")
    with pytest.raises(KreislaufInputError, match="JSON-konstante"):
        load_plan(path)
