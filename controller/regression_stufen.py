#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Regression-Stufen fuer V91 (Fremd-Kern der Betreiber-Uebergabe
26.11.2026: 5 Ebenen + Tier-0/1/2-Gewichtung). Reines DATENMODUL:
jede Selektion ist ein messbarer VORSCHLAG, KEINE Verminderung
bestehender CI-Pflicht. Die vorhandenen CI-Suiten laufen unveraendert
weiter; NUR der Betreiber veraendert .github/workflows.

Regeln:
- SELEKTION != VERIFIZIERT: wer selektiert, hat nichts bewiesen.
- SICHERHEIT VOR EFFIZIENZ (Betreiber-Feinabnahme 26.11.2026, #572).
- Laufzeiten sind NICHT_GEPRUEFT (Vibe-Sandbox ohne pytest; Messung
  auf der Zielumgebung nach docs/V91-TROCKENLAUF-REZEPT.md).
- MESSSTAND-Pins gelten NUR am MESSTAND_SHA (Momentaufnahme, n=1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MESSTAND_SHA = "c8693c21969cd9d55a774aafe796f88f3f9b7a02"

# Gezaehlt am main-Tarball MESSTAND_SHA (26.11.2026, Methode:
# ls/grep, KEIN pytest-Lauf: ZAEHLUNG != TESTLAUF).
MESSTAND_COUNTS = {
    "controller_module": 166,
    "py_dateien_ohne_tests": 220,
    "test_dateien": 247,
    "test_funktionen": 3422,
}

# Tier-Gewichtung: AENDERUNGEN AN TIER_0 LOESEN IMMER DIE BREITE
# REGRESSION AUS (im Ist-Zustand: die volle CI-Suite je PR).
TIER_MODULE = {
    "TIER_0_NOTAUS_LEDGER_AUDIT_RECOVERY": [
        "controller/emergency_stop.py",
        "controller/emergency_protocol.py",
        "controller/ledger.py",
        "controller/ledger_anchor.py",
        "controller/ledger_lock.py",
        "controller/ledger_recovery.py",
        "controller/claim_ledger.py",
        "controller/quorum_ledger.py",
        "controller/worm_ledger.py",
        "controller/secret_scan.py",
        "controller/fiction_scan.py",
    ],
    "TIER_1_WORKER_LISTENER_STATUS": [
        "controller/worker.py",
        "controller/v91_listener.py",
        "controller/status_exchange.py",
    ],
    # TIER_2 (CLI/Tools/Hilfsmodule) ist hier bewusst NICHT als Liste
    # gepinnt: es ist der Rest, keine Auswahlnoetigkeit.
}

# Ebene 1: Pre-Commit-Smoke, schlanke Auswahl. KEIN Zeitversprechen,
# nur Themenschnitt Tier 0/1. Zielordnung des Fremd-Entwurfs war
# "< 60 Sekunden, ~50-100 Tests" = ANGESTREBT, NICHT GEPRUEFT.
SMOKE_TESTS_E1 = [
    "tests/test_emergency_stop.py",
    "tests/test_emergency_protocol.py",
    "tests/test_ledger_gate.py",
    "tests/test_ledger_lock.py",
    "tests/test_ledger_recovery.py",
    "tests/test_ledger_process_safety.py",
    "tests/test_secret_scan.py",
    "tests/test_status_exchange_e2e.py",
    "tests/test_worker_observer.py",
]

EBENEN_STATUS = {
    "E1_PRE_COMMIT_SMOKE": "SELEKTION_BEREIT_LAUF_UNBEWIESEN",
    "E2_MODUL_REGRESSION": "TEILWEISE_MANUELLE_PRAXIS",
    "E3_PR_SUITE": "IMPLEMENTIERT_STRENGER_VOLL",
    "E4_NIGHTLY_FULL_RUN": "NICHT_IMPLEMENTIERT",
    "E5_RELEASE_GATE": "NICHT_IMPLEMENTIERT",
}

# E3 ist STAERKER als der Fremd-Entwurf verlangt: audit.yml
# (audit-checks) laeuft bei JEDEM PR die VOLLSTAENDIGE Suite
# "pytest tests/" zusaetzlich zu Scans/Compile/Docker. Eine
# Verknappung waere eine Betreiber-Strukturentscheidung
# (SELEKTION != VERIFIZIERT), KEIN autonomer Akt.


def smoke_command() -> str:
    """pytest-Aufruf der Ebene-1-Auswahl (Vorschlag, kein Beweis)."""
    return "python -m pytest " + " ".join(SMOKE_TESTS_E1)


def tier_dateien() -> list[str]:
    """Alle gepinnten Modul-Pfade (Tier 0/1), sortiert."""
    daten: list[str] = []
    for pfade in TIER_MODULE.values():
        daten.extend(pfade)
    return sorted(daten)


def fehlende_dateien() -> list[str]:
    """Pfad-Pflicht fail-closed: jeder gepinnte Pfad muss existieren."""
    fehlt = []
    for pfad in sorted(set(SMOKE_TESTS_E1) | set(tier_dateien())):
        if not (REPO_ROOT / pfad).is_file():
            fehlt.append(pfad)
    return fehlt


def self_check() -> dict:
    """Ehrlicher Selbstbericht: Datenlage ja, Laeufe nein."""
    fehlt = fehlende_dateien()
    return {
        "mechanismus": "regression_stufen_datenselektion",
        "messstand_sha": MESSTAND_SHA,
        "messstand_zaehlung": MESSTAND_COUNTS,
        "zaehlung_ist": "KEIN_TESTLAUF",
        "smoke_dateien": len(SMOKE_TESTS_E1),
        "smoke_laufzeit": "NICHT_GEPRUEFT",
        "ebenen_status": EBENEN_STATUS,
        "fehlende_dateien": fehlt,
        "status": "OK" if not fehlt else "FEHLT",
        "regeln": [
            "SELEKTION != VERIFIZIERT",
            "SICHERHEIT_VOR_EFFIZIENZ",
            "NUR_BETREIBER_VERAENDERT_WORKFLOWS",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V91 Regression-Stufen (Datenmodul, kein Gate)."
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Ehrlicher Statusbericht als JSON (kein Testlauf).",
    )
    args = parser.parse_args(argv)
    if args.self_check:
        bericht = self_check()
        print(json.dumps(bericht, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if bericht["status"] == "OK" else 2
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
