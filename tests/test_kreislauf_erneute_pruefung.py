"""
Tests fuer controller/kreislauf_erneute_pruefung.py (VIBE-LXXIV).

REUSE: Plan-/Status-Loader und Gate aus PR #365, Ledger-Loader und
KreislaufInputError aus PR #363 (NO_DUPLICATE_SYSTEMS).
"""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.kreislauf_status import (  # noqa: E402
    BELEGT,
    NICHT_GEPRUEFT,
    KreislaufInputError,
)
from controller.kreislauf_verbesserung import (  # noqa: E402
    ANGENOMMEN,
    load_plan,
    load_status_report,
)
from controller.kreislauf_erneute_pruefung import (  # noqa: E402
    ERFUELLT,
    EXIT_GESCHLOSSEN,
    EXIT_INPUT_ERROR,
    EXIT_OFFEN,
    NICHT_ERFUELLT,
    NICHT_MESSBAR,
    NICHT_PRUEFBAR,
    VERDICT_GESCHLOSSEN,
    VERDICT_OFFEN,
    _bewertet_ab_parsen,
    assess,
    format_text_report,
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
                  initiative="pil-x-2026"):
    alle = ("MOEGLICHKEIT", "PRUEFUNG", "NACHWEIS", "NUTZEN",
            "MONITORING", "VERBESSERUNG")
    phasen = {
        phase: _phasen_block(NICHT_GEPRUEFT if phase in offene else BELEGT)
        for phase in alle
    }
    report = {
        "initiative_id": initiative,
        "phasen": phasen,
        "offene_phasen": sorted(offene),
    }
    path = tmp_path / "status.json"
    path.write_text(json.dumps(report), encoding="ascii")
    return path


def massnahme(mid="m1", phase="NUTZEN", indikator="nutzwert",
              zielwert=10.0):
    return {
        "id": mid,
        "phase": phase,
        "befund": {"quelle": "ledgers/pilot-x.jsonl", "datum": "2026-11-23"},
        "ziel": {
            "indikator": indikator,
            "zielwert": zielwert,
            "messfenster": "2027-01-01/2027-12-31",
            "methode": "r3-ledger-je-quartal",
        },
        "verantwortung": "operator",
    }


def plan_file(tmp_path, massnahmen, initiative="pil-x-2026"):
    plan = {"initiative_id": initiative, "measures": massnahmen}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="ascii")
    return path


def ledger_datei(tmp_path, eintraege, initiative="pil-x-2026",
                 name="ledger.jsonl"):
    path = tmp_path / name
    zeilen = []
    for e in eintraege:
        eintrag = dict(e)
        eintrag.setdefault("initiative_id", initiative)
        eintrag.setdefault("indicator", "nutzwert")
        eintrag.setdefault("source", "test")
        zeilen.append(json.dumps(eintrag))
    path.write_text("\n".join(zeilen) + "\n", encoding="ascii")
    return path


def bewerte(tmp_path, massnahmen, eintraege, bewertet_ab="2026-12-01",
            offene=("PRUEFUNG", "NACHWEIS", "NUTZEN", "MONITORING",
                    "VERBESSERUNG")):
    plan = load_plan(plan_file(tmp_path, massnahmen))
    report = load_status_report(status_report(tmp_path, offene=offene))
    eintraege_geladen = []
    for e in eintraege:
        eintrag = dict(e)
        eintrag.setdefault("initiative_id", "pil-x-2026")
        eintrag.setdefault("indicator", "nutzwert")
        eintrag.setdefault("source", "test")
        eintraege_geladen.append(eintrag)
    return assess(plan, report, eintraege_geladen,
                  _bewertet_ab_parsen(bewertet_ab))


# --- stichtag ----------------------------------------------------------

def test_bewertet_ab_parsen_ok():
    assert _bewertet_ab_parsen("2026-12-01") == date(2026, 12, 1)


@pytest.mark.parametrize("schlecht", ["spaeter", "01.12.2026", ""])
def test_bewertet_ab_parsen_fail_closed(schlecht):
    with pytest.raises(KreislaufInputError, match="bewertet-ab"):
        _bewertet_ab_parsen(schlecht)


