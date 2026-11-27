#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
V91 Issue #492 Stufe-1-Rest: Text-Abgleich V91-COMMS-1 vs V91-CONTRIBUTION-1.

Zweck: Die Bestandsaufnahme #582 (Stufe 1, Verdikt TEILWEISE) stellte fest,
dass die Code-Konstanten die COMMS-1-Kette zwar kodieren, ein vollstaendiger
TEXT-Abgleich zwischen docs/V91_LEARNING_BLOCK_COMMUNICATION_PROTOCOL.md
(V91-COMMS-1-Grundlage) und docs/V91-CONTRIBUTION-1.md NICHT durchgefuehrt
wurde. Dieses Modul macht diesen Abgleich reproduzierbar: Es misst die
Statusketten, Feldlisten und Regelgegenstuecke beider Dokumente und liefert
einen Bericht. Es veraendert nichts, speichert nichts, ruft kein Netzwerk
auf und wertet nicht auf (CLAIM != EVIDENCE, TEXTABGLEICH != INHALTSPRUEFUNG,
ABGLEICH != FREIGABE).

Grenzen: Ein Wort- und Kettenabgleich beweist keine inhaltliche Richtigkeit
oder vollstaendige Regelentsprechung; er prueft nur die hier kodierten
Vergleichspunkte. Semantische Abweichungen bleiben Textbefunde, keine
Maschinenurteile ueber Sinnhaftigkeit.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Pfade relativ zum Repo-Wurzelverzeichnis, absicherbar vom Aufrufer.
COMMS_DOC_PATH = "docs/V91_LEARNING_BLOCK_COMMUNICATION_PROTOCOL.md"
CONTRIBUTION_DOC_PATH = "docs/V91-CONTRIBUTION-1.md"
SCHEMA_PATH = "schemas/contribution.schema.json"

EVIDENCE_CHAIN: Tuple[str, ...] = (
    "UNKNOWN", "DOCUMENTED", "IMPLEMENTED", "TESTED",
    "VERIFIED", "AUDITED", "PRODUCTION",
)
WORKFLOW_CHAIN: Tuple[str, ...] = (
    "RECEIVED", "TRIAGED", "TESTING", "ACCEPTED",
    "INTEGRATED", "REJECTED", "DEFERRED",
)

_ARROW = "\\u2192"  # Pfeil als Regex-Escape, damit diese Datei ASCII-pure bleibt.

_EVIDENCE_LINE_RE = re.compile(
    "UNKNOWN\\s*" + _ARROW + r".*?PRODUCTION"
)
_WORKFLOW_LINE_RE = re.compile(
    r"RECEIVED,\s*TRIAGED,\s*TESTING,\s*ACCEPTED,\s*INTEGRATED,\s*"
    r"REJECTED\s+oder\s+DEFERRED"
)


def _extract_chain(text: str, pattern: re.Pattern[str]) -> Optional[List[str]]:
    """Extrahiert eine Statuskette aus dem ersten Musterfund."""
    match = pattern.search(text)
    if match is None:
        return None
    tokens = re.findall(r"[A-Z]{4,}", match.group(0))
    return tokens if tokens else None


def _extract_fields(text: str, start_marker: str, end_marker: str) -> List[str]:
    """Extrahiert zur Attributliste gehoerige Backtick-Feldnamen eines Abschnitts."""
    start = text.find(start_marker)
    if start < 0:
        return []
    end = text.find(end_marker, start)
    section = text[start:] if end < 0 else text[start:end]
    return re.findall(r"`([a-z][a-z0-9_]+)`", section)


def _schema_enums(schema_text: str) -> Dict[str, List[str]]:
    """Liest enum-Listen aus dem Schema-JSON in Fundreihenfolge."""
    data = json.loads(schema_text)
    found: Dict[str, List[str]] = {}
    for match in re.finditer(r'"enum":\s*\[([^\]]*)\]', schema_text):
        values = re.findall(r'"([A-Z]+)"', match.group(1))
        found["enum_%d" % (len(found) + 1)] = values
    del data  # nur Textmessung; JSON-Parsing diente der Gueltigkeitsprobe
    return found


