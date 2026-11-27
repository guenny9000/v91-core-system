#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Audit-Ketten-Inspektor: Integritaetspruefung und Status-Auswertung
einer Sieben-Kriterien-audit_chain.jsonl (Betreiber-Baustein
27.11.2026, Auditblock V 2.4, Sieben-Kriterien-Kette).

Herkunft: eigenstaendiger Betreiber-Entwurf (reine Standardbibliothek,
ohne GitHub-Code), hier integriert NACH Fremdpruefung mit einem
echten Review-Befund: im Original wurde previous_digest_sha256 des
ERSTEN Eintrags nicht geprueft (Bedingung total > 1 uebersprang die
Zeile), sodass eine Kette, deren erster Eintrag einen beliebigen
Vorgaenger-Digest behauptete, als VALID_CHAIN durchging. Fix: der
erste Eintrag MUSS previous_digest_sha256 == GENESIS_HASH tragen;
der PowerShell-Startlauf des Betreibers schreibt genau das.
CHANGE != OWNERSHIP: Logikkern bleibt Betreiber-Werk, nur die
Genesis-Regel wurde nachgezogen und verriegelt (Tests).

Vertrag:
- GEMESSEN wird ausschliesslich die uebergebene JSONL-Datei; kein
  Netz, kein Schreiben, keine Code-Ausfuehrung (SCRIPTED != RUNNING).
- Eine korrupte Zeile macht die Kette CORRUPTED (fail-closed,
  UNKNOWN != PASS); Fehler werden je Zeile benannt, nicht geschoent.
- VALID_CHAIN ist ein INTEGRITAETS-Befund, KEINE inhaltliche Pruefung
  der sieben Kriterien (KETTE_INTAKT != KRITERIUM_ERFUELLT).

Ehrliche Grenzen:
- status_counts zaehlt SELBSTAUSKUNFTEN der Eintraege (Status ==
  Angabe != Nachweis).
- Eine leere, aber existierende Datei gilt als VALID_CHAIN mit
  total_records 0 (grenzwertig dokumentiert, kein Fehler).
- Kein Schutz gegen Neuordnung: das Umordnen vollstaendig neu
  verdrahteter Eintraege bleibt ausserhalb (KETTE != ZEITSTEMPEL).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

GENESIS_HASH = "GENESIS_000000000000000000000000000000000000000000000000000000000000"


@dataclass(frozen=True)
class AuditChainSummary:
    timestamp_utc: str
    chain_path: str
    status: str  # "MISSING_CHAIN", "VALID_CHAIN", "CORRUPTED_CHAIN"
    total_records: int
    status_counts: Dict[str, int]
    errors: List[str]
    digest_sha256: str


def _canonical_digest(entry: Dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "digest_sha256"}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _report_digest(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def inspect_audit_chain(chain_file: Path) -> AuditChainSummary:
    """Prueft Hash-Kette und Nutzdaten-Integritaet einer audit_chain.jsonl."""
    ts = datetime.now(timezone.utc).isoformat()
    path = Path(chain_file)

    if not path.exists() or not path.is_file():
        body: Dict[str, Any] = {
            "timestamp_utc": ts,
            "chain_path": str(path),
            "status": "MISSING_CHAIN",
            "total_records": 0,
            "status_counts": {},
            "errors": ["CHAIN_FILE_MISSING"],
        }
        return AuditChainSummary(**body, digest_sha256=_report_digest(body))

    errors: List[str] = []
    counts: Counter[str] = Counter()
    total = 0
    expected_prev = GENESIS_HASH

    with path.open("r", encoding="utf-8") as fh:
        for idx, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line_{idx}:JSON_DECODE_ERROR:{exc.msg}")
                continue
            if not isinstance(obj, dict):
                errors.append(f"line_{idx}:ENTRY_NOT_DICT")
                continue

            st = str(obj.get("status", "UNKNOWN")).strip() or "UNKNOWN"
            counts[st] += 1

            prev_val = str(obj.get("previous_digest_sha256", ""))
            # REVIEW-FIX 27.11.: ERSTER Eintrag muss von GENESIS ketten
            # (Original uebersprang Zeile 1; Details im Modulkopf).
            if prev_val != expected_prev:
                errors.append(f"line_{idx}:PREV_DIGEST_MISMATCH")

            digest_val = str(obj.get("digest_sha256", ""))
            recalc = _canonical_digest(obj)
            if not digest_val or recalc != digest_val:
                errors.append(f"line_{idx}:DIGEST_MISMATCH")

            expected_prev = digest_val or recalc

    status = "VALID_CHAIN" if not errors else "CORRUPTED_CHAIN"
    body = {
        "timestamp_utc": ts,
        "chain_path": str(path),
        "status": status,
        "total_records": total,
        "status_counts": dict(sorted(counts.items())),
        "errors": errors,
    }
    return AuditChainSummary(**body, digest_sha256=_report_digest(body))


if __name__ == "__main__":
    print(json.dumps(asdict(inspect_audit_chain(Path("audit_chain.jsonl"))), ensure_ascii=False, indent=2))
