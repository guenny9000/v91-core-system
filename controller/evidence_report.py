"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Stufe B des universellen Lernblocks (docs/V91-UNIVERSAL-
LEARNING-BLOCK.md): einheitliches, versioniertes Austauschformat
fuer modelluebergreifende Pruefberichte - kanonisches JSON mit
SHA-256-Pruefsummen und optionaler Versionskette.

Ehrliche Grenzen:
- FORMAT != SYNCHRONISATION: dieses Modul erzeugt und prueft Dateien,
  es haben keinen Netzwerktransport, keine Veroeffentlichung und keine
  globale Synchronisation.
- VALIDATED != INDEPENDENT: eine strukturell gueltige Evidenz-Referenz
  beweist Abrufbarkeit-Struktur, nicht Wahrheit oder Unabhaengigkeit.
- Keine Signaturen in dieser Stufe; Ed25519-Receipts existieren bereits
  (controller/crypto_receipts.py, PR #57) und koennen spaeter additiv
  ergaenzt werden (NO_DUPLICATE_SYSTEMS).
- Evidenz-Referenzpruefung wird aus v99/filter/source_quality.py
  (Evidenz-Vertrag v2, Issue #51 / PR #53) wiederverwendet, nicht
  dupliziert.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from v99.filter.source_quality import _is_valid_reference

SCHEMA_VERSION = 1

# Status-Meldungen des Universalen Lernblocks v1.0 (PR #134) -
# vereinfachte Zugangsfassung der Kern-Taxonomie (PR #120, #98).
VALID_STATUSES = frozenset({
    "BELEGT",
    "IN ARBEIT",
    "VORSCHLAG",
    "NICHT GEPRÜFT",
    "UNKNOWN",
})

TOP_LEVEL_KEYS = frozenset({
    "schema_version",
    "report_id",
    "created_at",
    "producer",
    "subject",
    "items",
    "previous_checksum",
    "checksum",
})
ITEM_KEYS = frozenset({"claim", "status", "evidence", "note"})


class EvidenceReportError(ValueError):
    """Fail-closed Signal fuer ungueltige Berichte (nie stilles Durchwinken)."""


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _normalize_evidence(evidence) -> list:
    if evidence is None:
        return []
    if isinstance(evidence, (list, tuple)):
        return list(evidence)
    return [evidence]


def _validate_item(item) -> None:
    if not isinstance(item, dict):
        raise EvidenceReportError("Item muss ein Objekt sein.")
    if set(item.keys()) - ITEM_KEYS:
        raise EvidenceReportError(f"Unbekannte Item-Felder: {sorted(set(item.keys()) - ITEM_KEYS)}")
    claim = item.get("claim")
    status = item.get("status")
    if not isinstance(claim, str) or not claim.strip():
        raise EvidenceReportError("Item benoetigt ein nicht-leeres 'claim'-Feld.")
    if status not in VALID_STATUSES:
        raise EvidenceReportError(
            f"Status {status!r} ist keine gueltige Statusmeldung des Lernblocks: {sorted(VALID_STATUSES)}"
        )
    entries = _normalize_evidence(item.get("evidence"))
    for entry in entries:
        if not _is_valid_reference(entry):
            raise EvidenceReportError(
                "EVIDENCE_SUPPLIED != EVIDENCE_VALID: jede gelieferte Evidenz muss eine "
                "strukturell gueltige Referenz sein (URL/DOI/SHA-256/Pfad/citation/ledger_id)."
            )
    if status == "BELEGT" and not entries:
        raise EvidenceReportError(
            "BELEGT ohne Evidenz-Referenz verweigert (CLAIM != EVIDENCE)."
        )
    note = item.get("note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        raise EvidenceReportError("'note' muss nicht-leerer Text oder fehlend sein.")


def _validate_timestamp(value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceReportError("created_at fehlt.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvidenceReportError(f"created_at ist kein ISO-8601-Zeitstempel: {value!r}") from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise EvidenceReportError("created_at muss zeitzonen-bewusst sein (naive Zeitstempel verweigert).")


def build_report(
    producer: str,
    subject: str,
    items: list,
    created_at: str | None = None,
    previous_checksum: str | None = None,
) -> dict:
    """Erzeugt einen versionierten, pruefsummen-gesicherten Pruefbericht.

    Fail-closed: ungueltige Items, naive Zeitstempel, leere Pflichtfelder
    und ungueltige Evidenz-Referenzen werden verweigert, nie korrigiert.
    previous_checksum verdraengt den Vorgaenger-Bericht nicht, es erzeugt
    nur eine nachvollziehbare Versionskette (ISOLATE_NOT_DESTROY).
    """
    if not isinstance(producer, str) or not producer.strip():
        raise EvidenceReportError("producer muss ein nicht-leerer Name (z. B. Modellname) sein.")
    if not isinstance(subject, str) or not subject.strip():
        raise EvidenceReportError("subject muss ein nicht-leerer Prüfgegenstand sein.")
    if not isinstance(items, list) or not items:
        raise EvidenceReportError("items muss eine nicht-leere Liste sein.")
    for item in items:
        _validate_item(item)
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    _validate_timestamp(timestamp)
    if previous_checksum is not None:
        if not isinstance(previous_checksum, str) or not previous_checksum.strip():
            raise EvidenceReportError("previous_checksum muss SHA-64-Hex oder fehlend sein.")
        if len(previous_checksum) != 64 or any(c not in "0123456789abcdef" for c in previous_checksum.lower()):
            raise EvidenceReportError("previous_checksum ist kein 64-stelliger Hex-String.")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": timestamp,
        "producer": producer,
        "subject": subject,
        "items": items,
        "previous_checksum": previous_checksum,
    }
    report_id = hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:16]
    payload["report_id"] = report_id
    checksum = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    payload["checksum"] = checksum
    return payload


def verify_report(report) -> tuple[bool, str]:
    """Prueft einen Bericht komplett nach: Schema, Zeitstempel, Items, Pruefsumme."""
    if not isinstance(report, dict):
        return False, "Bericht ist kein Objekt."
    if set(report.keys()) != TOP_LEVEL_KEYS:
        missing = sorted(TOP_LEVEL_KEYS - set(report.keys()))
        extra = sorted(set(report.keys()) - TOP_LEVEL_KEYS)
        return False, f"Schema-Abweichung: fehlend={missing}, unbekannt={extra}."
    if report.get("schema_version") != SCHEMA_VERSION:
        return False, f"schema_version muss {SCHEMA_VERSION} sein."
    try:
        _validate_timestamp(report.get("created_at"))
    except EvidenceReportError as exc:
        return False, str(exc)
    try:
        if not isinstance(report.get("producer"), str) or not report["producer"].strip():
            return False, "producer fehlt oder ist leer."
        if not isinstance(report.get("subject"), str) or not report["subject"].strip():
            return False, "subject fehlt oder ist leer."
        if not isinstance(report.get("items"), list) or not report["items"]:
            return False, "items fehlt oder ist leer."
        for item in report["items"]:
            _validate_item(item)
        prev = report.get("previous_checksum")
        if prev is not None and (
            not isinstance(prev, str)
            or len(prev) != 64
            or any(c not in "0123456789abcdef" for c in prev.lower())
        ):
            return False, "previous_checksum ist kein 64-stelliger Hex-String."
    except EvidenceReportError as exc:
        return False, str(exc)
    expected = hashlib.sha256(_canonical_bytes({k: v for k, v in report.items() if k != "checksum"})).hexdigest()
    if report.get("checksum") != expected:
        return False, "Pruefsumme stimmt nicht (Bericht wurde veraendert)."
    return True, "OK: Schema, Items, Zeitstempel und Pruefsumme stimmen."


def save_report(report: dict, path) -> None:
    """Schreibt den Bericht als kanonisches JSON in eine lokale Datei."""
    ok, reason = verify_report(report)
    if not ok:
        raise EvidenceReportError(f"Verweigert, unveraifizierten Bericht zu speichern: {reason}")
    Path(path).write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")


def load_report(path):
    """Laedt einen Bericht aus einer lokalen Datei (ungeprueft; verify_report beim Empfaenger)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="V91 evidence exchange (Stage B): versioniertes, pruefsummen-gesichertes Berichtsformat"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Bericht aus Items-JSON-Datei erzeugen")
    build.add_argument("--producer", required=True)
    build.add_argument("--subject", required=True)
    build.add_argument("--items-file", required=True, help="JSON-Liste von {claim, status, evidence?}-Items")
    build.add_argument("--previous-checksum", default=None)
    build.add_argument("--out", required=True)
    verify = sub.add_parser("verify", help="Berichtsdatei pruefen")
    verify.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    if args.command == "build":
        items = json.loads(Path(args.items_file).read_text(encoding="utf-8"))
        report = build_report(
            producer=args.producer,
            subject=args.subject,
            items=items,
            previous_checksum=args.previous_checksum,
        )
        save_report(report, args.out)
        print(json.dumps({"report_id": report["report_id"], "checksum": report["checksum"]}, ensure_ascii=False))
        return 0
    ok, reason = verify_report(load_report(args.file))
    print(json.dumps({"verified": ok, "reason": reason}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
