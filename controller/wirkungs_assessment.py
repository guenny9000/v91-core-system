"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Wirkungs-Assessment: R4-Schritt der Global Impact Engine (Modul-Schritt 6).
Bewertet EINE Pilot-Initiative anhand des validierten Messmatrix-Datasets
(R2, evaluate_messmatrix) und des SHA-256-verketteten Messwert-Ledgers
(R3, controller/messwerte_ingest.py). Vier Prueftore, alle fail-closed:
  GATE_1_DATASET:   Dataset via evaluate_messmatrix valide.
  GATE_2_LEDGER:    Ledger-Kette unveraendert (verify_chain).
  GATE_3_MATCH:     Jeder Ledger-Eintrag passt zur Initiative und
                    zu einem im Dataset definierten Indikator.
  GATE_4_EVIDENZ:   Jeder Eintrag traegt eine strukturell gueltige
                    Evidenz-Referenz und einen ISO-8601-Zeitstempel
                    innerhalb des Messfensters (baseline_at..target_at).
Erst wenn alle Tore offen sind, wird arithmetisch verglichen:
Fortschritt = (latest - baseline) / (target - baseline), begrenzt auf
[0, 1]; target_reached erst bei latest >= target. Ohne Messwerte oder
mit geschlossenem Tor bleibt der Indikator UNKNOWN (UNKNOWN != PASS).
WIRKUNG_BEOBACHTET ist niemals WIRKUNG_NACHGEWIESEN.
ZIELWERT != ERGEBNIS; ASSESSMENT != ENTSCHEIDUNG; MATRIZ != WIRKUNG.

Ehrliche Grenzen: das Assessment vergleicht Zahlen, es prueft nicht,
OB die Quelle wahr ist (SIGNATUR != WAHRHEIT); Kausalitaet bleibt
ungeprueft. Kein Netz, kein Abruf, keine Exekution.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):  # direkter CLI-Aufruf: Pfade erweitern
    _ROOT = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, _ROOT)
    from messwerte_ingest import (  # noqa: E402
        MesswerteIngestError,
        MesswertLedger,
        _valid_evidence_reference,
        load_dataset,
    )
else:
    from controller.messwerte_ingest import (  # noqa: E402
        MesswerteIngestError,
        MesswertLedger,
        _valid_evidence_reference,
        load_dataset,
    )

ASSESSMENT_VERSION = 1

GATES = (
    "GATE_1_DATASET",
    "GATE_2_LEDGER",
    "GATE_3_MATCH",
    "GATE_4_EVIDENZ",
)


class WirkungsAssessmentError(Exception):
    """Fail-closed Fehler des Wirkungs-Assessments."""


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _progress(latest: float, baseline: float, target: float) -> Optional[float]:
    """Arithmetischer Fortschritt, begrenzt auf [0, 1]; None wenn unbestimmt."""
    span = target - baseline
    if span == 0:
        return None
    fraction = (latest - baseline) / span
    if fraction < 0.0:
        return 0.0
    if fraction > 1.0:
        return 1.0
    return fraction


