#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
V91-Solar-Eval: verbindet physische Messreihe, Ledger und Manifest.

Zwei-Wege-Vertrag (das "Architektur-Dreieck" von Betreiber-Seite,
ohne dessen ueberzogene Vollendungs-Behauptungen zu uebernehmen):
1. Eine physische Messreihe (JSONL: {"timestamp": ISO-8601, "watt": >=0})
   wird NUR dann als VERIFIZIERT bewertet, wenn (a) die Reihe existiert
   und valide ist UND (b) ein Eintrag im Hash-Chain-Ledger
   (controller/ledger.py) existiert, dessen payload.series_digest mit
   dem SHA-256 der Reihendatei uebereinstimmt (SERIES == BEWEIS).
2. Der Manifest-Status (docs/ governance manifest) wird ausschliesslich
   aus diesem Ergebnis abgeleitet: VERIFIZIERT / UNVERIFIZIERT /
   MANIPULIERT (UNKNOWN != PASS, SCRIPTED != INSTALLED).

Ehrliche Grenzen (NICHT behauptet, NICHT simuliert):
- Dieses Modul ERZEUGT keine Messdaten. Ohne reale Messreihe bleibt
  der Status UNVERIFIZIERT; es werden KEINE Zahlen erfunden
  (UNBEKANNT != NULL != ERFUNDEN, NICHT_GEPRUEFT nie 0-Ersatz).
- Ledger-Verifikation ist tamper-EVIDENT, nicht tamper-proof.
- KEIN Netzwerk, KEIN Daemon, KEIN Hintergrundprozess.
- FAO/WHO/M_global-Anbindungen sind hier NICHT enthalten; der
  IEA-Adapter existiert separat (controller/iea_stats_adapter.py,
  Inbetriebnahme bleibt Betreiber-Aufgabe).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from controller.ledger import verify_chain
except ImportError:  # direkter Start aus controller/ (flat-Pfad)
    from ledger import verify_chain  # type: ignore[no-redef]

SERIES_SCHEMA = "v91.solar_eval.series.v1"
MANIFEST_SCHEMA = "v91.governance_status_manifest.v1"
EXIT_VERIFIZIERT = 0
EXIT_UNVERIFIZIERT = 3
EXIT_MANIPULIERT = 4
EXIT_FEHLER = 5


