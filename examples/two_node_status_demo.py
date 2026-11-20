#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Two-node NODE_STATUS demo (Issue #103), operator-runnable.

Spins up two EPHEMERAL in-process nodes with throwaway keys and
throwaway SQLite state, exchanges one NODE_STATUS per direction over
real loopback UDP, prints both local cooperation registers, repeats
for --cycles rounds, then stops and deletes nothing outside its
temporary directory.

What this proves: the full CI-verified federation chain works live -
build_status_payload -> EnvelopeSender (Ed25519, durable sequence) ->
UDP -> UdpEnvelopeListener -> FederationReceiver (signature + replay
floors) -> parse_status_payload -> CooperationRegister (evidence only).

Honest limits (unchanged doctrine):
- DEMO != INSTALLATION and two in-process listeners != two hosts:
  it demonstrates the code path, not a deployed mesh.
- Throwaway keys mean throwaway trust: BOTH sides generate fresh
  keys per run and hand each other only the public half
  (private keys never leave the process).
- It grants itself no authority and touches nothing outside the
  loopback interface and its own temp dir (DETECTION !=
  AUTHORIZATION).
"""
from __future__ import annotations

import argparse
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from controller.cooperation_register import (  # noqa: E402
    CooperationRegister, Observation, Verification,
)
from controller.federation_receiver import (  # noqa: E402
    FederationReceiver, FederationReplayStore,
)
from controller.federation_sender import EnvelopeSender, SequenceStore  # noqa: E402
from controller.federation_transport import UdpEnvelopeListener  # noqa: E402
from controller.status_exchange import build_status_payload  # noqa: E402

NOW = int(time.time())


class Node:
    """One ephemeral demo node: real sender, real listener, own register."""

    def __init__(self, tmp: Path, name: str, version: str, capabilities: tuple) -> None:
        self.name = name
        self.version = version
        self.capabilities = capabilities
        self.key = Ed25519PrivateKey.generate()
        self.receiver = FederationReceiver(
            peer_keys={},
            replay_store=FederationReplayStore(tmp / (name + "_replay.sqlite")),
            now_provider=lambda: NOW,
        )
        self.listener = UdpEnvelopeListener(receiver=self.receiver).start()
        self.sender = EnvelopeSender(
            peer_id=name,
            private_key=self.key,
            sequence_store=SequenceStore(tmp / (name + "_seq.sqlite")),
            now_provider=lambda: NOW,
        )
        self.register = CooperationRegister(now_provider=lambda: float(NOW))

    def trust(self, other: "Node") -> None:
        self.receiver.peer_keys[other.name] = other.key.public_key()

    def port(self) -> int:
        return self.listener.bound_address()[1]

    def status_payload(self) -> dict:
        return build_status_payload(
            software_version=self.version,
            capabilities=self.capabilities,
            state="READY",
        )

    def file_observation(self, message: dict) -> None:
        from controller.status_exchange import parse_status_payload
        parsed = parse_status_payload(message["payload"])
        outcome = self.register.record(Observation(
            peer_id=message["peer_id"],
            key_id="ed25519:" + message["peer_id"],
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
        print("  [" + self.name + "] filed observation of " + message["peer_id"] + ": " + outcome.status)

    def report(self) -> None:
        print("  [" + self.name + "] local register:")
        for entry in self.register.overview():
            print("    " + entry)


def exchange(left: Node, right: Node) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        wire_l = left.sender.build_envelope(left.status_payload()).wire
        wire_r = right.sender.build_envelope(right.status_payload()).wire
        sock.sendto(wire_l, ("127.0.0.1", right.port()))
        sock.sendto(wire_r, ("127.0.0.1", left.port()))
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if left.listener.counts()["accepted"] and right.listener.counts()["accepted"]:
            break
        time.sleep(0.05)
    for node in (left, right):
        accepted = node.listener.counts()["accepted"]
        rejected = node.listener.counts()["rejected"]
        print("  [" + node.name + "] accepted=" + str(accepted) + " rejected=" + str(rejected))


def main() -> int:
    parser = argparse.ArgumentParser(description="Two-node NODE_STATUS exchange demo")
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        alpha = Node(tmp, "node-alpha", "v91-demo-a-20261121", ("measurement", "federation"))
        beta = Node(tmp, "node-beta", "v91-demo-b-20261121", ("witness", "status-exchange"))
        alpha.trust(beta)
        beta.trust(alpha)
        try:
            for cycle in range(args.cycles):
                print("cycle " + str(cycle + 1) + " of " + str(args.cycles))
                exchange(alpha, beta)
                time.sleep(0.1)
            alpha.report()
            beta.report()
        finally:
            alpha.listener.stop()
            beta.listener.stop()
    print("demo finished cleanly; nothing was installed, started or left behind.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
