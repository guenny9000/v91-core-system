"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Cumulative-Stress-Load: kumulative Domänen-Belastung statt binärer
Einzel-Link-Kausalitaet. Anlass ist der externe Bericht 24.11.2026
(dritte Saettigungswelle), der einen Paradigmenwechsel von
"Ereignis A loest B aus" hin zu "mehrere gleichzeitige chronische
Belastungen destabilisieren das System" vorschlaegt.

PRUEFBFUND vor dem Bau (ehrlich, CLAIM != EVIDENCE): Die im Bericht
als vorhanden behauptete Infrastruktur (detect_cascades,
analyze_ewaste_to_soil, 16-Fall-Korpus Guiyu/Lagos/Nairobi/Schweiz,
Macro F1 0.59, 3104 Tests) existiert im Repository NICHT (0 Treffer
im ganzen Baum am main-Stand). Es werden KEINE Metrik-Gewinne
behauptet und KEIN bestehendes Modell "umgebaut"; umgesetzt wird
allein die tragfaehige Kernidee als NEUES, eigenstaendiges Modul.

Vertrag (je Aufruf EIN Bericht, Zahlen nie ohne Basis):
- Eingabe: Liste von Domaenen-Snapshots {domain, load_raw, basis}.
  load_raw ist ein roher Belastungsbruch 0..1; basis ist
  MEASURED oder CALCULATED (CALCULATED != MEASURED).
  basis UNKNOWN: keine Zahl, Domaene wird AUSGESCHLOSSEN und gezaehlt.
- Gewichte sind AUFRUFER-ANGABE (optional, > 0, endlich); fehlen sie,
  zaehen alle bekannten Domaenen gleich. GEWICHTE == ANGABE != BEWEIS.
- cumulative_index_raw = Summe(gewicht * load) / Summe(gewicht) ueber
  alle BEKANNTEN Domaenen, als rohe Zahl, nie gerundet (MITTEL !=
  MESSUNG).
- co_stress_domains: bekannte Domaenen an/ueber der Aufrufer-Schwelle
  high_threshold_raw; reine Zaehlung des gleichzeitigen Auftretens,
  CO_OCCURRENCE != SYNERGIE (keine Multiplikator-Fiktion).
- index_vs_critical: BELOW / AT_OR_ABOVE gegen die Aufrufer-Schwelle
  critical_threshold_raw. SCHWELLE == ANGABE != BEWEIS.

Zustaende:
- INDEX_REPORTED            : alle Domaenen bekannt, Index genannt.
- REPORTED_ON_INCOMPLETE_BASIS: mind. eine Domaene UNKNOWN oder
  ungueltig; Index nur ueber die bekannte Basis genannt,
  known_domain_ratio_raw und Ausschlusszaehlung genannt (fail-closed,
  nie geschoent).
- NOT_REPORTED              : ungueltige Eingabe oder keine bekannte
  Domaene; KEINE Zahl (UNKNOWN != PASS).

Ehrliche Grenzen:
- Kumulativer Index ist eine MITTELUNG ueber ANGABEN, keine Messung;
  einzelne kritische Link-Ausloeser werden NICHT erkannt (dieses
  Modul ist KEIN Kaskaden-Detektor).
- Keine Metrik-Behauptung: Es gibt hier bewusst KEINE F1-/Recall-/
  Precision-Angaben; solche DUERFEN nur aus echter Evaluierung mit
  Ground Truth stammen, die laut PRUEBFUND nicht existiert.
- Kein Daemon, kein Schreiben, keine Netz-Runtime,
  KLASSIFIKATION != EINGRIFF, SCRIPTED != RUNNING, REVIEW != DECISION.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from typing import Any

# Skript-Modus: controller/ auf sys.path[0] laesst "controller" auf
# controller/controller.py schatten (#460-Lektion); Skript-Ordner wird
# deshalb entfernt, bevor ROOT eingefuegt wird (idempotent).
_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

INDEX_REPORTED = "INDEX_REPORTED"
REPORTED_ON_INCOMPLETE_BASIS = "REPORTED_ON_INCOMPLETE_BASIS"
NOT_REPORTED = "NOT_REPORTED"

_KNOWN_BASES = ("MEASURED", "CALCULATED")

HONESTY_LIMITS = (
    "MITTEL == GEWICHTETE_ANGABE != MESSUNG, "
    "CALCULATED != MEASURED, GEWICHTE == ANGABE != BEWEIS, "
    "SCHWELLE == ANGABE != BEWEIS, CO_OCCURRENCE != SYNERGIE, "
    "KEIN_KASKADEN_DETEKTOR, KEINE_METRIK_BEHAUPTUNG_OHNE_GROUND_TRUTH, "
    "UNKNOWN != PASS, KLASSIFIKATION != EINGRIFF, SCRIPTED != RUNNING"
)


class InvalidInput(Exception):
    """Ungueltige Eingabe (CLI exit 2, fail-closed)."""


def _is_number(value: Any) -> bool:
    # bool ist in Python int-Subklasse: explizit ablehnen.
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _validate_load(load_raw: Any) -> float:
    if not _is_number(load_raw):
        raise InvalidInput("load_raw must be a finite number, bool rejected")
    if not (0.0 <= load_raw <= 1.0):
        raise InvalidInput("load_raw must be within [0.0, 1.0]")
    return float(load_raw)


