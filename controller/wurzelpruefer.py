#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
V91 Wurzelpruefer: Bewertung eines Systems gegen die 7 Pruefkriterien
Leistungsfaehigkeit, Nutzen, Schaden, Ressourcen, Transparenz,
Sicherheit, Verbesserung.

Ehrlichkeitsregeln (fail-closed):
- BELEGT gilt NUR mit nicht-leerer Evidenzangabe; sonst wird der
  Status NICHT GEPRUEFT (BEHAUPTUNG != BELEG, kein stiller PASS).
- Fehlende Kriterien sind NICHT GEPRUEFT, niemals bestanden.
- Ein PROBLEM beim Kriterium Schaden blockiert das Gesamtergebnis
  (BLOCKIERT); jedes andere PROBLEM blockiert ebenfalls.
- Unvollstaendige Pruefungen werden als UNVOLLSTAENDIG markiert,
  nicht als bestanden (UNKNOWN != PASS).
- Der Pruefer wertet NUR aus und protokolliert: RECHNER !=
  ENTSCHEIDER. Reale Eingriffe (Abschalten, Isolieren, Umlenken)
  bleiben je Aktion allowlist-pflichtig beim Betreiber
  (FREIGABE != BERECHTIGUNG Dritter gilt unveraendert).

Manipulationsschutz: jede Pruefung wird als Record in eine
Append-Only-Hash-Kette geschrieben (REUSE controller/ledger.py
HashChainLedger inkl. Interprozess-Lock; KEINE zweite
Hash-Implementierung). Bei manipulierter Kette verweigert der
Pruefer den Start. HASH_KETTE != WORM: tamper-EVIDENT, nicht
tamper-proof; verify_chain bleibt Massstab.

Grenzen: PRUEFPROTOKOLL != MESSUNG. Echte Messwerte muss die
Evidenzangabe liefern; dieses Modul erfindet keine Kennzahlen.
Betrieb auf SOLAR-DESKTOP-01: NICHT_GEPRUEFT von hier aus
(SCRIPTED != INSTALLED, kein Scheduler in diesem Modul).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from controller.ledger import HashChainLedger, verify_chain
except ImportError:  # direkter Start aus controller/ (flat-Pfad)
    from ledger import HashChainLedger, verify_chain

SCHEMA_VERSION = "v91.wurzelpruefer.v1"
DEFAULT_LEDGER_NAME = "wurzelpruefer_ledger.jsonl"

# Verbindliche Reihenfolge der 7 Pruefkriterien (Dauerprotokoll,
# docs/V91-MAX-BEST-DAUERPROTOKOLL.md; Reihenfolge aendern = Review).
KRITERIEN = (
    "leistungsfaehigkeit",
    "nutzen",
    "schaden",
    "ressourcen",
    "transparenz",
    "sicherheit",
    "verbesserung",
)

ERLAUBTE_STATUS = frozenset({"BELEGT", "NICHT_GEPRUEFT", "PROBLEM"})
VERDIKTE = frozenset({"BESTANDEN", "BLOCKIERT", "UNVOLLSTAENDIG"})


class WurzelprueferError(ValueError):
    """Ungueltige Eingabe (fail-closed, kein stiller Rueckfall)."""


def normalisiere_kriterium(eintrag: Any) -> str:
    """Ein Kriterium -> Status. BELEGT ohne Evidenz wird fail-closed
    zu NICHT_GEPRUEFT herabgestuft (CLAIM != EVIDENCE)."""
    if not isinstance(eintrag, dict):
        raise WurzelprueferError("kriterium_muss_objekt_sein")
    status = eintrag.get("status")
    if status not in ERLAUBTE_STATUS:
        raise WurzelprueferError(
            f"unzulaessiger_status:{status!r} "
            f"(erlaubt: {sorted(ERLAUBTE_STATUS)})"
        )
    if status == "BELEGT":
        evidenz = eintrag.get("evidenz")
        if not isinstance(evidenz, str) or not evidenz.strip():
            return "NICHT_GEPRUEFT"
    return status


