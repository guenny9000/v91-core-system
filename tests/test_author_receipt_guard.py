"""
Tests fuer controller/author_receipt_guard (VIBE-XLV Phase 3):
AUTHOR_CLAIM != IDENTITY, fail-closed Pruefung von fehlenden,
unvollstaendigen, widerrufenen, abgelaufenen, falsch gebundenen und
falsch signierten Author-Receipts. SIGNATURE != TRUTH, UNKNOWN != PASS.
"""
import unittest

from controller.author_receipt_guard import (
    AuthorReceipt,
    ClaimBindingContext,
    IdentityVerificationState,
    canonical_receipt_payload,
    evaluate_author_receipt,
)

NOW = 1_763_750_000


def make_context(**overrides):
    base = {
        "task_id": "VIBE-XLV-01",
        "scope": "controller/claim_ledger.py",
        "event_type": "CLAIM",
        "expected_base_sha": "a" * 40,
        "author_claim": "agent-alpha",
        "now_epoch": NOW,
    }
    base.update(overrides)
    return ClaimBindingContext(**base)


def verify_fn(payload, signature, key_id):
    """Deterministischer Pruef-Stub: Signatur bindet an Payload UND key."""
    return signature == "sig::" + key_id + "::" + payload


def make_receipt(ctx, signer_id="agent-alpha", key_id="k-1",
                 issued_at_epoch=NOW - 100, expires_at_epoch=None,
                 claimed_author="agent-alpha", signature=None):
    raw = AuthorReceipt(
        signer_id=signer_id,
        key_id=key_id,
        signature="",
        issued_at_epoch=issued_at_epoch,
        expires_at_epoch=expires_at_epoch,
        claimed_author=claimed_author,
    )
    if signature is None:
        signature = "sig::" + key_id + "::" + canonical_receipt_payload(ctx, raw)
    return AuthorReceipt(
        signer_id=signer_id,
        key_id=key_id,
        signature=signature,
        issued_at_epoch=issued_at_epoch,
        expires_at_epoch=expires_at_epoch,
        claimed_author=claimed_author,
    )


def evaluate(ctx, receipt, trusted_keys=None, **kwargs):
    params = {
        "trusted_keys": trusted_keys if trusted_keys is not None else {"k-1": "agent-alpha"},
        "verify_signature_fn": verify_fn,
    }
    params.update(kwargs)
    return evaluate_author_receipt(ctx, receipt, **params)


class MissingReceiptTests(unittest.TestCase):

    def test_missing_receipt_fail_closed_when_required(self):
        res = evaluate(make_context(), None)
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertFalse(res.permits_ledger_write)
        self.assertEqual("missing_author_receipt", res.reason)
        self.assertEqual("agent-alpha", res.author_claim)
        self.assertIsNone(res.verified_signer_id)

    def test_missing_receipt_marks_claim_only_when_allowed(self):
        res = evaluate(make_context(), None, require_verified_receipt=False)
        self.assertIs(res.state, IdentityVerificationState.UNVERIFIED_CLAIM_ONLY)
        self.assertTrue(res.permits_ledger_write)
        self.assertEqual("author_claim_unverified_no_receipt", res.reason)
        self.assertIsNone(res.verified_signer_id)


class ValidReceiptTests(unittest.TestCase):

    def test_valid_receipt_verifies_identity_and_context(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, expires_at_epoch=NOW + 3600))
        self.assertIs(res.state, IdentityVerificationState.VERIFIED)
        self.assertEqual("agent-alpha", res.verified_signer_id)
        self.assertTrue(res.permits_ledger_write)
        self.assertEqual("receipt_verified", res.reason)

    def test_incomplete_receipt_fields_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, signature=""))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("incomplete_receipt_fields", res.reason)
        self.assertFalse(res.permits_ledger_write)


class RevocationTests(unittest.TestCase):

    def test_revoked_signer_rejected(self):
        ctx = make_context()
        res = evaluate(
            ctx,
            make_receipt(ctx, signer_id="agent-gone"),
            trusted_keys={"k-1": "agent-gone"},
            revoked_signers=["agent-gone"],
        )
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("revoked_signer", res.reason)

    def test_revoked_key_rejected(self):
        ctx = make_context()
        res = evaluate(
            ctx,
            make_receipt(ctx, key_id="k-revoked"),
            trusted_keys={"k-revoked": "agent-alpha", "k-1": "agent-alpha"},
            revoked_keys=["k-revoked"],
        )
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("revoked_key", res.reason)


class TimeWindowTests(unittest.TestCase):

    def test_expired_receipt_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, expires_at_epoch=NOW))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("receipt_expired", res.reason)

    def test_future_issued_receipt_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, issued_at_epoch=NOW + 1))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("receipt_issued_in_future", res.reason)


class BindingTests(unittest.TestCase):

    def test_claimed_author_mismatch_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, claimed_author="agent-beta"))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("claimed_author_mismatch", res.reason)

    def test_untrusted_key_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, key_id="k-unknown"))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("untrusted_or_mismatched_key", res.reason)

    def test_key_bound_to_other_signer_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, signer_id="agent-beta"),
                       trusted_keys={"k-1": "agent-alpha"})
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("untrusted_or_mismatched_key", res.reason)

    def test_context_mutation_invalidates_receipt(self):
        """Receipt fuer Scope A ist fuer Scope B ungueltig (Bindung)."""
        ctx_a = make_context(scope="controller/a.py")
        receipt = make_receipt(ctx_a)
        ctx_b = make_context(scope="controller/b.py")
        res = evaluate(ctx_b, receipt)
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("invalid_signature", res.reason)


class SignatureTests(unittest.TestCase):

    def test_invalid_signature_rejected(self):
        ctx = make_context()
        res = evaluate(ctx, make_receipt(ctx, signature="sig::k-1::forged"))
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("invalid_signature", res.reason)

    def test_verifier_exception_is_rejected(self):
        ctx = make_context()
        def broken_verify(payload, signature, key_id):
            raise RuntimeError("backend down")
        res = evaluate(ctx, make_receipt(ctx), verify_signature_fn=broken_verify)
        self.assertIs(res.state, IdentityVerificationState.REJECTED)
        self.assertEqual("invalid_signature", res.reason)


if __name__ == "__main__":
    unittest.main()