def _validate_thresholds(payload: dict[str, Any]) -> tuple[float, float]:
    high = payload.get("high_threshold_raw", 0.0)
    critical = payload.get("critical_threshold_raw", 1.0)
    if not _is_number(high) or not (0.0 <= high <= 1.0):
        raise InvalidInput("high_threshold_raw must be a finite fraction in [0.0, 1.0]")
    if not _is_number(critical) or not (0.0 <= critical <= 1.0):
        raise InvalidInput("critical_threshold_raw must be a finite fraction in [0.0, 1.0]")
    return float(high), float(critical)


def _validate_weights(payload: dict[str, Any], domain_names: set[str]) -> dict[str, float]:
    weights_raw = payload.get("weights")
    if weights_raw is None:
        return {name: 1.0 for name in domain_names}
    if not isinstance(weights_raw, dict):
        raise InvalidInput("weights must be an object mapping domain -> weight")
    for name in weights_raw:
        if name not in domain_names:
            raise InvalidInput("weights key does not match any domain: " + str(name))
    weights: dict[str, float] = {}
    for name, value in weights_raw.items():
        if not _is_number(value) or value <= 0.0:
            raise InvalidInput("weight must be a finite number > 0 for domain: " + str(name))
        weights[name] = float(value)
    for name in domain_names:
        weights.setdefault(name, 1.0)
    return weights


def stress_load_report(payload: Any) -> dict[str, Any]:
    """Berechnet EINEN kumulativen Belastungsbericht aus Domaenen-Snapshots."""
    if not isinstance(payload, dict):
        return _not_reported("payload must be an object")
    try:
        high, critical = _validate_thresholds(payload)
    except InvalidInput as exc:
        return _not_reported("thresholds invalid: " + str(exc))

    domains_raw = payload.get("domains")
    if not isinstance(domains_raw, list) or not domains_raw:
        return _not_reported("domains must be a non-empty list")

    seen_names: set[str] = set()
    known: dict[str, tuple[float, str]] = {}
    unknown_domains: list[str] = []
    invalid_or_missing = 0
    violation = None

    for entry in domains_raw:
        if not isinstance(entry, dict):
            invalid_or_missing += 1
            continue
        name = entry.get("domain")
        basis = entry.get("basis")
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            invalid_or_missing += 1
            continue
        name = name.strip()
        if name in seen_names:
            violation = "duplicate domain name: " + name
            break
        seen_names.add(name)
        if basis == "UNKNOWN":
            if entry.get("load_raw") is not None:
                violation = "UNKNOWN basis must not carry a number: " + name
                break
            unknown_domains.append(name)
            continue
        if basis not in _KNOWN_BASES:
            invalid_or_missing += 1
            continue
        try:
            known[name] = (_validate_load(entry.get("load_raw")), str(basis))
        except InvalidInput as exc:
            violation = "invalid load for domain " + name + ": " + str(exc)
            break

    if violation is not None:
        return _not_reported(violation)
    if not known:
        return _not_reported("no known domain basis (all UNKNOWN or invalid)")

    try:
        weights = _validate_weights(payload, known.keys())
    except InvalidInput as exc:
        return _not_reported("weights invalid: " + str(exc))

    weight_sum = sum(weights[name] for name in known)
    weighted_load = sum(weights[name] * known[name][0] for name in known)
    index_raw = weighted_load / weight_sum

    co_stress = [
        {
            "domain": name,
            "load_raw": known[name][0],
            "basis": known[name][1],
        }
        for name in known
        if known[name][0] >= high
    ]

    total = len(domains_raw)
    known_count = len(known)
    state = INDEX_REPORTED
    if unknown_domains or invalid_or_missing:
        state = REPORTED_ON_INCOMPLETE_BASIS

    return {
        "state": state,
        "domains_total": total,
        "domains_known": known_count,
        "domains_unknown_excluded": unknown_domains,
        "domains_invalid_or_missing": invalid_or_missing,
        "known_domain_ratio_raw": known_count / total,
        "weights_are_caller_assumption": True,
        "weights": {name: weights[name] for name in known},
        "cumulative_index_raw": index_raw,
        "co_stress_boundary_raw": high,
        "co_stress_domains": co_stress,
        "co_occurrence_note": "CO_OCCURRENCE != SYNERGIE",
        "critical_boundary_raw": critical,
        "index_vs_critical": "AT_OR_ABOVE" if index_raw >= critical else "BELOW",
        "basis_breakdown": {
            "MEASURED": [n for n in known if known[n][1] == "MEASURED"],
            "CALCULATED": [n for n in known if known[n][1] == "CALCULATED"],
        },
        "honesty_limits": HONESTY_LIMITS,
    }


def _not_reported(reason: str) -> dict[str, Any]:
    return {
        "state": NOT_REPORTED,
        "reason": reason,
        "honesty_limits": HONESTY_LIMITS,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Cumulative stress load over domain snapshots (fail-closed)."
    )
    parser.add_argument("input", help="Pfad zu einer JSON-Payload-Datei")
    parser.add_argument("--output", default=None, help="Optionaler Ausgabepfad (JSON)")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps(_not_reported("unreadable input: " + str(exc)), indent=2))
        return 2

    report = stress_load_report(payload)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "
")
    print(text)
    if report["state"] == NOT_REPORTED:
        # Ungueltige Payload-Eingaben werden exit 2 gemeldet,
        # rueckgabe des Index-Typs mit fehlender Basis bleibt exit 1.
        if str(report.get("reason", "")).startswith("unreadable"):
            return 2
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