# --- assess: erfuellt / nicht erfuellt / nicht messbar ------------------

def test_erfuellt_nach_stichtag(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 11, "measured_at": "2026-12-02"}])
    assert report["verdict"] == VERDICT_GESCHLOSSEN
    assert report["massnahmen"][0]["status"] == ERFUELLT
    assert report["massnahmen"][0]["werte_nach_stichtag"] == [11.0]


def test_wert_vor_stichtag_zaehlt_nicht(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 11, "measured_at": "2026-11-30"}])
    assert report["verdict"] == VERDICT_OFFEN
    assert report["massnahmen"][0]["status"] == NICHT_MESSBAR


def test_nicht_erfuellt_unter_zielwert(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 4, "measured_at": "2026-12-05"}])
    assert report["verdict"] == VERDICT_OFFEN
    assert report["massnahmen"][0]["status"] == NICHT_ERFUELLT
    assert report["massnahmen"][0]["bestwert"] == 4.0


def test_stichtag_selber_tag_zaehlt(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 10, "measured_at": "2026-12-01T12:00:00Z"}])
    assert report["massnahmen"][0]["status"] == ERFUELLT


def test_bester_von_mehreren_werten_entscheidet(tmp_path):
    report = bewerte(tmp_path, [massnahme(zielwert=10.0)],
                     [{"value": 2, "measured_at": "2026-12-02"},
                      {"value": 15, "measured_at": "2026-12-03"}])
    assert report["massnahmen"][0]["status"] == ERFUELLT
    assert report["massnahmen"][0]["bestwert"] == 15.0


def test_keine_neue_evidenz_nicht_messbar(tmp_path):
    report = bewerte(tmp_path, [massnahme()], [])
    assert report["verdict"] == VERDICT_OFFEN
    assert report["massnahmen"][0]["status"] == NICHT_MESSBAR
    assert "VOLLZUG != GEMESSEN" in report["massnahmen"][0]["grund"]


# --- unbrauchbare eintraege: keine stille korrektur ---------------------

def test_unbrauchbares_datum_gefuehrt_nicht_zaehlt(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 99, "measured_at": "irgendwann"}])
    assert report["massnahmen"][0]["status"] == NICHT_MESSBAR
    assert report["massnahmen"][0]["unbrauchbare_eintraege"] == [
        "eintrag 99 ohne iso-datum ('irgendwann')"]


def test_wert_ohne_zahl_gefuehrt_nicht_zaehlt(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": "viel", "measured_at": "2026-12-02"},
                      {"value": True, "measured_at": "2026-12-02"}])
    assert report["massnahmen"][0]["status"] == NICHT_MESSBAR
    assert len(report["massnahmen"][0]["unbrauchbare_eintraege"]) == 2


def test_fremder_indikator_zaehlt_nicht(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 99, "measured_at": "2026-12-02",
                       "indicator": "anderer"}])
    assert report["massnahmen"][0]["status"] == NICHT_MESSBAR


# --- gate-reuse: abgelehnte massnahme nicht pruefbar --------------------

def test_abgelehnte_massnahme_nicht_pruefbar(tmp_path):
    schrott = {
        "id": "mbloed",
        "phase": "MOEGLICHKEIT",
        "befund": {"quelle": "x", "datum": "2026-11-23"},
        "ziel": {"indikator": "nutzwert", "zielwert": 1,
                 "messfenster": "x", "methode": "y"},
        "verantwortung": "operator",
    }
    report = bewerte(tmp_path, [schrott],
                     [{"value": 99, "measured_at": "2026-12-02"}])
    assert report["verdict"] == VERDICT_OFFEN
    assert report["massnahmen"][0]["status"] == NICHT_PRUEFBAR


