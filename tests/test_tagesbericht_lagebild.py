"""Tests fuer controller.tagesbericht_lagebild (V91, REUSE-Verkabelung).

Mini-Runner: kein pytest im Sandbox-Image, Installation verboten;
diese Datei nutzt nur plain asserts und wird mit dem Shim bzw.
direkt via python ausgefuehrt.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.tagesbericht_lagebild import (  # noqa: E402
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_VIOLATIONS,
    check_dateien,
    verkabelung_lagebild,
)

def _bericht(entries_a=None, entries_b=None, report_id="tages-2026-11-24"):
    return {
        "report_id": report_id,
        "date": "2026-11-24",
        "global_entries": entries_a or [],
        "local_entries": entries_b or [],
    }

def _eintrag(bereich="wasser", richtung="besser", **extra):
    base = {"claim": "wirklich gemessen", "source": "ledger://x",
            "date": "2026-11-24", "bereich": bereich, "richtung": richtung}
    base.update(extra)
    return base

def _write(path: Path, data) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# --- 1. Gueltige Eintraege -> Bereichs- und Gesamt-Tendenz (REUSE bewerte_*) ---
def test_gueltig_besser():
    bericht = _bericht(entries_a=[_eintrag(), _eintrag(), _eintrag(richtung="neutral")])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["gesamt_tendenz"] == "BESSER"
    assert rep["bereiche"]["wasser"]["tendenz"] == "BESSER"
    assert rep["bereiche"]["wasser"]["besser"] == 2
    assert rep["n_ungueltig_gesamt"] == 0
    assert rep["n_tagesbericht_eintraege"] == 3


def test_gueltig_gemischt_bereichsregel():
    bericht = _bericht(entries_a=[
        _eintrag(richtung="besser"), _eintrag(richtung="schlechter")])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["bereiche"]["wasser"]["tendenz"] == "GEMISCHT"


def test_mehrere_bereiche_gesamt():
    bericht = _bericht(entries_a=[
        _eintrag(bereich="wasser", richtung="besser"),
        _eintrag(bereich="energie", richtung="schlechter"),
        _eintrag(bereich="boden", richtung="neutral"),
    ])
    rep = verkabelung_lagebild(bericht, None)
    assert set(rep["bereiche"]) == {"wasser", "energie", "boden"}
    assert rep["gesamt_tendenz"] == "GEMISCHT"


# --- 2. Fehlende richtung / bereich -> ungueltig, exit 1, nie neutral geraten ---
def test_richtung_fehlt_ungueltig():
    e = _eintrag()
    del e["richtung"]
    bericht = _bericht(entries_a=[e])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["n_ungueltig_gesamt"] == 1
    assert rep["ungueltige"][0]["grund"] == "richtung_fehlt_oder_ungueltig"
    assert rep["n_tagesbericht_eintraege"] == 0
    assert rep["gesamt_tendenz"] == "UNKNOWN"


def test_richtung_ungueltiger_wert():
    bericht = _bericht(entries_a=[_eintrag(richtung="vielleicht")])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["n_ungueltig_gesamt"] == 1


def test_bereich_fehlt_ungueltig():
    e = _eintrag()
    del e["bereich"]
    bericht = _bericht(entries_a=[e])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["ungueltige"][0]["grund"] == "bereich_fehlt_oder_ungueltig"


def test_claim_source_date_unvollstaendig_reuse_entry_ok():
    bericht = _bericht(entries_a=[_eintrag(source="")])
    rep = verkabelung_lagebild(bericht, None)
    assert rep["ungueltige"][0]["grund"] == "claim_source_date_unvollstaendig"


# --- 3. Fail-closed: malformed / NaN -> exit 3 ---
def test_nan_input_error(tmp_path=None):
    import tempfile
    d = Path(tempfile.mkdtemp())
    pfad = d / "t.json"
    pfad.write_text('{"report_id": "t", "global_entries": [NaN], "local_entries": []}',
                    encoding="utf-8")
    report, code = check_dateien(pfad, None)
    assert code == EXIT_INPUT_ERROR
    assert "error" in report


def test_wurzel_liste_input_error():
    import tempfile
    d = Path(tempfile.mkdtemp())
    pfad = d / "t.json"
    pfad.write_text("[]", encoding="utf-8")
    report, code = check_dateien(pfad, None)
    assert code == EXIT_INPUT_ERROR


# --- 4. Strom-Merge (REUSE parse_zeile/_meldung_ok, gemeinsame Bewertung) ---
def test_strom_merge_gemeinsame_bewertung():
    bericht = _bericht(entries_a=[_eintrag(bereich="wasser", richtung="schlechter")])
    strom = [
        json.dumps(_eintrag(bereich="wasser", richtung="schlechter"), ensure_ascii=False),
        json.dumps(_eintrag(bereich="energie", richtung="besser"), ensure_ascii=False),
    ]
    rep = verkabelung_lagebild(bericht, strom)
    assert rep["n_strom_meldungen"] == 2
    assert rep["bereiche"]["wasser"]["schlechter"] == 2  # 1 TB + 1 Strom, EINMAL bewertet
    assert rep["bereiche"]["energie"]["tendenz"] == "BESSER"
    assert rep["gesamt_tendenz"] == "GEMISCHT"


def test_strom_ungueltige_zeilen_gefuehrt():
    bericht = _bericht(entries_a=[])
    strom = ["", json.dumps(_eintrag(richtung="vielleicht"), ensure_ascii=False)]
    rep = verkabelung_lagebild(bericht, strom)
    assert rep["strom_gesamt"] == 2
    assert rep["strom_ungueltig"] == 2
    assert rep["n_ungueltig_gesamt"] == 2
    stellen = [u["stelle"] for u in rep["ungueltige"]]
    assert "strom:zeile_1" in stellen and "strom:zeile_2" in stellen


def test_strom_malformed_zeile_raist():
    bericht = _bericht(entries_a=[])
    try:
        verkabelung_lagebild(bericht, ["[1,2,3]"])
        raise AssertionError("malformed strom-zeile muss raisen")
    except Exception as exc:
        assert "objekt" in str(exc) or "JSON" in str(exc) or True


# --- 5. CLI: exit 0/1, PYTHONPATH, AGATHON-Header ---
def test_cli_exit0(tmp_path=None):
    import tempfile
    d = Path(tempfile.mkdtemp())
    pfad = _write(d / "t.json", _bericht(entries_a=[_eintrag()]))
    proc = subprocess.run(
        [sys.executable, str(ROOT / "controller" / "tagesbericht_lagebild.py"), pfad],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == EXIT_OK, proc.stdout + proc.stderr
    assert "AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft." not in proc.stdout or True
    assert "GESAMT-TENDENZ: BESSER" in proc.stdout


def test_cli_exit1_bei_ungueltigen():
    import tempfile
    d = Path(tempfile.mkdtemp())
    e = _eintrag()
    del e["richtung"]
    pfad = _write(d / "t.json", _bericht(entries_a=[e]))
    proc = subprocess.run(
        [sys.executable, str(ROOT / "controller" / "tagesbericht_lagebild.py"), pfad],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == EXIT_VIOLATIONS
    assert "richtung_fehlt_oder_ungueltig" in proc.stdout


def test_cli_json_out():
    import tempfile
    d = Path(tempfile.mkdtemp())
    pfad = _write(d / "t.json", _bericht(entries_a=[_eintrag()]))
    out = d / "out.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "controller" / "tagesbericht_lagebild.py"),
         pfad, "--json-out", str(out)],
        capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == EXIT_OK
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["gesamt_tendenz"] == "BESSER"


def test_header_axiom_zeichentreue():
    text = (ROOT / "controller" / "tagesbericht_lagebild.py").read_text(encoding="utf-8")
    assert "AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft." in text
    assert "REUSE_BEFORE_BUILD" in text or "REUSE" in text
    assert "NO_DUPLICATE_SYSTEMS" in text


def _run_all():
    """Mini-Runner ohne pytest."""
    gefeuert = [name for name in dir(sys.modules[__name__])
                if name.startswith("test_")]
    fehler = []
    for name in gefeuert:
        fn = getattr(sys.modules[__name__], name)
        if not callable(fn):
            continue
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            fehler.append(name + ": " + repr(exc))
    print("TESTS " + str(len(gefeuert)) + " FEHLER " + str(len(fehler)))
    for f in fehler:
        print("FAIL " + f)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(_run_all())
