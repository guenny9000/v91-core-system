#!/usr/bin/env python3
"""V99 main.py (Phase 2): ein kontrollierter Betriebszyklus, ehrlich begrenzt.

Bewusst KEIN endloser sleep()-Loop: 'ewiger Betrieb' ist eine Eigenschaft des
OS-Dienstes (Phase 6: systemd/launchd/Taskplaner), nicht einer while-Schleife.
Dieses Skript macht genau einen (oder --max-cycles) messbaren Zyklus und
endet mit einem definierten Exit-Code:
  0 = Zyklus abgeschlossen, kein FAILED
  1 = FAILED oder Fehler
  2 = EMERGENCY_STOPPED: Notaus-Flag gesetzt, kein Zyklus ausgefuehrt
"""
import argparse
import json
import os
import sys

from controller.autarky_report import build_report
from controller.autarky_metrics import AutarkyMetricError
from controller.emergency_stop import EmergencyStopFlagReader
from controller.measurement_core import MeasurementError
from v99.agent_shim import build_registry_from_config, run_once


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V99 Universal Autonomous Core (Phase 2)")
    parser.add_argument("--config-dir", default="v99/config",
                        help="Verzeichnis mit module.json-Dateien (nur echte, keine *.example.json)")
    parser.add_argument("--interval", type=int, default=900,
                        help="Pruefintervall in Sekunden (nur fuer Konfiguration, kein Loop)")
    parser.add_argument("--max-cycles", type=int, default=1,
                        help="Anzahl der Zyklen pro Aufruf (Standard: 1)")
    parser.add_argument("--stop-flag", default="ledger/v91_stop.flag",
                        help="Pfad des Notaus-Flags (Issue #70); fehlt es, laeuft der Zyklus")
    parser.add_argument("--autarky-ledger", default=None,
                        help="Mess-Ledger fuer den Autarkie-Report (Issue #83 Phase 2); ohne Pfad kein Report")
    parser.add_argument("--autarky-regional-config", default=None,
                        help="Optionale JSON-Konfiguration fuer den Regionalkreislauf-Indikator")
    parser.add_argument("--autarky-biodiversity-log", default=None,
                        help="Optionales Biodiversitaets-JSONL (nur lokale Sicht)")
    args = parser.parse_args(argv)

    stopped, stop_reason = EmergencyStopFlagReader(args.stop_flag).is_stopped()
    if stopped:
        print(json.dumps({"status": "EMERGENCY_STOPPED", "reason": stop_reason,
                          "stop_flag": args.stop_flag}))
        return 2

    if not os.path.isdir(args.config_dir):
        print(json.dumps({"error": f"Konfigurationsverzeichnis fehlt: {args.config_dir}",
                          "status": "FAILED"}))
        return 1

    try:
        registry = build_registry_from_config(args.config_dir)
        result = run_once(registry, max_cycles=args.max_cycles,
                          interval_seconds=args.interval)
        if args.autarky_ledger:
            # Fail-sichtbar, nicht fail-crash: ein Autarkie-Lesefehler darf den
            # Messzyklus nicht toeten, darf aber niemals als Erfolg durchgehen.
            try:
                result["autarky"] = build_report(
                    args.autarky_ledger,
                    regional_config_path=args.autarky_regional_config,
                    biodiversity_log_path=args.autarky_biodiversity_log,
                )
            except (MeasurementError, AutarkyMetricError, OSError, ValueError) as exc:
                result["autarky"] = {"status": "ERROR", "error": str(exc)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("aggregate") != "FAILED" else 1
    except Exception as exc:  # noqa: BLE001 – Fail-closed: Fehler beendet den Lauf
        print(json.dumps({"error": str(exc), "status": "FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
