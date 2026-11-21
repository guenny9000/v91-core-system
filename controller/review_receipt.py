"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Review-Receipt-Envelope (MAX-BEST, VIBE-XXXV; Issue #167): versionierter,
ED25519-signierter Umschlag, der die persistente QuorumLedger-Stimme mit
den vom quorum_evaluator geforderten Disclosure-Feldern versiegelt.

Problem (Reconciliation 21.11.2026, Kommentar zu #167): Das Ledger-Schema
signiert agent_id/proposal_digest/epoch/sequence/approve/issued_at/
policy_version, aber NICHT provider/model, stance, rationale, evidence.
quorum_evaluator wertet genau diese Felder aus, verlangt sie aber
ungsigniert. Beide Systeme sind NICHT austauschbar; diese Luecke wird
hier geschlossen, indem der Disclosure KEIN unsignierter Anhang bleibt.

Regeln (fail-closed):
- Der Umschlag signiert ALLE Felder inkl. provider/model, stance,
  rationale, evidence (crypto_receipts.sign_record, REUSE).
- vote_binding_hash = SHA-256 ueber die kanonischen Bytes der KOMPLETTEN
  signierten Legacy-Stimme (inkl. deren Signatur). Jede Veraenderung an
  Stimme ODER Umschlag bricht die Paarung.
- Legacy-Stimmen bleiben unveraendert (explizite Versionsgrenze:
  receipt_schema_version "v1"; keine Migration, keine Rueckschreibung).
- evaluate_ledger_reviews verwirft jede Stimme ohne gueltigen
  Umschlag (UNSIGNED SIDECAR != SIGNIERTER DISCLOSURE), jeden Umschlag
  ohne passende Stimme, jede Diskrepanz bei policy_version.

REUSE (NO_DUPLICATE_SYSTEMS):
  crypto_receipts    kanonische Bytes + Ed25519 sign/verify
  quorum_ledger      Strukturpruefung der Stimme (vote_fields_valid),
                     Persistenz/Replay bleibt dort
  agent_consensus    Semantik-Spiegel des Konsensus (Digest, Epoche,
                     Sequenz-Floor, Zeitfenster, Einzigkeit je Agent)
  quorum_evaluator   Entscheidung inkl. Unabhaengigkeits-Gruppierung

Honest limits:
- SIGNIERT != WAHR: Ed25519 beweist Urheberschaft des Disclosures,
  nicht die Wahrheit der Bewertung (SOURCE != TRUTH).
- INDEPENDENCE != PROVEN: provider/model sind signierte Claims.
- RECEIPTS != LEDGER: Persistenz des Umschlags bleibt Caller-Pflicht,
  dieses Modul bewertet nur Records.
- EVALUATION != AUTHORIZATION: Ergebnisse genehmigen nichts.
- SIGNIERTER DISCLOSURE != ANGEWENDETE PRUEFUNG: der Umschlag selbst
  hat noch keine dritte Instanz geprueft.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Sequence

from controller.crypto_receipts import (
    SIGNATURE_FIELD,
    canonical_record_bytes,
    sign_record,
    verify_record_signature,
)
from controller.quorum_ledger import SIGNATURE_ALGORITHM, vote_fields_valid
from controller.agent_consensus import ConsensusResult, Decision, Vote
from controller.quorum_evaluator import (
    ALLOWED_STANCES,
    ReviewVote,
    ReviewDecision,
    evaluate_independent_quorum,
)

RECEIPT_RECORD_TYPE = "review_receipt"
RECEIPT_SCHEMA_VERSION = "v1"
_PLACEHOLDER_SIGNATURE = "0" * 64


class ReviewReceiptError(RuntimeError):
    """Fail-closed: unzulaessiger Receipt-Zustand."""


def _vote_binding_hash(vote_record: Dict) -> str:
    """SHA-256 ueber die kanonischen Bytes der kompletten signierten Stimme."""
    return hashlib.sha256(canonical_record_bytes(vote_record)).hexdigest()


def _stance_matches_approve(stance: str, approve: bool) -> bool:
    if stance == "APPROVE":
        return approve is True
    if stance in ("REJECT", "ABSTAIN"):
        return approve is False
    return False


def receipt_fields_valid(receipt: Any) -> bool:
    """Strukturelle Pruefung des Umschlags (ohne Signaturbeweis)."""
    if not isinstance(receipt, dict):
        return False
    if receipt.get("record_type") != RECEIPT_RECORD_TYPE:
        return False
    if receipt.get("receipt_schema_version") != RECEIPT_SCHEMA_VERSION:
        return False
    if receipt.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        return False
    if not isinstance(receipt.get("agent_id"), str) or not receipt["agent_id"].strip():
        return False
    for field in ("provider", "model", "stance", "rationale", "policy_version"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            return False
    if receipt.get("stance") not in ALLOWED_STANCES:
        return False
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or any(
            not isinstance(e, str) or not e.strip() for e in evidence):
        return False
    if receipt.get("stance") in ("APPROVE", "REJECT") and not evidence:
        return False
    if type(receipt.get("approve")) is not bool:
        return False
    if not isinstance(receipt.get("vote_binding_hash"), str):
        return False
    if type(receipt.get("epoch")) is not int or receipt["epoch"] < 0:
        return False
    if type(receipt.get("sequence")) is not int or receipt["sequence"] < 1:
        return False
    if type(receipt.get("issued_at")) is not int or receipt["issued_at"] < 0:
        return False
    return True


def build_review_receipt(
        vote_record: Mapping,
        *,
        provider: str,
        model: str,
        stance: str,
        rationale: str,
        evidence: Sequence[str],
        private_key: bytes,
) -> Dict:
    """Erzeugt den signierten Umschlag zu EINER bereits signierten Stimme.

    Fail-closed: die Stimme muss strukturell gueltig und signiert sein;
    stance muss zum signierten approve-Bit der Stimme passen.
    """
    if not isinstance(vote_record, Mapping) or not vote_fields_valid(dict(vote_record)):
        raise ReviewReceiptError("vote record invalid; fail closed")
    if SIGNATURE_FIELD not in vote_record:
        raise ReviewReceiptError("vote must already be signed; fail closed")
    if stance not in ALLOWED_STANCES:
        raise ReviewReceiptError("stance not in ALLOWED_STANCES")
    if not _stance_matches_approve(stance, vote_record["approve"]):
        raise ReviewReceiptError("stance does not match signed approve bit")
    if not isinstance(provider, str) or not provider.strip():
        raise ReviewReceiptError("provider missing")
    if not isinstance(model, str) or not model.strip():
        raise ReviewReceiptError("model missing")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ReviewReceiptError("rationale missing (CLAIM != EVIDENCE)")
    if not isinstance(evidence, (list, tuple)):
        raise ReviewReceiptError("evidence must be a list or tuple")
    evidence_list = list(evidence)
    if stance in ("APPROVE", "REJECT") and not evidence_list:
        raise ReviewReceiptError("evidence missing for stance (CLAIM != EVIDENCE)")
    if any(not isinstance(e, str) or not e.strip() for e in evidence_list):
        raise ReviewReceiptError("evidence entries must be non-empty strings")

    receipt: Dict = {
        "record_type": RECEIPT_RECORD_TYPE,
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "agent_id": vote_record["agent_id"],
        "proposal_digest": vote_record["proposal_digest"],
        "epoch": vote_record["epoch"],
        "sequence": vote_record["sequence"],
        "approve": vote_record["approve"],
        "issued_at": vote_record["issued_at"],
        "policy_version": vote_record["policy_version"],
        "provider": provider,
        "model": model,
        "stance": stance,
        "rationale": rationale,
        "evidence": evidence_list,
        "vote_binding_hash": _vote_binding_hash(dict(vote_record)),
    }
    if not receipt_fields_valid(receipt):
        raise ReviewReceiptError("receipt fields invalid; fail closed")
    receipt[SIGNATURE_FIELD] = sign_record(receipt, private_key)
    return receipt


def verify_review_receipt(receipt: Any, public_key: bytes) -> bool:
    """Struktur + Ed25519-Signatur des Umschlags; jede Rueckgabe ausser
    True ist Nein."""
    if not receipt_fields_valid(receipt):
        return False
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        return False
    return verify_record_signature(receipt, public_key)


def receipt_binds_to_vote(receipt: Any, vote_record: Any) -> bool:
    """Paarungspruefung: Feld-Gleichheit UND binding-hash ueber die
    komplette signierte Stimme (jede Abweichung bricht die Bindung)."""
    if not receipt_fields_valid(receipt):
        return False
    if not isinstance(vote_record, Mapping) or not vote_fields_valid(dict(vote_record)):
        return False
    for field in ("agent_id", "proposal_digest", "policy_version"):
        if receipt.get(field) != vote_record.get(field):
            return False
    for field in ("epoch", "sequence", "issued_at"):
        if receipt.get(field) != vote_record.get(field):
            return False
    if receipt.get("approve") is not vote_record.get("approve"):
        return False
    if not _stance_matches_approve(receipt["stance"], vote_record["approve"]):
        return False
    return receipt["vote_binding_hash"] == _vote_binding_hash(dict(vote_record))


def _ledger_consensus_evaluator(votes, *, member_keys, proposal_digest,
                                epoch, now, min_sequence_by_agent,
                                quorum, allowed_clock_skew_seconds):
    """Konsensus-Semantik-Spiegel fuer LEDGER-verifizierte Stimmen.

    Die Ed25519-Signatur- und Replay-Pruellung der Stimme hat bereits
    der QuorumLedger beim Laden/Anhaengen erledigt (REUSE; nicht hier
    wiederholt). Dieser Adapter prueft NUR die restliche Konsensus-
    Semantik (digest, epoch, Sequenz-Floor, Zeitfenster, Einzigkeit je
    Agent), analog agent_consensus.evaluate_consensus. HMAC- und
    Ed25519-Pfade bleiben bewusst getrennt (siehe quorum_ledger).
    Typfehler je Feld werden fail-closed als invalid vermerkt.
    """
    valid_by_agent: dict = {}
    invalid: list = []
    for vote in votes:
        if not isinstance(vote, Vote):
            invalid.append("malformed vote envelope")
            continue
        agent = vote.agent_id
        if agent not in member_keys:
            invalid.append("%s: unknown member" % agent)
            continue
        if vote.proposal_digest != proposal_digest or vote.epoch != epoch:
            invalid.append("%s: proposal or epoch mismatch" % agent)
            continue
        floor = min_sequence_by_agent.get(agent)
        if type(floor) is not int or floor < 0 or vote.sequence <= floor:
            invalid.append("%s: stale or untracked sequence" % agent)
            continue
        if abs(now - vote.issued_at) > allowed_clock_skew_seconds:
            invalid.append("%s: timestamp outside allowed window" % agent)
            continue
        valid_by_agent.setdefault(agent, []).append(vote)

    yes: list = []
    no: list = []
    for agent, agent_votes in sorted(valid_by_agent.items()):
        if len(agent_votes) != 1:
            invalid.append("%s: duplicate valid votes" % agent)
            continue
        (yes if agent_votes[0].approve else no).append(agent)
    decision = (Decision.ACCEPT if len(yes) >= quorum else
                Decision.REJECT if len(no) >= quorum else Decision.NO_QUORUM)
    return ConsensusResult(decision, quorum, len(yes), len(no),
                           tuple(sorted(yes)), tuple(sorted(no)), tuple(invalid))


def evaluate_ledger_reviews(
        ledger_records: Sequence[Mapping],
        receipts: Sequence[Mapping],
        public_keys: Mapping[str, bytes],
        *,
        proposal_digest: str,
        epoch: int,
        now: int,
        expected_policy_version: str,
        min_sequence_by_agent: Mapping[str, int],
        independent_sources_required: int = 2,
        allowed_clock_skew_seconds: int = 60,
) -> Dict:
    """Independence-aware Auswertung persistenter Stimmen mit Umschlaegen.

    - Stimme ohne gueltigen Umschlag: wird NIE gezaehlt
      (UNSIGNED SIDECAR != SIGNIERTER DISCLOSURE).
    - Umschlag ohne Stimme, falsche Signatur, gebrochene Bindung,
      falsche policy_version: jeweils invalid, fail-closed.
    - Semantikpruefung via _ledger_consensus_evaluator, Entscheidung und
      Unabhaengigkeits-Gruppierung via quorum_evaluator (REUSE).
    - Bewertet nur: keine Ausfuehrung, keine Autorisierung.
    """
    if not isinstance(ledger_records, (list, tuple)):
        raise ReviewReceiptError("ledger_records must be a list or tuple")
    if not isinstance(receipts, (list, tuple)):
        raise ReviewReceiptError("receipts must be a list or tuple")
    if not isinstance(public_keys, Mapping) or not public_keys:
        raise ReviewReceiptError("public_keys must be a non-empty mapping")
    if not isinstance(expected_policy_version, str) or not expected_policy_version.strip():
        raise ReviewReceiptError("expected_policy_version missing")

    votes_by_key: dict = {}
    for record in ledger_records:
        if not isinstance(record, Mapping) or not vote_fields_valid(dict(record)):
            raise ReviewReceiptError("ledger record invalid; fail closed")
        key = (record["agent_id"], record["sequence"])
        if key in votes_by_key:
            raise ReviewReceiptError("duplicate ledger record; fail closed")
        votes_by_key[key] = record

    reviews: list = []
    local_invalid: list = []
    consumed_keys: set = set()
    for receipt in receipts:
        agent_id = receipt.get("agent_id") if isinstance(receipt, Mapping) else None
        if not receipt_fields_valid(receipt):
            local_invalid.append("malformed receipt envelope")
            continue
        public_key = public_keys.get(agent_id)
        if not isinstance(public_key, bytes) or len(public_key) != 32:
            local_invalid.append("%s: unknown agent" % agent_id)
            continue
        if not verify_review_receipt(receipt, public_key):
            local_invalid.append("%s: receipt signature verification failed" % agent_id)
            continue
        key = (agent_id, receipt["sequence"])
        vote_record = votes_by_key.get(key)
        if vote_record is None or key in consumed_keys:
            local_invalid.append("%s: receipt without matching ledger vote" % agent_id)
            continue
        if not receipt_binds_to_vote(receipt, vote_record):
            local_invalid.append("%s: receipt binding failed (BINDING != BEHAUPTET)" % agent_id)
            continue
        if receipt["policy_version"] != expected_policy_version:
            local_invalid.append("%s: policy version mismatch" % agent_id)
            continue
        consumed_keys.add(key)
        reviews.append(ReviewVote(
            vote=Vote(agent_id=agent_id,
                      proposal_digest=receipt["proposal_digest"],
                      epoch=receipt["epoch"],
                      sequence=receipt["sequence"],
                      issued_at=receipt["issued_at"],
                      approve=receipt["approve"],
                      signature=_PLACEHOLDER_SIGNATURE),
            provider=receipt["provider"],
            model=receipt["model"],
            stance=receipt["stance"],
            rationale=receipt["rationale"],
            evidence=tuple(receipt["evidence"]),
        ))

    for key in votes_by_key:
        if key not in consumed_keys:
            local_invalid.append(
                "%s: vote without signed disclosure (UNSIGNED SIDECAR != "
                "SIGNIERTER DISCLOSURE)" % key[0])

    replay_floors = dict(min_sequence_by_agent)
    for agent_id in public_keys:
        replay_floors.setdefault(agent_id, 0)

    if reviews:
        result = evaluate_independent_quorum(
            reviews,
            member_keys=dict(public_keys),
            proposal_digest=proposal_digest,
            epoch=epoch,
            now=now,
            min_sequence_by_agent=replay_floors,
            independent_sources_required=independent_sources_required,
            allowed_clock_skew_seconds=allowed_clock_skew_seconds,
            quorum_evaluator=_ledger_consensus_evaluator)
        payload = result.as_dict()
    else:
        payload = {
            "decision": ReviewDecision.NO_QUORUM.value,
            "independent_sources_required": independent_sources_required,
            "approved_sources": [], "rejected_sources": [],
            "abstained_sources": [], "voided_sources": [],
            "invalid_reasons": [], "independence_note": "",
        }

    merged_invalid = local_invalid + [
        ("ledger layer: " + reason) if not reason.startswith("crypto layer:") else reason
        for reason in payload.get("invalid_reasons", [])]
    payload["invalid_reasons"] = merged_invalid
    payload["schema"] = "v91.review_receipt.v1"
    payload["authorization"] = "NONE (EVALUATION != AUTHORIZATION)"
    return payload
