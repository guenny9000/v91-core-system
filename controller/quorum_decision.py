"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Auswertung dauerhaft gespeicherter, Ed25519-verifizierter Abstimmungs-
belege (QuorumLedger) zu einer quorum-basierten ENTSCHEIDUNG ueber
einen konkreten Proposal-Digest. Issue #167: persistente Stimmen sollen
zu einer nachvollziehbaren, replizierbaren Entscheidung fuehren.

Ehrliche Grenzen (bewusst, keine Luecken):
- ENTSCHEIDUNG != AUSFUEHRUNG: Dieses Modul erlaubt nichts und fuehrt
  nichts aus. Jede Ausfuehrung bleibt an menschliche Freigabe,
  Faehigkeits-, Policy- und Zustandspruefungen gebunden.
- SIGNATUR != WAHRHEIT: Ed25519 beweist die Urheberschaft einer Stimme,
  NICHT die Richtigkeit ihrer Bewertung.
- Die Signaturen und die Hash-Kette wurden vom QuorumLedger beim Laden
  fail-closed geprueft. Dieses Modul enthaelt keinen eigenen Krypto-Code
  und vertraut ausschliesslich einem echten QuorumLedger.
- Der HMAC-Konsens (agent_consensus) und die ephemere Orchestrierung
  (agent_quorum) bleiben getrennte Systeme. Dieses Modul ist die
  Auswertungsbruecke fuer persistente Ed25519-Belege, kein Ersatz und
  keine zweite Orchestrierung (NO_DUPLICATE_SYSTEMS).
- Eine fehlende Stimme (kein Beleg) zaehlt weder als Zustimmung noch als
  Ablehnung; sie fuehrt hoechstens zu NO_QUORUM. Abstention existiert im
  Belegformat nicht.
- Die Mitgliederliste muss aus unabhaengig verwaltetem, vertrauens-
  wuerdigem Kontext stammen, NICHT aus dem Ledger gelesen werden.
"""
from __future__ import annotations

from dataclasses import dataclass

from controller.agent_consensus import Decision

HEX64 = set("0123456789abcdef")


class QuorumDecisionError(ValueError):
    """Fail-closed Fehler der Beleg-Auswertung."""


@dataclass(frozen=True)
class RecordedDecision:
    """Ergebnis der Auswertung persistenter Abstimmungsbelege."""
    decision: Decision
    quorum_required: int
    yes: tuple
    no: tuple
    excluded: tuple          # Aussgruende, sortiert, lesbare Strings
    matched_records: int     # Belege zum Digest/Epoche/Policy (vor Memberfilter)


def _is_hex64(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in HEX64 for c in value))


def _is_int(value: object) -> bool:
    return type(value) is int


def evaluate_recorded_votes(ledger, *, proposal_digest, epoch, policy_version,
                            member_ids, quorum=None) -> RecordedDecision:
    """Wertet gespeicherte, bereits verifizierte Belege eines QuorumLedger aus.

    Ordnungsunabhaengig: Ein Agent mit mehr als einem gueltigen Beleg zum
    selben Digest verwirft seinen Beitrag vollständig; unpassende Belege
    (anderer Digest, andere Epoche, andere Policy-Version) werden ignoriert
    und verhindern spaetere gueltige Belege desselben Agenten nicht.
    Faehige Mehrheiten: required = quorum oder len(member_ids)//2 + 1.
    """
    records_method = getattr(ledger, "records", None)
    if not callable(records_method):
        raise QuorumDecisionError("ledger must be a QuorumLedger with records()")
    if not _is_hex64(proposal_digest):
        raise QuorumDecisionError("proposal_digest must be lowercase sha256 hex")
    if not _is_int(epoch) or epoch < 0:
        raise QuorumDecisionError("epoch must be a non-negative integer")
    if (not isinstance(policy_version, str)
            or not policy_version.strip()):
        raise QuorumDecisionError("policy_version must be a non-empty string")
    if not isinstance(member_ids, (tuple, list)) or not member_ids:
        raise QuorumDecisionError("member_ids must be a non-empty tuple or list")
    members = []
    for member in member_ids:
        if not isinstance(member, str) or not member.strip():
            raise QuorumDecisionError("each member id must be a non-empty string")
        if member in members:
            raise QuorumDecisionError("duplicate member id: " + member)
        members.append(member)
    member_set = frozenset(members)
    required = quorum if quorum is not None else len(members) // 2 + 1
    if not _is_int(required) or not 1 <= required <= len(members):
        raise QuorumDecisionError(
            "quorum must be between 1 and the member count")

    matched: dict = {}
    excluded: list = []
    matched_records = 0
    for record in ledger.records():
        if not isinstance(record, dict):
            excluded.append("malformed record envelope")
            continue
        agent_id = record.get("agent_id")
        if (record.get("proposal_digest") != proposal_digest
                or record.get("epoch") != epoch
                or record.get("policy_version") != policy_version):
            continue  # gehoert zu einer anderen Abstimmung; hier irrelevant
        if not isinstance(agent_id, str) or not agent_id.strip():
            excluded.append("record without valid agent id")
            continue
        matched_records += 1
        if agent_id not in member_set:
            excluded.append(agent_id + ": not a configured member")
            continue
        matched.setdefault(agent_id, []).append(record)

    yes: list = []
    no: list = []
    for agent_id in members:
        agent_records = matched.get(agent_id, [])
        if len(agent_records) == 0:
            continue  # fehlende Stimme: weder ja noch nein
        if len(agent_records) > 1:
            excluded.append(agent_id + ": conflicting recorded votes")
            continue
        (yes if agent_records[0]["approve"] is True else no).append(agent_id)

    decision = (Decision.ACCEPT if len(yes) >= required else
                Decision.REJECT if len(no) >= required else Decision.NO_QUORUM)
    return RecordedDecision(
        decision=decision,
        quorum_required=required,
        yes=tuple(sorted(yes)),
        no=tuple(sorted(no)),
        excluded=tuple(sorted(excluded)),
        matched_records=matched_records,
    )
