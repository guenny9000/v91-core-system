"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Contribution-Review-Journal (Issue #492, Stufe-6-Rest): reines
Erfassungs- und Rueckmeldungswerkzeug fuer den PRUEF-PROZESS eines
V91-CONTRIBUTION-1-Umschlags. Die Bestandsaufnahme #582 verzeichnete
die Luecke ehrlich: Statuskala validierbar, Ablauf dokumentiert, aber
kein Ablageort je Beitrag fuer Annahme-/Ablehnungsgruende und kein
Werkzeug fuer die Rueckmeldung (PROZESS_BEIM_BETREIBER).

Regeln (fail-closed):
- Der Umschlag MUSS controller.contribution_intake.validate_contribution
  bestehen (REUSE, Einzelne Wahrheit; INTAKE != VALIDIERUNG bleibt).
- Der Review-Chain beginnt IMMER bei RECEIVED; der im Umschlag
  behauptete Status wird NICHT uebernommen (CLAIM != EVIDENCE).
- Zulaessige Uebergaenge sind fest verriegelt (TRANSITIONS);
  REJECTED und INTEGRATED sind Endzustaende.
- Kein Eintrag ohne nicht-leere Begruendung.
- Keine Selbstfreigabe: reviewer-Angabe darf nicht der Herkunft
  des Beitrags entsprechen (Stufe-6-Forderung). Ehrlichkeitsgrenze:
  REVIEWER_ANGABE != IDENTITAET, das Feld ist eine Angabe.
