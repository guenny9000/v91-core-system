"""Sender tests: roundtrip with the real receiver, durable sequences."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from controller.federation_receiver import (  # noqa: E402
    FederationReceiver, FederationReplayStore,
)
from controller.federation_sender import (  # noqa: E402
    EnvelopeSender, SenderError, SequenceStore,
)

NOW = 1800000000


def make_pair(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    sender = EnvelopeSender(peer_id="peer-alpha", private_key=private_key,
                           sequence_store=SequenceStore(tmp_path / "outbound.sqlite"),
                           epoch=1, now_provider=lambda: NOW)
    receiver = FederationReceiver(
        peer_keys={"peer-alpha": private_key.public_key()},
        replay_store=FederationReplayStore(tmp_path / "inbound.sqlite"),
        now_provider=lambda: NOW,
    )
    return sender, receiver


class EnvelopeSenderTest(unittest.TestCase):
    def test_roundtrip_accepted_by_real_receiver(self):
        with tempfile.TemporaryDirectory() as td:
            sender, receiver = make_pair(Path(td))
            env = sender.build_envelope({"metric": 42})
            self.assertEqual(env.sequence, 1)
            receipt = receiver.receive(env.wire)
            self.assertEqual(receipt.status, "ACCEPTED", receipt.reason)

    def test_roundtrip_accepts_unicode_payload(self):
        with tempfile.TemporaryDirectory() as td:
            sender, receiver = make_pair(Path(td))
            payload = {"message": "Grüße aus Alsfeld – Frieden für alle 🌍"}
            env = sender.build_envelope(payload)
            receipt = receiver.receive(env.wire)
            self.assertEqual(receipt.status, "ACCEPTED", receipt.reason)
            self.assertEqual(receipt.message["payload"], payload)

    def test_sequence_is_monotonic_and_replay_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            sender, receiver = make_pair(Path(td))
            first = sender.build_envelope({"n": 1})
            second = sender.build_envelope({"n": 2})
            self.assertEqual((first.sequence, second.sequence), (1, 2))
            self.assertEqual(receiver.receive(first.wire).status, "ACCEPTED")
            self.assertEqual(receiver.receive(second.wire).status, "ACCEPTED")
            # Retransmitting the first envelope hits the durable replay floor.
            replay = receiver.receive(first.wire)
            self.assertEqual(replay.status, "REJECTED")
            self.assertIn("duplicate", replay.reason)

    def test_sequence_survives_restart(self):
        with tempfile.TemporaryDirectory() as td:
            sender, _ = make_pair(Path(td))
            sender.build_envelope({"n": 1})
            sender.build_envelope({"n": 2})
            # "Restart": a fresh sender over the same durable store continues.
            restarted = EnvelopeSender(
                peer_id="peer-alpha", private_key=Ed25519PrivateKey.generate(),
                sequence_store=SequenceStore(Path(td) / "outbound.sqlite"),
                epoch=1, now_provider=lambda: NOW)
            env = restarted.build_envelope({"n": 3})
            self.assertEqual(env.sequence, 3)

    def test_refused_build_burns_no_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            sender, _ = make_pair(Path(td))
            for bad in ([1, 2, 3], {"k": float("nan")}, {"k": float("inf")},
                        b"raw-not-a-dict"):
                with self.assertRaises(SenderError, msg=repr(bad)):
                    sender.build_envelope(bad)
            env = sender.build_envelope({"ok": True})
            self.assertEqual(env.sequence, 1)

    def test_oversized_payload_refused(self):
        with tempfile.TemporaryDirectory() as td:
            sender, _ = make_pair(Path(td))
            big = {f"key{i}": "x" * 40 for i in range(300)}
            with self.assertRaises(SenderError):
                sender.build_envelope(big)

    def test_tampered_wire_fails_receiver(self):
        with tempfile.TemporaryDirectory() as td:
            sender, receiver = make_pair(Path(td))
            env = sender.build_envelope({"metric": 7})
            tampered = env.wire.replace(b'"metric": 7', b'"metric": 8')
            self.assertNotEqual(tampered, env.wire)
            receipt = receiver.receive(tampered)
            self.assertEqual(receipt.status, "REJECTED")

    def test_constructor_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            key = Ed25519PrivateKey.generate()
            store = SequenceStore(Path(td) / "s.sqlite")
            with self.assertRaises(SenderError):
                EnvelopeSender(peer_id="", private_key=key, sequence_store=store)
            with self.assertRaises(SenderError):
                EnvelopeSender(peer_id="p", private_key="not-a-key",  # type: ignore[arg-type]
                               sequence_store=store)
            with self.assertRaises(SenderError):
                EnvelopeSender(peer_id="p", private_key=key, sequence_store=store,
                               epoch=True)
            with self.assertRaises(SenderError):
                EnvelopeSender(peer_id="p", private_key=key, sequence_store="nope")  # type: ignore[arg-type]

    def test_invalid_now_provider_refused(self):
        with tempfile.TemporaryDirectory() as td:
            key = Ed25519PrivateKey.generate()
            sender = EnvelopeSender(peer_id="p", private_key=key,
                                    sequence_store=SequenceStore(Path(td) / "s.sqlite"),
                                    now_provider=lambda: -5)
            with self.assertRaises(SenderError):
                sender.build_envelope({"ok": True})


if __name__ == "__main__":
    unittest.main()
