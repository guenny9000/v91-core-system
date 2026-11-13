#!/usr/bin/env python3
"""Autarky report wiring (Issue #83 Phase 2).

Verbindet die Autarkie-Metriken (Phase 1) mit dem echten, hash-verketteten
Mess-Ledger aus controller/measurement_core.py. Ehrlichkeitsregeln:

- Nur gemessene Werte zaehlen: solar_w/grid_w werden nur uebernommen, wenn
  der Ledger-Eintrag status=DATA_AVAILABLE und einen nicht-negativen Zahlenwert
  enthaelt. Alles andere bleibt UNKNOWN und wird nie interpoliert.
- Der Ledger wird VOR dem Lesen vollstaendig verifiziert (fail-closed bei
  Korruption, Sequence-/Hash-Fehlern).
- Keine Netzaufrufe, keine Wirkung ueber den eigenen Rechner hinaus.
  WIRING != LAUFENDER DIENST: der Report wird nur gerechnet, wenn er
  aufgerufen wird (CLI oder main.py --autarky-ledger).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from controller.autarky_metrics import (
    AutarkyMetricError,
    BiodiversityLog,
    EnergyAutarky,
    RegionalLoopIndicator,
)
from controller.measurement_core import MeasurementError, verify_ledger


def load_measurement_records(ledger_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify the measurement ledger and extract solar_w/grid_w records.

    Returns (records, ledger_state). Records without measured solar/grid
    values are empty dicts and stay UNKNOWN in EnergyAutarky.
    """
    ledger = Path(ledger_path).expanduser().resolve()
    state = verify_ledger(ledger)
    records: list[dict[str, Any]] = []
    if state["status"] == "EMPTY_LEDGER":
        return records, state
    with ledger.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            snapshot = record.get("snapshot")
            host = snapshot.get("host_measurements") if isinstance(snapshot, dict) else None
            entry: dict[str, Any] = {}
            if isinstance(host, dict):
                for key in ("solar_w", "grid_w"):
                    metric_entry = host.get(key)
                    if not isinstance(metric_entry, dict):
                        continue
                    value = metric_entry.get("value")
                    if (metric_entry.get("status") == "DATA_AVAILABLE"
                            and isinstance(value, (int, float))
                            and not isinstance(value, bool)
                            and value >= 0):
                        entry[key] = float(value)
            records.append(entry)
    return records, state


def build_report(ledger_path: str | Path,
                 regional_config_path: str | Path | None = None,
                 biodiversity_log_path: str | Path | None = None) -> dict[str, Any]:
    records, ledger_state = load_measurement_records(ledger_path)
    report: dict[str, Any] = {
        "ledger": {
            "path": str(Path(ledger_path).expanduser().resolve()),
            "status": ledger_state["status"],
            "events": ledger_state["events"],
        },
        "energy_autarky": EnergyAutarky(records).compute(),
    }
    if regional_config_path is not None:
        config_path = Path(regional_config_path).expanduser().resolve()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise AutarkyMetricError("regional config must be a JSON object")
        report["regional_loop"] = RegionalLoopIndicator(config).compute()
    if biodiversity_log_path is not None:
        log = BiodiversityLog(biodiversity_log_path)
        report["biodiversity"] = {"chain_valid": log.verify_chain(), **log.totals()}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autarky report from the real measurement ledger (Issue #83 Phase 2)")
    parser.add_argument("--ledger", default="runtime/v91-measurements.jsonl",
                        help="Hash-verkettetes Mess-Ledger (controller/measurement_core.py)")
    parser.add_argument("--regional-config", default=None,
                        help="Optionale JSON-Konfiguration fuer den Regionalkreislauf-Indikator")
    parser.add_argument("--biodiversity-log", default=None,
                        help="Optionales Biodiversitaets-JSONL (nur lokale Sicht)")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.ledger, args.regional_config, args.biodiversity_log)
    except (MeasurementError, AutarkyMetricError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED_CLOSED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
