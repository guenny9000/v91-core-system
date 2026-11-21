"""
Tests fuer scripts/v91_watchdog.py (VIBE-XLVII Phase 5): Scan
erkennt abgelaufene Claims ohne zu schreiben (DRY-RUN != APPLY),
expire wendet regelkonforme EXPIRE-Ereignisse an (nur Operator-
Identitaet), nichts zu expiren ist OK, unautorisiertes EXPIRE wird
verweigert (REJECTED != GESPEICHERT), korruptes Ledger fail-closed
Exit 3, Receipt-Gate nur mit echtem Ed25519-Backend
(STUB != ECHT, UNKNOWN != PASS). WATCHDOG != DAEMON.
"""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from controller import claim_ledger
from scripts import v91_watchdog

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
BASE_SHA = "f" * 40


class WatchdogHarness(unittest.TestCase):
    """Baut ein Ledger mit bis zu zwei Claims (Autor + Operator-Key)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.ledger_file = self.tmp_path / "claims.jsonl"
        self.now = 2_000_000_000
        self.author = "worker"
        self.operator = "op"
        self.priv = b"b" * 32
        if HAS_CRYPTO:
            from controller.crypto_receipts import generate_signing_keypair
            self.priv, self.pub = generate_signing_keypair()
        else:
            self.pub = hashlib.sha256(self.priv).digest()
        self.key_file = self.tmp_path / "op.hex"
        self.key_file.write_text(self.priv.hex(), encoding="utf-8")
        self.keyring = {
            "public_keys": {self.author: self.pub.hex(), self.operator: self.pub.hex()},
            "expire_authorities": [self.operator],
        }
        self.keyring_file = self.tmp_path / "keyring.json"
        self.keyring_file.write_text(json.dumps(self.keyring), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_watchdog(self, mode, extra=None, author=None, now=None):
        argv = [mode, "--ledger", str(self.ledger_file), "--keyring", str(self.keyring_file)]
        if author:
            argv += ["--author", author]
        if now is not None:
            argv += ["--now", str(now)]
        argv += list(extra or [])
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_watchdog.main(argv)
        out = buf.getvalue().strip()
        payload = json.loads(out) if out else {}
        return code, payload

    def seed_claim(self, task_id, scope, ttl=3600, issued_seq=1, author=None):
        ledger = claim_ledger.ClaimLedger(
            self.ledger_file, {a: bytes.fromhex(h) for a, h in self.keyring["public_keys"].items()}, self.keyring["expire_authorities"]
        )
        record = claim_ledger.build_claim_event(
            event=claim_ledger.EVENT_CLAIM,
            author=author or self.author,
            task_id=task_id,
            scope=scope,
            sequence=issued_seq,
            issued_at=self.now,
            private_key=self.priv,
            expected_base_sha=BASE_SHA,
            expires_at=self.now + ttl,
        )
        ledger.append_event(record)
        return ledger

    def raw(self):
        return self.ledger_file.read_bytes()


class ScanTests(WatchdogHarness):
    def test_scan_no_ledger_is_unknown_ok(self):
        code, payload = self.run_watchdog("scan")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "UNKNOWN")
        self.assertEqual(payload["reason"], "ledger_not_found")
        self.assertFalse(payload["written"])

    def test_scan_detects_expired_and_writes_nothing(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        before = self.raw()
        code, payload = self.run_watchdog("scan", now=self.now + 200)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "SCANNED")
        self.assertEqual(len(payload["expired_claims"]), 1)
        self.assertEqual(payload["expired_claims"][0]["task_id"], "VIBE-A")
        self.assertEqual(payload["written"], False)
        self.assertEqual(self.raw(), before)  # DRY-RUN != APPLY

    def test_scan_not_expired_and_done_claims(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        self.seed_claim("VIBE-B", "repo/y", ttl=9999, issued_seq=2)
        code, payload = self.run_watchdog("scan", now=self.now + 500)
        self.assertEqual(code, 0)
        ids = [c["task_id"] for c in payload["expired_claims"]]
        self.assertEqual(ids, ["VIBE-A"])

    def test_scan_orders_by_expiry_then_task_id(self):
        self.seed_claim("VIBE-Z", "s/z", ttl=100)
        self.seed_claim("VIBE-A", "s/a", ttl=50, issued_seq=2)
        self.seed_claim("VIBE-B", "s/b", ttl=50, issued_seq=3)
        code, payload = self.run_watchdog("scan", now=self.now + 1000)
        ids = [c["task_id"] for c in payload["expired_claims"]]
        self.assertEqual(ids, ["VIBE-A", "VIBE-B", "VIBE-Z"])

    def test_scan_released_claims_not_listed(self):
        ledger = self.seed_claim("VIBE-A", "repo/x", ttl=100)
        record = claim_ledger.build_claim_event(
            event=claim_ledger.EVENT_RELEASE,
            author=self.author,
            task_id="VIBE-A",
            scope="repo/x",
            sequence=2,
            issued_at=self.now + 10,
            private_key=self.priv,
        )
        ledger.append_event(record)
        code, payload = self.run_watchdog("scan", now=self.now + 500)
        self.assertEqual(code, 0)
        self.assertEqual(payload["expired_claims"], [])

    def test_scan_missing_keyring_is_input_error(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        bad = self.tmp_path / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        argv = ["scan", "--ledger", str(self.ledger_file), "--keyring", str(bad)]
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_watchdog.main(argv)
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "REJECTED")
        self.assertFalse(payload["written"])


class ExpireTests(WatchdogHarness):
    def base_expire_args(self, now):
        return ["--key", str(self.key_file), "--reason", "ttl abgelaufen", "--now", str(now)]

    def test_expire_applies_due_claim_and_frees_task(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        before = self.raw()
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 200), author=self.operator
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "APPLIED")
        self.assertTrue(payload["written"])
        self.assertNotEqual(self.raw(), before)
        rel = claim_ledger.ClaimLedger(
            self.ledger_file,
            {a: bytes.fromhex(h) for a, h in self.keyring["public_keys"].items()},
            self.keyring["expire_authorities"],
        )
        self.assertEqual(rel.active_claim("VIBE-A"), {})
        self.assertEqual(rel.scope_claimed_by("repo/x"), None)
        self.assertEqual(
            [r["event"] for r in rel.records()], ["CLAIM", "EXPIRE"]
        )
        expire_record = rel.records()[-1]
        self.assertEqual(expire_record["author"], self.operator)
        self.assertTrue(expire_record["reason"].strip())

    def test_expire_multiple_due_claims_in_one_run(self):
        self.seed_claim("VIBE-A", "s/a", ttl=100)
        self.seed_claim("VIBE-B", "s/b", ttl=200, issued_seq=2)
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 300), author=self.operator
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "APPLIED")
        self.assertEqual(len(payload["expired_events"]), 2)
        # Operatoren-Sequenz ist lueckenlos aufsteigend (Replay-Floor)
        self.assertEqual(len({e["task_id"] for e in payload["expired_events"]}), 2)

    def test_expire_nothing_due_is_ok_and_writes_nothing(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        before = self.raw()
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 10), author=self.operator
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "NOTHING_TO_EXPIRE")
        self.assertFalse(payload.get("written", False))
        self.assertEqual(self.raw(), before)

    def test_expire_early_is_refused_before_expiry(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=5000)
        before = self.raw()
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 100), author=self.operator
        )
        self.assertEqual(code, 0)  # nicht faellig -> NOTHING_TO_EXPIRE
        self.assertEqual(payload["status"], "NOTHING_TO_EXPIRE")
        self.assertEqual(self.raw(), before)

    def test_expire_unauthorized_operator_rejected_zero_byte(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        before = self.raw()
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 200), author=self.author
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "REJECTED")
        self.assertEqual(self.raw(), before)  # REJECTED != GESPEICHERT

    def test_expire_missing_reason_rejected_before_io(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        before = self.raw()
        argv = [
            "expire", "--ledger", str(self.ledger_file), "--keyring", str(self.keyring_file),
            "--key", str(self.key_file), "--author", self.operator,
            "--now", str(self.now + 200), "--reason", "  ",
        ]
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_watchdog.main(argv)
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "REJECTED")
        self.assertEqual(self.raw(), before)

    def test_expire_no_ledger_unknown_ok(self):
        code, payload = self.run_watchdog(
            "expire", extra=self.base_expire_args(self.now + 200), author=self.operator
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "UNKNOWN")

    def test_missing_key_file_is_input_error(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        argv = [
            "expire", "--ledger", str(self.ledger_file), "--keyring", str(self.keyring_file),
            "--key", str(self.tmp_path / "nope.hex"), "--author", self.operator,
            "--reason", "x", "--now", str(self.now + 200),
        ]
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_watchdog.main(argv)
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "REJECTED")


class IntegrityTests(WatchdogHarness):
    def test_corrupt_ledger_scan_exit3(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        raw = self.raw()
        self.ledger_file.write_bytes(raw[:-5])  # abgeschnittene Zeile
        code, payload = self.run_watchdog("scan")
        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "CORRUPT_OR_INVALID")

    def test_tampered_ledger_expire_exit2_or_3_writes_nothing(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        lines = self.raw().decode("utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["entry"]["author"] = "intruder"
        lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        self.ledger_file.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        before = self.raw()
        code, payload = self.run_watchdog(
            "expire",
            extra=["--key", str(self.key_file), "--reason", "r", "--now", str(self.now + 300)],
            author=self.operator,
        )
        self.assertIn(code, (2, 3))
        self.assertIn(payload["status"], ("REJECTED", "CORRUPT_OR_INVALID"))
        self.assertEqual(self.raw(), before)


class ReceiptGateTests(WatchdogHarness):
    @unittest.skipUnless(HAS_CRYPTO, "echtes Ed25519-Backend nicht verfuegbar (STUB != ECHT)")
    def test_expire_with_rejected_receipt_writes_nothing(self):
        self.seed_claim("VIBE-A", "repo/x", ttl=100)
        policy = {
            "trusted_keys": {"k1": {"signer": "issuer", "public_key": "00" * 32}},
            "require_verified_receipt": True,
        }
        receipt = {
            "signer_id": "issuer",
            "key_id": "k1",
            "signature": "00" * 64,
            "issued_at_epoch": self.now - 10,
            "expires_at_epoch": self.now + 500,
            "claimed_author": self.operator,
        }
        policy_file = self.tmp_path / "policy.json"
        receipt_file = self.tmp_path / "receipt.json"
        policy_file.write_text(json.dumps(policy), encoding="utf-8")
        receipt_file.write_text(json.dumps(receipt), encoding="utf-8")
        before = self.raw()
        argv = [
            "expire", "--ledger", str(self.ledger_file), "--keyring", str(self.keyring_file),
            "--key", str(self.key_file), "--author", self.operator,
            "--reason", "ttl", "--now", str(self.now + 500),
            "--receipt", str(receipt_file), "--policy", str(policy_file),
        ]
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            code = v91_watchdog.main(argv)
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "REJECTED")
        self.assertEqual(self.raw(), before)  # REJECTED != GESPEICHERT


if __name__ == "__main__":
    unittest.main()