def test_mischung_erfuellt_und_nicht_messbar_offen(tmp_path):
    zwei = [massnahme(mid="m1", indikator="nutzwert", zielwert=10),
            massnahme(mid="m2", indikator="sparwert", zielwert=5)]
    report = bewerte(tmp_path, zwei,
                     [{"value": 12, "measured_at": "2026-12-02",
                       "indicator": "nutzwert"}],
                     offene=("NUTZEN", "PRUEFUNG"))
    assert report["massnahmen_pruefbar"] == 2
    assert report["massnahmen_erfuellt"] == 1
    assert report["verdict"] == VERDICT_OFFEN


# --- CLI: exit-codes und report-schreiben -------------------------------

def test_cli_exit_geschlossen(tmp_path, capsys):
    plan_path = plan_file(tmp_path, [massnahme()])
    status_path = status_report(tmp_path)
    ledger_path = ledger_datei(tmp_path, [
        {"value": 11, "measured_at": "2026-12-02"}])
    code = main([str(plan_path), "--status-report", str(status_path),
                 "--ledger", str(ledger_path),
                 "--bewertet-ab", "2026-12-01"])
    out = capsys.readouterr().out
    assert code == EXIT_GESCHLOSSEN
    assert "V91 Kreislauf-Erneute-Pruefung" in out
    assert ERFUELLT in out


def test_cli_exit_offen(tmp_path, capsys):
    plan_path = plan_file(tmp_path, [massnahme()])
    status_path = status_report(tmp_path)
    ledger_path = ledger_datei(tmp_path, [
        {"value": 3, "measured_at": "2026-12-02"}])
    code = main([str(plan_path), "--status-report", str(status_path),
                 "--ledger", str(ledger_path),
                 "--bewertet-ab", "2026-12-01"])
    assert code == EXIT_OFFEN


def test_cli_ledger_fehlt_input_error(tmp_path, capsys):
    plan_path = plan_file(tmp_path, [massnahme()])
    status_path = status_report(tmp_path)
    code = main([str(plan_path), "--status-report", str(status_path),
                 "--ledger", str(tmp_path / "fehlt.jsonl"),
                 "--bewertet-ab", "2026-12-01"])
    err = capsys.readouterr().err
    assert code == EXIT_INPUT_ERROR
    assert "INPUT_ERROR" in err


def test_cli_initiative_mismatch_input_error(tmp_path, capsys):
    plan_path = plan_file(tmp_path, [massnahme()], initiative="andere-init")
    status_path = status_report(tmp_path)
    ledger_path = ledger_datei(tmp_path, [
        {"value": 11, "measured_at": "2026-12-02"}])
    code = main([str(plan_path), "--status-report", str(status_path),
                 "--ledger", str(ledger_path),
                 "--bewertet-ab", "2026-12-01"])
    assert code == EXIT_INPUT_ERROR


def test_cli_report_dir_schreibt_txt_und_json(tmp_path):
    plan_path = plan_file(tmp_path, [massnahme()])
    status_path = status_report(tmp_path)
    ledger_path = ledger_datei(tmp_path, [
        {"value": 11, "measured_at": "2026-12-02"}])
    out_dir = tmp_path / "reports"
    main([str(plan_path), "--status-report", str(status_path),
          "--ledger", str(ledger_path), "--bewertet-ab", "2026-12-01",
          "--report-dir", str(out_dir)])
    names = sorted(p.name for p in out_dir.iterdir())
    assert names == ["kreislauf_erneute_pruefung_pil-x-2026.json",
                     "kreislauf_erneute_pruefung_pil-x-2026.txt"]
    geladen = json.loads(
        (out_dir / names[0]).read_text(encoding="ascii"))
    assert geladen["verdict"] == VERDICT_GESCHLOSSEN


def test_format_text_report_ascii_und_deterministisch(tmp_path):
    report = bewerte(tmp_path, [massnahme()],
                     [{"value": 11, "measured_at": "2026-12-02"}])
    text = format_text_report(report)
    text.encode("ascii")
    assert text == format_text_report(
        bewerte(tmp_path, [massnahme()],
                [{"value": 11, "measured_at": "2026-12-02"}]))
    assert "MESSWERT != URSACHE" in text