def assess(dataset_path: Path, ledger_path: Path,
           as_of: Optional[str] = None) -> Dict[str, Any]:
    """Bewertet eine Initiative aus Dataset und Ledger, fail-closed."""
    if not isinstance(dataset_path, Path) or not isinstance(ledger_path, Path):
        raise WirkungsAssessmentError("dataset_path and ledger_path must be Paths")
    cutoff = _parse_iso(as_of) if as_of else None
    gates: Dict[str, bool] = {gate: True for gate in GATES}
    closed_reasons: List[str] = []

    # Tor 1: Dataset valide (load_dataset fail-closed via evaluate_messmatrix).
    try:
        record = load_dataset(dataset_path)
    except MesswerteIngestError as error:
        gates["GATE_1_DATASET"] = False
        closed_reasons.append(f"dataset invalid: {error}")
        record = {}

    # Tor 2: Ledger-Kette unveraendert.
    ledger = MesswertLedger(ledger_path)
    try:
        chain_ok = ledger.verify_chain()
    except MesswerteIngestError as error:
        raise WirkungsAssessmentError(f"ledger not readable: {error}") from error
    if not chain_ok:
        gates["GATE_2_LEDGER"] = False
        closed_reasons.append("ledger chain broken")

    entries = ledger.entries()
    indicators = {entry.get("name"): entry
                  for entry in record.get("indicators", [])}
    initiative_id = record.get("initiative_id")

    # Tore 3 und 4: Eintraege muessen passen und belegt sein.
    observed: Dict[str, List[Dict[str, Any]]] = {name: [] for name in indicators}
    for entry in entries:
        if initiative_id is not None and entry.get("initiative_id") != initiative_id:
            gates["GATE_3_MATCH"] = False
            closed_reasons.append(
                f"initiative_id mismatch in seq {entry.get('seq')}")
            continue
        name = entry.get("indicator")
        if name not in indicators:
            gates["GATE_3_MATCH"] = False
            closed_reasons.append(f"unknown indicator: {name!r}")
            continue
        if not _valid_evidence_reference(entry.get("source")):
            gates["GATE_4_EVIDENZ"] = False
            closed_reasons.append(
                f"invalid evidence reference in seq {entry.get('seq')}")
            continue
        try:
            measured_at = _parse_iso(entry["measured_at"])
        except (KeyError, ValueError, TypeError):
            gates["GATE_4_EVIDENZ"] = False
            closed_reasons.append(
                f"missing/invalid measured_at in seq {entry.get('seq')}")
            continue
        period = indicators[name].get("period", {})
        if period:
            if measured_at < _parse_iso(period["baseline_at"]):
                gates["GATE_4_EVIDENZ"] = False
                closed_reasons.append(
                    f"measured_at before baseline_at in seq {entry.get('seq')}")
                continue
            if measured_at > _parse_iso(period["target_at"]):
                gates["GATE_4_EVIDENZ"] = False
                closed_reasons.append(
                    f"measured_at after target_at in seq {entry.get('seq')}")
                continue
        if cutoff is not None and measured_at > cutoff:
            continue  # Zukunftsluft: Messwert nach as_of zaehlt nicht
        observed[name].append(entry)

    all_open = all(gates.values())
    per_indicator: Dict[str, Dict[str, Any]] = {}
    for name, definition in indicators.items():
        rows = observed.get(name, [])
        if not all_open or not rows:
            status = "UNKNOWN"
            latest = None
            progress = None
            target_reached = False
        else:
            rows = sorted(rows, key=lambda item: _parse_iso(item["measured_at"]))
            latest = rows[-1]["value"]
            progress = _progress(
                float(latest), float(definition["baseline"]),
                float(definition["target"]))
            target_reached = float(latest) >= float(definition["target"])
            status = "ZIEL_ERREICHT" if target_reached else "WIRKUNG_BEOBACHTET"
            if definition.get("role") != "WIRKUNG" and not target_reached:
                status = "BEOBACHTET"
        per_indicator[name] = {
            "role": definition.get("role"),
            "unit": definition.get("unit"),
            "baseline": definition.get("baseline"),
            "target": definition.get("target"),
            "uncertainty": definition.get("uncertainty"),
            "measurement_count": len(rows),
            "latest": latest,
            "progress": progress,
            "target_reached": target_reached,
            "status": status,
        }

    wirkung_rows = [slot for slot in per_indicator.values()
                    if slot["role"] == "WIRKUNG"]
    if not all_open:
        overall = "UNBEWERTET_GESCHLOSSENES_TOR"
    elif wirkung_rows and all(slot["status"] != "UNKNOWN" for slot in wirkung_rows):
        overall = "WIRKUNG_BEOBACHTET"
    else:
        overall = "WIRKUNG_UNKNOWN"

    return {
        "assessment_version": ASSESSMENT_VERSION,
        "initiative_id": initiative_id,
        "watcher": record.get("watcher"),
        "maturity": record.get("maturity"),
        "as_of": as_of,
        "gates": gates,
        "all_gates_open": all_open,
        "closed_reasons": closed_reasons,
        "indicators": per_indicator,
        "wirkung_status": overall,
        "honest_limits": [
            "ZIELWERT != ERGEBNIS; target_reached ist Arithmetik, kein Wirkungsnachweis.",
            "WIRKUNG_BEOBACHTET ist niemals WIRKUNG_NACHGEWIESEN.",
            "Kausalitaet bleibt ungeprueft (SIGNATUR != WAHRHEIT).",
            "UNKNOWN != PASS; ohne Messwert bleibt der Indikator UNKNOWN.",
            "ASSESSMENT != ENTSCHEIDUNG; keine realen Interventionen ohne Freigabe.",
        ],
    }


def main(argv=None) -> int:
    """CLI: assess --dataset --ledger [--as-of]. Exit 0 ok, Exit 2 fail-closed."""
    parser = argparse.ArgumentParser(description="Wirkungs-Assessment (R4)")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--as-of", default=None,
                         help="ISO-8601; Messwerte danach zaehlen nicht")
    args = parser.parse_args(argv)
    try:
        result = assess(Path(args.dataset), Path(args.ledger), args.as_of)
    except (MesswerteIngestError, WirkungsAssessmentError, ValueError,
            OSError) as error:
        print(f"wirkungs-assessment: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2, sort_keys=True, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0 if result["all_gates_open"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
