"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Messwerte-Ingest: R3-Schritt der Global Impact Engine (Modul-Schritt 5).
Nimmt EINZELNE Messwerte gegen einen Indikator einer validierten
Messmatrix (docs/messmatrix, evaluate_messmatrix) auf, in ein
SHA-256-verkettetes, append-only JSONL-Ledger (Muster wie
controller/research_watch.py). Fail-closed: ungültiges Dataset,
falsche initiative_id, unbekannter Indikator, fehlende oder
strukturungültige Evidenz-Referenz (source) oder Manipulation am
Ledger verweigern den Eintrag. Keine Bewertung: ein Messwert ist
OBSERVED, nie ein Wirkungsnachweis; fehlende Messwerte bleiben
UNKNOWN (UNKNOWN != PASS).
MESSWERT != WIRKUNGNACHWEIS; LEDGER != BEURTEILUNG; ZIELWERT != ERGEBNIS.

Ehrliche Grenzen: das Ledger prüft Quelle und Zahl strukturell, nicht
inhaltlich (SIGNATUR != WAHRHEIT). Kein Netz, kein Abruf, keine
Exekution; recorded_status ist keine Zustimmung zu irgendwas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):  # direkter CLI-Aufruf: sys.path erweitern
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v91_impact_metrics.metrics import evaluate_messmatrix

LEDGER_VERSION = 1


class MesswerteIngestError(Exception):
    """Fail-closed Fehler des Messwerte-Ingest."""


def _valid_evidence_reference(ref: Any) -> bool:
    """Strukturelle Evidenz-Referenz-Pruefung: URL/DOI/Pfad/ledger-Id."""
    if not isinstance(ref, str) or not ref.strip():
        return False
    ref = ref.strip()
    return (
        ref.startswith("https://")
        or ref.startswith("http://")
        or ref.startswith("doi:")
        or ref.startswith("/")
        or ref.startswith("ledger::")
    )


def _parse_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MesswerteIngestError(f"{field} must be an ISO-8601 timestamp string")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise MesswerteIngestError(f"{field} is not ISO-8601: {value}") from error
    return text


def load_dataset(dataset_path: Path) -> Dict[str, Any]:
    """Laedt und validiert eine Messmatrix-Datei (fail-closed)."""
    if not isinstance(dataset_path, Path):
        raise MesswerteIngestError("dataset_path must be a Path")
    try:
        with dataset_path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as error:
        raise MesswerteIngestError(f"dataset not readable: {error}") from error
    try:
        evaluate_messmatrix(record)
    except (ValueError, TypeError, KeyError) as error:
        raise MesswerteIngestError(f"dataset invalid: {error}") from error
    return record


def _find_indicator(record: Dict[str, Any], indicator: str) -> Dict[str, Any]:
    for entry in record.get("indicators", []):
        if entry.get("name") == indicator:
            return entry
    raise MesswerteIngestError(f"indicator not found in dataset: {indicator}")


