#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Digital and cryptographic autarky assessment (Datensatz 7).

Messarchitektur fuer digitale/kryptografische Autarkie nach der
MAX-BEST-Entscheidung von 2026-11-21: Energie, Wasser und Ernaehrung
funktionieren nur dann zuverlaessig, wenn auch ihre digitalen
Steuerungs-, Kommunikations- und Wiederherstellungssysteme
ausfallsicher sind.

Messbereiche (alle 8 muessen einmal gemessen sein, bevor ein
Gesamtstatus aussagekraeftig ist):

    key_management       Anteil unabhaengig verwalteter Schluessel
    key_loss_recovery    Wiederherstellung nach simuliertem Verlust
    cloud_dependency     Kritische Funktionen ohne externe Cloud
    communication        Verfuegbarkeit alternativer Kommunikationswege
    data_backup          Wiederherstellung gepruefter Sicherungskopien
    identities           Unabhaengige Pruefung + Widerruf
    software_supply      Verifizierbare Herkunft, Signaturen, Updates
    restart_time         Tatsaechlich gemessene Wiederanlaufzeit

Fail-closed rules (UNKNOWN != PASS):

1. DATENSATZ != MESSWERT: published dataset entries are recorded
   as documented claims tied to their source; they are never
   automatically independent measurements.
2. KAPAZITAET != RESERVE: technical capacity (e.g. gas storage,
   water production) is not proof of an available reserve; the
   measure must state what was actually measured.
3. DRY RUN ONLY: drills must be kind "simulation"; kind "production"
   or "live" is refused (no real key deletion, no locked accounts,
   no third-party systems touched).
4. OWN NODE ONLY: a drill may only claim its own node scope;
   effects on other nodes fail closed (ISOLATE_NOT_DESTROY).
5. RECOVERY RESTRICTED: key-loss recovery must document that
   restored rights were re-verified (no blind restoration of old
   privileges: WIEDERHERSTELLUNG != ALTE RECHTE).
6. REVOKATION INDEPENDENT: revoking a compromised identity must be
   performed by a different identity than the compromised one.
7. TEST != AUTARKIE: a successful drill proves this drill on this
   node at this time, never global autarky; the summary never
   emits "AUTARK".
8. UNKNOWN never aggregates away: an unmeasured area keeps the
   overall status partial/unknown forever (BEOBACHTET != GESAMT).

Honest limits:
- SIMULATION != PRODUKTION, SCRIPTED != INSTALLED, REPORT != REALITAET.
- The module validates records and aggregates honestly; it performs
  no drills itself and reaches no external systems.
