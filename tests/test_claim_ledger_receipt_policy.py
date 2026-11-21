"""
Integrationstests fuer das Receipt-Gate in claim_ledger (VIBE-XLV
Phase 3): Ein abgelehnter Author-Receipt wirft ReceiptVerificationError
UND laesst die Ledger-Datei byte-identisch unberuehrt; ein gueltiger
Receipt erlaubt den Append; ohne Policy bleibt das Phase-2-Verhalten
erhalten (rueckwaertskompatibel). REJECTED != GESPEICHERT.
"""
import tempfile
import unittest
from pathlib import Path

from controller.author_receipt_guard import (
    AuthorReceipt,
    ClaimBindingContext,
    canonical_receipt_payload,
)
from controller.claim_ledger import (
    ClaimLedger,
    ReceiptPolicy,
    ReceiptVerificationError,
    build_claim_event,
)
from controller.crypto_receipts import generate_signing_keypair

KEYS = {
    "session-a": generate_signing_keypair(),
    "session-b": generate_signing_keypair(),
}
PUBLIC = {author: pub for author, (_, pub) in KEYS.items()}
BASE_SHA = "a" * 40
NOW = 2000

TRUSTED = {"k-valid": "session-a", "k-revoked": "session-a"}


def verify_fn(payload, signature, key_id):
    return signature == "sig::" + key_id + "::" + payload


def policy(require_verified_receipt=True, revoked_keys=()):
    return ReceiptPolicy(
        trusted_keys=TRUSTED,
        verify_signature_fn=verify_fn,
        now_epoch_fn=lambda: NOW,
        revoked_keys=revoked_keys,
        require_verified_receipt=require_verified_receipt,
    )


def receipt_for(record, key_id="k-valid", signature=None):
    body = AuthorReceipt(
        signer_id=record["author"], key_id=key_id, signature="",
        issued_at_epoch=NOW - 100, expires_at_epoch=NOW + 3600,
        claimed_author=record["author"],
    )
    ctx = ClaimBindingContext(
        task_id=record["task_id"],
        scope=record["scope"],
        event_type=record["event"],
        expected_base_sha=record.get("expected_base_sha", ""),
        author_claim=record["author"],
        now_epoch=NOW,
    )
    payload = canonical_receipt_payload(ctx, body)
    sig = signature if signature is not None else "sig::" + key_id + "::" + payload
    return AuthorReceipt(
        signer_id=record["author"], key_id=key_id, signature=sig,
        issued_at_epoch=NOW - 100, expires_at_epoch=NOW + 3600,
        claimed_author=record["author"],
    )


def claim_record(author="session-a", task_id="VIBE-X", scope="controller/example.py",
                 sequence=1, issued_at=1000, expires_at=1100):
    return build_claim_event(
        event="CLAIM", author=author, task_id=task_id, scope=scope,
        sequence=sequence, issued_at=issued_at,
        private_key=KEYS[author][0],
        expected_base_sha=BASE_SHA, expires_at=expires_at,
    )


def done_record(author="session-a", task_id="VIBE-X", scope="controller/example.py",
                sequence=2, issued_at=1200):
    return build_claim_event(
        event="DONE", author=author, task_id=task_id, scope=scope,
        sequence=sequence, issued_at=issued_at,
        private_key=KEYS[author][0],
    )


class AppendWithReceiptTests(unittest.TestCase):

    def test_rejected_receipt_writes_nothing_to_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            pol = policy(revoked_keys=("k-revoked",))
            ok = claim_record()
            ledger.append_event(ok, receipt=receipt_for(ok), receipt_policy=pol)
            self.assertEqual(1, ledger.entry_count())
            raw_before = path.read_bytes()

            revoked = claim_record(task_id="VIBE-XLV-B", scope="controller/b.py", sequence=1)
            with self.assertRaises(ReceiptVerificationError) as ctx_err:
                ledger.append_event(
                    revoked, receipt=receipt_for(revoked, key_id="k-revoked"),
                    receipt_policy=pol,
                )
            self.assertEqual("revoked_key", ctx_err.exception.evaluation.reason)
            self.assertEqual(raw_before, path.read_bytes())
            self.assertEqual(1, ledger.entry_count())

            bad_sig = claim_record(task_id="VIBE-XLV-C", scope="controller/c.py", sequence=1)
            with self.assertRaises(ReceiptVerificationError):
                ledger.append_event(
                    bad_sig, receipt=receipt_for(bad_sig, signature="sig::k-valid::forged"),
                    receipt_policy=pol,
                )
            self.assertEqual(raw_before, path.read_bytes())

            done = done_record()
            ledger.append_event(done, receipt=receipt_for(done), receipt_policy=pol)
            self.assertEqual(2, ledger.entry_count())
            raw_after = path.read_bytes()
            self.assertEqual(2, len(raw_after.strip().split(b"
")))
            self.assertTrue(raw_after.endswith(b"
"))
            reloaded = ClaimLedger(path, PUBLIC, ["operator"])
            self.assertEqual(2, reloaded.entry_count())

    def test_missing_receipt_fail_closed_with_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            rec = claim_record()
            with self.assertRaises(ReceiptVerificationError) as ctx_err:
                ledger.append_event(rec, receipt=None, receipt_policy=policy())
            self.assertEqual("missing_author_receipt", ctx_err.exception.evaluation.reason)
            self.assertFalse(path.exists())

    def test_missing_receipt_allowed_as_claim_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            rec = claim_record()
            ledger.append_event(
                rec, receipt=None,
                receipt_policy=policy(require_verified_receipt=False),
            )
            self.assertEqual(1, ledger.entry_count())

    def test_receipt_bound_to_other_context_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            first = claim_record()
            signed_for_first = receipt_for(first)
            other = claim_record(task_id="VIBE-OTHER", scope="controller/other.py", sequence=1)
            with self.assertRaises(ReceiptVerificationError) as ctx_err:
                ledger.append_event(
                    other, receipt=signed_for_first, receipt_policy=policy(),
                )
            self.assertEqual("invalid_signature", ctx_err.exception.evaluation.reason)
            self.assertFalse(path.exists())


class BackwardCompatibilityTests(unittest.TestCase):

    def test_append_without_policy_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim_record())
            ledger.append_event(done_record())
            self.assertEqual(2, ledger.entry_count())

    def test_append_with_receipt_but_no_policy_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            rec = claim_record()
            ledger.append_event(rec, receipt=None)  # no receipt, no policy
            self.assertEqual(1, ledger.entry_count())

    def test_reload_with_policy_then_gate_still_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            first = ClaimLedger(path, PUBLIC, ["operator"])
            rec = claim_record()
            first.append_event(rec, receipt=receipt_for(rec), receipt_policy=policy())
            reloaded = ClaimLedger(path, PUBLIC, ["operator"])
            done = done_record()
            with self.assertRaises(ReceiptVerificationError):
                reloaded.append_event(done, receipt=None, receipt_policy=policy())
            self.assertEqual(1, reloaded.entry_count())
            reloaded.append_event(done, receipt=receipt_for(done),
                                  receipt_policy=policy())
            self.assertEqual(2, reloaded.entry_count())


if __name__ == "__main__":
    unittest.main()
