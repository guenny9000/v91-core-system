"""Tests fuer controller.kreislauf_status (VIBE-LXX).

Alle Tests laufen offline, deterministisch, reine Standardbibliothek
(STUB != ECHT gilt hier nicht: ECHTE Dateien in tmp_path).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.kreislauf_status import (  # noqa: E402
    BELEGT,
    KreislaufInputError,
    EXIT_ALLE_BELEGT,
    EXIT_INPUT_ERROR,
    EXIT_OFFENE_PHASEN,
    NICHT_GEPRUEFT,
    assess,
    load_dataset,
    load_ledger,
    main,
)


def _dataset(tmp_path, indicators=None):
    if indicators is None:
        indicators = [{
            "role": "WIRKUNG",
            "name": "test-wirkung",
            "baseline": 0.0,
            "target": 10.0,
            "method": "zaehlung",
            "verifier": "operator",
            "period": {"baseline_at": "2026-01-01T00:00:00Z",
                       "target_at": "2027-01-01T00:00:00Z"},
        }]
    ds = {
        "initiative_id": "test-initiative-2026",
        "indicators": indicators,
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(ds), encoding="ascii")
    return path


def _ledger(tmp_path, entries, name="ledger.jsonl"):
    path = tmp_path / name
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def _eintrag(indicator, value, measured_at, note=None):
    e = {
        "initiative_id": "test-initiative-2026",
        "indicator": indicator,
        "value": value,
        "measured_at": measured_at,
        "source": "https://example.org/test",
        "measured_by": "operator",
    }
    if note is not None:
        e["note"] = note
    return e


# --- Dataset-Loader -------------------------------------------------------

def test_load_dataset_ok(tmp_path):
    path = _dataset(tmp_path)
    ds = load_dataset(path)
    assert ds["initiative_id"] == "test-initiative-2026"
    assert len(ds["indicators"]) == 1


def test_load_dataset_fehlt(tmp_path):
    with pytest.raises(KreislaufInputError):
        load_dataset(tmp_path / "fehlt.json")


def test_load_dataset_kein_json(tmp_path):
    path = tmp_path / "kaputt.json"
    path.write_text("{kein json", encoding="ascii")
    with pytest.raises(KreislaufInputError):
        load_dataset(path)


def test_load_dataset_indikatoren_leer(tmp_path):
    path = tmp_path / "leer.json"
    path.write_text('{"initiative_id": "x", "indicators": []}',
                    encoding="ascii")
    with pytest.raises(KreislaufInputError):
        load_dataset(path)


def test_load_dataset_fehlendes_feld(tmp_path):
    path = tmp_path / "ohne.json"
    path.write_text('{"indicators": [{}]}', encoding="ascii")
    with pytest.raises(KreislaufInputError):
        load_dataset(path)


# --- Ledger-Loader --------------------------------------------------------

def test_load_ledger_none_ohne_datei():
    assert load_ledger(None, "x") == []


def test_load_ledger_kaputte_zeile(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"initiative_id": "x"' + "\n", encoding="ascii")
    with pytest.raises(KreislaufInputError):
        load_ledger(path, "x")


def test_load_ledger_fremde_initiative_wird_korrekt_ignoriert(tmp_path):
    e = _eintrag("test-wirkung", 1.0, "2026-02-01T00:00:00Z")
    e["initiative_id"] = "andere-initiative"
    path = _ledger(tmp_path, [e])
    assert load_ledger(path, "test-initiative-2026") == []


def test_load_ledger_fehlendes_pflichtfeld(tmp_path):
    e = _eintrag("test-wirkung", 1.0, "2026-02-01T00:00:00Z")
    del e["source"]
    path = _ledger(tmp_path, [e])
    with pytest.raises(KreislaufInputError):
        load_ledger(path, "test-initiative-2026")


# --- assess: Phasen -------------------------------------------------------

def _load_dataset_via_dict():
    return {
        "initiative_id": "test-initiative-2026",
        "indicators": [{
            "role": "WIRKUNG",
            "name": "test-wirkung",
            "baseline": 0.0,
            "target": 10.0,
            "method": "zaehlung",
            "verifier": "operator",
            "period": {"baseline_at": "2026-01-01T00:00:00Z",
                       "target_at": "2027-01-01T00:00:00Z"},
        }],
    }


load_dataset_via_dict = _load_dataset_via_dict


def test_assess_vollstaendiger_kreislauf():
    ds = load_dataset_via_dict()
    entries = [
        _eintrag("test-wirkung", 1.0, "2026-02-01T00:00:00Z"),
        _eintrag("test-wirkung", 5.0, "2026-03-01T00:00:00Z"),
    ]
    report = assess(ds, entries)
    assert report["phasen"]["MOEGLICHKEIT"]["verdict"] == BELEGT
    assert report["phasen"]["PRUEFUNG"]["verdict"] == BELEGT
    assert report["phasen"]["NACHWEIS"]["verdict"] == BELEGT
    assert report["phasen"]["NUTZEN"]["verdict"] == BELEGT
    assert report["phasen"]["MONITORING"]["verdict"] == BELEGT
    assert report["phasen"]["VERBESSERUNG"]["verdict"] == BELEGT
    assert report["offene_phasen"] == []


def test_assess_ohne_ledger_unknown_phasen():
    ds = _load_dataset_via_dict()
    report = assess(ds, [])
    assert report["phasen"]["MOEGLICHKEIT"]["verdict"] == BELEGT
    assert report["phasen"]["NACHWEIS"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["NUTZEN"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["MONITORING"]["verdict"] == NICHT_GEPRUEFT
    assert "NACHWEIS" in report["offene_phasen"]


def test_assess_pruefung_unvollstaendig():
    ds = _load_dataset_via_dict()
    ds["indicators"][0].pop("method")
    report = assess(ds, [])
    assert report["phasen"]["PRUEFUNG"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["PRUEFUNG"]["unvollstaendige_indikatoren"] == [
        "test-wirkung"]


def test_assess_ein_eintrag_nutzen_ohne_monitoring():
    ds = _load_dataset_via_dict()
    entries = [_eintrag("test-wirkung", 3.0, "2026-02-01T00:00:00Z")]
    report = assess(ds, entries)
    assert report["phasen"]["NACHWEIS"]["verdict"] == BELEGT
    assert report["phasen"]["NUTZEN"]["verdict"] == BELEGT
    assert report["phasen"]["MONITORING"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["VERBESSERUNG"]["verdict"] == NICHT_GEPRUEFT


def test_assess_fremdindikator_nicht_belegt():
    ds = _load_dataset_via_dict()
    entries = [_eintrag("gibts-nicht", 1.0, "2026-02-01T00:00:00Z")]
    report = assess(ds, entries)
    assert report["phasen"]["NACHWEIS"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["NACHWEIS"]["fremdindikatoren"] == ["gibts-nicht"]


def test_assess_wirkung_unter_baseline_kein_nutzen():
    ds = _load_dataset_via_dict()
    entries = [_eintrag("test-wirkung", 0.0, "2026-02-01T00:00:00Z")]
    report = assess(ds, entries)
    assert report["phasen"]["NUTZEN"]["verdict"] == NICHT_GEPRUEFT


def test_assess_ruecklauf_ist_keine_verbesserung():
    ds = _load_dataset_via_dict()
    entries = [
        _eintrag("test-wirkung", 5.0, "2026-02-01T00:00:00Z"),
        _eintrag("test-wirkung", 1.0, "2026-03-01T00:00:00Z"),
    ]
    report = assess(ds, entries)
    assert report["phasen"]["VERBESSERUNG"]["verdict"] == NICHT_GEPRUEFT
    assert report["phasen"]["MONITORING"]["verdict"] == BELEGT


def test_assess_resilienz_zaehlt_fuer_verbesserung():
    ds = _load_dataset_via_dict()
    ds["indicators"][0]["role"] = "RESILIENZ"
    entries = [
        _eintrag("test-wirkung", 1.0, "2026-02-01T00:00:00Z"),
        _eintrag("test-wirkung", 2.0, "2026-03-01T00:00:00Z"),
    ]
    report = assess(ds, entries)
    assert report["phasen"]["VERBESSERUNG"]["verdict"] == BELEGT


def test_assess_grenze_im_report():
    report = assess(_load_dataset_via_dict(), [])
    assert "GELESEN != VERIFIZIERT" in report["grenzen"]
    assert "REVIEW != ENTSCHEIDUNG" in report["grenzen"]


# --- CLI ------------------------------------------------------------------

def test_cli_vollstaendig(tmp_path, capsys):
    dspath = _dataset(tmp_path)
    ledpath = _ledger(tmp_path, [
        _eintrag("test-wirkung", 1.0, "2026-02-01T00:00:00Z"),
        _eintrag("test-wirkung", 5.0, "2026-03-01T00:00:00Z"),
    ])
    rc = main([str(dspath), "--ledger", str(ledpath)])
    out = capsys.readouterr().out
    assert rc == EXIT_ALLE_BELEGT
    assert "MOEGLICHKEIT" in out
    assert "offene phasen  : keine" in out


def test_cli_offene_phasen(tmp_path):
    dspath = _dataset(tmp_path)
    rc = main([str(dspath)])
    assert rc == EXIT_OFFENE_PHASEN


def test_cli_input_error(tmp_path):
    rc = main([str(tmp_path / "fehlt.json")])
    assert rc == EXIT_INPUT_ERROR


def test_cli_report_dir(tmp_path):
    dspath = _dataset(tmp_path)
    ledpath = _ledger(tmp_path, [
        _eintrag("test-wirkung", 2.0, "2026-02-01T00:00:00Z"),
        _eintrag("test-wirkung", 4.0, "2026-03-01T00:00:00Z"),
    ])
    outdir = tmp_path / "reports"
    rc = main([str(dspath), "--ledger", str(ledpath),
               "--report-dir", str(outdir)])
    assert rc == EXIT_ALLE_BELEGT
    txt = (outdir / "kreislauf_test-initiative-2026.txt").read_text("ascii")
    payload = json.loads(
        (outdir / "kreislauf_test-initiative-2026.json").read_text("ascii"))
    assert "V91 Kreislauf-Status" in txt
    assert payload["initiative_id"] == "test-initiative-2026"


def test_report_ascii_pure():
    from controller.kreislauf_status import format_text_report
    report = assess(_load_dataset_via_dict(), [])
    text = format_text_report(report)
    bad = [ch for ch in text if ord(ch) > 126]
    assert bad == []


def test_offene_phasen_reihenfolge_deterministisch():
    report = assess(_load_dataset_via_dict(), [])
    assert report["offene_phasen"] == [
        "NACHWEIS", "NUTZEN", "MONITORING", "VERBESSERUNG"]
