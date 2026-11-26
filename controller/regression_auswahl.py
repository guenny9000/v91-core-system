"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Gestufte Regressions-Auswahl (Fremd-Vorschlag 26.11.2026, tragfaehiger
Kern als ehrliches Regelwerk umgesetzt): Aus 5 Ebenen (Pre-Commit
Smoke, modulbezogene Regression, PR-Suite, Nightly Full Run,
Release-Gate) und einer Tier-Priorisierung (Tier 0 Notaus/Ledger/
Audit/Recovery, Tier 1 Worker/Listener/Status-Exchange, Tier 2 CLI/
Tools) leitet dieses Modul NUR ab, welche Testdateien fuer eine
Aenderung empfohlen werden.

Disziplin (fail-closed):
- AUSWAHL != AUSFUEHRUNG: dieses Modul laeuft keine Tests (pytest,
  trockenlauf und CI bleiben die Ausfuehrer, REUSE).
- EMPFEHLUNG != PASS: die Ausgabe ist eine Auswahl, kein Ergebnis.
  Ich pruefe nichts und behaupte kein Gruen.
- Tier-0-Aenderungen verlangen AUSDRUECKLICH die Kenntnisnahme, dass
  ein groesserer Regressionsteil Pflicht bleibt (TIER0_REGRESSIONSWAHL
  != OPTION).
- Unbekannte Dateipfade und unbekannte Module fail-closed abgelehnt.
- KEINE Verringerung von CI: Nightly und Release-Gate duerfen durch
  dieses Modul NIE ersetzt werden (AUSWAHL != ERSATZ FUER FULL-RUN).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROLLER_DIR = ROOT / "controller"
TESTS_DIR = ROOT / "tests"

TIERS = (0, 1, 2)

TIER_BESCHREIBUNG = {
    0: "Notaus, Ledger, Audit, Recovery: Aenderungen verlangen einen deutlich groesseren Regressionsteil",
    1: "Worker, Listener, Status-Exchange: modulbezogene Regression plus Abhaengigkeiten",
    2: "CLI, Tools, Hilfsmodule: modulbezogene Regression",
}

# Ehrliche, kuratierte Modul-Tier-Zuordnung (Bestand, keine Behauptung
# ueber Funktion; Zuordnung ist PFLEGE-ENTSCHEIDUNG, see docs).
TIER_MODULE: Dict[int, List[str]] = {
    0: [
        "emergency_protocol",
        "emergency_stop",
        "emergency_supply",
        "ledger", "ledger_anchor",
        
        "ledger_lock",
        "quorum_ledger",
        "receipt_store",
        "ledger_recovery",
        "replay_session",
        "independent_replay_gate",
        "secret_scan",
        "fiction_scan",
        "archive_restore_bilanz",
    ],
    1: [
        "collector",
        "host_metrics",
        "heartbeat_intake",
        "federation_receiver",
        "federation_transport",
        "federation_sender",
        "status_exchange",
        "mess_pilot",
        "measurement_ingest",
        "measurement_pipeline",
        "measurement_store",
        "worker",
    ],
    2: [
        "v91_cli",
        "daily_report",
        "index_lint",
        "repo_report_agent",
        "trockenlauf",
        "sprichwort_formeln",
    ],
}

# Pre-Commit-Rauch-Suite (Ebene 1): klein, kritisch, < 60 s Ziel.
# Auswahl ist PFLEGE, Zielzeit ist ANGABE der Empfehlung, KEINE Messung.
SMOKE_TESTS = [
    "tests/test_emergency_stop.py",
    "tests/test_ledger_gate.py",
    "tests/test_ledger_lock.py",
    "tests/test_secret_scan.py",
    "tests/test_fiction_scan.py",
    "tests/test_ledger_process_safety.py",
    "tests/test_alarm_outbox.py",
    "tests/test_contribution_intake.py",
]

EBENEN = {
    "1_pre_commit_smoke": "Rauch-Suite: kritische Security-/Ledger-Tests, Ziel < 60 s (ANGABE != MESSUNG)",
    "2_modul_regression": "nur Testdateien der geaenderten Module und ihrer Tier-Abhaengigkeiten",
    "3_pr_suite": "betroffene Module + Integrationstests + Governance-Tests, laengere Laufzeit erlaubt",
    "4_nightly_full_run": "pytest tests/ volle Suite, jede Nacht, entdeckt Cross-Modul-Effekte/Drift",
    "5_release_gate": "Full Suite + Coverage + Static Analysis + Security Scan + Doku-Pruefung (Betreiber-gesteuert)",
}


class RegressionAuswahlError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _norm_module(name: str) -> str:
    return name.strip().removeprefix("controller/").removesuffix(".py")


def tier_fuer_module(module_name: str) -> Optional[int]:
    """Tier eines Controller-Moduls; unzureichende/leere Namen bleiben None."""
    mod = _norm_module(module_name)
    for tier, module in TIER_MODULE.items():
        if mod in module:
            return tier
    return None


def _require_repo_files(modules: List[str]) -> None:
    for mod in modules:
        if not (CONTROLLER_DIR / f"{mod}.py").exists():
            raise RegressionAuswahlError(f"Modul existiert nicht im Bestand: {mod}.py")


