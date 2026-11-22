"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kurzlauf-Validierer fuer das Wirkungsregister (VIBE-LXVIII).

Validierungs-Gate fuer Kurzlauf-CSVs der vier VB-Messpunkte aus
controller.mess_pilot (VB METRICS-REUSE, Runbook-Abschnitt 2).

Ehrliche Grenzen dieses Moduls:
- VALID != EINTRAG: dieses Modul schreibt NIE ins R3-Ledger. Das
  Anhaengen von Wirkungsregister-Eintraegen bleibt allein bei
  controller.messwerte_ingest MesswertLedger.append
  (NO_DUPLICATE_SYSTEMS, Redundante Register bleiben verboten).
- UNKNOWN != PASS: UNKNOWN bedeutet fehlenden Kontext (Cold-Start,
  zu kurzer Vorgaenger), niemals einen bestandenen Wert.
- SCRIPTED != INSTALLED: kein Daemon, kein Taskplaner, keine
  Cron-Bindung; der zyklische Betrieb bleibt Betreiber-Entscheid
  (Ewigbetrieb-Doku PR #272).
- Drift-Pruefungen sind Statistik, keine Kausalitaet: DRIFT sagt
  'Abweichung erkannt', nie 'Ursache bekannt'
  (KORRELATION != URSACHE).

CSV-Format (strikt, fail-closed):
- Optionaler Header 'metric_id,value' in Zeile 1.
- Danach je Zeile: <VB-MESSPUNKT-ID>,<float> (Komma oder Semikolon
  als Trenner; '#' startet einen Kommentar bis Zeilenende).
- Unbekannte Messpunkt-ID, nicht-numerische Werte, leere Daten,
  Werte ausserhalb der logischen Plausibilitaets-Ranges aus VB_METRICS
  fuehren zu Verdict-Abwertung bzw. INPUT_ERROR, nie zu stiller
  Korrektur.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from controller.mess_pilot import VB_METRICS

# --- Schwellenwerte (Konstanten, deterministisch, nicht aus Env) -----------
# drift_max   : relative Abweichung des Mittels gegen den Vorgaenger
# outlier_max : Anteil statistisch auffaelliger Werte (IQR + Z-Score)
DEFAULT_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "VB-ENERGIE-01": {"drift_max": 0.10, "outlier_max": 0.20},
    "VB-NETZ-01": {"drift_max": 0.10, "outlier_max": 0.20},
    "VB-SYS-01": {"drift_max": 0.10, "outlier_max": 0.20},
    "VB-UMWELT-01": {"drift_max": 0.10, "outlier_max": 0.20},
}
ZSCORE_LIMIT = 3.0
IQR_FACTOR = 1.5
MIN_VORGAENGER_POINTS = 5

VALID = "VALID"
UNKNOWN = "UNKNOWN"
DRIFT = "DRIFT"
EXIT_VALID, EXIT_UNKNOWN, EXIT_DRIFT, EXIT_INPUT_ERROR = 0, 1, 2, 3


class KurzlaufInputError(ValueError):
    """Fail-closed fuer unbrauchbare Eingabedaten (SCRIPTED != GEMESSEN)."""


def parse_kurzlauf_csv(path: Path) -> Dict[str, List[float]]:
    """Liest eine Kurzlauf-CSV ein; strict fail-closed."""
    if not path.is_file():
        raise KurzlaufInputError("datei fehlt: %s" % path)
    data: Dict[str, List[float]] = {}
    with path.open("r", encoding="ascii") as handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if lineno == 1 and line.lower() in (
                "metric_id,value", "messpunkt,value", "metric_id;value"
            ):
                continue
            parts = line.replace(";", ",").split(",")
            if len(parts) != 2:
                raise KurzlaufInputError(
                    "zeile %d: erwartet '<metric_id>,<value>', erhalten: %r"
                    % (lineno, raw.strip()))
            metric_id, raw_value = parts[0].strip(), parts[1].strip()
            if metric_id not in VB_METRICS:
                raise KurzlaufInputError(
                    "zeile %d: unbekannter Messpunkt %r (bekannt: %s)"
                    % (lineno, metric_id, ", ".join(sorted(VB_METRICS))))
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise KurzlaufInputError(
                    "zeile %d: wert %r ist nicht numerisch" % (lineno, raw_value)
                ) from exc
            data.setdefault(metric_id, []).append(value)
    if not data:
        raise KurzlaufInputError("keine messwerte in %s" % path)
    return data


