"""Ehrlichkeits-Verriegelung fuer controller/nachweis_check.py (28.11.2026).

Anlass: Phantom-Bericht '16/18 BELEGT' (28.11., Office-Agent) gegen
nicht existierende Pfade. Diese Tests pinnen das ehrliche Verhalten:
- BELEGT zaehlt NUR Punkte, deren Pruefung wirklich lief.
- NICHT_GEPRUEFT bleibt NICHT_GEPRUEFT, egal wie oft behauptet.
- Betreiber-Punkte werden NICHT vom Repo-Check 'belegt' (FREIGABE !=
  BERECHTIGUNG, SCRIPTED != INSTALLED, UNKNOWN != PASS).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

_spec = importlib.util.spec_from_file_location(
    "nachweis_check_mod", str(REPO_ROOT / "controller" / "nachweis_check.py"))
nachweis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nachweis)

ERGEBNIS = nachweis.pruefe(REPO_ROOT)


def test_bestandsmodule_belegt():
    punkt = next(p for p in ERGEBNIS["belegt"] if p["punkt"] == "bestandsmodule_existieren")
    assert punkt["status"] == "BELEGT"


def test_runtime_requirements_belegt_und_minimal():
    punkt = next(p for p in ERGEBNIS["belegt"] if p["punkt"] == "runtime_requirements")
    assert punkt["status"] == "BELEGT"
    assert punkt["messwert"] == "Runtime-Menge = cryptography"


def test_index_und_archiv_lint_belegt():
    punkt = next(p for p in ERGEBNIS["belegt"] if p["punkt"] == "index_archiv_lint")
    assert punkt["status"] == "BELEGT"


def test_zaehler_zahlen_nur_gelaufene_pruefungen():
    z = ERGEBNIS["zaehler"]
    assert z["belegt"] == z["belegt_gesamt"] == 4
    assert z["nicht_geprueft"] == 4
    assert z["nur_betreiber"] == 2


def test_nicht_geprueft_bleibt_nicht_geprueft():
    punkte = {p["punkt"]: p for p in ERGEBNIS["nicht_geprueft"]}
    for name in ("reale_messreihe", "produktions_runtime", "macro_f1_d2", "autarkie_reell"):
        assert punkte[name]["status"] == "NICHT_GEPRUEFT", name
    assert punkte["reale_messreihe"]["messwert"].startswith("keine reale Messreihe")


def test_betreiber_punkte_werden_nicht_vom_repo_belegt():
    punkte = {p["punkt"]: p for p in ERGEBNIS["nur_betreiber"]}
    assert punkte["schluesselrotation_239"]["status"] == "NUR_BETREIBER"
    assert punkte["branch_schutz_main"]["status"] == "NUR_BETREIBER"


def test_keine_belegt_behauptung_ohne_pruefung():
    # Jeder BELEGT-Punkt muss einen Messwert oder Details tragen.
    for punkt in ERGEBNIS["belegt"]:
        assert punkt.get("messwert") or punkt.get("details"), punkt["punkt"]


def test_fail_closed_bei_falschem_repo_root():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        try:
            nachweis.pruefe(pathlib.Path(tmp) / "gibtsnicht")
            raised = False
        except nachweis.NachweisCheckError:
            raised = True
        assert raised


def test_fehlendes_bestandsmodul_wird_fehlt_nicht_belegt():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "controller").mkdir()
        for name in nachweis.BESTANDS_MODULE:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text("# stub\n", encoding="utf-8")
        # EIN Modul entfernen -> FEHLT, nicht BELEGT
        (root / "controller/ledger.py").unlink()
        ergebnis = nachweis.pruefe(root)
        punkt = next(p for p in ergebnis["belegt"] if p["punkt"] == "bestandsmodule_existieren")
        assert punkt["status"] == "FEHLT"
        assert "controller/ledger.py" in punkt["fehlt"]


def test_dokumentation_der_klassen_ist_ascii_policy_konform():
    source = (REPO_ROOT / "controller" / "nachweis_check.py").read_text(encoding="utf-8")
    for regel in ("CLAIM != EVIDENCE", "UNKNOWN != PASS", "SCRIPTED != INSTALLED"):
        assert regel in source, regel
    # Protokoll-Token-Policy: keine Fremdserien-Marker im Code.
    import re
    assert not re.search(r"V91-AUDIT-V[0-9]", source)
