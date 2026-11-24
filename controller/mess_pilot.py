"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Mess-Pilot Rohdaten-Writer: lokaler Pfad des Mess-Piloten
Alsfeld/Vogelsberg (Runbook docs/V91-MESS-PILOT-ALSFELD-VOGELSBURG-
RUNBOOK.md, gemergt als PR #214; Issue #101). Schreibt append-only
JSONL-Rohprotokolle (raw/) nach runbook-Abschnitt 3: je Eintrag seq
streng monoton, prev_hash -> entry_hash SHA-256-Kette, fsync. Misst
SELBST NICHTS (MESSUNG != DATASET): Werte kommen von außen, dieser
Writer prüft nur Struktur, Status-Wortschatz, Einheit und Range.
NO_DUPLICATE_SYSTEMS: die Aufnahme in die Wirkungs-Messwerte-Reihe
erfolgt ausschliesslich via controller/messwerte_ingest.py (#200)
gegen die validierte Pilot-F-Messmatrix (#215); dieses Modul ist die
getrennte lokale Rohdatenerfassung des Piloten. Fail-closed:
Schreib- und Kettenfehler werden nie stillschweigend verworfen.
SCRIPTED != INSTALLED: angebundene Sensoren sind Betreibersache;
nicht konfigurierte Messpunkte bleiben NOT_CONFIGURED, fehlende
Handshakes SENSOR_MISSING (UNKNOWN != PASS).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from controller.ledger_lock import exclusive_ledger_lock

if __package__ in (None, ""):  # direkter CLI-Aufruf: sys.path erweitern
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCHEMA_VERSION = "1.0"
PILOT_ID = "alsfeld-vogelsberg-issue-101"
MIN_FREE_BYTES = 1_048_576  # 1 MiB Platz_minimum Pre-Check

# Status-Wortschatz des Runbooks; bewusst keine freien Strings.
STATUSES = frozenset({
    "OK", "UNKNOWN", "ERROR", "DEGRADED", "OFFLINE",
    "NOT_CONFIGURED", "SENSOR_MISSING", "OUT_OF_RANGE",
})

# Misslingende Messwerte: kein Wert, kein Erfolg; Fehler offen.
STATUS_WITHOUT_VALUE = frozenset({
    "UNKNOWN", "ERROR", "DEGRADED", "OFFLINE",
    "NOT_CONFIGURED", "SENSOR_MISSING", "OUT_OF_RANGE",
})

# VB-Messpunkt-Definitionen (Runbook-Abschnitt 2). Range = logische
# Plausibilitaetsgrenze, kein Qualitaetsurteil; Werte ausserhalb werden
# als OUT_OF_RANGE gefuehrt, nie still korrigiert.
VB_METRICS: Dict[str, Dict[str, Any]] = {
    "VB-ENERGIE-01": {"unit": "kW", "kind": "float",
                      "range": (0.0, 100_000.0)},
    "VB-NETZ-01": {"unit": "ms", "kind": "float",
                   "range": (0.0, 60_000.0)},
    "VB-SYS-01": {"unit": "percent", "kind": "float",
                  "range": (0.0, 100.0)},
    "VB-UMWELT-01": {"unit": "degC", "kind": "float",
                     "range": (-60.0, 100.0)},
}


class MessPilotError(Exception):
    """Fail-closed Fehler des Pilot-Writers; nie still verwerfen."""


def _canonical(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _entry_hash(entry: Dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical(entry).encode("utf-8")).hexdigest()


def validate_reading(metric_id: str, status: str, value: Any,
                     unit: Optional[str]) -> Tuple[str, Any]:
    """Prueft Messpunkt, Status, Einheit, Wert und Range.

    Laesst den Wert unveraendert durch, wenn alle Pruefungen
    bestehen; wirft MessPilotError fail-closed. OUT_OF_RANGE wird NICHT

    geworfen, sondern als Status zurueckgegeben (Wert bleibt sichtbar)."""

    if metric_id not in VB_METRICS:
        raise MessPilotError(
            "unbekannter Messpunkt: %r (erlaubt: %s)"
            % (metric_id, ", ".join(sorted(VB_METRICS))))
    if status not in STATUSES:
        raise MessPilotError(
            "unbekannter Status: %r (erlaubt: %s)"
            % (status, ", ".join(sorted(STATUSES))))
    spec = VB_METRICS[metric_id]
    if unit is not None and unit != spec["unit"]:
        raise MessPilotError(
            "Einheit %r passt nicht zu %s (%s)"
            % (unit, metric_id, spec["unit"]))
    if status in STATUS_WITHOUT_VALUE and value is not None:
        raise MessPilotError(
            "Status %s trägt KEINEN Wert (UNKNOWN != PASS)" % status)
    if value is not None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MessPilotError("Wert muss Zahl sein, nicht %r" % (value,))
        lo, hi = spec["range"]
        if not (lo <= value <= hi):
            return "OUT_OF_RANGE", value
    return status, value


@contextmanager
def _exclusive_log_lock(log_path: Path) -> Iterator[None]:
    """Prozessuebergreifender Schreibschutz fuer EINE Log-Datei.

    Muster-Heimat seit PR #517 (hier reproduzierte TOCTOU-Race);
    der Baustein wurde als controller/ledger_lock.py gehoben und
    diese Stelle DELEGIERT seither (REUSE != COPY, keine zweite
    Lock-Implementierung im System [NO_DUPLICATE_SYSTEMS]).
    """
    with exclusive_ledger_lock(log_path):
        yield


class PilotLog:
    """Append-only Rohprotokoll mit SHA-256-Kette und seq-Zaehler."""

    def __init__(self, path: Path, host_id: str = "local-node-01",
                 pilot_id: str = PILOT_ID) -> None:
        self.path = Path(path)
        self.host_id = host_id
        self.pilot_id = pilot_id

    # -- Pre-Check -----------------------------------------------------
    def precheck(self) -> None:
        d = self.path.parent
        d.mkdir(parents=True, exist_ok=True)
        if not os.access(d, os.W_OK):
            raise MessPilotError("Verzeichnis nicht beschreibbar: %s" % d)
        free = shutil.disk_usage(d).free
        if free < MIN_FREE_BYTES:
            raise MessPilotError(
                "zu wenig Speicher: %d frei (< %d)" % (free, MIN_FREE_BYTES))

    # -- Kettenzustand ---------------------------------------------------
    def _read_last(self) -> Tuple[int, str, Optional[List[str]]]:
        """Liefert (seq, prev_entry_hash, korrupte_endzeilen_ggf).

        Eine unvollstaendige/korrupte LETZTE Zeile (Absturz beim Schreiben,
        abgeschnittener Datentraeger) ist kein gueltiger Datensatz. Sie
        wird zurueckgegeben und beim naechsten append entfernt (Runbook 4:
        Bruch markieren statt still weiterketten), statt das Protokoll
        dauerhaft unlesbar zu machen.
        """
        if not self.path.is_file():
            return 0, "sha256:" + "0" * 64, None
        lines = [ln for ln in self.path.read_text(
            encoding="utf-8").split("\n") if ln.strip()]
        if not lines:
            return 0, "sha256:" + "0" * 64, None
        try:
            last = json.loads(lines[-1])
            return int(last["seq"]), last["entry_hash"], None
        except (ValueError, KeyError, TypeError):
            # Gueltigen Vorgaenger suchen, Rest ist korrupter Schwanz.
            keep: List[str] = []
            prev_seq, prev_hash = 0, "sha256:" + "0" * 64
            for ln in lines:
                try:
                    cand = json.loads(ln)
                    prev_seq = int(cand["seq"])
                    prev_hash = cand["entry_hash"]
                    keep.append(ln)
                except (ValueError, KeyError, TypeError):
                    break
            return prev_seq, prev_hash, keep

    # -- Schreiben -------------------------------------------------------
    def append(self, metric_id: str, status: str, value: Any = None,
               unit: Optional[str] = None, timestamp_utc: Optional[str] = None,
               error_code: Optional[str] = None) -> Dict[str, Any]:
        with _exclusive_log_lock(self.path):
            return self._append_locked(metric_id, status, value, unit,
                                       timestamp_utc, error_code)

    def _append_locked(self, metric_id: str, status: str, value: Any = None,
                       unit: Optional[str] = None,
                       timestamp_utc: Optional[str] = None,
                       error_code: Optional[str] = None) -> Dict[str, Any]:
        status_out, value_out = validate_reading(metric_id, status, value, unit)
        self.precheck()
        seq, prev_hash, chain_broken = self._read_last()
        entry: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "pilot_id": self.pilot_id,
            "seq": seq + 1,
            "timestamp_utc": timestamp_utc,
            "host_id": self.host_id,
            "metric_id": metric_id,
            "status": status_out,
            "value": value_out,
            "unit": unit,
            "prev_hash": prev_hash,
        }
        if error_code is not None:
            entry["error_code"] = error_code
        if chain_broken:
            # Runbook 4: Bruch offen markieren, nie still weiterketten.
            # Korrupte Restzeilen werden entfernt (kein gueltiger Datensatz),
            # die Markierung macht den Bruch sichtbar und pruefbar.
            entry["chain_break_detected"] = True
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(chain_broken) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        entry["entry_hash"] = _entry_hash(entry)
        line = _canonical(entry) + "\n"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        # Post-Check: Zeile komplett mit Newline, Hash reproduzierbar.
        raw = self.path.read_text(encoding="utf-8")
        if not raw.endswith("\n"):
            raise MessPilotError(
                "Post-Check: letzte Zeile ohne Abschluss-Newline")
        last_line = [ln for ln in raw.split("\n") if ln.strip()][-1]
        reread = json.loads(last_line)
        if reread["entry_hash"] != entry["entry_hash"] \
                or _entry_hash({k: v for k, v in reread.items()
                                if k != "entry_hash"}) != entry["entry_hash"]:
            raise MessPilotError(
                "Post-Check: entry_hash nicht reproduzierbar")
        return entry


def verify(path: Path) -> Dict[str, Any]:
    """Praeft eine Protokolldatei: Kette, seq, Schema. Kein Beweis."""
    path = Path(path)
    result: Dict[str, Any] = {
        "file": str(path), "entries": 0, "chain_ok": True, "seq_ok": True,
        "schema_ok": True, "statuses": {}, "chain_breaks": 0, "ok": True,
    }
    if not path.is_file():
        result.update(ok=False, error="Datei fehlt")
        return result
    prev_hash = "sha256:" + "0" * 64
    expected_seq = 1
    for ln in [l for l in path.read_text(encoding="utf-8").split("\n")
               if l.strip()]:
        result["entries"] += 1
        try:
            entry = json.loads(ln)
        except ValueError:
            result.update(ok=False, schema_ok=False,
                          error="korrupte JSON-Zeile seq_Ordnung=%d"
                          % result["entries"])
            return result
        for key in ("schema_version", "pilot_id", "seq", "timestamp_utc",
                    "host_id", "metric_id", "status", "prev_hash",
                    "entry_hash"):
            if key not in entry:
                result.update(ok=False, schema_ok=False,
                              error="Feld fehlt: %s" % key)
                return result
        if entry["status"] not in STATUSES:
            result.update(ok=False, schema_ok=False,
                          error="unbekannter Status: %r" % entry["status"])
            return result
        recomputed = _entry_hash({k: v for k, v in entry.items()
                                  if k != "entry_hash"})
        if recomputed != entry["entry_hash"]:
            result.update(ok=False, chain_ok=False,
                          error="Hash-Kette bricht bei seq %s" % entry["seq"])
            return result
        if entry.get("chain_break_detected"):
            result["chain_breaks"] += 1
        elif entry["prev_hash"] != prev_hash:
            result.update(ok=False, chain_ok=False,
                          error="prev_hash falsch bei seq %s" % entry["seq"])
            return result
        if entry["seq"] != expected_seq:
            result.update(ok=False, seq_ok=False,
                          error="seq nicht monoton: %s (erwartet %d)"
                          % (entry["seq"], expected_seq))
            return result
        prev_hash = entry["entry_hash"]
        expected_seq += 1
        result["statuses"][entry["status"]] = (
            result["statuses"].get(entry["status"], 0) + 1)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mess-Pilot Rohdaten-Writer (Alsfeld/Vogelsberg)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_append = sub.add_parser("append", help="Einen Rohdaten-Eintrag anhaengen")
    p_append.add_argument("--log", required=True)
    p_append.add_argument("--host", default="local-node-01")
    p_append.add_argument("--metric", required=True)
    p_append.add_argument("--status", required=True)
    p_append.add_argument("--value", default=None)
    p_append.add_argument("--unit", default=None)
    p_append.add_argument("--timestamp-utc", default=None)
    p_verify = sub.add_parser("verify", help="Protokoll pruefen (Exit 0/2)")
    p_verify.add_argument("--log", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "verify":
        outcome = verify(Path(args.log))
        print(json.dumps(outcome, sort_keys=True))
        return 0 if outcome["ok"] else 2
    value = None
    if args.value is not None:
        try:
            value = float(args.value)
        except ValueError:
            print("MESSPILOT-ERROR: --value muss Zahl sein", file=sys.stderr)
            return 2
    try:
        log = PilotLog(Path(args.log), host_id=args.host)
        entry = log.append(args.metric, args.status, value,
                           unit=args.unit,
                           timestamp_utc=args.timestamp_utc)
    except MessPilotError as exc:
        print("MESSPILOT-ERROR: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