def compare_texts(
    comms_text: str,
    contribution_text: str,
    schema_text: Optional[str] = None,
    contribution_intake_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Vergleicht beide Protokolldokumente Punkt fuer Punkt.

    Rueckgabe ist ein reiner Befundbericht (dict). Er enthaelt KEINE
    Bewertung, Freigabe oder Empfehlung; Verdikte werden im
    Abgleich-Dokument textlich begruendet, nicht hier erfunden.
    """
    report: Dict[str, Any] = {}

    chain_comms = _extract_chain(comms_text, _EVIDENCE_LINE_RE)
    chain_contribution = _extract_chain(contribution_text, _EVIDENCE_LINE_RE)
    report["evidence_chain_comms"] = chain_comms
    report["evidence_chain_contribution"] = chain_contribution
    report["evidence_chain_identical"] = (
        chain_comms is not None
        and chain_comms == chain_contribution
        and tuple(chain_comms) == EVIDENCE_CHAIN
    )

    workflow_in_comms = _extract_chain(comms_text, _WORKFLOW_LINE_RE)
    report["workflow_chain_in_comms"] = workflow_in_comms
    workflow_in_contribution = _extract_chain(
        contribution_text, _WORKFLOW_LINE_RE
    )
    report["workflow_chain_in_contribution"] = workflow_in_contribution
    report["workflow_chain_matches_reference"] = (
        workflow_in_contribution is not None
        and tuple(workflow_in_contribution) == WORKFLOW_CHAIN
    )

    comms_fields = _extract_fields(
        comms_text, "## 4. Agenten-Kommunikationsvertrag", "## 5."
    )
    contribution_fields = _extract_fields(
        contribution_text, "## Pflichtfelder", "## Status und Pr"
    )
    report["comms_task_fields"] = comms_fields
    report["contribution_fields"] = contribution_fields
    overlap = sorted(set(comms_fields) & set(contribution_fields))
    report["field_overlap"] = overlap
    report["only_comms_fields"] = sorted(set(comms_fields) - set(contribution_fields))
    report["only_contribution_fields"] = sorted(
        set(contribution_fields) - set(comms_fields)
    )

    if schema_text is not None:
        enums = _schema_enums(schema_text)
        report["schema_evidence_enum_matches"] = (
            enums.get("enum_1") == list(EVIDENCE_CHAIN)
        )
        report["schema_workflow_enum_matches"] = (
            enums.get("enum_2") == list(WORKFLOW_CHAIN)
        )

    if contribution_intake_status is not None:
        ev_source = contribution_intake_status.get("evidence") or ()
        wf_source = contribution_intake_status.get("workflow") or ()
        # Frozensets sind unsortiert: gegen die kanonische Referenz ordnen,
        # damit der Befund von der Eingabereihenfolge unabhaengig ist.
        ev = [s for s in EVIDENCE_CHAIN if s in set(ev_source)]
        wf = [s for s in WORKFLOW_CHAIN if s in set(wf_source)]
        report["code_evidence_chain_matches"] = (
            len(ev) == len(EVIDENCE_CHAIN) and tuple(ev) == EVIDENCE_CHAIN
        )
        report["code_workflow_chain_matches"] = (
            len(wf) == len(WORKFLOW_CHAIN) and tuple(wf) == WORKFLOW_CHAIN
        )

    # Regelgegenstuecke: Kernschutzregeln gegen Beitragsumschlag-Dokument.
    rules = {
        "claim_is_not_evidence": ("behauptung", "CONTRIBUTION"),
        "no_secrets_in_public_channels": ("Tokens", "CONTRIBUTION"),
        "untrusted_external_content": ("nicht vertrauensw", "CONTRIBUTION"),
        "no_authorization_granted": ("authorization", "CONTRIBUTION"),
        "isolation_before_integration": ("isolierten Branch", "CONTRIBUTION"),
        "offline_usable": ("Offline", "CONTRIBUTION"),
    }
    rule_findings: Dict[str, bool] = {}
    for name, (needle, which) in rules.items():
        text = comms_text if which == "COMMS" else contribution_text
        rule_findings[name] = needle.lower() in text.lower()
    report["rule_counterpart_findings"] = rule_findings
    report["all_rule_counterparts_found"] = all(rule_findings.values())

    return report


def compare_repo_files(repo_root: str) -> Dict[str, Any]:
    """Laedt die drei Referenzdateien und fuehrt den Abgleich aus."""
    from pathlib import Path

    root = Path(repo_root)
    comms_text = (root / COMMS_DOC_PATH).read_text(encoding="utf-8")
    contribution_text = (root / CONTRIBUTION_DOC_PATH).read_text(encoding="utf-8")
    schema_text = (root / SCHEMA_PATH).read_text(encoding="utf-8")

    status: Dict[str, Any] = {}
    try:
        from controller import contribution_intake as ci

        status["evidence"] = tuple(
            sorted(ci.EVIDENCE_STATUSES, key=list(EVIDENCE_CHAIN).index)
        )
        status["workflow"] = tuple(
            sorted(ci.CONTRIBUTION_STATUSES, key=list(WORKFLOW_CHAIN).index)
        )
    except Exception:
        status = {}

    return compare_texts(comms_text, contribution_text, schema_text, status or None)


if __name__ == "__main__":  # Skript-Modus-Echtlauf (#605-Muster)
    import sys

    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = compare_repo_files(repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    incomplete = sorted(key for key, value in result.items() if value is False)
    print("ABGLEICH_UNVOLLSTAENDIG: %s" % ",".join(sorted(incomplete)))
    sys.exit(0)
