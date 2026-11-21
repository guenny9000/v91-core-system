"""
Tests fuer controller/claim_ledger (VIBE-XLIV Phase 2): Doppel-Claim-
CONFLICT fail-closed, Freigabe nur durch Halter/Operator, autorisiertes
EXPIRE nur nach Ablauf, atomares Schreiben, Crash-/Manipulations-
Erkennung beim Laden, Replay-Floors ueber Neustarts.
"""
import json
import tempfile
import unittest
from pathlib import Path

from controller.crypto_receipts import generate_signing_keypair
from controller.claim_ledger import (
    GENESIS,
    ClaimLedger,
    ClaimLedgerError,
    build_claim_event,
    verify_claim_event,
)

KEYS = {
    "session-a": generate_signing_keypair(),
    "session-b": generate_signing_keypair(),
    "operator": generate_signing_keypair(),
}
PUBLIC = {author: pub for author, (_, pub) in KEYS.items()}
BASE_SHA = "e" * 40


def claim(author, task_id="VIBE-X", scope="controller/example.py", sequence=1, issued_at=1000, expires_at=1100):
    return build_claim_event(
        event="CLAIM", author=author, task_id=task_id, scope=scope,
        sequence=sequence, issued_at=issued_at,
        private_key=KEYS[author][0],
        expected_base_sha=BASE_SHA, expires_at=expires_at,
    )


def follow(event, author, task_id="VIBE-X", scope="controller/example.py", sequence=2, issued_at=1200, reason="stale"):
    return build_claim_event(
        event=event, author=author, task_id=task_id, scope=scope,
        sequence=sequence, issued_at=issued_at,
        private_key=KEYS[author][0], reason=reason,
    )


class BuildClaimEventTests(unittest.TestCase):

    def test_roundtrip_verify_ok(self):
        rec = claim("session-a")
        self.assertTrue(verify_claim_event(rec, PUBLIC["session-a"]))
        self.assertEqual("forum_claim_event", rec["record_type"])
        self.assertEqual("CLAIM", rec["event"])
        self.assertEqual(128, len(rec["receipt_signature"]))

    def test_wrong_key_rejected(self):
        rec = claim("session-a")
        self.assertFalse(verify_claim_event(rec, PUBLIC["session-b"]))

    def test_tampered_record_rejected(self):
        rec = claim("session-a")
        forged = dict(rec)
        forged["task_id"] = "VIBE-Y"
        self.assertFalse(verify_claim_event(forged, PUBLIC["session-a"]))

    def test_invalid_fields_fail_closed(self):
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("CLAIM", "", "T", "s", 1, 1000, KEYS["session-a"][0], BASE_SHA, 1100)
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("NOPE", "session-a", "T", "s", 1, 1000, KEYS["session-a"][0], BASE_SHA, 1100)
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("CLAIM", "session-a", "T", "s", 0, 1000, KEYS["session-a"][0], BASE_SHA, 1100)
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("CLAIM", "session-a", "T", "s", 1, 1000, KEYS["session-a"][0], "nothex", 1100)
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("CLAIM", "session-a", "T", "s", 1, 1000, KEYS["session-a"][0], BASE_SHA, 1000)
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("EXPIRE", "operator", "T", "s", 1, 1200, KEYS["operator"][0], reason="")
        with self.assertRaises(ClaimLedgerError):
            build_claim_event("RELEASE", "session-a", "T", "s", 1, 1200, KEYS["session-a"][0])


