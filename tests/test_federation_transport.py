"""Transport binding tests: real loopback UDP, receiver decides (Issue #103 P2)."""
import json
import socket
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from controller.federation_receiver import (  # noqa: E402
    FederationReceiver, FederationReplayStore,
)
from controller.federation_transport import (  # noqa: E402
    TransportError, UdpEnvelopeListener,
)

NOW = 1800000000


def envelope_bytes(private_key, peer_id: str, sequence: int, issued_at: int = NOW) -> bytes:
    payload = {
        "schema_version": 1, "peer_id": peer_id, "epoch": 1,
        "sequence": sequence, "issued_at": issued_at, "payload": {"metric": sequence},
    }
    signature = private_key.sign(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hex()
    payload["signature"] = signature
    return json.dumps(payload).encode("utf-8")


def make_receiver(tmp_path, private_key) -> FederationReceiver:
    public_key = private_key.public_key()
    return FederationReceiver(
        peer_keys={"peer-alpha": public_key},
        replay_store=FederationReplayStore(tmp_path / "replay.sqlite"),
        now_provider=lambda: NOW,
    )


def wait_for(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met within timeout")


class UdpTransportTest(unittest.TestCase):
    def test_loopback_roundtrip_accepted_then_rejected(self):
        import tempfile
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            receiver = make_receiver(Path(td), private_key)
            with UdpEnvelopeListener(receiver=receiver) as listener:
                host, port = listener.bound_address()[0], listener.bound_address()[1]
                self.assertEqual(host, "127.0.0.1")
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.sendto(envelope_bytes(private_key, "peer-alpha", 1), ("127.0.0.1", port))
                    sock.sendto(b"garbage", ("127.0.0.1", port))
                    wait_for(lambda: listener.counts() == {"accepted": 1, "rejected": 1})
                finally:
                    sock.close()
                outcomes = listener.outcomes()
                self.assertEqual(outcomes[0].status, "ACCEPTED")
                self.assertEqual(outcomes[1].status, "REJECTED")
                self.assertTrue(outcomes[1].reason.startswith("malformed env    def test_large_non_json_datagram_is_receiver_rejected(self):
        # UDP datagrams cap at 65507 bytes, below the receiver's 64 KiB
        # envelope bound: the size check is defense in depth for other
        # transports. What CAN arrive is a large non-JSON payload.
        import tempfile
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            receiver = make_receiver(Path(td), private_key)
            with UdpEnvelopeListener(receiver=receiver) as listener:
                port = listener.bound_address()[1]
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.sendto(b"\x00" * 65_000, ("127.0.0.1", port))
                    wait_for(lambda: listener.counts()["rejected"] == 1)
                finally:
                    sock.close()
                outcome = listener.outcomes()[0]
                self.assertEqual(outcome.size, 65_000)
                self.assertTrue(outcome.reason.startswith("malformed envelope"))

    def test_non_allowlisted_bind_host_refused(self):
        import tempfile
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            receiver = make_receiver(Path(td), private_key)
            with self.assertRaises(TransportError):
                UdpEnvelopeListener(receiver=receiver, host="0.0.0.0")
            with self.assertRaises(TransportError):
                UdpEnvelopeListener(receiver=receiver, host="192.168.1.10")

    def test_constructor_fail_closed(self):
        import tempfile
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            receiver = make_receiver(Path(td), private_key)
            with self.assertRaises(TransportError):
                UdpEnvelopeListener(receiver=None)  # type: ignore[arg-type]
            with self.assertRaises(TransportError):
                UdpEnvelopeListener(receiver=receiver, port=-1)
            with self.assertRaises(TransportError):
                UdpEnvelopeListener(receiver=receiver, outcome_log_size=0)

    def test_stop_is_idempotent_and_no_listener_leak(self):
        import tempfile
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            receiver = make_receiver(Path(td), private_key)
            listener = UdpEnvelopeListener(receiver=receiver)
            listener.start()
            self.assertTrue(listener.running)
            listener.stop()
            listener.stop()
            self.assertFalse(listener.running)
            with self.assertRaises(TransportError):
                listener.bound_address()


if __name__ == "__main__":
    unittest.main()
