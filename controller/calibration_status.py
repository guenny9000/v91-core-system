"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kalibrierungs-Status je Sensor (Issue #419-Rest):
Ein Register fuer den Kalibrierungszustand jedes Mess-Sensors, denn
Schwellen und VALID-Claims haengen an tatsaechlich angewandter
Messtechnik (Protokoll #417 Abschnitt 4; PARAMETERIZABLE !=
CALIBRATED, PR #436). Ein Sensor gilt NUR als CALIBRATED, wenn eine
strukturgueltige Evidenz-Referenz UND ein zeitzonen-bewusster
Kalibrierungs-Zeitstempel UND (falls angegeben) ein gueltiges
Gueltigkeitsfenster vorliegen; alles andere bleibt UNKNOWN oder
REVIEW_REQUIRED. Nichtwissen wird nie als brauchbar ausgegeben.

Zustaende je Sensor:
- CALIBRATED      : Evidenz-Referenz strukturell gueltig, Zeitstempel
                    tz-bewusst, Fenster (falls gesetzt) unexpired.
- EXPIRED         : Fenster abgelaufen -> zaehlt NICHT als kalibriert.
- REVIEW_REQUIRED : Eintrag vorhanden, aber Evidenz-Referenz fehlt
                    oder ist strukturell ungueltig.
- UNKNOWN         : kein Eintrag fuer diesen Sensor.

Ehrliche Grenzen:
- CALIBRATED != ACCURATE: eine Registrierung beweist Struktur, keine
  Messgenauigkeit; VALID != INDEPENDENTLY_VERIFIED bleibt.
- Evidenz-Referenzpruefung wird aus v99/filter/source_quality.py
  wiederverwendet, nicht dupliziert (NO_DUPLICATE_SYSTEMS).
- Kein Daemon, keine Netzwerk-Calls, keine Zustandsaenderung an
  Sensoren. SCRIPTED != RUNNING; REGISTRY != KALIBRIERUNG: der echte
  Abgleich gegen Referenzgeraete bleibt Betreiber-Arbeit vor Ort.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

# Skript-Modus setzt sys.path[0] auf controller/; ROOT fuer v99 erreichbar
# (gleiche Ursache wie im CI-Fix zu domain_usecase_gate #434).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from v99.filter.source_quality import _is_valid_reference

CALIBRATED = "CALIBRATED"
EXPIRED = "EXPIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNKNOWN = "UNKNOWN"
REVIEW_STATUS = "CALIBRATION_REVIEW_ONLY"


class CalibrationStatusError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _parse_tz_timestamp(value: Any, field: str) -> datetime.datetime:
    """Zeitstempel Pflicht tz-bewusst; naive Werte werden REJIZIERT (nie still UTC)."""
    if not isinstance(value, str) or not value.strip():
        raise CalibrationStatusError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise CalibrationStatusError(f"{field} is not ISO-8601: {value}") from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise CalibrationStatusError(f"{field} must be timezone-aware; naive timestamps are rejected")
    return parsed


def evaluate_sensor(entry: Any, now: datetime.datetime) -> Dict[str, Any]:
    """Ein Sensor-Eintrag -> Kalibrierungszustand (fail-closed)."""
    if not isinstance(entry, dict):
        raise CalibrationStatusError("sensor entry must be an object")
    sensor_id = entry.get("sensor_id")
    if not isinstance(sensor_id, str) or not sensor_id.strip():
        raise CalibrationStatusError("sensor_id needs a non-empty name")
    sensor_id = sensor_id.strip()
    evidence = entry.get("evidence")
    if evidence is None or not _is_valid_reference(evidence):
        return {"sensor_id": sensor_id, "state": REVIEW_REQUIRED}
    calibrated_at = _parse_tz_timestamp(entry.get("calibrated_at"), "calibrated_at")
    valid_until_raw = entry.get("valid_until")
    if valid_until_raw is not None:
        valid_until = _parse_tz_timestamp(valid_until_raw, "valid_until")
        if valid_until <= calibrated_at:
            raise CalibrationStatusError(f"valid_until must be after calibrated_at for {sensor_id}")
        if now > valid_until:
            return {"sensor_id": sensor_id, "state": EXPIRED, "expires": valid_until.isoformat()}
    if now.tzinfo is None:
        raise CalibrationStatusError("now must be timezone-aware")
    return {"sensor_id": sensor_id, "state": CALIBRATED, "calibrated_at": calibrated_at.isoformat()}


def evaluate_calibration_registry(entries: Any, now: Any, sensor_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Register auswerten; nicht registrierte Sensoren bleiben UNKNOWN."""
    if not isinstance(entries, list):
        raise CalibrationStatusError("entries must be a list")
    now_dt = _parse_tz_timestamp(now, "now") if isinstance(now, str) else now
    if not isinstance(now_dt, datetime.datetime):
        raise CalibrationStatusError("now must be a tz-aware datetime or ISO-8601 string")
    if now_dt.tzinfo is None:
        raise CalibrationStatusError("now must be timezone-aware; naive timestamps are rejected")
    seen = set()
    results: List[Dict[str, Any]] = []
    for entry in entries:
        sid = entry.get("sensor_id") if isinstance(entry, dict) else None
        if sid is not None and str(sid).strip() in seen:
            raise CalibrationStatusError(f"duplicate sensor_id: {sid}")
        if sid is not None:
            seen.add(str(sid).strip())
        results.append(evaluate_sensor(entry, now_dt))
    if sensor_ids is not None:
        if not isinstance(sensor_ids, list) or any(not isinstance(s, str) or not s.strip() for s in sensor_ids):
            raise CalibrationStatusError("sensor_ids must be a list of non-empty strings")
        for sid in sensor_ids:
            if sid.strip() not in seen:
                results.append({"sensor_id": sid.strip(), "state": UNKNOWN})
    if not results:
        raise CalibrationStatusError("registry is empty and no sensor_ids given")
    counts = {CALIBRATED: 0, EXPIRED: 0, REVIEW_REQUIRED: 0, UNKNOWN: 0}
    for r in results:
        counts[r["state"]] += 1
    usable = counts[CALIBRATED]
    total = len(results)
    coverage = round(usable / total, 4)
    return {
        "sensors": results,
        "state_counts": counts,
        "calibration_coverage": coverage,
        "coverage_status": "CALCULATED_ONLY",
        "honest_limits": [
            "CALIBRATED != ACCURATE: registry proves structure, not measurement accuracy",
            "REGISTRY != KALIBRIERUNG: the physical comparison against reference devices remains operator work",
        ],
        "review_status": REVIEW_STATUS,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed per-sensor calibration status registry (review only)")
    parser.add_argument("input", help="JSON file {'entries': [...], 'now': '...', 'sensor_ids': [...]} or '-' for stdin")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, "r", encoding="utf-8").read()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise CalibrationStatusError("input must be a JSON object")
        report = evaluate_calibration_registry(data.get("entries", []), data.get("now"), data.get("sensor_ids"))
    except (CalibrationStatusError, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if report["state_counts"][REVIEW_REQUIRED] or report["state_counts"][UNKNOWN] or report["state_counts"][EXPIRED]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