def _quartiles(values: List[float]) -> Tuple[float, float, float]:
    """Q1/IQR/Q3 mit 'inclusive'-Interpolation (statistics-stdlib)."""
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q3 - q1, q3


def describe(values: List[float]) -> Dict[str, Any]:
    """Ehrliche Statistik; fehlende Groessen bleiben None statt geraten.

    Bei n < 2 sind Quartile nicht interpolierbar (statistik-stdlib
    verlangt mindestens zwei Punkte); dann wird ehrlich IQR 0 mit
    Schrumpf-Zaehlung gefuehrt, nie geraten."""
    n = len(values)
    if n < 2:
        q1 = q3 = statistics.median(values)
        iqr = 0.0
        outliers = []
    else:
        q1, iqr, q3 = _quartiles(values)
        lower_fence = q1 - IQR_FACTOR * iqr
        upper_fence = q3 + IQR_FACTOR * iqr
        outliers = [v for v in values
                    if v < lower_fence or v > upper_fence]
    std = statistics.pstdev(values) if n >= 2 else None
    if std is not None and std > 0.0 and n >= 3:
        mean_val = statistics.fmean(values)
        z_outliers = [v for v in values
                      if abs((v - mean_val) / std) > ZSCORE_LIMIT]
    else:
        z_outliers = []
    outlier_fraction = len(outliers) / n if n else 0.0
    return {
        "n": n,
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "std": std,
        "min": min(values),
        "max": max(values),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "outlier_fraction": outlier_fraction,
        "outliers_iqr": len(outliers),
        "outliers_zscore": len(z_outliers),
    }


def _out_of_range(metric_id: str, values: List[float]) -> int:
    lo, hi = VB_METRICS[metric_id]["range"]
    return sum(1 for v in values if v < lo or v > hi)


def classify(metric_id: str, values: List[float],
             prev_values: Optional[List[float]]) -> Dict[str, Any]:
    """Verdict je Messpunkt: VALID/UNKNOWN/DRIFT, UNKNOWN != PASS."""
    stats = describe(values)
    thresholds = DEFAULT_THRESHOLDS[metric_id]
    oor = _out_of_range(metric_id, values)
    result: Dict[str, Any] = {
        "metric_id": metric_id,
        "unit": VB_METRICS[metric_id]["unit"],
        "stats": stats,
        "out_of_range": oor,
        "drift_percent": None,
        "verdict": VALID,
        "reasons": [],
    }
    if oor > 0:
        result["verdict"] = DRIFT
        result["reasons"].append(
            "OUT_OF_RANGE: %d werte ausserhalb der logischen Range ("
            "Plausibilitaetsgrenze, nie still korrigiert)" % oor)
    if prev_values is None:
        result["verdict"] = DRIFT if result["verdict"] == DRIFT else UNKNOWN
        result["reasons"].append(
            "COLD_START: kein vorgaenger-kurzlauf, kein drift-vergleich")
    elif len(prev_values) < MIN_VORGAENGER_POINTS:
        result["verdict"] = DRIFT if result["verdict"] == DRIFT else UNKNOWN
        result["reasons"].append(
            "VORGAENGER_UNVOLLLSTAENDIG: %d < %d punkte"
            % (len(prev_values), MIN_VORGAENGER_POINTS))
    else:
        prev_stats = describe(prev_values)
        prev_mean = prev_stats["mean"]
        cur_mean = stats["mean"]
        if prev_mean == 0.0:
            drift_percent = None
            result["reasons"].append(
                "DRIFT_NICHT_BERECHENBAR: vorgaenger-mittel ist 0.0")
            result["verdict"] = DRIFT
        else:
            drift_percent = abs(cur_mean - prev_mean) / abs(prev_mean) * 100.0
            result["drift_percent"] = round(drift_percent, 4)
            if drift_percent > thresholds["drift_max"] * 100.0:
                result["verdict"] = DRIFT
                result["reasons"].append(
                    "DRIFT: %.4f%% > schwelle %.0f%% (mittel %.6f vs %.6f)"
                    % (drift_percent, thresholds["drift_max"] * 100.0,
                       cur_mean, prev_mean))
        result["prev_stats"] = prev_stats
    if stats["outlier_fraction"] > thresholds["outlier_max"]:
        result["verdict"] = DRIFT
        result["reasons"].append(
            "AUSREISSER_ANTEIL: %.4f > schwelle %.2f (IQR+Z-Score)"
            % (stats["outlier_fraction"], thresholds["outlier_max"]))
    return result


