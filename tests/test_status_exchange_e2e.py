"""End-to-end NODE_STATUS exchange: two nodes, real loopback UDP (Issue #103).

Full honest chain, all parts CI-verified modules already on main:
  build_status_payload (controller/status_exchange)
  -> EnvelopeSender with durable sequence (controller/federation_sender)
  -> real UDP socket to a UdpEnvelopeListener (controller/federation_transport)
  -> FederationReceiver Ed25519 + replay floors (controller/federation_receiver)
  -> parse_status_payload re-validation
  -> CooperationRegister evidence filing (controller/cooperation_register)

This test IS a real socket roundtrip, but it is still a TEST:
SCRIPTED != INSTALLED, two in-process listeners != two hosts.
"""
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from controller.cooperation_register import (  # noqa: E402
    CooperationRegister, Observation, Verification,
)
from controller.federation_receiver import (  # noqa: E402
    FederationReceiver, FederationReplayStore,
)
from controller.federation_sender import (  # noqa: E402
    EnvelopeSender, SequenceStore,
)
from controller.federation_transport import UdpEnvelopeListener  # noqa: E402
from controller.status_exchange import (  # noqa: E402
    ALLOWED_STATES, STATUS_KIND, StatusExchangeError,
    build_status_payload, parse_status_payload,
)

NOW = 1800000000


