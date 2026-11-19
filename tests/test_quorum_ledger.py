"""
Tests fuer controller/quorum_ledger: Ed25519-signierte Abstimmungsbelege,
persistente Hash-Kette, Replay-Floor ueber Neustarts, fail-closed bei
Manipulation, unbekannten Agenten und gefaelschten Signaturen.
"""
import json
import tempfile
import unittest
from pathlib import Path

from controller.crypto_receipts import generate_signing_keypair
from controller.quorum_ledger import (
    GENESIS,
    QuorumLedger,
    QuorumLedgerError,
    build_signed_vote,
    verify_signed_vote,
)

KEYS = {"agent-a": generate_signing_keypair(), "agent-b": generate_signing_keypair()}
PUBLIC = {agent: pub for agent, (_, pub) in KEYS.items()}


def vote(agent, sequence, approve=True, digest="a" * 64, epoch=1, issued_at=1000):
    return build_signed_vote(
        agent_id=agent, proposal_digest=digest, epoch=epoch, sequence=sequence,
        approve=approve, issued_at=issued_at, policy_version="v1",
        private_key=KEYS[agent][0],
    )


class BuildSignedVoteTests(unittest.TestCase):

    def test_roundtrip_verify_ok(self):
        rec = vote("agent-a", 1)
        self.assertTrue(verify_signed_vote(rec, PUBLIC["agent-a"]))
        self.assertEqual("quorum_vote", rec["record_type"])
        self.assertEqual(128, len(rec["receipt_signature"]))

    def test_wrong_key_rejected(self):
        rec = vote("agent-a", 1)
        self.assertFalse(verify_signed_vote(rec, PUBLIC["agent-b"]))

    def test_wrong_public_key_size_rejected(self):
        rec = vote("agent-a", 1)
        self.assertFalse(verify_signed_vote(rec, b"short"))

    def test_tampered_record_rejected(self):
        rec = vote("agent-a", 1, approve=False)
        forged = dict(rec)
        forged["approve"] = True
        self.assertFalse(verify_signed_vote(forged, PUBLIC["agent-a"]))

    def test_invalid_fields_fail_closed(self):
        with self.assertRaises(QuorumLedgerError):
            build_signed_vote("", "a" * 64, 1, 1, True, 1000, "v1", KEYS["agent-a"][0])
        with self.assertRaises(QuorumLedgerError):
            build_signed_vote("agent-a", "nothex", 1, 1, True, 1000, "v1", KEYS["agent-a"][0])
        with self.assertRaises(QuorumLedgerError):
            build_signed_vote("agent-a", "a" * 64, True, 1, True, 1000, "v1", KEYS["agent-a"][0])
        with self.assertRaises(QuorumLedgerError):
            build_signed_vote("agent-a", "a" * 64, 1, 0, True, 1000, "v1", KEYS["agent-a"][0])
        with self.assertRaises(QuorumLedgerError):
            build_signed_vote("agent-a", "a" * 64, 1, 1, "ja", 1000, "v1", KEYS["agent-a"][0])


class LedgerTests(unittest.TestCase):

    def test_append_and_reload_with_floors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            self.assertEqual(0, ledger.entry_count())
            ledger.append_vote(vote("agent-a", 1))
            ledger.append_vote(vote("agent-b", 1))
            ledger.append_vote(vote("agent-a", 2))
            reloaded = QuorumLedger(path, PUBLIC)
            self.assertEqual(3, reloaded.entry_count())
            self.assertEqual(2, reloaded.replay_floor("agent-a"))
            self.assertEqual(1, reloaded.replay_floor("agent-b"))
            self.assertEqual(0, reloaded.replay_floor("agent-c"))

    def test_replay_identical_sequence_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            ledger.append_vote(vote("agent-a", 1))
            with self.assertRaises(QuorumLedgerError):
                ledger.append_vote(vote("agent-a", 1))

    def test_stale_sequence_refused_after_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            ledger.append_vote(vote("agent-a", 5))
            reloaded = QuorumLedger(path, PUBLIC)
            with self.assertRaises(QuorumLedgerError):
                reloaded.append_vote(vote("agent-a", 4))

    def test_forged_signature_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            rec = vote("agent-a", 1)
            forged = dict(rec)
            forged["receipt_signature"] = "0" * 128
            with self.assertRaises(QuorumLedgerError):
                ledger.append_vote(forged)

    def test_unknown_agent_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            other_key = KEYS["agent-a"][0]
            stranger = build_signed_vote(
                agent_id="agent-x", proposal_digest="a" * 64, epoch=1,
                sequence=1, approve=True, issued_at=1000,
                policy_version="v1", private_key=other_key,
            )
            with self.assertRaises(QuorumLedgerError):
                ledger.append_vote(stranger)

    def test_tampered_ledger_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            ledger.append_vote(vote("agent-a", 1))
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            entry = json.loads(lines[0])
            entry["entry"]["approve"] = not entry["entry"]["approve"]
            lines[0] = json.dumps(entry)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(path, PUBLIC)

    def test_broken_chain_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            ledger.append_vote(vote("agent-a", 1))
            ledger.append_vote(vote("agent-b", 1))
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            second = json.loads(lines[1])
            second["prev"] = GENESIS
            lines[1] = json.dumps(second)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(path, PUBLIC)

    def test_blank_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            path.write_text("\n", encoding="utf-8")
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(path, PUBLIC)

    def test_truncated_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quorum_ledger.jsonl"
            ledger = QuorumLedger(path, PUBLIC)
            ledger.append_vote(vote("agent-a", 1))
            text = path.read_text(encoding="utf-8")
            path.write_text(text[:-5], encoding="utf-8")
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(path, PUBLIC)

    def test_bad_constructor_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger("kein-pfad", PUBLIC)
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(Path(tmp) / "x.jsonl", {})
            with self.assertRaises(QuorumLedgerError):
                QuorumLedger(Path(tmp) / "x.jsonl", {"agent-a": b"kurz"})


if __name__ == "__main__":
    unittest.main()