- Journal append-only unter exklusivem Ledger-Lock (REUSE #529);
  jede Zeile wird beim Laden neu verifiziert, EINE korrupte Zeile
  stoppt den Lauf (JOURNAL_INTEGRITAET != HOFFNUNG).
- Jeder Eintrag traegt rights=NOT_GRANTED und execution=NOT_PERFORMED:
  JOURNAL != FREIGABE, RECORD != BERECHTIGUNG, kein Vollzug.
- envelope_digest (SHA-256 ueber kanonisches JSON) bindet den Eintrag
  an den GEPRUEFTEN Inhalt; veraendert sich der Umschlag, weicht der
  Digest im naechsten Eintrag ab (sichtbar, nicht blockierend).

Grenzen: das Journal ist Dokumentation des Pruefprozesses, kein
Beweis dafuer, dass geprueft wurde, was begruendet wurde. Zeitstempel
sind Angaben (Default: jetzt UTC, injizierbar fuer Determinismus).
Kein Netz, keine Ausfuehrung, keine Rechte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    # Skript-Modus: #460/#605-Schatten reparieren (controller/controller.py
    # verdraengt sonst das Namespace-Paket). Nur hier, niemals beim Import.
    sys.path[:] = [
        p for p in sys.path
        if os.path.abspath(p if p else os.getcwd()) != _HERE
    ]
    sys.path.insert(0, os.path.dirname(_HERE))

from controller import contribution_intake  # noqa: E402
from controller.ledger_lock import exclusive_ledger_lock  # noqa: E402

JOURNAL_PROTOCOL = "V91-CONTRIBUTION-REVIEW-1"
MAX_REASON_CHARS = 4096

CONTRIBUTION_STATUSES = contribution_intake.CONTRIBUTION_STATUSES

TRANSITIONS: dict[str, frozenset[str]] = {
    "RECEIVED": frozenset({"TRIAGED", "REJECTED", "DEFERRED"}),
    "TRIAGED": frozenset({"TESTING", "REJECTED", "DEFERRED"}),
    "TESTING": frozenset({"ACCEPTED", "REJECTED", "DEFERRED"}),
    "ACCEPTED": frozenset({"INTEGRATED", "REJECTED"}),
    "DEFERRED": frozenset({"TESTING", "REJECTED"}),
    "REJECTED": frozenset(),
    "INTEGRATED": frozenset(),
}

ENTRY_KEYS = frozenset({
    "protocol", "contribution_id", "from_status", "to_status",
    "reviewer", "reason", "recorded_at", "envelope_digest",
    "rights", "execution",
})


class ReviewBlockedError(RuntimeError):
    """Ein Eintrag wurde regelkonform verweigert (fail-closed)."""


class JournalIntegrityError(RuntimeError):
    """Das Journal ist korrupt oder kettenwidrig; Append verweigert."""


def canonical_digest(payload: Any) -> str:
    """SHA-256 ueber kanonisches JSON (gleiche Serialisierung wie der Validator)."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check_timestamp(value: str) -> str | None:
    """None bei gueltigem ISO-8601-Zeitstempel MIT Zeitzone, sonst Fehlertext."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "recorded_at: must be an ISO-8601 timestamp"
    if parsed.tzinfo is None:
        return "recorded_at: timezone is required"
    return None


def _check_entry(raw: str, line_no: int) -> dict[str, Any]:
    """Eine Journal-Zeile verifizieren; bei Verstoss JournalIntegrityError."""
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JournalIntegrityError(
            f"journal line {line_no}: not valid JSON ({exc})"
        ) from exc
    if not isinstance(entry, dict):
        raise JournalIntegrityError(f"journal line {line_no}: not an object")
    missing = sorted(ENTRY_KEYS - set(entry))
    unknown = sorted(str(k) for k in set(entry) - ENTRY_KEYS)
    if missing or unknown:
        raise JournalIntegrityError(
            f"journal line {line_no}: fields missing={missing} unknown={unknown}"
        )
    if entry["protocol"] != JOURNAL_PROTOCOL:
        raise JournalIntegrityError(
            f"journal line {line_no}: wrong protocol {entry['protocol']!r}"
        )
    for key in ("contribution_id", "reviewer", "reason", "recorded_at"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise JournalIntegrityError(
                f"journal line {line_no}: {key} must be a non-empty string"
            )
    for key in ("from_status", "to_status"):
        if entry[key] not in CONTRIBUTION_STATUSES:
            raise JournalIntegrityError(
                f"journal line {line_no}: {key}={entry[key]!r} outside scale"
            )
    error = _check_timestamp(entry["recorded_at"])
    if error:
        raise JournalIntegrityError(f"journal line {line_no}: {error}")
    return entry


def load_journal(journal_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Journal laden und je Beitrag die Review-Kette verifizieren.

    Rueckgabe: contribution_id -> Liste der Eintraege in Append-Reihenfolge.
    Fail-closed: EINE ungueltige Zeile macht den ganzen Lauf ungueltig.
    """
    chains: dict[str, list[dict[str, Any]]] = {}
    if not journal_path.exists():
        return chains
    with journal_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            entry = _check_entry(raw, line_no)
            chain = chains.setdefault(entry["contribution_id"], [])
            expected_from = chain[-1]["to_status"] if chain else "RECEIVED"
            if entry["from_status"] != expected_from:
                raise JournalIntegrityError(
                    f"journal line {line_no}: chain break, expected"
                    f" from_status={expected_from!r}, got"
                    f" {entry['from_status']!r}"
                )
            if entry["to_status"] not in TRANSITIONS[entry["from_status"]]:
                raise JournalIntegrityError(
                    f"journal line {line_no}: transition"
                    f" {entry['from_status']!r} ->"
                    f" {entry['to_status']!r} is not allowed"
                )
            chain.append(entry)
    return chains


def record_review(
    envelope: Any,
    journal_path: Path,
    to_status: str,
    reason: str,
    reviewer: str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Einen Review-Schritt aufzeichnen. Kein Vollzug, keine Rechte."""
    valid, errors = contribution_intake.validate_contribution(envelope)
    if not valid:
        raise ReviewBlockedError(
            "envelope rejected: " + "; ".join(errors[:8])
            + (" ..." if len(errors) > 8 else "")
        )
    if not isinstance(to_status, str) or to_status not in CONTRIBUTION_STATUSES:
        raise ReviewBlockedError(f"to_status={to_status!r} outside scale")
    if not isinstance(reason, str) or not reason.strip():
        raise ReviewBlockedError("reason: must be a non-empty string")
    if len(reason) > MAX_REASON_CHARS:
        raise ReviewBlockedError(f"reason: exceeds {MAX_REASON_CHARS} characters")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewBlockedError("reviewer: must be a non-empty string")
    origin_name = str(
        (envelope.get("origin") or {}).get("model_or_person", "")
    ).strip()
    if origin_name and reviewer.strip().lower() == origin_name.lower():
        raise ReviewBlockedError(
            "self-approval forbidden: reviewer matches origin.model_or_person"
            " (Stufe 6, keine Selbstfreigabe)"
        )
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc).isoformat()
    timestamp_error = _check_timestamp(recorded_at)
    if timestamp_error:
        raise ReviewBlockedError(timestamp_error)

    contribution_id = envelope["contribution_id"]
    journal_path = Path(journal_path)
    with exclusive_ledger_lock(journal_path):
        chains = load_journal(journal_path)  # frisch IM Lock (#538-Lehre)
        chain = chains.get(contribution_id, [])
        from_status = chain[-1]["to_status"] if chain else "RECEIVED"
        if to_status not in TRANSITIONS[from_status]:
            raise ReviewBlockedError(
                f"transition {from_status!r} -> {to_status!r} is not allowed"
            )
        entry = {
            "protocol": JOURNAL_PROTOCOL,
            "contribution_id": contribution_id,
            "from_status": from_status,
            "to_status": to_status,
            "reviewer": reviewer.strip(),
            "reason": reason.strip(),
            "recorded_at": recorded_at,
            "envelope_digest": canonical_digest(envelope),
            "rights": "NOT_GRANTED",
            "execution": "NOT_PERFORMED",
        }
        line = json.dumps(
            entry, ensure_ascii=False, sort_keys=True, allow_nan=False
        )
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contribution_review",
        description=(
            "Record one review step for a V91-CONTRIBUTION-1 envelope"
            " in an append-only review journal. Documentation only:"
            " no rights, no execution."
        ),
    )
    parser.add_argument("--envelope", required=True, help="Pfad zum Umschlag-JSON")
    parser.add_argument("--journal", required=True, help="Pfad zum Review-Journal (JSONL)")
    parser.add_argument("--to", required=True, help="Ziel-Status der Kette")
    parser.add_argument("--reason", required=True, help="nachvollziehbare Begruendung")
    parser.add_argument("--reviewer", required=True, help="Angabe des Pruefenden")
    parser.add_argument("--at", default=None, help="ISO-8601-Zeitstempel mit Zeitzone")
    args = parser.parse_args(argv)

    try:
        with open(args.envelope, "r", encoding="utf-8") as handle:
            envelope = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"recorded": False, "error": f"envelope unreadable: {exc}"}))
        return 1
    try:
        entry = record_review(
            envelope,
            Path(args.journal),
            args.to,
            args.reason,
            args.reviewer,
            recorded_at=args.at,
        )
    except (ReviewBlockedError, JournalIntegrityError) as exc:
        print(json.dumps({"recorded": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"recorded": True, "entry": entry}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