def validate(current_csv: Path,
             vorgaenger_csv: Optional[Path] = None) -> Dict[str, Any]:
    """Voller Validierungslauf; wirft KurzlaufInputError bei unbrauchbarer
    Eingabe (fail-closed). Rueckgabe ist ein deterministischer Report."""
    current = parse_kurzlauf_csv(current_csv)
    previous = (parse_kurzlauf_csv(vorgaenger_csv)
                if vorgaenger_csv is not None else None)
    per_metric: List[Dict[str, Any]] = []
    for metric_id in sorted(current):
        per_metric.append(
            classify(metric_id, current[metric_id],
                      previous.get(metric_id) if previous else None))
    overall = VALID
    if any(m["verdict"] == DRIFT for m in per_metric):
        overall = DRIFT
    elif any(m["verdict"] == UNKNOWN for m in per_metric):
        overall = UNKNOWN
    return {
        "current_csv": current_csv.name,
        "vorgaenger_csv": vorgaenger_csv.name if vorgaenger_csv else None,
        "overall": overall,
        "per_metric": per_metric,
        "grenzen": "VALID != EINTRAG; R3-Append NUR via "
                   "messwerte_ingest MesswertLedger.append (NO_DUPLICATE_"
                   "SYSTEMS); SCRIPTED != INSTALLED; UNKNOWN != PASS",
    }


def format_text_report(report: Dict[str, Any]) -> str:
    """Lesbarer, ASCII-purer, deterministischer Bericht."""
    lines = [
        "V91 Kurzlauf-Validierung (Wirkungsregister-Gate)",
        "csv       : %s" % report["current_csv"],
        "vorgaenger: %s" % (report["vorgaenger_csv"] or "-"),
        "gesamt    : %s" % report["overall"],
        "",
    ]
    for m in report["per_metric"]:
        s = m["stats"]
        lines.append("%s" % m["metric_id"])
        lines.append("   bewertung : %s" % m["verdict"])
        lines.append("   n         : %d" % s["n"])
        if m["drift_percent"] is not None:
            lines.append("   drift     : %.4f%%" % m["drift_percent"])
        lines.append("   mittel    : %.6f" % s["mean"])
        lines.append("   median    : %.6f" % s["median"])
        lines.append("   std       : %s" % ("%.6f" % s["std"]
                                            if s["std"] is not None else "UNKNOWN"))
        lines.append("   min/max   : %.6f / %.6f" % (s["min"], s["max"]))
        lines.append("   ausreisser: %.4f (IQR %d, Z %d) / out_of_range %d"
                     % (s["outlier_fraction"], s["outliers_iqr"],
                        s["outliers_zscore"], m["out_of_range"]))
        for reason in m["reasons"]:
            lines.append("   hinweis   : %s" % reason)
        lines.append("")
    lines.append("grenze: %s" % report["grenzen"])
    return "\n".join(lines) + "\n"


def _write_reports(report: Dict[str, Any], out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(report["current_csv"]).stem
    txt_path = out_dir / ("validierung_%s.txt" % stem)
    json_path = out_dir / ("validierung_%s.json" % stem)
    txt_path.write_text(format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                          ensure_ascii=True) + "\n"
    json_path.write_text(payload, encoding="ascii")
    return txt_path, json_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kurzlauf-Validierer (advisory Gate, VALID != EINTRAG)")
    parser.add_argument("kurzlauf_csv", help=" aktuelle Kurzlauf-CSV")
    parser.add_argument("--vorgaenger", default=None,
                        help="Vorgaenger-Kurzlauf-CSV fuer Drift-Vergleich")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        report = validate(
            Path(args.kurzlauf_csv),
            Path(args.vorgaenger) if args.vorgaenger else None)
    except KurzlaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    return {VALID: EXIT_VALID, UNKNOWN: EXIT_UNKNOWN,
            DRIFT: EXIT_DRIFT}[report["overall"]]


if __name__ == "__main__":
    sys.exit(main())
