"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Evidenz-Collector (PR-Review-Nachweise): erzeugt eine maschinen-
lesbare Nachweisdatei v91.evidence_collector.v1 aus REAL vorhandenen
Artefakten (Mess-/Test-/Benchmark-Dateien). Der Collector fuehrt fuer
jeden Eintrag eine Integritaetspruefung durch (Datei existiert, liegt
INNERHALB der Basis, SHA-256 stimmt mit der neu berechneten Pruefsumme
ueberein) und vergibt NUR dann den Status VERIFIZIERT.

Kernregel (fail-closed):
- FILE_EXISTS != VERIFIED_IMPROVEMENT: eine existierende Datei allein
  ist KEIN Nachweis; ohne passende SHA-256 bleibt der Eintrag
  NICHT_GEPRUEFT (Grund wird angegeben).
- KEIN handgesetztes PASS: der Collector nimmt keine Statusfelder aus
  der Eingabe entgegen, er vergibt Status ausschliesslich aus der
  eigenen Messung (CLAIM != EVIDENCE, UNKNOWN != PASS).
- INTEGRITAET != WIRKUNG: eine verifizierte Pruefsumme belegt, dass
  die Datei unveraendert vorliegt; ob ihr Inhalt eine reale
  Verbesserung belegt, bleibt menschliche/Prozess-Pruefung
  (Handinhaltliche Pruefung bleibt Pflicht).
- Pfad-Disziplin: Artefakt-Pfade duerfen die Basis nicht verlassen
  ( '../'-Escape und absolute Pfade werden abgelehnt).
- Zeitstempel muessen timezone-aware sein (naive = abgelehnt).
- commit_sha ist Pflichtfeld (40 Hex); er pinnt den Review auf den
  geprueften Stand (CI-Stand != HEAD-Stand ohne Pin).

REUSE-Abgrenzung (NO_DUPLICATE_SYSTEMS): controller/hashchain_ledger.py
verkettet MESSWERTE in einer Hash-Kette; dieses Modul prueft DATEI-
ARTEFAKT-Integritaet fuer Review-Nachweise. Es fuehrt KEINE zweite
Ledger- oder Validierungslogik ein, sondern nur Datei-SHA-256-Abgleich
fuer Review-Artefakte. Kein Daemon, kein Netzwerk, keine zufaelligen
Werte; alle Eingaben EXPLIZIT (JUSTIFIED != DEFAULT).

Ehrliche Grenzen:
- SCRIPTED != INSTALLED: Ein CI-Aufruf belegt die Funktion im Runner,
  keine Produktivwirkung (WIRKUNG AUSSEN != REGISTRIEREN INNEN).
- Der Collector ersetzt KEIN bestehendes Gate (Governance-Gate #96,
  Promotion-Gates #145/#146, governance-gate-Workflow #551 bleiben
  unveraendert verbindlich); er liefert ihnen nur belastbarere
  Nachweisdateien.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional

SCHEMA = "v91.evidence_collector.v1"
STATUS_VERIFIZIERT = "VERIFIZIERT"
STATUS_NICHT_GEPRUEFT = "NICHT_GEPRUEFT"
GESAMT_VERIFIZIERT = "NACHWEIS_VERIFIZIERT"
GESAMT_UNVOLLSTAENDIG = "UNVOLLSTAENDIG"
HONEST_LIMITS = [
    "FILE_EXISTS != VERIFIED_IMPROVEMENT: Integritaet belegt Existenz und Unaendertheit, NICHT inhaltliche Wirkung",
    "INTEGRITAET != WIRKUNG: ob das Artefakt eine reale Verbesserung belegt, bleibt Review/Prozess",
    "SCRIPTED != INSTALLED: Collector-Lauf im Runner ist keine Produktivwirkung",
]


class EvidenzCollectorError(ValueError):
    """Eingabe kann nicht ehrlich ausgewertet werden (fail-closed)."""


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenzCollectorError(f"{field} needs a non-empty string")
    return value.strip()


def _require_iso_tz(value: Any, field: str) -> datetime.datetime:
    if not isinstance(value, str):
        raise EvidenzCollectorError(f"{field} needs an ISO-8601 string")
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvidenzCollectorError(f"{field} is not valid ISO-8601: {exc}") from exc
    if parsed.tzinfo is None:
        raise EvidenzCollectorError(f"{field} must be timezone-aware; naive timestamps are rejected")
    return parsed


def _require_sha256(value: Any, field: str) -> str:
    text = _require_nonempty_str(value, field)
    cleaned = text.lower()
    if len(cleaned) != 64 or any(c not in "0123456789abcdef" for c in cleaned):
        raise EvidenzCollectorError(f"{field} must be a 64-character hex SHA-256")
    return cleaned


def _require_commit_sha(value: Any, field: str) -> str:
    text = _require_nonempty_str(value, field)
    if len(text) != 40 or any(c not in "0123456789abcdef" for c in text.lower()):
        raise EvidenzCollectorError(f"{field} must be a 40-character hex commit SHA")
    return text.lower()