def pruefe(assessment: Any) -> dict[str, Any]:
    """Bewertet ein Assessment gegen die 7 Kriterien.

    Assessment-Form: {"kriterien": {"<name>": {"status": ..., "evidenz": ...}}, ...}
    Fehlende Kriterien: NICHT_GEPRUEFT (kein Default-PASS).
    """
    if not isinstance(assessment, dict):
        raise WurzelprueferError("assessment_muss_objekt_sein")
    kriterien_in = assessment.get("kriterien")
    if not isinstance(kriterien_in, dict):
        raise WurzelprueferError("kriterien_muessen_objekt_sein")

    bewertung: dict[str, str] = {}
    for name in KRITERIEN:
        if name not in kriterien_in:
            bewertung[name] = "NICHT_GEPRUEFT"
        else:
            bewertung[name] = normalisiere_kriterium(kriterien_in[name])

    # Unbekannte zusaetzliche Schluessel ablehnen (kein stilles
    # Ueberlesen; Dokumentationsdisziplin).
    unbekannt = sorted(set(kriterien_in) - set(KRITERIEN))
    if unbekannt:
        raise WurzelprueferError(f"unbekannte_kriterien:{unbekannt}")

    if any(bewertung[name] == "PROBLEM" for name in KRITERIEN):
        verdikt = "BLOCKIERT"
    elif any(bewertung[name] == "NICHT_GEPRUEFT" for name in KRITERIEN):
        verdikt = "UNVOLLSTAENDIG"
    else:
        verdikt = "BESTANDEN"

    return {
        "schema": SCHEMA_VERSION,
        "kriterien": bewertung,
        "verdikt": verdikt,
        "pruefstatus": {
            "bestanden": sum(1 for s in bewertung.values() if s == "BELEGT"),
            "probleme": sum(1 for s in bewertung.values() if s == "PROBLEM"),
            "ungeprueft": sum(1 for s in bewertung.values() if s == "NICHT_GEPRUEFT"),
        },
    }


def protokolliere(ergebnis: dict[str, Any], ledger_pfad: str,
                  timestamp: str) -> dict[str, Any]:
    """Ergebnis als Record in die Hash-Kette schreiben (append-only).
    Manipulierte Kette laesst HashChainLedger den Start verweigern."""
    ledger = HashChainLedger(ledger_pfad)
    record = ledger.append(ergebnis, timestamp)
    return record


def _self_check_payload() -> dict[str, Any]:
    """Fixture-Belegung NUR fuer --self-check: KEINE Datenfiktion,
    reale Pruefungen bleiben NICHT_GEPRUEFT."""
    return {
        "kriterien": {
            name: {"status": "NICHT_GEPRUEFT", "evidenz": "SELF_CHECK_FICTIVE_PROBE"}
            for name in KRITERIEN
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wurzelpruefer",
        description="7-Kriterien-Wurzelpruefung mit Hash-Ketten-Protokoll",
    )
    parser.add_argument("--assessment", default=None,
                        help="Pfad zur Assessment-JSON-Datei")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER_NAME,
                        help="Pfad zur Audit-Hash-Kette (JSONL, append-only)")
    parser.add_argument("--verify", action="store_true",
                        help="Nur Kette verifizieren, keine neue Pruefung")
    parser.add_argument("--self-check", action="store_true",
                        help="Fixture-Selbstpruefung ohne echte Daten")
    parser.add_argument("--timestamp-utc", default=None,
                        help="ISO-8601-Zeitstempel (Default: now UTC)")
    args = parser.parse_args(argv)

    if args.verify:
        report = verify_chain(args.ledger)
        print(json.dumps({"modus": "verify", **report}, sort_keys=True))
        return 0 if report["chain_valid"] else 3

    if args.self_check:
        ergebnis = pruefe(_self_check_payload())
        ergebnis["selbstpruefung"] = {
            "mechanismus": "getestet",
            "reale_pruefungen": "NICHT_GEPRUEFT",
        }
        print(json.dumps(ergebnis, sort_keys=True))
        return 2  # UNVOLLSTAENDIG ist der ehrliche Fixture-Status

    if not args.assessment:
        parser.error("--assessment oder --self-check oder --verify noetig")

    pfad = Path(args.assessment)
    try:
        assessment = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"fehler": f"assessment_unlesbar:{exc}"}))
        return 2

    try:
        ergebnis = pruefe(assessment)
    except WurzelprueferError as exc:
        print(json.dumps({"fehler": str(exc)}))
        return 2

    timestamp = args.timestamp_utc or datetime.now(timezone.utc).isoformat()
    try:
        protokolliere(ergebnis, args.ledger, timestamp)
    except ValueError as exc:  # manipulierte Kette
        print(json.dumps({"fehler": f"ledger_integritaet:{exc}"}))
        return 3

    print(json.dumps(ergebnis, sort_keys=True))
    return {"BESTANDEN": 0, "BLOCKIERT": 1, "UNVOLLSTAENDIG": 2}[ergebnis["verdikt"]]


if __name__ == "__main__":
    sys.exit(main())