def wait_for(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met within timeout")


class CapturingReceiver(FederationReceiver):
    """Thin pass-through that keeps ACCEPTED messages for assertions.

    It adds no behavior: every byte still goes through the real
    FederationReceiver. Capture is test observability only.
    """

    def __init__(self, inner: FederationReceiver) -> None:
        self._inner = inner
        self.captured: list[dict] = []

    def receive(self, raw):  # type: ignore[override]
        receipt = self._inner.receive(raw)
        if receipt.status == "ACCEPTED":
            self.captured.append(receipt.message)
        return receipt


def make_node(tmp: Path, peer_id: str, own_key: Ed25519PrivateKey,
                   remote_peer_id: str, remote_public_key) -> dict:
    receiver = CapturingReceiver(FederationReceiver(
        peer_keys={remote_peer_id: remote_public_key},
        replay_store=FederationReplayStore(tmp / f"{peer_id}_replay.sqlite"),
        now_provider=lambda: NOW,
    ))
    listener = UdpEnvelopeListener(receiver=receiver).start()
    sender = EnvelopeSender(
        peer_id=peer_id,
        private_key=own_key,
        sequence_store=SequenceStore(tmp / f"{peer_id}_seq.sqlite"),
        now_provider=lambda: NOW,
    )
    register = CooperationRegister(now_provider=lambda: float(NOW))
    return {
        "peer_id": peer_id,
        "receiver": receiver,
        "listener": listener,
        "sender": sender,
        "register": register,
    }


def status_payload(version: str, caps: tuple) -> dict:
    return build_status_payload(
        software_version=version,
        capabilities=caps,
        state="READY",
        knowledge_digests={"controller/peer_sync.py": "a" * 64},
    )


class StatusExchangeUnitTest(unittest.TestCase):
    def test_roundtrip_preserves_content_and_sorts(self):
        payload = status_payload("core-2026-11-20", ("measurement", "federation"))
        parsed = parse_status_payload(payload)
        self.assertEqual(parsed["software_version"], "core-2026-11-20")
        self.assertEqual(parsed["capabilities"], ["federation", "measurement"])
        self.assertEqual(parsed["state"], "READY")
        self.assertEqual(parsed["status_kind"], STATUS_KIND)

    def test_invalid_state_refused(self):
        with self.assertRaises(StatusExchangeError):
            build_status_payload(software_version="v", capabilities=(), state="HACKED")

    def test_duplicate_capability_refused(self):
        with self.assertRaises(StatusExchangeError):
            build_status_payload(software_version="v", capabilities=("a", "a"))

    def test_bad_digest_refused(self):
        with self.assertRaises(StatusExchangeError):
            build_status_payload(
                software_version="v", capabilities=(),
                knowledge_digests={"m": "g" * 64},
            )

    def test_foreign_payload_with_extra_field_refused(self):
        payload = status_payload("v", ())
        payload["eigenmacht"] = "yes"
        with self.assertRaises(StatusExchangeError):
            parse_status_payload(payload)

    def test_foreign_payload_wrong_kind_refused(self):
        payload = status_payload("v", ())
        payload = dict(payload, status_kind="REMOTE_COMMAND")
        with self.assertRaises(StatusExchangeError):
            parse_status_payload(payload)

    def test_foreign_payload_wrong_version_refused(self):
        payload = status_payload("v", ())
        payload = dict(payload, schema_version=99)
        with self.assertRaises(StatusExchangeError):
            parse_status_payload(payload)

    def test_non_dict_refused(self):
        with self.assertRaises(StatusExchangeError):
            parse_status_payload("nope")

    def test_allowed_states_unchanged(self):
        self.assertEqual(ALLOWED_STATES, frozenset({"READY", "BUSY", "DEGRADED", "STOPPING"}))


class TwoNodeLoopbackTest(unittest.TestCase):
    def test_bidirectional_status_exchange_and_register_filing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key_a = Ed25519PrivateKey.generate()
            key_b = Ed25519PrivateKey.generate()
            node_a = make_node(tmp, "node-alpha", key_a, "node-beta", key_b.public_key())
            node_b = make_node(tmp, "node-beta", key_b, "node-alpha", key_a.public_key())
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                port_a = node_a["listener"].bound_address()[1]
                port_b = node_b["listener"].bound_address()[1]

                wire_a = node_a["sender"].build_envelope(
                    status_payload("core-2026-11-20-alpha", ("measurement", "federation"))
                ).wire
                wire_b = node_b["sender"].build_envelope(
                    status_payload("core-2026-11-20-beta", ("witness",))
                ).wire

                sock.sendto(wire_a, ("127.0.0.1", port_b))
                sock.sendto(wire_b, ("127.0.0.1", port_a))
                wait_for(lambda: node_a["listener"].counts()["accepted"] == 1
                         and node_b["listener"].counts()["accepted"] == 1)
            finally:
                sock.close()

            # Node A files its VERIFIED observation of node B locally.
            message = node_a["receiver"].captured[0]
            self.assertEqual(message["peer_id"], "node-beta")
            parsed = parse_status_payload(message["payload"])
            self.assertEqual(parsed["software_version"], "core-2026-11-20-beta")
            outcome = node_a["register"].record(Observation(
                peer_id="node-beta",
                key_id="ed25519:node-beta",
                sequence=message["sequence"],
                received_at=float(NOW),
                software_version=parsed["software_version"],
                capabilities=tuple(parsed["capabilities"]),
                state=parsed["state"],
                verification=Verification(
                    state="ALIVE_VERIFIED",
                    reason="federation envelope signature verified",
                ),
            ))
            self.assertEqual(outcome.status, "VERIFIED_RECORDED")
            view = node_a["register"].view("node-beta")
            self.assertEqual(view["health"], "ALIVE_VERIFIED")
            self.assertEqual(view["software_version"], "core-2026-11-20-beta")
            self.assertEqual(view["capabilities"], ["witness"])

            # Node B files its VERIFIED observation of node A locally.
            message_b = node_b["receiver"].captured[0]
            parsed_b = parse_status_payload(message_b["payload"])
            self.assertEqual(parsed_b["software_version"], "core-2026-11-20-alpha")
            outcome_b = node_b["register"].record(Observation(
                peer_id="node-alpha",
                key_id="ed25519:node-alpha",
                sequence=message_b["sequence"],
                received_at=float(NOW),
                software_version=parsed_b["software_version"],
                capabilities=tuple(parsed_b["capabilities"]),
                state=parsed_b["state"],
                verification=Verification(
                    state="ALIVE_VERIFIED",
                    reason="federation envelope signature verified",
                ),
            ))
            self.assertEqual(outcome_b.status, "VERIFIED_RECORDED")
            self.assertEqual(
                node_b["register"].view("node-alpha")["health"], "ALIVE_VERIFIED")

            node_a["listener"].stop()
            node_b["listener"].stop()

    def test_replay_of_same_envelope_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key_a = Ed25519PrivateKey.generate()
            key_b = Ed25519PrivateKey.generate()
            node_a = make_node(tmp, "node-alpha", key_a, "node-beta", key_b.public_key())
            node_b = make_node(tmp, "node-beta", key_b, "node-alpha", key_a.public_key())
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                wire = node_a["sender"].build_envelope(
                    status_payload("core-2026-11-20-alpha", ())
                ).wire
                port_b = node_b["listener"].bound_address()[1]
                sock.sendto(wire, ("127.0.0.1", port_b))
                sock.sendto(wire, ("127.0.0.1", port_b))
                wait_for(lambda: node_b["listener"].counts() == {"accepted": 1, "rejected": 1})
            finally:
                sock.close()
            self.assertEqual(len(node_b["receiver"].captured), 1)
            node_a["listener"].stop()
            node_b["listener"].stop()

    def test_tampered_signature_is_rejected_and_not_captured(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key_a = Ed25519PrivateKey.generate()
            key_b = Ed25519PrivateKey.generate()
            node_a = make_node(tmp, "node-alpha", key_a, "node-beta", key_b.public_key())
            node_b = make_node(tmp, "node-beta", key_b, "node-alpha", key_a.public_key())
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                wire = bytearray(node_a["sender"].build_envelope(
                    status_payload("core-2026-11-20-alpha", ())
                ).wire)
                # Flip one byte inside the hex signature region.
                wire[-2] = ord("0") if wire[-2] != ord("0") else ord("1")
                port_b = node_b["listener"].bound_address()[1]
                sock.sendto(bytes(wire), ("127.0.0.1", port_b))
                wait_for(lambda: node_b["listener"].counts()["rejected"] == 1)
            finally:
                sock.close()
            self.assertEqual(node_b["receiver"].captured, [])
            node_a["listener"].stop()
            node_b["listener"].stop()


if __name__ == "__main__":
    unittest.main()
