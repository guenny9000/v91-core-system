"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Legacy-Coverage: messbare Minimum-Ausgabe 1 von Issue #276
("Legacy inventory coverage and percentage with named owner and
lifecycle status") als Aggregationsschicht UEBER dem
Node-Inventar-Auditor. Der Auditor selbst (#278,
controller/node_inventory.py, Issue #276 Faehigkeiten 1+2) bleibt
alleinverbindlich fuer Validierung und Klassifikation.

REUSE statt Duplikat (NO_DUPLICATE_SYSTEMS): Dieses Modul validiert
NICHT selbst, es ruft controller.node_inventory.validate_inventory
auf und aggregiert ausschliesslich dessen geprueften Bestand. Alle
Feldregeln (Pflichtfelder, Evidenz, Lifecycle-Plaene,
Kritikalitaets-Waechter) bleiben allein in node_inventory.

Messgroessen (je Aufruf EIN Bericht, Zahlen nie ohne Basis):
- owner_named / owner_total(=components_total) / owner_named_ratio_raw
  (Anteil der Komponenten mit benanntem Owner, gezogen ueber ALLE
  erfassten Komponenten einschliesslich INCOMPLETE-Eintraegen).
- eol_distribution (supported/replace/isolate/retire/unknown/
  invalid_or_missing) und eol_status_known_ratio_raw (Anteil mit
  benanntem, nicht-unknown Lifecycle-Status; UNKNOWN zaehlt NICHT
  als bekannt).
- critical_plan_flags: Komponenten mit critical_service == True und
  isolate/retire-Klassifikation (KRITISCH_WARNUNG; die Entscheidung
  bleibt beim Betreiber, KLASSIFIKATION != EINGRIFF).

Zustaende:
- REPORTED_COMPLETE            : Basis-Inventar ohne Verletzungen.
- REPORTED_ON_INCOMPLETE_BASIS : Basis-Inventar mit INCOMPLETE-
  Eintraegen; alle Zahlen werden genannt, aber die Basis ist
  ehrlich als lueckenhaft markiert (fail-closed, nie geschönt).
- NOT_REPORTED                 : Basis-Inventar abgelehnt
  (Validierungsverletzungen); es wird KEINE Zahl ausgegeben,
  UNKNOWN != PASS.

Ehrliche Grenzen:
- DECKUNG == ANTEIL_DER_ERFASSTEN != ERFASSTE_REALITAET: Ein
  Prozentwert ist ein Verhaeltnis aus erfassten Eintraegen; ueber
  NICHT erfasste Komponenten sagt er nichts (INVENTAR != REALITAET).
- Verhaeltnisse werden als rohe Bruchzahl mit Zaehler und Nenner
  ausgegeben, nie still gerundet.
- Kein Eingriff, kein Schreiben in Bestaende, kein Daemon,
  SCRIPTED != RUNNING, REVIEW != DECISION.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Optional

# Skript-Modus: controller/ auf sys.path[0] laesst "controller" auf
# controller/controller.py schatten (#460-Lektion); Skript-Ordner wird
# deshalb entfernt, bevor ROOT eingefuegt wird (idempotent).
_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller.node_inventory import validate_inventory  # REUSE, kein Duplikat

REPORTED_COMPLETE = "REPORTED_COMPLETE"
REPORTED_ON_INCOMPLETE_BASIS = "REPORTED_ON_INCOMPLETE_BASIS"
NOT_REPORTED = "NOT_REPORTED"

_EOL_BUCKETS = ("supported", "replace", "isolate", "retire", "unknown")
HONESTY_LIMITS = (
    "DECKUNG == ANTEIL_DER_ERFASSTEN != ERFASSTE_REALITAET, "
    "ROHE_BRUCHZAHLEN_STATT_GESCHOENTER_PROZENTE, "
    "UNKNOWN_ZAEHLT_NICHT_ALS_BEKANNT, "
    "KLASSIFIKATION != EINGRIFF, SCRIPTED != RUNNING, REVIEW != DECISION"
)


def coverage_report(inventory: Any) -> dict[str, Any]:
    """Aggregiert EIN geprueftes Node-Inventar zu AK-1-Messzahlen."""
    try:
        base = validate_inventory(inventory)  # REUSE: Alleinverbindlich
    except Exception as exc:  # ungueltige Eingabe ist kein Basis-Fund
        return {
            "state": NOT_REPORTED,
            "reason": "inventory rejected by validator: " + str(exc),
            "honesty_limits": HONESTY_LIMITS,
        }

    if base["decision"] == "REJECTED":
        return {
            "state": NOT_REPORTED,
            "reason": "basis inventory REJECTED: " + "; ".join(base["violations"]),
            "honesty_limits": HONESTY_LIMITS,
        }

    components = inventory.get("components", [])
    total = len(components)

    owner_named = 0
    eol_distribution: dict[str, int] = {bucket: 0 for bucket in _EOL_BUCKETS}
    eol_distribution["invalid_or_missing"] = 0
    critical_plan_flags: list[dict[str, Any]] = []

    for component in components:
        if not isinstance(component, dict):
            eol_distribution["invalid_or_missing"] += 1
            continue
        owner = component.get("owner")
        if isinstance(owner, str) and owner.strip():
            owner_named += 1
        eol = component.get("eol_status")
        if isinstance(eol, str) and eol in _EOL_BUCKETS:
            eol_distribution[eol] += 1
        else:
            eol_distribution["invalid_or_missing"] += 1
        if component.get("critical_service") is True and eol in ("isolate", "retire"):
            critical_plan_flags.append({
                "component_id": component.get("component_id")
                if isinstance(component.get("component_id"), str) else None,
                "eol_status": eol,
                "warning": (
                    "critical service has isolate/retire classification; "
                    "decision and continuity proof stay with the operator "
                    "(KLASSIFIKATION != EINGRIFF, MENSCH != KOSTENZENTRUM)"
                ),
            })

    eol_known = sum(eol_distribution[b] for b in ("supported", "replace", "isolate", "retire"))
    owner_ratio = (owner_named / total) if total else 0.0
    eol_known_ratio = (eol_known / total) if total else 0.0

    state = (
        REPORTED_COMPLETE
        if base["decision"] == "INVENTORY_COMPLETE"
        else REPORTED_ON_INCOMPLETE_BASIS
    )
    return {
        "state": state,
        "basis_decision": base["decision"],
        "components_total": total,
        "owner_named": owner_named,
        "owner_named_ratio_raw": owner_ratio,
        "eol_distribution": eol_distribution,
        "eol_status_known": eol_known,
        "eol_status_known_ratio_raw": eol_known_ratio,
        "critical_plan_flags": critical_plan_flags,
        "honesty_limits": HONESTY_LIMITS,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: exit 0 = REPORTED*, 1 = NOT_REPORTED, 2 = Nutzungs-/I/O-Fehler."""
    parser = argparse.ArgumentParser(
        prog="legacy_coverage",
        description="AK-1-Messzahlen (Issue #276) ueber EIN geprueftes "
                    "Node-Inventar (Validierung via node_inventory).")
    parser.add_argument("--inventory", required=True,
                        help="Pfad zur Inventar-JSON-Datei")
    args = parser.parse_args(argv)

    try:
        with open(args.inventory, encoding="utf-8") as fh:
            inventory = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print("legacy_coverage: I/O error: " + str(exc), file=sys.stderr)
        return 2

    report = coverage_report(inventory)
    print(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if report["state"] != NOT_REPORTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