class SolarEvalError(ValueError):
    """Fail-closed bei unbrauchbaren Eingaben (KEIN stilles Clampen)."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_series(path: Path) -> list[dict[str, Any]]:
    """Liest und validiert die Messreihe. Fehler wirfen SolarEvalError."""
    if not path.exists():
        raise SolarEvalError(f"SERIES_UNAVAILABLE: {path}")
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                raise SolarEvalError(f"line {line_no}: MALFORMED_JSON") from exc
            if not isinstance(rec, dict) or rec.get("schema") != SERIES_SCHEMA:
                raise SolarEvalError(f"line {line_no}: SCHEMA_MISMATCH")
            watt = rec.get("watt")
            if isinstance(watt, bool) or not isinstance(watt, (int, float)) or watt < 0:
                raise SolarEvalError(f"line {line_no}: WATT_INVALID")
            try:
                datetime.fromisoformat(str(rec["timestamp"]))
            except (KeyError, ValueError) as exc:
                raise SolarEvalError(f"line {line_no}: TIMESTAMP_INVALID") from exc
            records.append({"timestamp": rec["timestamp"], "watt": watt})
    if not records:
        raise SolarEvalError("SERIES_EMPTY")
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    watts = [r["watt"] for r in records]
    return {
        "n_samples": len(records),
        "first_timestamp": records[0]["timestamp"],
        "last_timestamp": records[-1]["timestamp"],
        "mean_watt": sum(watts) / len(watts),
        "max_watt": max(watts),
    }


def ledger_has_series(ledger_path: Path, series_digest: str) -> bool:
    """True nur wenn ein valider Ledger-Eintrag diesen Series-Digest referenziert."""
    report = verify_chain(str(ledger_path))
    if not report["chain_valid"]:
        raise SolarEvalError("LEDGER_MANIPULIERT: " + "; ".join(report["errors"][:3]))
    if not Path(ledger_path).exists():
        return False
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("payload", {}).get("series_digest") == series_digest:
                return True
    return False


def evaluate(series_path: Path, ledger_path: Path | None = None) -> dict[str, Any]:
    """3-Wege-Evaluierung. Liefert dict mit status und (nur bei VERIFIZIERT) Kennzahlen."""
    result: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "series": str(series_path),
        "status": "UNVERIFIZIERT",
        "summary": None,
        "ledger_verified": False,
        "reason": "NICHT_GEPRUEFT: keine bewertbare Messreihe verfuegbar",
    }
    try:
        records = load_series(series_path)
    except SolarEvalError as exc:
        result["reason"] = str(exc)
        return result
    if ledger_path is None:
        result["reason"] = "LEDGER_UNVERWEISEN: kein Ledger-Pfad angegeben"
        result["summary"] = summarize(records)
        return result
    digest = _sha256_file(series_path)
    try:
        found = ledger_has_series(ledger_path, digest)
    except SolarEvalError as exc:
        result["status"] = "MANIPULIERT"
        result["reason"] = str(exc)
        return result
    result["ledger_verified"] = found
    result["summary"] = summarize(records)
    if found:
        result["status"] = "VERIFIZIERT"
        result["series_digest"] = digest
        result["reason"] = "Eine Messreihe wurde gegen den Ledger proofen: Series == Beweis."
    else:
        result["reason"] = "LEDGER_EINTRAG_FEHLT: keine Ledger-Referenz auf diesen Series-Digest"
    return result


def write_manifest(result: dict[str, Any], manifest_path: Path) -> None:
    """Schreibt das Governance-Status-Manifest (klein, append-freundlich)."""
    payload = dict(result)
    payload["schema"] = MANIFEST_SCHEMA
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, ensure_ascii=True, indent=2)
        fh.write("\n")


def self_check() -> dict[str, Any]:
    """CI-Selbsttest: prueft den GATE-MECHANISMUS mit_FIXTURE-Daten.

    Beweist, dass die Evaluierungslogik funktioniert - NICHT dass eine
    reale Messreihe existiert (GATE != MESSUNG, FORMELN == LEITBILD
    != MESSUNG)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        series = tmp_path / "self_check_series.jsonl"
        series.write_text(
            json.dumps({"schema": SERIES_SCHEMA, "timestamp": "2026-11-25T12:00:00+01:00", "watt": 0}) + "\n"
            + json.dumps({"schema": SERIES_SCHEMA, "timestamp": "2026-11-25T12:15:00+01:00", "watt": 120}) + "\n",
            encoding="utf-8",
        )
        # Ohne Ledger: UNVERIFIZIERT (NICHT_GEPRUEFT, keine Zahlen-Fiktion)
        r1 = evaluate(series)
        assert r1["status"] == "UNVERIFIZIERT", r1
        # Mit Ledger ohne Eintrag: bleib UNVERIFIZIERT
        empty_ledger = tmp_path / "empty_ledger.jsonl"
        empty_ledger.write_text("", encoding="utf-8")
        r2 = evaluate(series, empty_ledger)
        assert r2["status"] == "UNVERIFIZIERT", r2
        # Mit passendem Ledger-Eintrag: VERIFIZIERT
        from controller.ledger import HashChainLedger

        linked = tmp_path / "linked_ledger.jsonl"
        ledger = HashChainLedger(str(linked))
        ledger.append(
            {"kind": "SOLAR_EVAL_SERIES", "series_digest": _sha256_file(series)},
            timestamp="2026-11-25T12:20:00+01:00",
        )
        r3 = evaluate(series, linked)
        assert r3["status"] == "VERIFIZIERT", r3
        assert r3["summary"]["n_samples"] == 2, r3
        # Manipulierter Ledger: MANIPULIERT, nie still
        tampered = tmp_path / "tampered.jsonl"
        rec = json.loads(linked.read_text(encoding="utf-8"))
        rec["payload"]["series_digest"] = "0" * 64  # Faelschung ohne Neuberechnung der Kette
        tampered.write_text(json.dumps(rec, sort_keys=True) + "\n", encoding="utf-8")
        r4 = evaluate(series, tampered)
        assert r4["status"] == "MANIPULIERT", r4
    return {"self_check": "PASS", "mechanism": "getestet", "reale_messreihe": "NICHT_GEPRUEFT"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Solar-Eval: Messreihe-Ledger-Manifest-Gate")
    parser.add_argument("--series", type=Path, help="Pfad zur Messreihen-JSONL")
    parser.add_argument("--ledger", type=Path, help="Pfad zum Hash-Chain-Ledger (JSONL)")
    parser.add_argument("--manifest", type=Path, help="Zielpfad fuer das Status-Manifest")
    parser.add_argument("--self-check", action="store_true", help="CI-Selbsttest des Gate-Mechanismus")
    args = parser.parse_args(argv)
    if args.self_check:
        print(json.dumps(self_check(), sort_keys=True))
        return EXIT_VERIFIZIERT
    if args.series is None:
        parser.error("--series erforderlich (oder --self-check)")
    try:
        result = evaluate(args.series, args.ledger)
    except SolarEvalError as exc:
        print(json.dumps({"status": "MANIPULIERT", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return EXIT_FEHLER
    output = json.dumps(result, sort_keys=True, ensure_ascii=True)
    if args.manifest:
        write_manifest(result, args.manifest)
        print(output)
    else:
        print(output)
    return {
        "VERIFIZIERT": EXIT_VERIFIZIERT,
        "UNVERIFIZIERT": EXIT_UNVERIFIZIERT,
        "MANIPULIERT": EXIT_MANIPULIERT,
    }[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
