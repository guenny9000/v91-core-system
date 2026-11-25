"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Workload-/Output-Nenner fuer Impact-Ergebnisse (Issue #419, Protokoll
#417 Abschnitt 4): saved_per_sample aus controller/impact.py ist nur
pro Sample; dieses Modul normalisiert EIN Impact-Ergebnis auf einen
vom Aufrufer belegten Workload-Nenner (Produktion, Belegung,
Service-Level). Kein zweites Impact-Modul (NO_DUPLICATE_SYSTEMS):
Periodenvergleich und VALID-Logik bleiben allein in impact.py; hier
wird ausschliesslich dividiert und geprueft, was impact.py bereits
berechnet hat.

Zustaende:
- NORMALIZED      : Impact-Ergebnis tragfaehig, Workload-Serie im
                    Beobachtungsfenster gueltig, Nenner > 0 und endlich.
- NOT_NORMALIZED  : fail-closed (zu wenige/stichprobenschwache
                    Workload-Daten, ungueltige Werte, naive Zeitstempel,
                    fehlende Grenzangabe); UNKNOWN wird nie als
                    brauchbar ausgegeben.

Ehrliche Grenzen:
- NORMALIZED != GEMESSEN: Division einer berechneten Groesse bleibt
  CALCULATED_ONLY; VALID != INDEPENDENTLY_VERIFIED bleibt unberuehrt.
- Fensterabgleich nur strukturell (Zeitstempel innerhalb des vom
  Aufrufer angegebenen Fensters); ob das Fenster wirklich zum
  Messzeitraum des Impact-Ergebnisses gehoert, kann das Modul nicht
  pruefen (WINDOW == ANGABE != BEWEIS).
- Keine Aggregation ueber Records: je Aufruf genau EIN Ergebnis.
- Kein Daemon, keine Netzwerk-Calls. SCRIPTED != RUNNING.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import pathlib
import statistics
import sys
from typing import Any, Dict, List

# Skript-Modus: controller/ auf sys.path[0] laesst "controller" auf
# controller/controller.py schatten (#460-Lektion); Skript-Ordner wird
# deshalb IM Script-Modus entfernt, bevor ROOT eingefuegt wird.
_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
# #460-Lektion: im Skript-Modus schattet controller/controller.py das
# Namespace-Paket; der Skript-Ordner wird deshalb entfernt (idempotent).
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from controller.impact import SOURCE_CONFIDENCE  # REUSE, kein Duplikat
except ModuleNotFoundError:
    # impact.py selbst importiert "ledger" flach (Legacy-Stil, wie
    # tests/test_impact.py); ohne controller/ auf sys.path schlaegt das
    # fehl. Fallback: controller-Ordner ANHAENGEN (nicht vorne), damit das
    # Paket 'controller' aus ROOT Vorrang behaelt (#460-Schatten-Lektion).
    if _SCRIPT_DIR not in sys.path:
        sys.path.append(_SCRIPT_DIR)
    from controller.impact import SOURCE_CONFIDENCE  # noqa: E402

NORMALIZED = "NORMALIZED"
NOT_NORMALIZED = "NOT_NORMALIZED"
MIN_WORKLOAD_SAMPLES = 2


class WorkloadNormError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _parse_tz_timestamp(value: Any, field: str) -> datetime.datetime:
    """Zeitstempel Pflicht tz-bewusst; naive Werte werden REJIZIERT (nie still UTC)."""
    if not isinstance(value, str) or not value.strip():
        raise WorkloadNormError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise WorkloadNormError(f"{field} is not ISO-8601: {value}") from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise WorkloadNormError(f"{field} must be timezone-aware; naive timestamps are rejected")
    return parsed


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkloadNormError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_workload_rows(rows: Any, window_start: datetime.datetime,
                         window_end: datetime.datetime) -> tuple[List[tuple[datetime.datetime, float, str]], int]:
    """Gueltige Workload-Proben im Fenster + Anzahl abgelehnter Zeilen (fail-closed).

    Gueltig: tz-bewusster Zeitstempel innerhalb [window_start, window_end],
    endlicher Wert > 0 (Nenner 0 oder negativ wäre keine Normalisierung,
    sondern ein Bruch oder eine Vorzeichenumkehr), source_type bekannt.
    """
    if not isinstance(rows, list):
        raise WorkloadNormError("workload rows must be a list")
    # Eine leere Serie ist kein Fehler, sondern fail-closed TOO_FEW_...
    good: List[tuple[datetime.datetime, float, str]] = []
    rejected = 0
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError
            ts_raw = row.get("timestamp")
            if not isinstance(ts_raw, str):
                raise ValueError
            ts = _parse_tz_timestamp(ts_raw, "workload timestamp")
            if ts < window_start or ts > window_end:
                rejected += 1
                continue
            value = row.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            source = row.get("source_type", "")
            if not isinstance(source, str) or source.strip() not in SOURCE_CONFIDENCE:
                raise ValueError
            good.append((ts, value, source.strip()))
        except (ValueError, WorkloadNormError, TypeError):
            rejected += 1
    return good, rejected


def _workload_dqi(samples: List[tuple[datetime.datetime, float, str]], rejected: int) -> float:
    total = len(samples) + rejected
    if not samples:
        return 0.0
    completeness = len(samples) / total
    confidence = statistics.mean(SOURCE_CONFIDENCE[s[2]] for s in samples)
    return round(completeness * confidence, 4)