def _artifact_path(base_dir: pathlib.Path, artifact: str) -> pathlib.Path:
    if not isinstance(artifact, str) or not artifact.strip():
        raise EvidenzCollectorError("artifact needs a non-empty relative path")
    candidate = pathlib.Path(artifact.strip())
    if candidate.is_absolute():
        raise EvidenzCollectorError(f"artifact must be relative to base_dir: {artifact}")
    resolved_base = base_dir.resolve()
    resolved = (base_dir / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise EvidenzCollectorError(
            f"artifact escapes base_dir (path traversal rejected): {artifact}"
        ) from exc
    return resolved


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_evidence(plan: Any, now: Any) -> Dict[str, Any]:
    """Plan (dict oder Dateipfad) -> Nachweisdatei-Inhalt v1 (fail-closed).

    Vergibt Status ausschliesslich aus eigener Messung; ein im Plan
    mitgeliefertes 'status'-Feld wird bewusst IGNORIERT (KEIN
    handgesetztes PASS).
    """
    if isinstance(plan, str):
        try:
            with open(plan, encoding="utf-8") as fh:
                plan = json.load(fh)
        except OSError as exc:
            raise EvidenzCollectorError(f"plan unreadable: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise EvidenzCollectorError(f"plan invalid JSON: {exc}") from exc
    if not isinstance(plan, dict):
        raise EvidenzCollectorError("plan must be an object (or a path to one)")
    base_dir_value = plan.get("base_dir")
    base_dir = pathlib.Path(_require_nonempty_str(base_dir_value, "base_dir"))
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        raise EvidenzCollectorError("items must be a non-empty list")
    now_dt = _require_iso_tz(now, "now")
    verified = 0
    results: List[Dict[str, Any]] = []
    seen_labels: set = set()
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise EvidenzCollectorError(f"items[{index}] must be an object")
        label = _require_nonempty_str(raw.get("label"), f"items[{index}].label")
        if label in seen_labels:
            raise EvidenzCollectorError(f"duplicate label: {label}")
        seen_labels.add(label)
        methode = _require_nonempty_str(raw.get("methode"), f"items[{label}].methode")
        erwartung = _require_nonempty_str(raw.get("erwartung"), f"items[{label}].erwartung")
        expected_sha = _require_sha256(raw.get("sha256"), f"items[{label}].sha256")
        commit_sha = _require_commit_sha(raw.get("commit_sha"), f"items[{label}].commit_sha")
        gemessen_at = _require_iso_tz(raw.get("gemessen_at"), f"items[{label}].gemessen_at")
        if gemessen_at > now_dt + datetime.timedelta(seconds=0):
            raise EvidenzCollectorError(
                f"items[{label}].gemessen_at lies in the future relative to now"
            )
        artifact = str(raw.get("artifact", "")).strip()
        entry: Dict[str, Any] = {
            "label": label,
            "artifact": artifact,
            "methode": methode,
            "erwartung": erwartung,
            "ergebnis": raw.get("ergebnis") if isinstance(raw.get("ergebnis"), str) else None,
            "commit_sha": commit_sha,
            "gemessen_at": gemessen_at.isoformat(),
            "status": STATUS_NICHT_GEPRUEFT,
            "grund": None,
        }
        try:
            path = _artifact_path(base_dir, artifact)
            if not path.is_file():
                entry["grund"] = "ARTIFACT_MISSING"
            elif _sha256_file(path) != expected_sha:
                entry["grund"] = "SHA256_MISMATCH"
            else:
                entry["status"] = STATUS_VERIFIZIERT
                verified += 1
        except EvidenzCollectorError as exc:
            entry["grund"] = f"EINGABE_FEHLER: {exc}"
        results.append(entry)
    gesamt = GESAMT_VERIFIZIERT if verified == len(items) else GESAMT_UNVOLLSTAENDIG
    return {
        "schema": SCHEMA,
        "now": now_dt.isoformat(),
        "status": gesamt,
        "verified_items": verified,
        "total_items": len(items),
        "items": results,
        "honest_limits": HONEST_LIMITS,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Evidenz-Collector (Review-Nachweise, fail-closed)")
    parser.add_argument("--plan", help="JSON-Datei mit base_dir + items (label/artifact/sha256/commit_sha/methode/erwartung)")
    parser.add_argument("--out", help="optionaler Ausgabepfad fuer die Nachweisdatei")
    parser.add_argument("--now", help="ISO-8601 timezone-aware Referenzzeitpunkt (default: UTC jetzt)")
    args = parser.parse_args(argv)
    if not args.plan:
        print("usage: --plan FILE [--out FILE] [--now ISO8601]", file=sys.stderr)
        return 2
    if args.now:
        try:
            now_value: Any = _require_iso_tz(args.now, "--now")
        except EvidenzCollectorError as exc:
            print(json.dumps({"status": "INPUT_FEHLER", "error": str(exc)}), file=sys.stderr)
            return 2
    else:
        now_value = datetime.datetime.now(datetime.timezone.utc)
    try:
        result = collect_evidence(args.plan, now_value)
    except EvidenzCollectorError as exc:
        print(json.dumps({"status": "INPUT_FEHLER", "error": str(exc)}), file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if result["status"] == GESAMT_VERIFIZIERT else 1


if __name__ == "__main__":
    raise SystemExit(main())
