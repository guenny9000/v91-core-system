"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Use-Case-Anwendungspflicht nach Verfassung Abschnitt 8
(V91_Agathon, docs/AGATHON_VERFASSUNG_ENTWURF.md, PR #19, 23.11.2026):
Die sechs verbindlichen Review-Domaenen (D1-D6) sind zwingende
Pruefkomponenten. Jeder Architektur- oder Wirkungs-Claim, der eine
Domaene beruehrt, MUSS den Status der betroffenen Pruefkriterien
ausweisen (BELEGT / IN ARBEIT / VORSCHLAG / NICHT GEPRUEFT / UNKNOWN,
Taxonomie Universeller Lernblock v1.0, PR #134). Fehlt die Ausweisung,
wird der Claim mit REVIEW_REQUIRED zurueckgegeben, nicht still
akzeptiert.

Ehrliche Grenzen:
- GEMELDET != EVIDENZ: Lageberichte (Weltlage-News) sind Kontext,
  niemals V91-Nachweis. BELEGT verlangt strukturell gueltige
  Evidenz-Referenz, Quelle und zeitzonen-bewussten Zeitstempel.
- VALIDATED != INDEPENDENT: eine gueltige Referenz beweist Struktur,
  nicht Wahrheit oder Unabhaengigkeit.
- INDEX != ABSCHALTLISTE; REVIEW != ENTSCHEIDUNG; DETECTION !=
  AUTHORIZATION. Dieses Modul bewertet Angaben, es ergreift nichts,
  ruft niemanden an, veraendert keine Fremdsysteme.
- Evidenz-Referenzpruefung wird aus v99/filter/source_quality.py
  (Evidenz-Vertrag v2, Issue #51 / PR #53) wiederverwendet, nicht
  dupliziert (NO_DUPLICATE_SYSTEMS).
- Status-Vokabular bewusst ASCII ('NICHT GEPRUEFT' statt 'NICHT
  GEPRUEFöT'-Varianten); Schema nicht-live, kein Daemon, kein
  Netzwerk. SCRIPTED != RUNNING.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from v99.filter.source_quality import _is_valid_reference

SCHEMA_VERSION = 1

# Verbindliche Domaenen exakt nach Verfassung Abschnitt 8 (PR #19).
DOMAINS: Dict[str, Dict[str, str]] = {
    "D1": {
        "name": "notfallkommunikation_telekom_resilienz",
        "pruefkriterium": (
            "Unabhaengiger Ersatzkommunikationsweg mit Messnachweis "
            "(Testprotokoll mit Zeitstempel und Intervall)."
        ),
    },
    "D2": {
        "name": "krankenhaus_offline_faehigkeit",
        "pruefkriterium": (
            "Geuebter, papiergestuetzter Notfallbetrieb mit nachweisbarer "
            "Uebung (Datum, Teilnehmer, Dauer, Leitstellen-Bestaetigung); "
            "abgelaufene Uebung = EXPIRED => UNKNOWN."
        ),
    },
    "D3": {
        "name": "legacy_migrationsrisiko",
        "pruefkriterium": (
            "Rollback- und Parallelbetriebsnachweis je Migration "
            "(Risikoanalyse, Stufenplan, Abbruchkriterium)."
        ),
    },
    "D4": {
        "name": "ressourcenverlust_messung",
        "pruefkriterium": (
            "Verlustmessung mit Methode, Zeitraum, Quelle und Baseline; "
            "Einsparungsziffer nur aus Vorher/Nachher-Differenz."
        ),
    },
    "D5": {
        "name": "duerre_niedrigwasser_kettenreaktionen",
        "pruefkriterium": (
            "Dokumentiert durchlaufener Ketten-Belastungstest mit "
            "definierten Koppelpunkten (Protokoll/Quelle)."
        ),
    },
    "D6": {
        "name": "energie_legacy_transition",
        "pruefkriterium": (
            "Je Speicher-/Erzeugungs-Alternative: Kosten je MWh, "
            "Wirkungsgrad, Lebenszykluskosten nur mit Primaerquelle; "
            "bis dahin UNKNOWN (nie 0)."
        ),
    },
}

VALID_STATUSES = frozenset({
    "BELEGT",
    "IN ARBEIT",
    "VORSCHLAG",
    "NICHT GEPRUEFT",
    "UNKNOWN",
})

VERDICT_ERFUELLT = "ANWENDUNGSPFLICHT_ERFUELLT_AUSGEWIESEN"
VERDICT_REVIEW = "REVIEW_REQUIRED_FEHLENDE_AUSWEISUNG"


class DomainUseCaseError(ValueError):
    """Fail-closed Signal fuer ungueltige Use-Case-Ausweisungen."""


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainUseCaseError(f"{field} muss ein nicht-leerer String sein.")
    return value


def _validate_assessed_at(value: Any, domain: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainUseCaseError(
            f"Domaene {domain}: BELEGT verlangt assessed_at (ISO-8601, zeitzonen-bewusst)."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DomainUseCaseError(
            f"Domaene {domain}: assessed_at ist kein ISO-8601-Zeitstempel: {value!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise DomainUseCaseError(
            f"Domaene {domain}: assessed_at muss zeitzonen-bewusst sein (naiv verweigert)."
        )


def _normalize_evidence(evidence: Any, domain: str) -> List[Any]:
    if evidence is None:
        return []
    entries = list(evidence) if isinstance(evidence, (list, tuple)) else [evidence]
    for entry in entries:
        if not _is_valid_reference(entry):
            raise DomainUseCaseError(
                f"Domaene {domain}: EVIDENCE_SUPPLIED != EVIDENCE_VALID - jede Evidenz "
                "muss eine strukturell gueltige Referenz sein "
                "(URL/DOI/SHA-256/Pfad/citation/ledger_id)."
            )
    return entries


def evaluate_domain_claim(claim: Dict) -> Dict:
    """Prueft EINEN Claim gegen die Anwendungspflicht der Domaenen.

    Eingabe (dict):
      claim_id        - nicht-leerer str
      claimant        - nicht-leerer str (z. B. Modellname)
      touched_domains - nicht-leere Liste gueltiger Domaenen-IDs (D1-D6)
      assessments     - {domain_id: {status, evidence?, source?, assessed_at?}}

    Regeln (fail-closed):
    - Jede angefasste Domaene braucht eine Ausweisung. Fehlt sie, lautet
      das Gesamtergebnis REVIEW_REQUIRED_FEHLENDE_AUSWEISUNG (nie still
      akzeptiert, nie erfunden).
    - BELEGT verlangt mindestens eine strukturell gueltige Evidenz-
      Referenz, nicht-leere Quelle und zeitzonen-bewusstes assessed_at.
    - IN ARBEIT / VORSCHLAG / NICHT GEPRUEFT / UNKNOWN sind ehrliche
      Ausweisungen ohne Evidenz-Zwang (UNKNOWN != PASS, aber UNKNOWN
      != LUEGE).
    - Ergebnis enthaelt je Domaene: status, belegt (bool) und bei
      BELEGT die Anzahl der Evidenz-Referenzen.
    """
    if not isinstance(claim, dict):
        raise DomainUseCaseError("claim muss ein Objekt sein.")
    claim_id = _require_str(claim.get("claim_id"), "claim_id")
    claimant = _require_str(claim.get("claimant"), "claimant")
    touched = claim.get("touched_domains")
    if not isinstance(touched, list) or not touched:
        raise DomainUseCaseError("touched_domains muss eine nicht-leere Liste sein.")
    seen: set = set()
    for domain in touched:
        if not isinstance(domain, str) or domain not in DOMAINS:
            raise DomainUseCaseError(
                f"Unbekannte Domaenen-ID {domain!r} (erlaubt: {sorted(DOMAINS)})."
            )
        if domain in seen:
            raise DomainUseCaseError(f"Domaene {domain} doppelt in touched_domains.")
        seen.add(domain)
    assessments = claim.get("assessments")
    if not isinstance(assessments, dict):
        raise DomainUseCaseError("assessments muss ein Objekt sein.")
    unknown_keys = set(assessments) - set(touched)
    if unknown_keys:
        raise DomainUseCaseError(
            f"assessments enthaelt nicht beruehrte Domaenen: {sorted(unknown_keys)} "
            "(ausgewiesen wird nur, was beruehrt wird)."
        )

    missing: List[str] = []
    results: Dict[str, Dict] = {}
    for domain in touched:
        entry = assessments.get(domain)
        if not isinstance(entry, dict):
            missing.append(domain)
            continue
        status = entry.get("status")
        if status not in VALID_STATUSES:
            raise DomainUseCaseError(
                f"Domaene {domain}: status {status!r} ist keine gueltige "
                f"Statusmeldung: {sorted(VALID_STATUSES)}"
            )
        entries = _normalize_evidence(entry.get("evidence"), domain)
        if status == "BELEGT":
            if not entries:
                raise DomainUseCaseError(
                    f"Domaene {domain}: BELEGT ohne Evidenz-Referenz verweigert (CLAIM != EVIDENCE)."
                )
            _require_str(entry.get("source"), f"Domaene {domain}: source")
            _validate_assessed_at(entry.get("assessed_at"), domain)
        elif entry.get("source") is not None:
            _require_str(entry.get("source"), f"Domaene {domain}: source")
        results[domain] = {
            "status": status,
            "belegt": status == "BELEGT",
            "evidenz_referenzen": len(entries) if entries else 0,
        }

    verdict = VERDICT_ERFUELLT if not missing else VERDICT_REVIEW
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_id": claim_id,
        "claimant": claimant,
        "domains_total": len(touched),
        "domains_belegt": sum(1 for r in results.values() if r["belegt"]),
        "fehlende_ausweisung": sorted(missing),
        "ausweisungen": results,
        "verdict": verdict,
        "honest_limits": [
            "GEMELDET != EVIDENZ: Lageberichte sind Kontext, kein Nachweis.",
            "VALIDATED != INDEPENDENT: Referenzstruktur beweist keine Wahrheit.",
            "REVIEW != ENTSCHEIDUNG; INDEX != ABSCHALTLISTE.",
            "SCRIPTED != RUNNING: Register und Pruefung, kein Daemon.",
        ],
    }


def main(argv: Optional[List] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Verfassung Abschnitt 8: Anwendungspflicht-Pruefung von Claims "
            "gegen die verbindlichen Review-Domaenen D1-D6"
        )
    )
    parser.add_argument("--claim-json", required=True, help="Pfad zur Claim-JSON-Datei")
    args = parser.parse_args(argv)

    try:
        with open(args.claim_json, "r", encoding="utf-8") as handle:
            claim = json.load(handle)
        result = evaluate_domain_claim(claim)
    except OSError as exc:
        print(json.dumps({"error": f"cannot read claim: {exc}"}))
        return 2
    except (json.JSONDecodeError, DomainUseCaseError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verdict"] == VERDICT_ERFUELLT else 1


if __name__ == "__main__":
    sys.exit(main())
