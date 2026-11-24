"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Legacy-Radar: proaktive Arbeitsauftraege aus dem ECHTEN Node-Inventar.

Anlass ist Issue #503: Die Kritik des Betreibers vom 24.11.2026, dass
proaktives Aufdecken von Legacy-Strukturen zu wenig hervortritt, wird
hier als messbare Aufgabe umgesetzt. Der Radar DUPPLIERT KEIN
Messsystem: Struktur- und Statuspruefung bleiben alleinverbindlich in
controller/node_inventory (#278), Kennzahlen bleiben in
controller/legacy_coverage (#473); der Radar erzeugt daraus NUR die
proaktive Arbeitsauftrags-Liste pro Komponente (Weg-eigener Zweck
REUSE: validate_inventory aus node_inventory bleibt die einzige
Basis-Pruefung, NO_DUPLICATE_SYSTEMS).

Item-Klassen (pro Komponente, ehrlich, keine Spekulation):
- MODERNIZATION_CANDIDATE: eol_status replace.
- ISOLATE_CANDIDATE: eol_status isolate; bei critical_service == true
  zusaetzliche WARNUNG (Kontinuitaetsbeweis bleibt beim Betreiber).
- RETIRE_CANDIDATE: eol_status retire (Rueckweg muss laut Basis
  geprueft sein; Ausserkraftsetzen nur mit Betreiber-Freigabe).
- UNKNOWN_EOL: eol_status unknown - PROAKTIV sichtbar gemacht, NICHT
  als geprueft behandelt (UNKNOWN != PASS).
- OWNER_UNKNOWN: owner fehlt oder ist leer.
- INCOMPLETE_BASE_ENTRY: vom Basis-Validator als INCOMPLETE
  markierte Komponente; Verletzungen werden ehrlich durchgereicht.

Jeder Item verlangt FREIGABE_BETREIBER als naechsten Schritt: der
Radar wertet NICHT aus und greift NIEMALS ein (KLASSIFIKATION !=
EINGRIFF, REVIEW != DECISION, ISOLATE_NOT_DESTROY).

Ehrliche Grenzen:
- RADAR == ANTEIL_DER_ERFASSTEN != REALITAET: nicht inventarisierte
  Komponenten erscheinen nie (INVENTAR != REALITAET).
- Verhaeltnisse roh als Bruchzahl, nie gerundet.
- Kein Schreiben in Bestaende, kein Daemon, SCRIPTED != RUNNING.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Optional

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller.node_inventory import validate_inventory  # REUSE: alleinverbindlich

ITEM_MODERNIZE = "MODERNIZATION_CANDIDATE"
ITEM_ISOLATE = "ISOLATE_CANDIDATE"
ITEM_RETIRE = "RETIRE_CANDIDATE"
ITEM_UNKNOWN_EOL = "UNKNOWN_EOL"
ITEM_OWNER_UNKNOWN = "OWNER_UNKNOWN"
ITEM_INCOMPLETE = "INCOMPLETE_BASE_ENTRY"
ITEM_CLASSES = (
    ITEM_MODERNIZE, ITEM_ISOLATE, ITEM_RETIRE,
    ITEM_UNKNOWN_EOL, ITEM_OWNER_UNKNOWN, ITEM_INCOMPLETE,
)

NOT_REPORTED = "NOT_REPORTED"
RADAR_REPORTED_COMPLETE = "RADAR_REPORTED_COMPLETE"
RADAR_REPORTED_ON_INCOMPLETE_BASIS = "RADAR_REPORTED_ON_INCOMPLETE_BASIS"

HONESTY_LIMITS = (
    "KLASSIFIKATION != EINGRIFF, REVIEW != DECISION, "
    "FREIGABE_BETREIBER ist der einzige naechste Schritt, "
    "UNKNOWN != PASS, RADAR == ANTEIL_DER_ERFASSTEN != REALITAET, "
    "ISOLATE_NOT_DESTROY, kein Daemon, SCRIPTED != RUNNING"
)

OWNER_ACTION = (
    "FREIGABE_BETREIBER: bewerten und einzeln freigeben; "
    "der Radar fuehrt keine Aktion aus"
)


def _item(component_id, item_class, reason, extra=None):
    record = {
        "component_id": component_id,
        "item_class": item_class,
        "reason": reason,
        "required_owner_action": OWNER_ACTION,
    }
    if extra:
        record.update(extra)
    return record


def radar_report(inventory: Any) -> dict[str, Any]:
    """Erzeugt proaktive Arbeitsauftraege aus EINEM echten Inventar."""
    try:
        base = validate_inventory(inventory)
    except Exception as exc:
        return {
            "state": NOT_REPORTED,
            "reason": "inventory rejected by validator: " + str(exc),
            "items": [],
            "honesty_limits": HONESTY_LIMITS,
        }
    if base["decision"] == "REJECTED":
        return {
            "state": NOT_REPORTED,
            "reason": "basis inventory REJECTED: " + "; ".join(base["violations"]),
            "items": [],
            "honesty_limits": HONESTY_LIMITS,
        }

    components = inventory.get("components", [])
    comp_results = base["component_results"]
    items: list[dict[str, Any]] = []
    counts = {cls: 0 for cls in ITEM_CLASSES}

    for idx, component in enumerate(components):
        res = comp_results[idx] if idx < len(comp_results) else None
        if res is not None and res["result"] != "OK":
            counts[ITEM_INCOMPLETE] += 1
            items.append(_item(
                res.get("component_id"), ITEM_INCOMPLETE,
                "Basis-Validierung INCOMPLETE: " + ", ".join(res["violations"]),
            ))
        if not isinstance(component, dict):
            continue
        comp_id = component.get("component_id")
        comp_id = comp_id if isinstance(comp_id, str) and comp_id.strip() else None
        eol = component.get("eol_status")
        owner = component.get("owner")
        has_owner = isinstance(owner, str) and owner.strip()
        if eol == "replace":
            counts[ITEM_MODERNIZE] += 1
            items.append(_item(comp_id, ITEM_MODERNIZE,
                               "eol_status replace: Modernisierungskandidat aus dem echten Inventar"))
        elif eol == "isolate":
            extra = None
            if component.get("critical_service") is True:
                extra = {"critical_service_warning":
                         "kritischer Dienst mit isolate-Klassifikation; Kontinuitaetsbeweis entscheidet der Betreiber (MENSCH != KOSTENZENTRUM)"}
            counts[ITEM_ISOLATE] += 1
            items.append(_item(comp_id, ITEM_ISOLATE,
                               "eol_status isolate: Isolationskandidat (kein Aus fuer sich)", extra))
        elif eol == "retire":
            extra = None
            if component.get("critical_service") is True:
                extra = {"critical_service_warning":
                         "kritischer Dienst mit retire-Klassifikation; Rueckweg und Kontinuitaet bleiben Betreiber-Entscheidung"}
            counts[ITEM_RETIRE] += 1
            items.append(_item(comp_id, ITEM_RETIRE,
                               "eol_status retire: Rueckweg ist laut Basis zu pruefen; Ausserkraftsetzen nur mit Freigabe", extra))
        elif eol == "unknown":
            counts[ITEM_UNKNOWN_EOL] += 1
            items.append(_item(comp_id, ITEM_UNKNOWN_EOL,
                               "eol_status unknown: unbekannter Lebenszyklusstatus, proaktiv sichtbar, NICHT geprueft (UNKNOWN != PASS)"))
        if not has_owner:
            counts[ITEM_OWNER_UNKNOWN] += 1
            items.append(_item(comp_id, ITEM_OWNER_UNKNOWN,
                               "owner fehlt oder ist leer: Verantwortung unbenannt (OWNER_UNKNOWN != benannt)"))

    total = len(components)
    attention = len(items)
    state = (
        RADAR_REPORTED_COMPLETE
        if base["decision"] == "INVENTORY_COMPLETE"
        else RADAR_REPORTED_ON_INCOMPLETE_BASIS
    )
    return {
        "state": state,
        "basis_decision": base["decision"],
        "components_total": total,
        "attention_items": attention,
        "attention_ratio_raw": (attention / total) if total else 0.0,
        "item_counts": counts,
        "items": items,
        "honesty_limits": HONESTY_LIMITS,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Legacy-Radar: proaktive Arbeitsauftraege aus dem echten Node-Inventar (Issue #503), keine Aktion, FREIGABE_BETREIBER.")
    parser.add_argument("target", help="Pfad zur Inventar-JSON-Datei")
    parser.add_argument("--output", default=None, help="Optioneller JSON-Bericht-Ausgabepfad")
    args = parser.parse_args(argv)

    path = pathlib.Path(args.target)
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("LEGACY-RADAR FEHLER (fail-closed): " + str(exc))
        return 2
    report = radar_report(inventory)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    # exit 0: Bericht erzeugt (auch UNC bekannt transparent, Items sind KEINE Entscheidungen);
    # exit 2: Ziel unlesbar. NOT_REPORTED liefert KEINE Zahl (UNKNOWN != PASS).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
