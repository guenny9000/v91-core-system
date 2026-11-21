"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Fail-closed Author-Receipt-Pruefung (Taskboard-Konvention Phase 3,
VIBE-XLV). Wiederverwendung der claim_ledger/crypto_receipts-Prinzipien.

Grundsaetze:
- AUTHOR_CLAIM != IDENTITY: Ein author_claim ist eine Selbstauskunft
  und wird NIE automatisch als gesicherte Identitaet gewertet.
- SIGNATURE != TRUTH, UNKNOWN != PASS: Auch eine gueltige Signatur
  beweist nur die Schluesselherrschaft, NICHT die Wahrheit der
  Autor-Angabe.
- Fail-closed: Fehlende, unvollstaendige, widerrufene, abgelaufene,
  zeitlich ungueltige, falsch gebundene oder falsch signierte
  Receipts werden klar abgewiesen (REJECTED) oder ehrlich als
  UNVERIFIED_CLAIM_ONLY markiert. Kein stillares Durchwinken.

Ehrliche Grenzen (bewusst, nicht Luecken):
- trusted_keys und Widerrufslisten kommen aus unabhaengig
  vertrauenswuerdigem Caller-Kontext, NIEMALS aus dem Receipt selbst.
- Die kanonische Nutzlast bindet den Receipt an exakten Kontext
  (task_id, scope, event_type, expected_base_sha, author_claim,
  signer, Schluessel, Ausstellungszeit). JEDE Abweichung macht ihn
  ungueltig; ein Receipt fuer einen Kontext gilt nie fuer einen
  anderen.
- SCRIPTED != INSTALLED: Kein laufender Dienst bindet dieses Modul
  bisher ein; die Kopplung an claim_ledger.append_event ist optional
  und rueckwaertskompatibel (Wiring bleibt Folgearbeit).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable


class IdentityVerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED_CLAIM_ONLY = "UNVERIFIED_CLAIM_ONLY"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class AuthorReceipt:
    """Signierter Autor-Beleg; KEINE Selbstauskunft. Der behauptete
    Autor (claimed_author) bleibt Angabe, nur der signierende
    Schluessel-Nachweis kann die Identitaet heben (SIGNATURE != TRUTH)."""
    signer_id: str
    key_id: str
    signature: str
    issued_at_epoch: int
    expires_at_epoch: int | None = None
    claimed_author: str | None = None


@dataclass(frozen=True)
class ClaimBindingContext:
    task_id: str
    scope: str
    event_type: str
    expected_base_sha: str
    author_claim: str
    now_epoch: int


@dataclass(frozen=True)
class ReceiptEvaluation:
    state: IdentityVerificationState
    author_claim: str
    verified_signer_id: str | None
    reason: str
    permits_ledger_write: bool


def _rejected(context: ClaimBindingContext, reason: str) -> ReceiptEvaluation:
    return ReceiptEvaluation(
        state=IdentityVerificationState.REJECTED,
        author_claim=context.author_claim,
        verified_signer_id=None,
        reason=reason,
        permits_ledger_write=False,
    )


def canonical_receipt_payload(
    context: ClaimBindingContext,
    receipt: AuthorReceipt,
) -> str:
    """Kanonische Nutzlast: Receipt gilt NUR fuer exakt diesen Kontext."""
    return "|".join(
        [
            context.task_id,
            context.scope,
            context.event_type,
            context.expected_base_sha,
            context.author_claim,
            receipt.signer_id,
            receipt.key_id,
            str(receipt.issued_at_epoch),
        ]
    )


def evaluate_author_receipt(
    context: ClaimBindingContext,
    receipt: AuthorReceipt | None,
    *,
    trusted_keys: dict[str, str],
    revoked_signers: Iterable[str] = (),
    revoked_keys: Iterable[str] = (),
    verify_signature_fn: Callable[[str, str, str], bool],
    require_verified_receipt: bool = True,
) -> ReceiptEvaluation:
    """
    Prueft einen Author-Receipt strikt fail-closed gegen den Kontext.

    - Ohne Receipt: REJECTED (fail-closed), wenn verifizierte Receipts
      Pflicht sind; sonst ehrlich UNVERIFIED_CLAIM_ONLY.
    - Widerruf, Ablauf, Zukunfts-Ausstellung, unpassende Bindung oder
      Signaturfehler: IMMER REJECTED.
    - Nur gueltiger Schluessel + gueltige Signatur ueber den exakten
      kanonischen Kontext: VERIFIED.
    """
    if receipt is None:
        if require_verified_receipt:
            return _rejected(context, "missing_author_receipt")
        return ReceiptEvaluation(
            state=IdentityVerificationState.UNVERIFIED_CLAIM_ONLY,
            author_claim=context.author_claim,
            verified_signer_id=None,
            reason="author_claim_unverified_no_receipt",
            permits_ledger_write=True,
        )

    if not receipt.signer_id or not receipt.key_id or not receipt.signature:
        return _rejected(context, "incomplete_receipt_fields")

    if receipt.signer_id in set(revoked_signers):
        return _rejected(context, "revoked_signer")

    if receipt.key_id in set(revoked_keys):
        return _rejected(context, "revoked_key")

    if receipt.issued_at_epoch > context.now_epoch:
        return _rejected(context, "receipt_issued_in_future")

    if receipt.expires_at_epoch is not None and context.now_epoch >= receipt.expires_at_epoch:
        return _rejected(context, "receipt_expired")

    if receipt.claimed_author is not None and receipt.claimed_author != context.author_claim:
        return _rejected(context, "claimed_author_mismatch")

    expected_signer = trusted_keys.get(receipt.key_id)
    if not expected_signer or expected_signer != receipt.signer_id:
        return _rejected(context, "untrusted_or_mismatched_key")

    canonical_payload = canonical_receipt_payload(context, receipt)

    try:
        is_valid = bool(verify_signature_fn(canonical_payload, receipt.signature, receipt.key_id))
    except Exception:
        is_valid = False

    if not is_valid:
        return _rejected(context, "invalid_signature")

    return ReceiptEvaluation(
        state=IdentityVerificationState.VERIFIED,
        author_claim=context.author_claim,
        verified_signer_id=receipt.signer_id,
        reason="receipt_verified",
        permits_ledger_write=True,
    )