"""

from __future__ import annotations

MEASUREMENT_AREAS = frozenset({
    "key_management",
    "key_loss_recovery",
    "cloud_dependency",
    "communication",
    "data_backup",
    "identities",
    "software_supply",
    "restart_time",
})

ALLOWED_MEASUREMENT_STATUS = frozenset({"OK", "FAIL", "OUT_OF_RANGE", "UNKNOWN"})

ALLOWED_DRILLS = frozenset({
    "cloud_outage",
    "key_loss",
    "network_outage",
    "compromised_identity",
    "restart",
})

ALLOWED_DRILL_KINDS = frozenset({"simulation"})

DATASET_ENTRY_STATUS = "DOCUMENTED_CLAIM_SOURCE_BOUND"


class DigitalAutarkyError(Exception):
    """Raised fail-closed with a machine-readable reason."""


def _require_str(record: dict, key: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DigitalAutarkyError("field_missing_or_empty:" + key)


def _validate_struct(state: dict) -> None:
    if not isinstance(state, dict) or "nodes" not in state or "dataset_entries" not in state:
        raise DigitalAutarkyError("state_malformed")
    if not isinstance(state["nodes"], dict):
        raise DigitalAutarkyError("nodes_must_be_dict")
    if not isinstance(state["dataset_entries"], list):
        raise DigitalAutarkyError("dataset_entries_must_be_list")


def new_state() -> dict:
    return {"nodes": {}, "dataset_entries": []}


def register_dataset_entry(state: dict, entry: dict) -> str:
    """DATENSATZ != MESSWERT: documented claim, bound to its source."""
    _validate_struct(state)
    if not isinstance(entry, dict):
        raise DigitalAutarkyError("entry_not_a_dict")
    for key in ("topic", "value", "source", "checked_on"):
        _require_str(entry, key)
    stored = {
        "topic": entry["topic"],
        "value": entry["value"],
        "source": entry["source"],
        "checked_on": entry["checked_on"],
        "status": DATASET_ENTRY_STATUS,
        "note": (
            "documented dataset claim, NOT an independent measurement"
        ),
    }
    state["dataset_entries"].append(stored)
    return DATASET_ENTRY_STATUS


def _node(state: dict, node_id: str) -> dict:
    if node_id not in state["nodes"]:
        state["nodes"][node_id] = {
            "measurements": {},
            "drills": [],
        }
    return state["nodes"][node_id]


def register_measurement(state: dict, node_id: str, measurement: dict) -> str:
    """Record one measurement for one area of one node."""
    _validate_struct(state)
    _require_str({"node_id": node_id}, "node_id")
    if not isinstance(measurement, dict):
        raise DigitalAutarkyError("measurement_not_a_dict")
    _require_str(measurement, "area")
    if measurement["area"] not in MEASUREMENT_AREAS:
        raise DigitalAutarkyError("area_unknown:" + str(measurement["area"]))
    _require_str(measurement, "source")
    _require_str(measurement, "checked_on")
    status = measurement.get("status")
    if status == "OK" and not measurement.get("value"):
        # An OK claim without a measured value is not a measurement.
        raise DigitalAutarkyError("ok_needs_measured_value")
    if status not in ALLOWED_MEASUREMENT_STATUS:
        raise DigitalAutarkyError("status_unknown:" + str(status))

    node = _node(state, node_id)
    area = measurement["area"]
    record = {
        "area": area,
        "status": status,
        "value": measurement.get("value"),
        "capacity_note": (
            "KAPAZITAET != RESERVE: value reflects only what was measured"
        ),
        "source": measurement["source"],
        "checked_on": measurement["checked_on"],
    }
    node["measurements"].setdefault(area, []).append(record)
    return status


def record_drill(state: dict, node_id: str, drill: dict) -> str:
    """Record a dry-run drill result. SIMULATION != PRODUKTION."""
    _validate_struct(state)
    _require_str({"node_id": node_id}, "node_id")
    if not isinstance(drill, dict):
        raise DigitalAutarkyError("drill_not_a_dict")
    _require_str(drill, "drill")
    if drill["drill"] not in ALLOWED_DRILLS:
        raise DigitalAutarkyError("drill_unknown:" + str(drill["drill"]))
    _require_str(drill, "kind")
    if drill["kind"] not in ALLOWED_DRILL_KINDS:
        raise DigitalAutarkyError("kind_must_be_simulation:" + str(drill["kind"]))
    if drill.get("affected_scope") not in ("own_node",):
        raise DigitalAutarkyError("scope_must_be_own_node")
    passed = drill.get("passed")
    if not isinstance(passed, bool):
        raise DigitalAutarkyError("passed_must_be_bool")

    name = drill["drill"]
    if name == "key_loss" and passed:
        if drill.get("restored_rights_verified") is not True:
            raise DigitalAutarkyError(
                "recovery_needs_rights_reverification"
            )
        if drill.get("integrity_verified") is not True:
            raise DigitalAutarkyError("recovery_needs_integrity_verification")
    if name == "restart" and passed:
        seconds = drill.get("measured_recovery_seconds")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds < 0:
            raise DigitalAutarkyError("restart_needs_measured_seconds")
    if name == "compromised_identity" and passed:
        _require_str(drill, "revoked_by")
        _require_str(drill, "compromised_identity")
        if drill["revoked_by"] == drill["compromised_identity"]:
            raise DigitalAutarkyError("revocation_not_independent")

    node = _node(state, node_id)
    stored = {
        "drill": name,
        "kind": "simulation",
        "affected_scope": "own_node",
        "passed": passed,
        "checked_on": drill.get("checked_on", ""),
    }
    if name == "key_loss":
        stored["restored_rights_verified"] = drill.get("restored_rights_verified")
        stored["integrity_verified"] = drill.get("integrity_verified")
    if name == "restart":
        stored["measured_recovery_seconds"] = drill.get("measured_recovery_seconds")
    if name == "compromised_identity":
        stored["revoked_by"] = drill.get("revoked_by")
        stored["compromised_identity"] = drill.get("compromised_identity")
    node["drills"].append(stored)
    return "DRY_RUN_RECORDED"


def summarize_node(state: dict, node_id: str) -> dict:
    """Per-node honest aggregate. TEST != AUTARKIE."""
    _validate_struct(state)
    if node_id not in state["nodes"]:
        raise DigitalAutarkyError("node_not_found:" + str(node_id))
    node = state["nodes"][node_id]
    by_area: dict[str, str] = {}
    for area in MEASUREMENT_AREAS:
        records = node["measurements"].get(area, [])
        if not records:
            by_area[area] = "UNMEASURED"
        else:
            by_area[area] = records[-1]["status"]
    measured = sum(1 for s in by_area.values() if s != "UNMEASURED")
    unknown_areas = [a for a in sorted(by_area) if by_area[a] in ("UNMEASURED", "UNKNOWN")]
    drills_passed = sum(1 for d in node["drills"] if d["passed"])
    drills_failed = sum(1 for d in node["drills"] if not d["passed"])
    if measured == len(MEASUREMENT_AREAS) and not unknown_areas:
        overall = "MEASURED_FULLY"
    elif measured > 0:
        overall = "MEASURED_PARTIALLY"
    else:
        overall = "UNMEASURED"
    return {
        "node_id": node_id,
        "areas_total": len(MEASUREMENT_AREAS),
        "measured_areas": measured,
        "by_area": by_area,
        "unmeasured_or_unknown": unknown_areas,
        "drills_recorded": len(node["drills"]),
        "drills_passed": drills_passed,
        "drills_failed": drills_failed,
        "overall": overall,
        "honesty_limits": (
            "TEST != AUTARKIE, SIMULATION != PRODUKTION, "
            "DATENSATZ != MESSWERT, KAPAZITAET != RESERVE, "
            "WIEDERHERSTELLUNG != ALTE RECHTE, SCRIPTED != INSTALLED"
        ),
    }


def summarize(state: dict) -> dict:
    """Global aggregate across nodes. BEOBACHTET != GESAMT."""
    _validate_struct(state)
    nodes = state["nodes"]
    per_node = {node_id: summarize_node(state, node_id) for node_id in nodes}
    states = [item["overall"] for item in per_node.values()]
    if not states:
        overall = "UNMEASURED"
    elif all(s == "MEASURED_FULLY" for s in states):
        overall = "MEASURED_ALL_NODES"
    elif any(s != "UNMEASURED" for s in states):
        overall = "MEASURED_PARTIALLY"
    else:
        overall = "UNMEASURED"
    return {
        "nodes_total": len(nodes),
        "overall": overall,
        "per_node": per_node,
        "dataset_entries_total": len(state["dataset_entries"]),
        "dataset_entry_status": DATASET_ENTRY_STATUS,
        "honesty_limits": (
            "TEST != AUTARKIE, KEIN GLOBALER NACHWEIS AUS "
            "EINZELTESTS, DATENSATZ != MESSWERT, SCRIPTED != INSTALLED"
        ),
    }
