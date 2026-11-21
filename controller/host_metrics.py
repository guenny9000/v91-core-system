"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Read-only Host-Metriken-Adapter fuer SOLAR-DESKTOP-01 und jedes
andere Pilot-Geraet (tragfaehige Einzelidee aus dem geschlossenen
PR #3, hier als kleines, CI-geprueftes Modul umgesetzt; Issue #101
Teilschritt 'automatisches Auslesen'). Liest NUR, was die Python-
stdlib lokal ehrlich messen kann, und schreibt ausschliesslich ueber
den bestehenden PilotLog aus controller/mess_pilot.py (PR #216)
in das Rohprotokoll des Piloten (NO_DUPLICATE_SYSTEMS: kein zweites
Ledger, keine zweite Validierung).

Messquellen (bewusst explizit, nie geraten):
- cpu_load: 1-Minuten-Load-Average in Prozent der CPU-Anzahl via
  os.getloadavg (nur POSIX; auf Windows nicht messbar -> ehrlich
  UNKNOWN ohne Wert, UNKNOWN != PASS).
- disk_used: belegter Anteil des Zieldatentraegers in Prozent via
  shutil.disk_usage (plattformunabhaengig).

Nicht lesbare Groessen werden NICHT simuliert: Strom/Netz/Umgebung
(VB-ENERGIE-01 etc.) brauchen echte Zaehler-Hardware oder operatorseitige Erfassung; dieses Modul unternimmt dafuer nichts.

Ehrliche Grenzen: READING != SENSORWERT (getloadavg = Kernel-Schnitt-
stelle, kein Energiezaehler), SNAPSHOT != ZEITREIHE, SCRIPTED !=
INSTALLED (der automatische 15-Min-Takt gehoert dem OS-Timer, siehe
docs/V91-EWIGBETRIEB-INSTALLATION-OPERATOR.md, PR #272). Kein Netz, keine Fremdwirkung, keine Schreibrechte ausserhalb des genannten Rohprotokolls.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

if __package__ in (None, ""):  # direkter CLI-Aufruf: sys.path erweitern
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.mess_pilot import MessPilotError, PilotLog

VB_SYS_METRIC = "VB-SYS-01"  # percent, Range (0.0, 100.0), PR #216
SOURCES = ("cpu_load", "disk_used")


class HostMetricsError(Exception):
    """Fail-closed Fehler des Adapters; nie still verwerfen."""


def cpu_count() -> Optional[int]:
    """Konfigurierte CPU-Anzahl; None, wenn der Kernel nichts meldet."""
    try:
        return os.cpu_count()
    except (OSError, NotImplementedError):  # pragma: no cover
        return None


def cpu_load_percent(getloadavg=None) -> Optional[float]:
    """1-Minuten-Load-Average in Prozent der Kern-Anzahl.

    Gibt None zurueck, wenn die Plattform (Windows) getloadavg nicht
    anbietet oder der Kernel-Aufruf fehlschlaegt — dann bleibt der
    Messwert UNKNOWN, er wird nie geraten.
    """
    getter = getloadavg if getloadavg is not None else os.getloadavg
    cores = cpu_count()
    if not cores or cores < 1:
        return None
    try:
        load1 = float(getter()[0])
    except (NotImplementedError, OSError, ValueError, IndexError):
        return None
    if load1 < 0 or load1 != load1 or load1 == float("inf"):
        return None
    return load1 * 100.0 / cores


def disk_used_percent(target_path: str = "/", disk_usage=None) -> Optional[float]:
    """Belegter Anteil des Datentraegers unter target_path in Prozent."""
    usage_fn = disk_usage if disk_usage is not None else shutil.disk_usage
    try:
        usage = usage_fn(target_path)
    except (OSError, ValueError):
        return None
    total = float(usage.total)
    if total <= 0.0 or usage.used < 0 or usage.used > total:
        return None
    return float(usage.used) * 100.0 / total


def snapshot(target_path: str = "/",
             getloadavg=None, disk_usage=None) -> Dict[str, Any]:
    """Read-only Bestandsaufnahme; UNKNOWN bleibt UNKNOWN, nie 0."""
    cores = cpu_count()
    load = cpu_load_percent(getloadavg=getloadavg)
    disk_pct = disk_used_percent(target_path, disk_usage=disk_usage)
    disk_free = None
    try:
        usage = (disk_usage or shutil.disk_usage)(target_path)
        disk_free = usage.free
    except (OSError, ValueError):
        disk_free = None
    return {
        "schema_version": "1.0",
        "cpu_count": cores,
        "cpu_load_percent": load,
        "disk_target_path": str(target_path),
        "disk_used_percent": disk_pct,
        "disk_free_bytes": disk_free,
        "platform": sys.platform,
        "limits": "READING != SENSORWERT, SNAPSHOT != ZEITREIHE",
    }


def append_reading(log: PilotLog, source: str,
                    target_path: str = "/", getloadavg=None,
                    disk_usage=None,
                    timestamp_utc: Optional[str] = None) -> Dict[str, Any]:
    """Haengt EINE ehrliche Lesung an das Pilot-Rohprotokoll an.

    Messbarer Wert -> Status OK; nicht messbar -> Status UNKNOWN ohne
    Wert (UNKNOWN bleibt sichtbar, nie PASS). Validierung, Range und
    Hash-Kette uebernimmt ausschliesslich PilotLog (#216).
    """
    if source not in SOURCES:
        raise HostMetricsError(
            "unbekannte Quelle: %r (erlaubt: %s)"
            % (source, ", ".join(SOURCES)))
    value: Optional[float]
    if source == "cpu_load":
        value = cpu_load_percent(getloadavg=getloadavg)
    else:
        value = disk_used_percent(target_path, disk_usage=disk_usage)
    status = "OK" if value is not None else "UNKNOWN"
    try:
        return log.append(VB_SYS_METRIC, status, value,
                          unit="percent", timestamp_utc=timestamp_utc)
    except (MessPilotError, OSError) as exc:
        # Auch rohe OS-Fehler (z. B. unbeschreibbarer Pfad) werden
        # fail-closed als HostMetricsError gemeldet, nie verschluckt.
        raise HostMetricsError("PilotLog verweigert: %s" % exc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Host-Metriken-Adapter (Pilot Alsfeld/Vogelsberg)")
    parser.add_argument("--log", default=None,
                        help="Pfad des Pilot-Rohprotokolls (raw/...jsonl)")
    parser.add_argument("--source", choices=SOURCES, default=None)
    parser.add_argument("--target-path", default="/")
    parser.add_argument("--host", default="SOLAR-DESKTOP-01")
    parser.add_argument("--timestamp-utc", default=None)
    args = parser.parse_args(argv)

    if args.log is None and args.source is None:
        print(json.dumps(snapshot(args.target_path), sort_keys=True))
        return 0
    if args.log is None or args.source is None:
        print("HOSTMETRICS-ERROR: --log und --source sind zusammen Pflicht", file=sys.stderr)
        return 2
    try:
        log = PilotLog(Path(args.log), host_id=args.host)
        entry = append_reading(log, args.source,
                                target_path=args.target_path,
                                timestamp_utc=args.timestamp_utc)
    except (HostMetricsError, MessPilotError) as exc:
        print("HOSTMETRICS-ERROR: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(entry, sort_keys=True))
    return 1 if entry["status"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())
