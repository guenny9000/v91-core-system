"""Pins fuer controller/regression_stufen.py (Regression-Stufen 26.11.2026).

Doku-pinnend und selbst-enthalten: keine Netzwerk-, Daten- oder
Laufzeitbehauptung. NEGATIV-Tests verriegeln, dass E4/E5 NICHT als
implementiert behauptet werden und dass die Selektion keine
Verduennung bestehender CI-Pflichten darstellt.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import regression_stufen as rs

REPO_ROOT = Path(__file__).resolve().parents[1]
DOKU = REPO_ROOT / "docs" / "V91-TEST-STUFUNG-2026-11-26.md"

ALLOWED_EBENEN_VERDIKTE = {
    "SELEKTION_BEREIT_LAUF_UNBEWIESEN",
    "TEILWEISE_MANUELLE_PRAXIS",
    "IMPLEMENTIERT_STRENGER_VOLL",
    "NICHT_IMPLEMENTIERT",
}


def test_smoke_command_enthaelt_alle_selektierten_dateien():
    cmd = rs.smoke_command()
    assert cmd.startswith("python -m pytest ")
    for datei in rs.SMOKE_TESTS_E1:
        assert datei in cmd, f"Smoke-Kommando verliert {datei}"


def test_alle_gepinnten_dateien_existieren_fail_closed():
    assert rs.fehlende_dateien() == [], rs.fehlende_dateien()


def test_smoke_auswahl_is_schlank():
    assert 5 <= len(rs.SMOKE_TESTS_E1) <= 15, (
        "Ebene-1-Auswahl muss schlank bleiben (Vorschlag des"
        " Fremd-Kerns: unter 60 Sekunden, ZIEL != GEPRUEFT)."
    )


def test_tier0_mehr_pflichtpaare_als_tier1():
    tier0 = rs.TIER_MODULE["TIER_0_NOTAUS_LEDGER_AUDIT_RECOVERY"]
    tier1 = rs.TIER_MODULE["TIER_1_WORKER_LISTENER_STATUS"]
    assert len(tier0) >= len(tier1) * 2, (
        "Tier-0 schuetzt die Lebensadern und muss die breitere"
        " Pflichtmenge pinnen."
    )


def test_tier0_enthaelt_notaus_ledger_und_scan():
    tier0 = rs.TIER_MODULE["TIER_0_NOTAUS_LEDGER_AUDIT_RECOVERY"]
    text = " ".join(tier0)
    for kern in ("emergency_stop", "ledger", "secret_scan"):
        assert kern in text, f"Tier 0 verliert {kern}"


def test_tier1_enthaelt_worker_listener_status():
    tier1 = rs.TIER_MODULE["TIER_1_WORKER_LISTENER_STATUS"]
    text = " ".join(tier1)
    for kern in ("worker", "v91_listener", "status_exchange"):
        assert kern in text, f"Tier 1 verliert {kern}"


def test_ebenen_verdiktwoerter_erlaubt():
    for wert in rs.EBENEN_STATUS.values():
        assert wert in ALLOWED_EBENEN_VERDIKTE, wert


def test_negativ_nightly_ist_nicht_behauptet():
    assert rs.EBENEN_STATUS["E4_NIGHTLY_FULL_RUN"] == "NICHT_IMPLEMENTIERT"


def test_negativ_release_gate_ist_nicht_behauptet():
    assert rs.EBENEN_STATUS["E5_RELEASE_GATE"] == "NICHT_IMPLEMENTIERT"


def test_e3_bleibt_strenger_voll():
    assert rs.EBENEN_STATUS["E3_PR_SUITE"] == "IMPLEMENTIERT_STRENGER_VOLL"


def test_messstand_pins_am_quota_sha():
    assert rs.MESSTAND_SHA.startswith("c8693c21")
    assert rs.MESSTAND_COUNTS["test_funktionen"] == 3422
    assert rs.MESSTAND_COUNTS["controller_module"] == 166


def test_self_check_meldet_zaehlung_als_keinen_testlauf():
    bericht = rs.self_check()
    assert bericht["status"] == "OK"
    assert bericht["smoke_laufzeit"] == "NICHT_GEPRUEFT"
    assert bericht["zaehlung_ist"] == "KEIN_TESTLAUF"


def test_self_check_ist_ascii_rein():
    text = json.dumps(rs.self_check(), ensure_ascii=True)
    assert all(ord(zeichen) < 128 for zeichen in text)


def test_subprocess_self_check_exit_ok():
    ergebnis = subprocess.run(
        [sys.executable, "controller/regression_stufen.py", "--self-check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    daten = json.loads(ergebnis.stdout)
    assert daten["status"] == "OK"


def test_doku_pins_nachmessung_und_marken_der_ehrlichkeit():
    inhalt = DOKU.read_text(encoding="utf-8")
    for anker in (
        "c8693c21",
        "NICHT GEPRUEFT",
        "4051",
        "180/180",
        "SELEKTION != VERIFIZIERT",
        "BETREIBER-STRUKTURENTSCHEIDUNG",
    ):
        assert anker in inhalt, f"Doku verliert Anker {anker}"
