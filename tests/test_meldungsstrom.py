"""Tests fuer controller/meldungsstrom.py (VIBE-LXXXCVI)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller import meldungsstrom as ms
from controller.nachrichten_lagebild import (
    EXIT_INPUT_ERROR as LB_INPUT_ERROR,
    bewerte_bereich as lb_bewerte_bereich,
)


def _meldung(bereich="energie", richtung="besser", claim="EE-Ausbau steigt"):
    return {
        "bereich": bereich,
        "claim": claim,
        "source": "quelle test",
        "date": "2026-11-24",
        "richtung": richtung,
    }


def _zeilen(n, **kwargs):
    return [json.dumps(_meldung(**kwargs)) for _ in range(n)]


# ---------- parse_zeile ----------

def test_parse_zeile_gueltig():
    assert ms.parse_zeile(json.dumps({"a": 1})) == {"a": 1}


def test_parse_zeile_kein_json_fail_closed():
    with pytest.raises(ms.MeldungsstromError):
        ms.parse_zeile("kein json {")


def test_parse_zeile_nicht_objekt_fail_closed():
    with pytest.raises(ms.MeldungsstromError):
        ms.parse_zeile(json.dumps([1, 2]))


def test_parse_zeile_nan_abgelehnt():
    with pytest.raises(ms.MeldungsstromError):
        ms.parse_zeile('{"x": NaN}')


def test_parse_zeile_infinity_abgelehnt():
    with pytest.raises(ms.MeldungsstromError):
        ms.parse_zeile('{"x": Infinity}')


# ---------- _meldung_ok (REUSE _entry_ok) ----------

def test_meldung_ok_volle_meldung():
    valid, grund = ms._meldung_ok(_meldung())
    assert valid and grund == ""


def test_meldung_ohne_claim_ungueltig():
    m = _meldung()
    del m["claim"]
    valid, grund = ms._meldung_ok(m)
    assert not valid and grund == "claim_source_date_unvollstaendig"


def test_meldung_leere_source_ungueltig():
    m = _meldung()
    m["source"] = "   "
    valid, grund = ms._meldung_ok(m)
    assert not valid and grund == "claim_source_date_unvollstaendig"


def test_meldung_bereich_mit_umbruch_ungueltig():
    m = _meldung()
    m["bereich"] = " energie "
    valid, grund = ms._meldung_ok(m)
    assert not valid and grund == "bereich_ungueltig"


def test_meldung_richtung_unbekannt_ungueltig():
    m = _meldung()
    m["richtung"] = "vielleicht"
    valid, grund = ms._meldung_ok(m)
    assert not valid and grund == "richtung_ungueltig"


# ---------- verarbeite_strom: Kernverhalten ----------

def test_strom_leer_ist_unknown_exit0():
    r = ms.verarbeite_strom([], "LEER")
    assert r["n_gesamt"] == 0 and r["gesamt_tendenz"] == "UNKNOWN"


def test_strom_besser_ueberwiegt():
    r = ms.verarbeite_strom(
        _zeilen(3, richtung="besser") + _zeilen(1, richtung="neutral"), "B"
    )
    # REUSE-Paritaet: jeder besser UND schlechter waere GEMISCHT (kein
    # Mehrheitszaehlen); hier ohne schlechter = BESSER
    assert r["bereiche"]["energie"]["tendenz"] == "BESSER"
    assert r["gesamt_tendenz"] == "BESSER"
    assert r["n_gueltig"] == 4 and r["n_ungueltig"] == 0


def test_strom_gemischt():
    r = ms.verarbeite_strom(
        _zeilen(2, richtung="besser") + _zeilen(2, richtung="schlechter"), "G"
    )
    assert r["bereiche"]["energie"]["tendenz"] == "GEMISCHT"
    # Einzelner GEMISCHT-Bereich: bewerte_gesamt kennt kein GEMISCHT ->
    # NEUTRAL (REUSE-Paritaet, keine Zweitbewertung)
    assert r["gesamt_tendenz"] == "NEUTRAL"


def test_strom_mehrere_bereiche_gesamt_nur_besser_und_neutral():
    r = ms.verarbeite_strom(
        _zeilen(1, bereich="energie", richtung="besser")
        + _zeilen(1, bereich="krieg", richtung="neutral"),
        "MB",
    )
    assert set(r["bereiche"]) == {"energie", "krieg"}
    assert r["gesamt_tendenz"] == "NEUTRAL" or r["gesamt_tendenz"] == "BESSER"


def test_strom_gesamt_schlechter_wenn_nur_schlechter():
    r = ms.verarbeite_strom(_zeilen(2, bereich="klima", richtung="schlechter"), "S")
    assert r["gesamt_tendenz"] == "SCHLECHTER"


def test_strom_ungueltige_mit_zeilennummer_gefuehrt_nie_gedroppt():
    zeilen = _zeilen(2) + [""] + [json.dumps({"bereich": "energie"})]
    r = ms.verarbeite_strom(zeilen, "U")
    assert r["n_gesamt"] == 4 and r["n_ungueltig"] == 2
    assert r["ungueltige_zeilen"][0] == {"zeile": 3, "grund": "leere_zeile"}
    assert r["ungueltige_zeilen"][1]["grund"] == "claim_source_date_unvollstaendig"


def test_strom_malformed_json_fail_closed():
    with pytest.raises(ms.MeldungsstromError):
        ms.verarbeite_strom(_zeilen(1) + ["{kein json"], "X")


def test_strom_bericht_id_leer_fail_closed():
    with pytest.raises(ms.MeldungsstromError):
        ms.verarbeite_strom(_zeilen(1), " ")


def test_strom_reuse_nachrichten_lagebild_gleiche_bewertung():
    eintraege = [dict(_meldung(richtung=d)) for d in ("besser", "besser", "neutral")]
    zeilen = [json.dumps(e) for e in eintraege]
    r = ms.verarbeite_strom(zeilen, "R")
    assert r["bereiche"]["energie"] == lb_bewerte_bereich(eintraege)


def test_strom_headerreihe_zaehlt_als_ungueltig_nicht_verloren():
    r = ms.verarbeite_strom([""], "H")
    assert r["ungueltige_zeilen"] == [{"zeile": 1, "grund": "leere_zeile"}]


# ---------- Hochvolumen (Betreiber-Direktiv: tausende taeglich) ----------

def test_strom_hochvolumen_5000_meldungen_ehrlich_und_vollstaendig():
    zeilen = (
        _zeilen(2000, bereich="energie", richtung="besser")
        + _zeilen(1500, bereich="klima", richtung="schlechter")
        + _zeilen(1000, bereich="krieg", richtung="neutral")
        + _zeilen(499, bereich="gesundheit", richtung="besser")
        + ["", json.dumps({"bereich": "energie"})]
    )
    r = ms.verarbeite_strom(zeilen, "HV")
    assert r["n_gesamt"] == 5001
    assert r["n_gueltig"] == 4999
    assert r["n_ungueltig"] == 2
    assert r["bereiche"]["energie"]["besser"] == 2000
    assert r["bereiche"]["klima"]["schlechter"] == 1500
    assert r["gesamt_tendenz"] == "GEMISCHT"


def test_strom_max_lines_ueberschritten_fail_closed(monkeypatch):
    monkeypatch.setattr(ms, "MAX_LINES_DEFAULT", 5)
    with pytest.raises(ms.MeldungsstromError):
        ms.verarbeite_strom(_zeilen(6), "ML")


def test_strom_max_lines_exakt_grenzfall_erlaubt(monkeypatch):
    monkeypatch.setattr(ms, "MAX_LINES_DEFAULT", 5)
    r = ms.verarbeite_strom(_zeilen(5), "ML5")
    assert r["n_gesamt"] == 5


# ---------- check_strom_datei / CLI ----------

def test_check_strom_datei_exit0(tmp_path):
    p = tmp_path / "strom.ndjson"
    p.write_text("\n".join(_zeilen(3)), encoding="utf-8")
    report, code = ms.check_strom_datei(p, "D1")
    assert code == ms.EXIT_OK and report["n_gueltig"] == 3


def test_check_strom_datei_ungueltige_exit1(tmp_path):
    p = tmp_path / "strom.ndjson"
    p.write_text(_zeilen(1)[0] + "\n\n", encoding="utf-8")
    report, code = ms.check_strom_datei(p, "D2")
    assert code == ms.EXIT_VIOLATIONS and report["n_ungueltig"] == 1


def test_check_strom_datei_malformed_exit3(tmp_path):
    p = tmp_path / "strom.ndjson"
    p.write_text("{schrott", encoding="utf-8")
    report, code = ms.check_strom_datei(p, "D3")
    assert code == ms.EXIT_INPUT_ERROR and "error" in report


def test_check_strom_datei_fehlt_exit3(tmp_path):
    report, code = ms.check_strom_datei(tmp_path / "gibt-es-nicht.ndjson", "D4")
    assert code == ms.EXIT_INPUT_ERROR


def test_cli_json_out_im_repo_abgewiesen(tmp_path, capsys):
    code = ms.main([str(tmp_path / "in.ndjson"), "--json-out",
                    os.path.join(os.path.dirname(__file__), "unten", "out.json")])
    assert code == ms.EXIT_INPUT_ERROR
    assert "Ragnarok-Phase-1" in capsys.readouterr().out


def test_cli_json_out_ausserhalb_erlaubt(tmp_path):
    infile = tmp_path / "strom.ndjson"
    infile.write_text("\n".join(_zeilen(2)), encoding="utf-8")
    outfile = tmp_path / "report.json"
    code = ms.main([str(infile), "--bericht-id", "CLI-1", "--json-out", str(outfile)])
    assert code == ms.EXIT_OK
    data = json.loads(outfile.read_text(encoding="utf-8"))
    assert data["bericht_id"] == "CLI-1" and data["n_gueltig"] == 2


def test_cli_bericht_id_default_aus_dateiname(tmp_path, capsys):
    infile = tmp_path / "mein-strom.ndjson"
    infile.write_text("\n".join(_zeilen(1)), encoding="utf-8")
    code = ms.main([str(infile)])
    out = capsys.readouterr().out
    assert code == ms.EXIT_OK
    assert "meldungsstrom-mein-strom.ndjson" in out
    assert "GESAMT-TENDENZ: BESSER" in out


def test_format_text_report_zeigt_grenzen():
    r = ms.verarbeite_strom(_zeilen(1), "F")
    text = ms.format_text_report(r)
    assert "STROM != SYSTEM" in text
    assert "GRENZE:" in text