class ConflictTests(unittest.TestCase):

    def test_double_claim_same_task_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(claim("session-b", sequence=1))

    def test_double_claim_same_scope_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a", task_id="VIBE-X"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(claim("session-b", task_id="VIBE-Y", sequence=1))

    def test_expired_claim_blocks_until_explicit_expire(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a", expires_at=1100))
            later = claim("session-b", task_id="VIBE-X", sequence=1, issued_at=9000, expires_at=9999)
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(later)
            self.assertEqual("session-a", ledger.active_claim("VIBE-X")["author"])


class LifecycleTests(unittest.TestCase):

    def test_release_by_holder_frees_task_and_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            ledger.append_event(follow("RELEASE", "session-a"))
            self.assertEqual({}, ledger.active_claim("VIBE-X"))
            self.assertEqual(None, ledger.scope_claimed_by("controller/example.py"))
            ledger.append_event(claim("session-b", task_id="VIBE-X", sequence=1, issued_at=1300, expires_at=1400))

    def test_release_by_stranger_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("RELEASE", "session-b"))

    def test_done_only_by_holder(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("DONE", "session-b"))
            ledger.append_event(follow("DONE", "session-a"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("DONE", "session-a", sequence=3))

    def test_expire_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a", expires_at=1100))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("EXPIRE", "session-a", sequence=2, issued_at=1050))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("EXPIRE", "session-b", sequence=2, issued_at=1200))
            ledger.append_event(follow("EXPIRE", "operator", sequence=1, issued_at=1200))
            self.assertEqual({}, ledger.active_claim("VIBE-X"))
            ledger.append_event(claim("session-b", task_id="VIBE-X", sequence=1, issued_at=1300, expires_at=1400))

    def test_scope_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(follow("RELEASE", "session-a", scope="controller/other.py"))


class IntegrityTests(unittest.TestCase):

    def test_forged_signature_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ClaimLedger(Path(tmp) / "claims.jsonl", PUBLIC, ["operator"])
            forged = dict(claim("session-a"))
            forged["receipt_signature"] = "0" * 128
            with self.assertRaises(ClaimLedgerError):
                ledger.append_event(forged)

    def test_replay_sequence_refused_after_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a", sequence=5))
            reloaded = ClaimLedger(path, PUBLIC, ["operator"])
            self.assertEqual(5, reloaded.replay_floor("session-a"))
            with self.assertRaises(ClaimLedgerError):
                reloaded.append_event(follow("RELEASE", "session-a", sequence=4))

    def test_tampered_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            lines = path.read_text(encoding="utf-8").strip().split(chr(10))
            entry = json.loads(lines[0])
            entry["entry"]["task_id"] = "VIBE-HACK"
            lines[0] = json.dumps(entry)
            path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(path, PUBLIC, ["operator"])

    def test_broken_chain_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a", sequence=1))
            ledger.append_event(follow("RELEASE", "session-a", sequence=2))
            lines = path.read_text(encoding="utf-8").strip().split(chr(10))
            second = json.loads(lines[1])
            second["prev"] = GENESIS
            lines[1] = json.dumps(second)
            path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(path, PUBLIC, ["operator"])

    def test_truncated_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            text = path.read_text(encoding="utf-8")
            path.write_text(text[:-5], encoding="utf-8")
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(path, PUBLIC, ["operator"])

    def test_blank_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            path.write_text(chr(10), encoding="utf-8")
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(path, PUBLIC, ["operator"])

    def test_leftover_tmp_file_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            junk = Path(tmp) / "claim-ledger-tmp-999.jsonl-partial"
            junk.write_text("garbage", encoding="utf-8")
            reloaded = ClaimLedger(path, PUBLIC, ["operator"])
            self.assertEqual(1, reloaded.entry_count())

    def test_file_stays_complete_after_each_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.jsonl"
            ledger = ClaimLedger(path, PUBLIC, ["operator"])
            ledger.append_event(claim("session-a"))
            ledger.append_event(follow("DONE", "session-a", sequence=2))
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith(chr(10)))
            self.assertEqual(2, len(raw.strip().split(chr(10))))
            reloaded = ClaimLedger(path, PUBLIC, ["operator"])
            self.assertEqual(2, reloaded.entry_count())
            self.assertEqual(2, reloaded.replay_floor("session-a"))
            self.assertEqual({}, reloaded.active_claim("VIBE-X"))

    def test_bad_constructor_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger("kein-pfad", PUBLIC, ["operator"])
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(Path(tmp) / "c.jsonl", {}, ["operator"])
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(Path(tmp) / "c.jsonl", {"session-a": b"kurz"}, ["operator"])
            with self.assertRaises(ClaimLedgerError):
                ClaimLedger(Path(tmp) / "c.jsonl", PUBLIC, "operator")


if __name__ == "__main__":
    unittest.main()
