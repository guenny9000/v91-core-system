"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Schwellen-Registry je Use Case (Issue #419-Rest, parameterisierbare
Schwellen + Kalibrierungs-Registry): verbindet die parameterisierbaren
Gates aus controller/impact.py (_validate_thresholds, REUSE, keine
zweite Validierungslogik) mit dem Kalibrierungs-Zustand je Sensor aus
controller/calibration_status.py (evaluate_sensor, REUSE).

Regel (fail-closed): Eine use-case-Schwelle wird NUR als BINDUNG
ausgegeben, wenn der zugehoerige Sensor laut Registry CALIBRATED ist.
Bei EXPIRED, REVIEW_REQUIRED oder UNKNOWN gibt die Registry KEINE
Schwellen aus (thresholds = None). Es gibt KEINEN stillen Fallback auf
Dokument-Defaults, denn Default-Schwellen auf unkalibriertem Sensor
waeren eine ungedeckte VALID-Behauptung (UNKNOWN != PASS,
REGISTRY != KALIBRIERUNG, BINDUNG != MESSTECHNIK).

Ehrliche Grenzen:
- BINDUNG != MESSTECHNIK: die physische Kalibrierung gegen
  Referenzgeraete bleibt Betreiber-Arbeit vor Ort (Issue #101).
- CALIBRATED != ACCURATE (siehe calibration_status.py).
- Verzicht auf None-Eingaben: Registry-Eintraege muessen die Schwellen
  je Use Case EXPLIZIT setzen (JUSTIFIED != DEFAULT); Module-Defaults
  aus impact.py sind fuer diese Registry bewusst NICHT waehlbar.
- Kein Daemon, kein Netzwerk, keine zufaelligen Werte.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
# impact.py nutzt 'from ledger import HashChainLedger'; ledger.py liegt in
# controller/ und ist nur erreichbar, wenn controller/ selbst auf sys.path
# liegt (gleiche Ursache wie im Skript-Modus aller Controller-CLIs).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:  # Paket-Import (Tests/CI starten ab Wurzel)
    from controller.calibration_status import (
        CALIBRATED,
        CalibrationStatusError,
        EXPIRED,
        REVIEW_REQUIRED,
        UNKNOWN,
        evaluate_sensor,
    )
    from controller.impact import _validate_thresholds
except ImportError:  # Skript-Modus: python controller/schwellen_registry.py
    from calibration_status import (  # type: ignore
        CALIBRATED,
        CalibrationStatusError,
        EXPIRED,
        REVIEW_REQUIRED,
        UNKNOWN,
        evaluate_sensor,
    )
    from impact import _validate_thresholds  # type: ignore

BINDUNG = "BINDUNG_GUELTIG"
THRESHOLD_KEYS = ("min_samples", "dqi_min", "noise_factor")


class SchwellenRegistryError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchwellenRegistryError(f"{field} needs a non-empty string")
    return value.strip()


def _load_json_source(source: Any, label: str) -> Any:
    if isinstance(source, str):
        try:
            with open(source, encoding="utf-8") as fh:
                return json.load(fh)
        except OSError as exc:
            raise SchwellenRegistryError(f"{label} unreadable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SchwellenRegistryError(f"{label} invalid JSON: {exc}") from exc
    if isinstance(source, list):
        return source
    raise SchwellenRegistryError(f"{label} must be a file path or a list")


def _validate_threshold_entry(raw: Any, use_case: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise SchwellenRegistryError(f"thresholds for {use_case} must be an object")
    missing = [k for k in THRESHOLD_KEYS if k not in raw]
    if missing:
        raise SchwellenRegistryError(
            f"thresholds for {use_case} must set all of {list(THRESHOLD_KEYS)} explicitly "
            f"(missing: {missing}); defaults are not selectable here"
        )
    if raw.get("min_samples") is None or raw.get("dqi_min") is None or raw.get("noise_factor") is None:
        raise SchwellenRegistryError(
            f"thresholds for {use_case} must be explicit, None is not allowed (JUSTIFIED != DEFAULT)"
        )
    try:
        return _validate_thresholds(raw["min_samples"], raw["dqi_min"], raw["noise_factor"])
    except ValueError as exc:
        raise SchwellenRegistryError(f"invalid thresholds for {use_case}: {exc}") from exc


def bind_use_case(entry: Any, calibration_entry: Any, now: Any) -> Dict[str, Any]:
    """Ein Registry-Eintrag -> gebundene Schwellen oder NICHT_GEBUNDEN (fail-closed).

    thresholds sind NUR bei sensor_state == CALIBRATED ein Dict, sonst
    bewusst None. Nie ein stiller Default. Never a silent default.
    """
    if not isinstance(entry, dict):
        raise SchwellenRegistryError("registry entry must be an object")
    use_case = _require_nonempty_str(entry.get("use_case"), "use_case")
    if not isinstance(entry.get("sensor_id"), str) or not entry["sensor_id"].strip():
        raise SchwellenRegistryError(f"sensor_id for {use_case} needs a non-empty string")
    thresholds = _validate_threshold_entry(entry.get("thresholds"), use_case)
    try:
        sensor_state = evaluate_sensor(calibration_entry, now)
    except CalibrationStatusError as exc:
        raise SchwellenRegistryError(f"calibration entry for {use_case} invalid: {exc}") from exc
    state = sensor_state["state"]
    if state == CALIBRATED:
        bound: Optional[Dict[str, Any]] = dict(thresholds)
        status = BINDUNG
    else:
        bound = None
        status = "NICHT_GEBUNDEN"
    result: Dict[str, Any] = {
        "use_case": use_case,
        "sensor_id": entry["sensor_id"].strip(),
        "sensor_state": state,
        "thresholds": bound,
        "binding_status": status,
    }
    if state == EXPIRED:
        result["reason"] = "sensor calibration window expired"
    elif state == REVIEW_REQUIRED:
        result["reason"] = "sensor evidence reference missing or structurally invalid"
    elif state == UNKNOWN:
        result["reason"] = "sensor not present in calibration registry"
    return result


def bind_registry(
    entries: Any,
    calibration_entries: Any,
    now: Any,
    use_cases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Alle Registry-Eintraege binden; doppelte use_cases fail-closed."""
    entries = _load_json_source(entries, "threshold registry")
    calibration_entries = _load_json_source(calibration_entries, "calibration registry")
    if not isinstance(entries, list) or not entries:
        raise SchwellenRegistryError("threshold registry must be a non-empty list")
    if not isinstance(calibration_entries, list):
        raise SchwellenRegistryError("calibration registry must be a list")
    if isinstance(now, str):
        try:
            now_dt = datetime.datetime.fromisoformat(now)
        except ValueError as exc:
            raise SchwellenRegistryError(f"now is not a valid ISO-8601 timestamp: {exc}") from exc
    else:
        now_dt = now
    if not isinstance(now_dt, datetime.datetime):
        raise SchwellenRegistryError("now must be a tz-aware datetime or ISO-8601 string")
    if now_dt.tzinfo is None:
        raise SchwellenRegistryError("now must be timezone-aware; naive timestamps are rejected")
    cal_by_sensor: Dict[str, Any] = {}
    for cal in calibration_entries:
        if isinstance(cal, dict) and isinstance(cal.get("sensor_id"), str):
            sid = cal["sensor_id"].strip()
            if sid in cal_by_sensor:
                raise SchwellenRegistryError(f"duplicate calibration entry: {sid}")
            cal_by_sensor[sid] = cal
    seen: set = set()
    bindings: List[Dict[str, Any]] = []
    for entry in entries:
        uc = entry.get("use_case") if isinstance(entry, dict) else None
        if isinstance(uc, str) and uc.strip() in seen:
            raise SchwellenRegistryError(f"duplicate use_case: {uc}")
        if isinstance(uc, str):
            seen.add(uc.strip())
        cal = cal_by_sensor.get(entry["sensor_id"].strip()) if isinstance(entry, dict) else None
        if cal is None:
            raise SchwellenRegistryError(
                f"no calibration entry for sensor of use_case {uc!r}; uncalibrated sensors are not silently bound"
            )
        bindings.append(bind_use_case(entry, cal, now_dt))
    if use_cases is not None:
        for uc in use_cases:
            if uc not in seen:
                raise SchwellenRegistryError(f"use_case not in registry: {uc}")
    bound_count = sum(1 for b in bindings if b["binding_status"] == BINDUNG)
    return {
        "schema": "v91.schwellen_registry.v1",
        "bindings": bindings,
        "bound_use_cases": bound_count,
        "total_use_cases": len(bindings),
        "honest_limits": [
            "BINDUNG != MESSTECHNIK: the physical comparison against reference devices remains operator work",
            "CALIBRATED != ACCURATE (see controller/calibration_status.py)",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Schwellen-Registry (Issue #419)")
    parser.add_argument("--self-check", action="store_true", help="synthetic fixture self-check (SYNTHETISCH != MESSUNG)")
    parser.add_argument("--registry", help="JSON file with use-case threshold registry")
    parser.add_argument("--calibration", help="JSON file with calibration registry entries")
    parser.add_argument("--now", help="ISO-8601 timezone-aware timestamp")
    args = parser.parse_args(argv)
    if args.self_check:
        cal = {
            "sensor_id": "synthetic_meter",
            "evidence": "ledger::selfcheck-001",
            "calibrated_at": "2026-11-01T10:00:00+00:00",
        }
        reg = [
            {
                "use_case": "selfcheck_demo",
                "sensor_id": "synthetic_meter",
                "thresholds": {"min_samples": 5, "dqi_min": 0.85, "noise_factor": 2.0},
            }
        ]
        out = bind_registry(reg, [cal], datetime.datetime(2026, 11, 25, 12, 0, 0, tzinfo=datetime.timezone.utc))
        print(json.dumps({"mechanism": "getestet", "reale_messreihe": "NICHT_GEPRUEFT", **out}, indent=2))
        return 0
    if not args.registry or not args.calibration or not args.now:
        print("usage: --registry FILE --calibration FILE --now ISO8601 (or --self-check)", file=sys.stderr)
        return 2
    try:
        now_dt = datetime.datetime.fromisoformat(args.now)
        if now_dt.tzinfo is None:
            raise SchwellenRegistryError("now must be timezone-aware; naive timestamps are rejected")
        out = bind_registry(args.registry, args.calibration, now_dt)
    except (SchwellenRegistryError, CalibrationStatusError, ValueError, OSError) as exc:
        print(json.dumps({"status": "INPUT_FEHLER", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0 if out["bound_use_cases"] == out["total_use_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
