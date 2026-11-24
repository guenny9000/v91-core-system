"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Entkopplungs-Audit (The Decoupling Audit, externer V108-Entwurf):
Der externe Bericht nennt einen "Master-Daemon" und Pseudo-Zustaende;
Codessuche am 24.11.2026: 0 Treffer, alles TEXT-ONLY. Umgesetzt wird
nur die tragfaehige Kernidee: eine Notwendigkeits-Matrix, die
Infrastruktur-Komponenten in drei messbare Schichten einordnet und
fuer die essenzielle Schicht eine strukturell gueltige Evidenz-Referenz
verlangt. Das Ergebnis ist ein AUDIT-PLAN, niemals ein Befehl:
dieses Modul schaltet nichts ab, erreicht keine Fremdsysteme und
fuehrt keine Aktion aus.

Drei Schichten (Taxonomie, ASCII):
- essential   : Basisversorgung fuer primaere menschliche Existenz
                (Wasser, Nahrung, einfache Kommunikation). Muss mit
                strukturell gueltiger Evidenz-Referenz belegt werden,
                sonst REVIEW_REQUIRED (fail-closed).
- circulating  : unterstuetzende, nicht-essenzielle Dienste.
                Kandidat fuer betrachtetes Entkoppeln (nur Plan).
- opulence     : ueber kritischen Bedarf hinausgehende Systeme.
                Kandidat fuer Archivierung/Stilllegung (nur Plan).

Zusaetzlich: local_global_ratio (E_local / E_global) als reine
Berechnung. Sie misst NICHT real, setzt keine Schwelle als
Gueltigkeitsbeweis (Kalibrierung bleibt offen, vgl. Issue #419) und
beantwortet keine Versorgungsfrage.

Ehrliche Grenzen:
- PLAN != BEFEHL, AUDIT != ABSCHALTUNG, CLASSIFIED != VERIFIZIERT.
- Evidenz-Referenzpruefung wird aus v99/filter/source_quality.py
  (Evidenz-Vertrag v2, Issue #51 / PR #53) wiederverwendet, nicht
  dupliziert (NO_DUPLICATE_SYSTEMS). Eine gueltige Referenz beweist
  Struktur, nicht Wahrheit (VALID != INDEPENDENTLY_VERIFIED).
- Kein Daemon, kein Netzwerk, kein Zustandsanspruch. SCRIPTED !=
  RUNNING.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

# Skript-Modus setzt sys.path[0] auf controller/; ROOT muss fuer v99 erreichbar sein
# (gleiche Ursache wie im CI-Fix zu domain_usecase_gate #434).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from v99.filter.source_quality import _is_valid_reference

TIERS = frozenset({"essential", "circulating", "opulence"})
AUDIT_STATUS = "AUDIT_ONLY"
PLAN_MARKER = "PLAN_NOT_COMMAND"

REVIEW_REQUIRED = "REVIEW_REQUIRED_MISSING_EVIDENCE"
UNKNOWN_TIER = "UNKNOWN_TIER"


class DecouplingAuditError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _require_component(entry: Any) -> str:
    if not isinstance(entry, dict):
        raise DecouplingAuditError("component entry must be an object")
    component = entry.get("component")
    if not isinstance(component, str) or not component.strip():
        raise DecouplingAuditError("component needs a non-empty name")
    return component.strip()


def local_global_ratio(local: Any, total: Any) -> Dict[str, Any]:
    """E_local / E_global als reine Berechnung; fail-closed bei unklaren Eingaben."""
    for name, value in (("local", local), ("total", total)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DecouplingAuditError(f"{name} must be a finite number, not {type(value).__name__}")
        if value != value or value in (float("inf"), float("-inf")):
            raise DecouplingAuditError(f"{name} must be finite")
        if value < 0:
            raise DecouplingAuditError(f"{name} must be >= 0")
    if total == 0:
        raise DecouplingAuditError("total must be > 0 for a ratio")
    if local > total:
        raise DecouplingAuditError("local must not exceed total (would fabricate coverage)")
    ratio = local / total
    return {
        "ratio": ratio,
        "ratio_status": "CALCULATED_ONLY",
        "calibration_status": "UNKNOWN",
        "note": "ratio is a calculation, not a measurement and not a threshold claim",
    }


def evaluate_entry(entry: Any) -> Dict[str, Any]:
    """Einordnung einer Komponente mit fail-closed Pruefung."""
    component = _require_component(entry)
    tier = entry.get("tier")
    if not isinstance(tier, str) or tier.strip().lower() not in TIERS:
        return {"component": component, "tier": tier, "state": UNKNOWN_TIER}
    tier = tier.strip().lower()
    if tier == "essential":
        evidence = entry.get("evidence")
        if evidence is None or not _is_valid_reference(evidence):
            return {"component": component, "tier": tier, "state": REVIEW_REQUIRED}
        return {"component": component, "tier": tier, "state": "ESSENTIAL_EVIDENCED"}
    state = "CLASSIFIED_CIRCULATING" if tier == "circulating" else "CLASSIFIED_OPULENCE"
    return {"component": component, "tier": tier, "state": state}


def evaluate_decoupling_plan(entries: Any, ratio: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Notwendigkeits-Matrix als Plan: zaehlt Schichten, entscheidet nichts."""
    if not isinstance(entries, list) or not entries:
        raise DecouplingAuditError("entries must be a non-empty list")
    seen = set()
    results: List[Dict[str, Any]] = []
    for entry in entries:
        component = _require_component(entry)
        if component in seen:
            raise DecouplingAuditError(f"duplicate component: {component}")
        seen.add(component)
        results.append(evaluate_entry(entry))
    counts: Dict[str, int] = {t: 0 for t in TIERS}
    for r in results:
        if r["tier"] in counts:
            counts[r["tier"]] += 1
    report: Dict[str, Any] = {
        "entries": results,
        "tier_counts": counts,
        "review_required": sum(1 for r in results if r["state"] == REVIEW_REQUIRED),
        "unknown_tiers": sum(1 for r in results if r["state"] == UNKNOWN_TIER),
        "review_status": AUDIT_STATUS,
        PLAN_MARKER: True,
        "honest_limits": [
            "PLAN != BEFEHL: this report proposes, it never commands",
            "CLASSIFIED != VERIFIZIERT: tiers are claims, evidence proves structure only",
        ],
    }
    if ratio is not None:
        if not isinstance(ratio, dict):
            raise DecouplingAuditError("ratio must be an object from local_global_ratio")
        report["ratio"] = ratio
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed decoupling audit (plan, not command)")
    parser.add_argument("input", help="JSON file with {'entries': [...], 'ratio': {'local':..,'total':..}} or '-' for stdin")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, "r", encoding="utf-8").read()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise DecouplingAuditError("input must be a JSON object")
        ratio = None
        if "ratio" in data:
            ratio = local_global_ratio(data["ratio"].get("local"), data["ratio"].get("total"))
        report = evaluate_decoupling_plan(data.get("entries"), ratio)
    except (DecouplingAuditError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if report["review_required"] or report["unknown_tiers"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
