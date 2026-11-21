"""
Tests fuer scripts/v91_claim_cli.py (VIBE-XLVI Phase 4): E2E-CLI-
Lebenszyklus claim -> status -> done -> Reload, Doppel-Claim-CONFLICT,
unautorisiertes EXPIRE vor Ablauf, korruptes Ledger fail-closed,
Receipt-Gate (echtes Ed25519-Backend, soweit verfuegbar;
UNKNOWN != PASS, STUB != ECHT). REJECTED != GESPEICHERT.
"""
import importlib.util
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import v91_claim_cli

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
BASE_SHA = "e" * 40


class CliHarness(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.ledger_file = self.tmp_path / "claims.jsonl"
        self.author = "session-a"
        self.priv = b"a" * 32
        self.pub = None
        if HAS_CRYPTO:
            from controller.crypto_receipts import generate_signing_keypair
            self.priv, self.pub = generate_signing_keypair()
        else:
            import hashlib
            self.pub = hashlib.sha256(self.priv).digest()
        self.key_file = self.tmp_path / "key.hex"
        self.key_file.write_text(self.priv.hex(), encoding="utf-8")
        self.keyring_file = self.tmp_path / "keyring.json"
        self.keyring_file.write_text(
            json.dumps(
                {
                    "public_keys": {self.author: self.pub.hex(), "operator": self.pub.hex()},
                    "expire_authorities": ["operator"],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, argv):
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_claim_cli.main(argv)
        out = buf.getvalue().strip()
        payload = json.loads(out) if out else {}
        return code, payload

    def claim_cmd(self, task_id="VIBE-XLVI", scope="scripts/v91_claim_cli.py",
                  author=None, issued_at=1000, ttl=3600, sequence=1, extra=()):
        argv = [
            "claim",
            "--ledger", str(self.ledger_file),
            "--keyring", str(self.keyring_file),
            "--key", str(self.key_file),
            "--author", author or self.author,
            "--task-id", task_id,
            "--scope", scope,
            "--sequence", str(sequence),
            "--issued-at", str(issued_at),
            "--base-sha", BASE_SHA,
            "--ttl-seconds", str(ttl),
        ]
        argv.extend(extra)
        return self.run_cli(argv)

    def follow_cmd(self, command, author=None, task_id="VIBE-XLVI",
                   scope="scripts/v91_claim_cli.py", issued_at=2000, sequence=2, extra=()):
        argv = [
            command,
            "--ledger", str(self.ledger_file),
            "--keyring", str(self.keyring_file),
            "--key", str(self.key_file),
            "--author", author or self.author,
            "--task-id", task_id,
            "--scope", scope,
            "--sequence", str(sequence),
            "--issued-at", str(issued_at),
        ]
        argv.extend(extra)
        return self.run_cli(argv)


class EndToEndTests(CliHarness):

    def test_claim_status_done_reload_lifecycle(self):
        code, payload = self.claim_cmd()
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        self.assertEqual("ACCEPTED", payload["status"])
        self.assertTrue(self.ledger_file.read_bytes().endswith(bytes([10])))

        code, payload = self.run_cli(["status", "--ledger", str(self.ledger_file),
                                      "--keyring", str(self.keyring_file)])
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        self.assertEqual("VERIFIED_CHAIN", payload["status"])
        self.assertEqual(1, payload["entry_count"])
        self.assertEqual({"VIBE-XLVI": self.author}, payload["active_claims"])

        code, payload = self.follow_cmd("done", sequence=2)
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        self.assertEqual("ACCEPTED", payload["status"])

        code, payload = self.run_cli(["status", "--ledger", str(self.ledger_file),
                                      "--keyring", str(self.keyring_file)])
        self.assertNotIn("VIBE-XLVI", payload["active_claims"])
        self.assertEqual(2, payload["entry_count"])

        text = self.ledger_file.read_text(encoding="utf-8")
        self.assertEqual(2, len(text.strip().split(chr(10))))

    def test_double_claim_conflict_exit_two_file_unchanged(self):
        code, _ = self.claim_cmd()
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        raw_before = self.ledger_file.read_bytes()
        code, payload = self.run_cli([
            "claim",
            "--ledger", str(self.ledger_file),
            "--keyring", str(self.keyring_file),
            "--key", str(self.key_file),
            "--author", "session-b",
            "--task-id", "VIBE-XLVI",
            "--scope", "controller/other.py",
            "--sequence", "1",
            "--issued-at", "1500",
            "--base-sha", BASE_SHA,
            "--ttl-seconds", "600",
        ])
        self.assertEqual(v91_claim_cli.EXIT_REJECTED_OR_CONFLICT, code)
        self.assertEqual("REJECTED", payload["status"])
        self.assertFalse(payload["written"])
        self.assertEqual(raw_before, self.ledger_file.read_bytes())


class AuthorizationTests(CliHarness):

    def test_expire_before_deadline_refused(self):
        code, _ = self.claim_cmd()
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        code, payload = self.follow_cmd("expire", author="operator", sequence=1,
                                        issued_at=1100, extra=["--reason", "too early"])
        self.assertEqual(v91_claim_cli.EXIT_REJECTED_OR_CONFLICT, code)
        self.assertEqual("REJECTED", payload["status"])
        self.assertFalse(payload["written"])

    def test_expire_without_reason_refused_as_input_error(self):
        code, _ = self.claim_cmd()
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        code, payload = self.follow_cmd("expire", author="operator", sequence=1, issued_at=9999)
        self.assertEqual(v91_claim_cli.EXIT_USAGE_OR_INPUT, code)
        self.assertEqual("REJECTED", payload["status"])

    def test_claim_without_base_sha_refused_as_input_error(self):
        code, payload = self.run_cli([
            "claim",
            "--ledger", str(self.ledger_file),
            "--keyring", str(self.keyring_file),
            "--key", str(self.key_file),
            "--author", self.author,
            "--task-id", "VIBE-XLVI-B",
            "--scope", "scripts/b.py",
            "--sequence", "1",
            "--issued-at", "1000",
            "--base-sha", "kurz",
            "--ttl-seconds", "600",
        ])
        self.assertEqual(v91_claim_cli.EXIT_USAGE_OR_INPUT, code)
        self.assertFalse(self.ledger_file.exists())


class IntegrityTests(CliHarness):

    def test_status_missing_ledger_is_unknown_not_failure(self):
        code, payload = self.run_cli(["status", "--ledger", str(self.ledger_file),
                                      "--keyring", str(self.keyring_file)])
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        self.assertEqual("UNKNOWN", payload["status"])
        self.assertEqual(0, payload["entry_count"])

    def test_corrupt_ledger_fails_closed_on_status(self):
        self.ledger_file.write_bytes(b'{"corrupt": true}' + bytes([10]))
        code, payload = self.run_cli(["status", "--ledger", str(self.ledger_file),
                                     "--keyring", str(self.keyring_file)])
        self.assertEqual(v91_claim_cli.EXIT_IO_OR_CORRUPT, code)
        self.assertEqual("CORRUPT_OR_INVALID", payload["status"])

    def test_status_missing_keyring_fails_closed(self):
        self.ledger_file.write_bytes(b"")
        code, payload = self.run_cli(["status", "--ledger", str(self.ledger_file),
                                      "--keyring", str(self.tmp_path / "nope.json")])
        self.assertEqual(v91_claim_cli.EXIT_IO_OR_CORRUPT, code)
        self.assertEqual("CORRUPT_OR_INVALID", payload["status"])


@unittest.skipUnless(HAS_CRYPTO, "echtes Ed25519-Backend nicht verfuegbar (STUB != ECHT)")
class ReceiptGateTests(CliHarness):

    def setUp(self):
        super().setUp()
        self.receipt_file = self.tmp_path / "receipt.json"
        self.policy_file = self.tmp_path / "policy.json"
        import time
        from controller.crypto_receipts import generate_signing_keypair
        from controller.author_receipt_guard import AuthorReceipt, ClaimBindingContext, canonical_receipt_payload
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        r_priv, r_pub = generate_signing_keypair()
        task_id, scope = "VIBE-XLVI", "scripts/v91_claim_cli.py"
        self.now_epoch = int(time.time())
        issued_epoch = self.now_epoch - 100
        expires_epoch = self.now_epoch - 100 + 3600
        body = AuthorReceipt(
            signer_id=self.author, key_id="k-1", signature="",
            issued_at_epoch=issued_epoch, expires_at_epoch=expires_epoch,
            claimed_author=self.author,
        )
        ctx = ClaimBindingContext(
            task_id=task_id, scope=scope, event_type="CLAIM",
            expected_base_sha=BASE_SHA, author_claim=self.author, now_epoch=self.now_epoch,
        )
        payload = canonical_receipt_payload(ctx, body)
        sig = Ed25519PrivateKey.from_private_bytes(r_priv).sign(payload.encode("utf-8")).hex()
        self.receipt_file.write_text(json.dumps({
            "signer_id": self.author, "key_id": "k-1", "signature": sig,
            "issued_at_epoch": issued_epoch, "expires_at_epoch": expires_epoch,
            "claimed_author": self.author,
        }), encoding="utf-8")
        self.policy_file.write_text(json.dumps({
            "trusted_keys": {"k-1": {"signer": self.author, "public_key": r_pub.hex()}},
            "require_verified_receipt": True,
        }), encoding="utf-8")

    def test_valid_receipt_claim_accepted(self):
        code, payload = self.claim_cmd(extra=["--receipt", str(self.receipt_file),
                                              "--policy", str(self.policy_file)])
        self.assertEqual(v91_claim_cli.EXIT_OK, code)
        self.assertEqual("ACCEPTED", payload["status"])
        self.assertTrue(payload["written"])

    def test_revoked_key_receipt_rejected_zero_bytes(self):
        policy = json.loads(self.policy_file.read_text(encoding="utf-8"))
        policy["revoked_keys"] = ["k-1"]
        self.policy_file.write_text(json.dumps(policy), encoding="utf-8")
        code, payload = self.claim_cmd(extra=["--receipt", str(self.receipt_file),
                                              "--policy", str(self.policy_file)])
        self.assertEqual(v91_claim_cli.EXIT_REJECTED_OR_CONFLICT, code)
        self.assertEqual("REJECTED", payload["status"])
        self.assertFalse(payload["written"])
        self.assertFalse(self.ledger_file.exists())

    def test_missing_receipt_with_policy_fail_closed(self):
        code, payload = self.claim_cmd(extra=["--policy", str(self.policy_file)])
        self.assertEqual(v91_claim_cli.EXIT_REJECTED_OR_CONFLICT, code)
        self.assertEqual("missing_author_receipt", payload["reason"])
        self.assertFalse(self.ledger_file.exists())


if __name__ == "__main__":
    unittest.main()