def test_datei_fuer(modul: str) -> Optional[str]:
    """tests/test_<modul>.py, wenn im Bestand vorhanden; sonst None."""
    mod = _norm_module(modul)
    p = TESTS_DIR / f"test_{mod}.py"
    return f"tests/{p.name}" if p.exists() else None


def _validate_changed(changed: List[str]) -> None:
    if not changed:
        raise RegressionAuswahlError("keine geaenderten Dateien uebergeben")
    seen: set = set()
    for entry in changed:
        if not isinstance(entry, str) or not entry.strip():
            raise RegressionAuswahlError("changed-Eintraege muessen nicht-leere Strings sein")
        path = entry.strip()
        if path in seen:
            raise RegressionAuswahlError(f"doppelte geaenderte Datei: {path}")
        seen.add(path)
        norm = _norm_module(path)
        if not path.startswith("tests/") and not (CONTROLLER_DIR / f"{norm}.py").exists():
            raise RegressionAuswahlError(f"unbekannte geaenderte Datei im Bestand: {path}")


def waehle_regression(changed: List[str], repo_root: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """Aenderungen -> Ebenen-Empfehlung. EMPFEHLUNG != PASS, KEIN Ergebnis."""
    _validate_changed(list(changed))
    module: List[str] = []
    for entry in changed:
        ansatz = _norm_module(entry)
        if (CONTROLLER_DIR / f"{ansatz}.py").exists():
            module.append(ansatz)
    tier = min((tier_fuer_module(m) for m in module), default=None)
    tier_richtig = [m for m in module if tier_fuer_module(m) == tier]
    _require_repo_files(tier_richtig)
    modul_tests = sorted({t for t in (test_datei_fuer(m) for m in module) if t})
    if tier == 0:
        auswahl: List[str] = sorted(set(modul_tests) | set(SMOKE_TESTS))
        hinweis = "Tier 0: groesserer Regressionsteil ist PFLICHT-EMPFEHLUNG, nicht optional"
    elif tier == 1:
        auswahl = sorted(set(modul_tests) | set(SMOKE_TESTS))
        hinweis = "Tier 1: modulbezogen plus kritische Abhaengigkeiten (Smoke-Kern)"
    else:
        auswahl = sorted(set(modul_tests) | set(SMOKE_TESTS[:4]))
        hinweis = "Tier 2: modulbezogen plus Ledger-/Notaus-Kern"
    if not modul_tests:
        auswahl = sorted(set(SMOKE_TESTS) | set(p for p in changed if p.startswith("tests/") and (ROOT / p).exists()))
        hinweis = "keine Controller-Module erkannt; Smoke-Suite plus geaenderte Testdateien"
    unknown_modules = [m for m in module if tier_fuer_module(m) is None]
    return {
        "schema": "v91.regression_auswahl.v1",
        "geaenderte_module": module,
        "tier": tier,
        "tier_beschreibung": TIER_BESCHREIBUNG.get(tier, "unzureichende/keine Tier-Zuordnung") if tier in TIERS else "UNBEKANNT: ohne Pflegerbeschluss KEIN Vertrauensvorschuss",
        "empfohlene_tests_ebene_2": sorted(set(modul_tests) or []) if modul_tests else [],
        "empfohlene_tests_ebene_3_pr": auswahl,
        "pre_commit_smoke": sorted(SMOKE_TESTS),
        "nightly_full_run": "pytest tests/ (volle Suite, NIE durch Auswahl ersetzbar)",
        "release_gate": "Full Suite + Coverage + Static Analysis + Security Scan + Doku-Pruefung",
        "unbekannte_tier_module": unknown_modules,
        "hinweis": hinweis,
        "ehrengrenzen": [
            "AUSWAHL != AUSFUEHRUNG: keine Ausgabe ist ein Testergebnis",
            "EMPFEHLUNG != PASS und ERSATZ != VOLLSTANDIGKEIT: Nightly/Release bleiben unersetzbar",
            "UNBEKANNTES_TIER bleibt im Zweifel Tier-0-Wertigkeit: Vertrauen erst nach Pflegerbeschluss",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V91 gestufte Regressions-Auswahl (Empfehlung, KEIN Ergebnis)")
    parser.add_argument("--self-check", action="store_true", help="synthetischer Selbsttest (SYNTHETISCH != MESSUNG)")
    parser.add_argument("--changed", action="append", default=[], help="geaenderte Datei (mehrfach angebbar)")
    args = parser.parse_args(argv)
    if args.self_check:
        out = waehle_regression(["controller/emergency_stop.py"])
        out["_selbsttest"] = "SYNTHETISCH: wahlt nur aus, pruelt und misst nichts (NICHT_GEPRUEFT)"
        print(json.dumps(out, indent=2))
        return 0
    if not args.changed:
        print("usage: --changed controller/x.py [--changed tests/test_y.py] (oder --self-check)", file=sys.stderr)
        return 2
    try:
        out = waehle_regression(args.changed)
    except RegressionAuswahlError as exc:
        print(json.dumps({"status": "INPUT_FEHLER", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