class MesswertLedger:
    """Hash-verkettetes, append-only Messwert-Ledger (JSONL)."""

    def __init__(self, path: Path):
        if not isinstance(path, Path):
            raise MesswerteIngestError("path must be a Path")
        self._path = path
        self._prev_hash = ""
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                lines = [line for line in handle if line.strip()]
        except OSError as error:
            raise MesswerteIngestError(f"ledger not readable: {error}") from error
        try:
            self._entries = [json.loads(line) for line in lines]
        except ValueError as error:
            raise MesswerteIngestError(f"ledger line not JSON: {error}") from error
        if self._entries:
            self._prev_hash = self._entries[-1]["entry_hash"]

    def _append_line(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def verify_chain(self) -> bool:
        prev = ""
        for index, entry in enumerate(self._entries, start=1):
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            digest = hashlib.sha256(
                json.dumps({k: v for k, v in entry.items()
                            if k not in ("entry_hash",)},
                           sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if entry.get("entry_hash") != digest:
                return False
            prev = entry["entry_hash"]
        return True

    def entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def append(self, payload: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        """Haengt einen Messwert an; alle Pruefungen fail-closed."""
        if not isinstance(payload, dict):
            raise MesswerteIngestError("payload must be an object")
        if not self.verify_chain():
            raise MesswerteIngestError("ledger chain broken, refusing append")
        initiative_id = payload.get("initiative_id")
        if initiative_id != record.get("initiative_id"):
            raise MesswerteIngestError(
                f"initiative_id mismatch: {initiative_id!r} != "
                f"{record.get('initiative_id')!r}")
        indicator = payload.get("indicator")
        if not isinstance(indicator, str) or not indicator.strip():
            raise MesswerteIngestError("indicator must be a non-empty string")
        definition = _find_indicator(record, indicator)
        value = payload.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MesswerteIngestError("value must be a number (no booleans)")
        if value < 0:
            raise MesswerteIngestError("value must be non-negative")
        _parse_timestamp(payload.get("measured_at"), "measured_at")
        source = payload.get("source")
        if not _valid_evidence_reference(source):
            raise MesswerteIngestError(
                "source must be a structural evidence reference "
                "(https://, http://, doi:, /path, ledger::)")
        note = payload.get("note")
        if note is not None and not isinstance(note, str):
            raise MesswerteIngestError("note must be a string when given")
        measured_by = payload.get("measured_by")
        if measured_by is not None and not isinstance(measured_by, str):
            raise MesswerteIngestError("measured_by must be a string when given")

        entry: Dict[str, Any] = {
            "ledger_version": LEDGER_VERSION,
            "seq": len(self._entries) + 1,
            "initiative_id": initiative_id,
            "indicator": indicator,
            "role": definition["role"],
            "unit": definition["unit"],
            "value": value,
            "measured_at": payload["measured_at"],
            "source": source.strip(),
            "note": note,
            "measured_by": measured_by,
            "target": definition["target"],
            "recorded_status": "OBSERVED",
        }
        entry["prev_hash"] = self._prev_hash
        entry["entry_hash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self._append_line(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        self._entries.append(entry)
        self._prev_hash = entry["entry_hash"]
        return entry

    def report(self, record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Maschinenlesbarer Report: Messwerte je Indikator, keine Bewertung."""
        if not self.verify_chain():
            raise MesswerteIngestError("ledger chain broken")
        per_indicator: Dict[str, Dict[str, Any]] = {}
        for definition in (record or {}).get("indicators", []):
            per_indicator[definition["name"]] = {
                "role": definition["role"],
                "unit": definition["unit"],
                "target": definition["target"],
                "values": [],
                "measurement_count": 0,
                "latest": None,
                "status": "UNKNOWN",
            }
        for entry in self._entries:
            name = entry["indicator"]
            slot = per_indicator.setdefault(name, {
                "role": entry.get("role"), "unit": entry.get("unit"),
                "target": entry.get("target"), "values": [],
                "measurement_count": 0, "latest": None, "status": "UNKNOWN"})
            slot["values"].append(entry["value"])
            slot["measurement_count"] += 1
            slot["latest"] = entry["value"]
            slot["status"] = "OBSERVED"
        return {
            "ledger_version": LEDGER_VERSION,
            "entries_total": len(self._entries),
            "initiative_id": (record or {}).get("initiative_id"),
            "indicators": per_indicator,
            "honest_limits": [
                "MESSWERT != WIRKUNGNACHWEIS; ein Messwert ist eine Beobachtung.",
                "LEDGER != BEURTEILUNG; dieser Report vergleicht nicht mit dem Ziel.",
                "UNKNOWN bleibt UNKNOWN; ohne Messwert bleibt der Indikator UNKNOWN.",
            ],
        }


def main(argv=None) -> int:
    """CLI: append/verify/report. Exit 0 ok, Exit 2 fail-closed."""
    parser = argparse.ArgumentParser(description="Messwerte ingest (R3)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_append = sub.add_parser("append")
    p_append.add_argument("--dataset", required=True)
    p_append.add_argument("--ledger", required=True)
    p_append.add_argument("--payload", required=True,
                          help="JSON object string")
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--ledger", required=True)
    p_report = sub.add_parser("report")
    p_report.add_argument("--dataset", required=True)
    p_report.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)
    try:
        ledger = MesswertLedger(Path(args.ledger))
        if args.command == "verify":
            if not ledger.verify_chain():
                print("messwerte-ingest: chain broken", file=sys.stderr)
                return 2
            print(json.dumps({"chain_verified": True,
                              "entries_total": len(ledger.entries())}))
            return 0
        dataset = load_dataset(Path(args.dataset))
        if args.command == "append":
            try:
                payload = json.loads(args.payload)
            except ValueError as error:
                raise MesswerteIngestError(f"payload not JSON: {error}") from error
            entry = ledger.append(payload, dataset)
            print(json.dumps({"seq": entry["seq"],
                              "entry_hash": entry["entry_hash"]}))
            return 0
        if args.command == "report":
            print(json.dumps(ledger.report(dataset), indent=2,
                             ensure_ascii=False, sort_keys=True))
            return 0
    except MesswerteIngestError as error:
        print(f"messwerte-ingest error: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
