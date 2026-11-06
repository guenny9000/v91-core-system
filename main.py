#!/usr/bin/env python3
"""V99 main.py (Phase 2): ein kontrollierter Betriebszyklus, ehrlich begrenzt.

Bewusst KEIN endloser sleep()-Loop: 'ewiger Betrieb' ist eine Eigenschaft des
OS-Dienstes (Phase 6: systemd/launchd/Taskplaner), nicht einer while-Schleife.
Dieses Skript macht genau einen (oder --max-cycles) messbaren Zyklus und
endet mit einem definierten Exit-Code:
  0 = Zyklus abgeschlossen, kein FAILED
  1 = FAILED oder Fehler
"""
import argparse
import json
import os
import sys

from v99.agent_shim import build_registry_from_config, run_once


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V99 Universal Autonomous Core (Phase 2)")
    parser.add_argument("--config-dir", default="v99/config",
                        help="Verzeichnis mit module.json-Dateien (nur echte, keine *.example.json)")
    parser.add_argument("--interval", type=int, default=900,
                        help="Pruefintervall in Sekunden (nur fuer Konfiguration, kein Loop)")
    parser.add_argument("--max-cycles", type=int, default=1,
                        help="Anzahl der Zyklen pro Aufruf (Standard: 1)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.config_dir):
        print(json.dumps({"error": f"Konfigurationsverzeichnis fehlt: {args.config_dir}",
                          "status": "FAILED"}))
        return 1

    try:
        registry = build_registry_from_config(args.config_dir)
        result = run_once(registry, max_cycles=args.max_cycles,
                          interval_seconds=args.interval)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("aggregate") != "FAILED" else 1
    except Exception as exc:  # noqa: BLE001 – Fail-closed: Fehler beendet den Lauf
        print(json.dumps({"error": str(exc), "status": "FAILED"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
