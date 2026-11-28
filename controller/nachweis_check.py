"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Ehrlicher Nachweis-Check fuer den V91-Bestand (Betreiber-Anlass
'18/18-Nachweis', 28.11.2026). Antworten auf den Phantom-Bericht vom
28.11. (Office-Agent '16/18 BELEGT'): Der Nachweis wird NUR gegen
den REAL existierenden Bestand gefuehrt, mit drei ehrlichen Klassen:

- BELEGT: Die Pruefung wurde IN DIESEM LAUF gegen den Baum ausgefuehrt
  und bestanden (Existenz, Lint, Menge). BELEGT == GEPRUEFT_JETZT.
- NICHT_GEPRUEFT: Echte Mess- und Betriebsgroessen, die im Baum nicht
  existieren (reale Messreihe, Produktions-Runtime, Macro-F1-D2).
  UNKNOWN != PASS: Diese Punkte bleiben NICHT_GEPRUEFT, egal wie oft
  sie behauptet werden (CLAIM != EVIDENCE).
- NUR_BETREIBER: Punkte, die Sebastian nur ausserhalb des Repos
  erledigen kann (Branch-Schutz, Schluesselrotation #239). Ein
  Repo-Check kann sie nicht belegen; FREIGABE != BERECHTIGUNG.

Dauerregeln verriegelt: SCRIPTED != INSTALLED, CI_PASS != PRODUCTION,
STATUS == Angabe != Nachweis. Das Modul misst, es behauptet nichts:
Es gibt KEIN 'Alles geloest', nur die konkrete Punkteliste mit
Messwerten. BELEGT-Zaehler duerfen nur Punkte zaehlen, deren Pruefung
wirklich lief. KEINE Geheimnisse, kein Netz (Token nur optional via
Env GITHUB_TOKEN fuer den Branch-Schutz-Status; ohne Token bleibt
der Punkt UNKNOWN).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:  # Paket-Import (Tests/CI starten ab Wurzel)
    import controller.index_lint as index_lint_mod
except ImportError:  # Skript-Modus
    import index_lint as index_lint_mod  # type: ignore

BELEGT = "BELEGT"
NICHT_GEPRUEFT = "NICHT_GEPRUEFT"
NUR_BETREIBER = "NUR_BETREIBER"
FEHLT = "FEHLT"

# Kernmodule des Bestands: Existenz ist die minimale, ehrliche Behauptung.
BESTANDS_MODULE: tuple = (
    "controller/measurement_ingest.py",
    "controller/measurement_store.py",
    "controller/measurement_pipeline.py",
    "controller/measurement_monitor.py",
    "controller/emergency_stop.py",
    "controller/ledger.py",
    "controller/ledger_lock.py",
    "controller/audit_chain_inspect.py",
    "controller/calibration_status.py",
    "controller/schwellen_registry.py",
    "controller/iea_stats_adapter.py",
    "controller/fao_stats_adapter.py",
    "controller/who_stats_adapter.py",
    "controller/wurzelpruefer.py",
)

RUNTIME_REQUIREMENTS_ERWARTET = {"cryptography"}

VERSION = "v91.nachweis_check.v1"


class NachweisCheckError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _check_bestands_module(repo_root: pathlib.Path) -> Dict[str, Any]:
    fehlt = [m for m in BESTANDS_MODULE if not (repo_root / m).is_file()]
    status = BELEGT if not fehlt else FEHLT
    return {
        "punkt": "bestandsmodule_existieren",
        "status": status,
        "geprueft": len(BESTANDS_MODULE),
        "fehlt": fehlt,
        "messwert": f"{len(BESTANDS_MODULE) - len(fehlt)}/{len(BESTANDS_MODULE)} Dateien vorhanden",
    }


def _check_runtime_requirements(repo_root: pathlib.Path) -> Dict[str, Any]:
    try:
        from dependency_audit import parse_requirements
    except ImportError:
        return {"punkt": "runtime_requirements", "status": NICHT_GEPRUEFT,
                "messwert": "dependency_audit nicht importierbar"}
    req = repo_root / "requirements.txt"
    if not req.is_file():
        return {"punkt": "runtime_requirements", "status": FEHLT,
                "messwert": "requirements.txt fehlt"}
    menge = {r.name for r in parse_requirements(str(req))}
    ok = menge == RUNTIME_REQUIREMENTS_ERWARTET
    return {
        "punkt": "runtime_requirements",
        "status": BELEGT if ok else FEHLT,
        "messwert": "Runtime-Menge = " + (", ".join(sorted(menge)) or "(leer)"),
        "erwartet": sorted(RUNTIME_REQUIREMENTS_ERWARTET),
    }


def _check_index_und_archiv(repo_root: pathlib.Path) -> Dict[str, Any]:
    ergebnisse: List[Dict[str, Any]] = []
    for label, pfad in (("index", repo_root / "docs/V91-ARCHITEKTUR-INDEX.md"),
                        ("archiv", repo_root / "docs/archive/V91-ARCHITEKTUR-AENDERUNGSLOG.md")):
        if not pfad.is_file():
            ergebnisse.append({"datei": label, "status": FEHLT, "fehler": [str(pfad)]})
            continue
        lintergebnis = index_lint_mod.lint_text(pfad.read_text(encoding="utf-8"))
        if getattr(lintergebnis, "ok", False):
            ergebnisse.append({"datei": label, "status": BELEGT,
                               "eintraege": getattr(lintergebnis, "entries", None),
                               "fehler": 0})
        else:
            ergebnisse.append({"datei": label, "status": FEHLT,
                               "fehler": getattr(lintergebnis, "errors", [])})
    ok = all(e["status"] == BELEGT for e in ergebnisse)
    return {"punkt": "index_archiv_lint", "status": BELEGT if ok else FEHLT,
            "details": ergebnisse}


def _check_audit_chain_inspect(repo_root: pathlib.Path) -> Dict[str, Any]:
    """Importierbarkeit des Inspektors (KEINE Behauptung ueber Laufzeit)."""
    try:
        import audit_chain_inspect  # noqa: F401  (Skript-Modus-Import)
        return {"punkt": "audit_chain_inspect_importierbar", "status": BELEGT,
                "messwert": "Modul laedt; eine echte chain liegt NICHT im Repo"}
    except Exception as exc:  # pragma: no cover - defensiv
        return {"punkt": "audit_chain_inspect_importierbar", "status": FEHLT,
                "messwert": f"Import fehlgeschlagen: {exc}"}


def _punkt(name: str, status: str, wert: str) -> Dict[str, Any]:
    return {"punkt": name, "status": status, "messwert": wert}


def _nicht_gepruefte_punkte() -> List[Dict[str, Any]]:
    """Echte Mess-/Betriebsgroessen: im Baum NICHT vorhanden, UNKNOWN bleibt UNKNOWN."""
    return [
        _punkt("reale_messreihe", NICHT_GEPRUEFT,
               "keine reale Messreihe im Repo; Messpfad Alsfeld offen (Issue #101)"),
        _punkt("produktions_runtime", NICHT_GEPRUEFT,
               "SCRIPTED != INSTALLED; Laufzeit auf SOLAR-DESKTOP-01 ist hier nicht pruefbar"),
        _punkt("macro_f1_d2", NICHT_GEPRUEFT,
               "D2-Validierung ist vorregistriert und NICHT verbraucht (One-Shot-Regel)"),
        _punkt("autarkie_reell", NICHT_GEPRUEFT,
               "Modulstatus ist NICHT_GEPRUEFT solange keine Messdaten vorliegen"),
    ]


def _nur_betreiber_punkte(github_token: Optional[str]) -> List[Dict[str, Any]]:
    punkte = [
        _punkt("schluesselrotation_239", NUR_BETREIBER,
               "Windows Credential Manager SOLAR-DESKTOP-01; danach git filter-repo"),
    ]
    if not github_token:
        punkte.append(_punkt("branch_schutz_main", NUR_BETREIBER,
                              "ohne Token UNKNOWN; Einstellung in GitHub Settings"))
        return punkte
    # Mit Token: echter API-Status, aber die EINSTELLUNG bleibt Betreiber-Sache.
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/guenny9000/v91-core-system/branches/main",
            headers={"Authorization": "token " + github_token, "User-Agent": "V91-nachweis-check"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        geschuetzt = bool(data.get("protected", False))
        punkte.append({"punkt": "branch_schutz_main", "status": BELEGT if geschuetzt else NUR_BETREIBER,
                       "messwert": "API: protected=" + str(geschuetzt),
                       "hinweis": "" if geschuetzt else "Schutz EINSCHALTEN (Settings -> Branches)"})
    except Exception as exc:
        punkte.append(_punkt("branch_schutz_main", NICHT_GEPRUEFT, "API-Fehler: " + str(exc)[:120]))
    return punkte


def pruefe(repo_root: pathlib.Path, github_token: Optional[str] = None) -> Dict[str, Any]:
    repo_root = pathlib.Path(repo_root)
    if not repo_root.is_dir():
        raise NachweisCheckError("repo_root fehlt: " + str(repo_root))
    belege = [
        _check_bestands_module(repo_root),
        _check_runtime_requirements(repo_root),
        _check_index_und_archiv(repo_root),
        _check_audit_chain_inspect(repo_root),
    ]
    nicht_geprueft = _nicht_gepruefte_punkte()
    nur_betreiber = _nur_betreiber_punkte(github_token)
    return {
        "version": VERSION,
        "repo": str(repo_root),
        "belegt": belege,
        "nicht_geprueft": nicht_geprueft,
        "nur_betreiber": nur_betreiber,
        "zaehler": {
            "belegt": sum(1 for p in belege if p["status"] == BELEGT),
            "belegt_gesamt": len(belege),
            "nicht_geprueft": len(nicht_geprueft),
            "nur_betreiber": len(nur_betreiber),
        },
    }


def _self_check() -> int:
    """CI-Fixture: Lauf gegen das ECHTE Repo (Tests/CI starten ab Wurzel)."""
    ergebnis = pruefe(pathlib.Path(__file__).resolve().parents[1])
    zaehler = ergebnis["zaehler"]
    print(json.dumps({
        "mechanismus": "getestet",
        "self_check": "PASS" if zaehler["belegt"] == zaehler["belegt_gesamt"] else "BEFUNDE_FEHLT",
        "belegt": zaehler["belegt"],
        "nicht_geprueft": zaehler["nicht_geprueft"],
        "nur_betreiber": zaehler["nur_betreiber"],
        "echtes_repo": "GEPRUEFT_GEGEN_BAUM",
    }, ensure_ascii=False))
    return 0 if zaehler["belegt"] == zaehler["belegt_gesamt"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ehrlicher Nachweis-Check V91")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parents[1]))
    parser.add_argument("--github-token", default=None)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    token = args.github_token or os.environ.get("GITHUB_TOKEN")
    ergebnis = pruefe(pathlib.Path(args.repo), github_token=token)
    text = json.dumps(ergebnis, ensure_ascii=False, indent=2, default=str)
    if args.json_out:
        pathlib.Path(args.json_out).write_text(text, encoding="utf-8")
    else:
        print(text)
    z = ergebnis["zaehler"]
    print(f"ERGEBNIS: {z['belegt']}/{z['belegt_gesamt']} BELEGT, "
          f"{z['nicht_geprueft']} NICHT_GEPRUEFT, {z['nur_betreiber']} NUR_BETREIBER")
    return 0 if z["belegt"] == z["belegt_gesamt"] else 1


if __name__ == "__main__":
    sys.exit(main())
