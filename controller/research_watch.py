"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Forschungs-Beobachtungslog: Wissenschafts-/Forschungsbeobachtungs-
Wächter (11. Rolle der Direktiv, docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md).
Verzeichnet beobachtete Forschungs-Claims in einem SHA-256-verketteten
JSONL-Log, fail-closed bei Manipulation. Ein Claim ohne strukturell
gültige Evidenz-Referenz bleibt UNKNOWN - mit Evidenz ist er
BELEGT_EINSCHAETZUNG (nie "bestätigt"; lokale Prüfung ist keine
unabhängige Replikation). Kein Netz, kein Abruf, keine Bewertung
fremder Personen. LOG != BEURTEILUNG; BELEGT != VERIFIZIERT.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ResearchWatchError(Exception):
    """Fail-closed Fehler des Forschungs-Beobachtungslogs."""


def _valid_evidence_reference(ref: Any) -> bool:
    """Strukturelle Evidenz-Referenz-Prüfung: URL/DOI/Pfad/ledger-Id."""
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


class ResearchObservationLog:
    """Hash-verkettetes, append-only Beobachtungslog (JSONL)."""

    def __init__(self, path: Path):
        if not isinstance(path, Path):
            raise ResearchWatchError("path must be a Path")
        self._path = path
        self._prev_hash = ""
        if path.exists():
            entries = self._read_entries()
            if entries:
                self._prev_hash = entries[-1]["entry_hash"]

    # -- interne Kette -------------------------------------------------
    def _read_entries(self) -> List:
        if not self._path.exists():
            return []
        entries: List = []
        raw = self._path.read_text(encoding="utf-8")
        if raw.strip() and not raw.endswith("\n"):
            raise ResearchWatchError("corrupt log: unterminated last line")
        for number, line in enumerate(raw.splitlines(), start=1):
            if not line:
                raise ResearchWatchError(f"blank log line: {number}")
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ResearchWatchError(f"corrupt log line {number}: {exc}") from exc
            if not isinstance(entry, dict) or not isinstance(entry.get("entry_hash"), str):
                raise ResearchWatchError(f"corrupt log line {number}: missing entry_hash")
            entries.append(entry)
        return entries

    def verify_chain(self) -> bool:
        entries = self._read_entries()
        prev = ""
        for index, entry in enumerate(entries, start=1):
            if entry.get("seq") != index or entry.get("prev_hash") != prev:
                return False
            payload = {k: v for k, v in entry.items() if k not in ("entry_hash",)}
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                .encode("utf-8")
            ).hexdigest()
            if digest != entry.get("entry_hash"):
                return False
            prev = entry["entry_hash"]
        return True

    # -- oeffentliche API ------------------------------------------------
    def record_claim(
        self,
        claim: str,
        claim_kind: str,
        evidence_reference: Optional[str] = None,
        note: str = "",
        now: Optional[datetime] = None,
    ) -> Dict:
        """Verzeichnet EINE Forschungsbeobachtung; Manipulation verweigert Append."""
        if self._path.exists() and not self.verify_chain():
            raise ResearchWatchError("log chain invalid; append refused")
        if not isinstance(claim, str) or not claim.strip():
            raise ResearchWatchError("claim must be a non-empty string")
        if not isinstance(claim_kind, str) or not claim_kind.strip():
            raise ResearchWatchError("claim_kind must be a non-empty string")
        if evidence_reference is not None and not _valid_evidence_reference(evidence_reference):
            raise ResearchWatchError(
                "evidence_reference must be a structural URL/DOI/path/ledger reference or None"
            )
        if not isinstance(note, str):
            raise ResearchWatchError("note must be a string")
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        status = "BELEGT_EINSCHAETZUNG" if evidence_reference else "UNKNOWN"
        entries = self._read_entries()
        record: Dict = {
            "seq": len(entries) + 1,
            "recorded_at_utc": timestamp,
            "claim": claim.strip(),
            "claim_kind": claim_kind.strip(),
            "status": status,
            "evidence_reference": evidence_reference,
            "note": note,
        }
        record["prev_hash"] = self._prev_hash
        record["entry_hash"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            .encode("utf-8")
        ).hexdigest()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if self._path.exists() else "w"
        with open(self._path, mode, encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._prev_hash = record["entry_hash"]
        return record

    def list_entries(self) -> List:
        return list(self._read_entries())

    def open_claims(self) -> List:
        """Claims ohne Evidenz-Referenz (ehrliche UNKNOWN-Liste)."""
        return [e for e in self._read_entries() if e.get("status") == "UNKNOWN"]

    def verified(self) -> bool:
        return self.verify_chain()