def normalize_impact(impact: Any, workload_rows: Any, workload_unit: Any,
                     system_boundary: Any, window_start: Any, window_end: Any,
                     min_workload_samples: int | None = None) -> Dict[str, Any]:
    """Normalisiert EIN impact-Ergebnis auf einen Workload-Nenner (fail-closed).

    Der Aufrufer liefert das Beobachtungsfenster des Impact-Ergebnisses
    explizit; das Modul prueft nur strukturell, dass die Workload-Proben
    darin liegen (WINDOW == ANGABE != BEWEIS).
    """
    if min_workload_samples is None:
        ms = MIN_WORKLOAD_SAMPLES
    elif isinstance(min_workload_samples, bool) or not isinstance(min_workload_samples, int) or min_workload_samples < 1:
        raise WorkloadNormError("min_workload_samples must be an integer >= 1 when provided")
    else:
        ms = min_workload_samples

    if not isinstance(impact, dict):
        raise WorkloadNormError("impact must be a dict (Ergebnis aus controller/impact.py)")
    unit = _require_nonempty_str(impact.get("unit"), "impact['unit']")
    saved = impact.get("saved_per_sample")
    if isinstance(saved, bool) or not isinstance(saved, (int, float)) or not math.isfinite(float(saved)):
        raise WorkloadNormError("impact['saved_per_sample'] must be a finite number")
    saved = float(saved)

    # A denominator must never promote an upstream quarantined or unknown
    # impact calculation into a NORMALIZED result. Preserve NO_IMPROVEMENT
    # so worsening/non-improving measurements can still be normalized
    # without being misrepresented as savings.
    impact_status = impact.get("status")
    if not isinstance(impact_status, str) or impact_status not in ("VALID", "NO_IMPROVEMENT"):
        raise WorkloadNormError(
            "impact['status'] must be VALID or NO_IMPROVEMENT; "
            "quarantined or unknown impact results cannot be normalized"
        )
    if impact_status == "VALID" and saved <= 0:
        raise WorkloadNormError("VALID impact must have saved_per_sample > 0")
    if impact_status == "NO_IMPROVEMENT" and saved > 0:
        raise WorkloadNormError("NO_IMPROVEMENT impact must not have saved_per_sample > 0")

    w_unit = _require_nonempty_str(workload_unit, "workload_unit")
    boundary = _require_nonempty_str(system_boundary, "system_boundary")
    ws = _parse_tz_timestamp(window_start, "window_start")
    we = _parse_tz_timestamp(window_end, "window_end")
    if ws >= we:
        raise WorkloadNormError("window_start must be before window_end")

    samples, rejected = _parse_workload_rows(workload_rows, ws, we)
    flags: List[str] = []
    if len(samples) < ms:
        flags.append("TOO_FEW_WORKLOAD_SAMPLES")

    result: Dict[str, Any] = {
        "normalized_unit": f"{unit}/{w_unit}",
        "impact_status": impact_status,
        "workload_unit": w_unit,
        "system_boundary": boundary,
        "window_start": ws.isoformat(),
        "window_end": we.isoformat(),
        "n_workload_samples": len(samples),
        "rejected_workload_rows": rejected,
        "min_workload_samples": ms,
    }

    dqi = _workload_dqi(samples, rejected)
    result["workload_dqi"] = dqi

    if samples:
        w_mean = statistics.mean(s[1] for s in samples)
        result["workload_mean"] = round(w_mean, 6)
        if not flags:
            result["saved_per_workload_unit"] = round(saved / w_mean, 9)
            co2 = impact.get("co2_change_kg_per_sample")
            if co2 is not None and not isinstance(co2, bool) and isinstance(co2, (int, float)) and math.isfinite(float(co2)):
                result["co2_change_kg_per_workload_unit"] = round(float(co2) / w_mean, 9)

    status = NOT_NORMALIZED if flags else NORMALIZED
    result["status"] = status
    result["flags"] = flags
    return result


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workload_norm",
        description="Workload-/Output-Nenner fuer EIN impact-Ergebnis (Issue #419)",
    )
    parser.add_argument("--impact-json", required=True,
                        help="JSON-Datei mit EINEM impact-Ergebnis (aus controller/impact.py)")
    parser.add_argument("--workload-csv", required=True,
                        help="CSV timestamp,value,source_type (Workload-Nenner im Beobachtungsfenster)")
    parser.add_argument("--workload-unit", required=True)
    parser.add_argument("--system-boundary", required=True)
    parser.add_argument("--window-start", required=True, help="ISO-8601 tz-bewusst")
    parser.add_argument("--window-end", required=True, help="ISO-8601 tz-bewusst")
    args = parser.parse_args(argv)

    try:
        with open(args.impact_json, encoding="utf-8") as fh:
            impact = json.load(fh)
        import csv as _csv
        with open(args.workload_csv, newline="", encoding="utf-8") as fh:
            rows = list(_csv.DictReader(fh))

        def _to_number(v):
            if isinstance(v, str):
                try:
                    return float(v)
                except ValueError:
                    return v
            return v

        rows = [{**row, "value": _to_number(row.get("value"))} for row in rows]
        result = normalize_impact(
            impact, rows, args.workload_unit, args.system_boundary,
            args.window_start, args.window_end,
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"workload_norm: I/O error: {exc}", file=sys.stderr)
        return 2
    except WorkloadNormError as exc:
        print(f"workload_norm: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == NORMALIZED else 1


if __name__ == "__main__":
    raise SystemExit(main())
