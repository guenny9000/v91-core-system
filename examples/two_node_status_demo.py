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
for --cycles rounds, then stops and leaves nothing behind outside
its temporary directory.

What this proves live: the full CI-verified federation chain -
build_status_payload -> EnvelopeSender (Ed25519, durable sequence) ->
UDP -> UdpEnvelopeListener -> FederationReceiver (signature + replay
floors) -> parse_status_payload -> CooperationRegister (evidence only).

Honest limits (unchanged doctrine):
- DEMO != INSTALLATION; two in-process listeners != two hosts.
- Throwaway keys mean throwaway trust: fresh keys per run, only the
  public halves cross the wire inside this process.
- No authority is granted by anything here (DETECTION !=
  AUTHORIZATION); the register refuses a global status by design.
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
from controller.status_exchange import (  # noqa: E402
    build_status_payload, parse_status_payload, StatusExchangeError,
)

NOW = int(time.time())


class CapturingReceiver(FederationReceiver):
    """Pass-through that keeps ACCEPTED messages for the demo prints.

    Every byte still goes through the real FederationReceiver; the
    capture adds observability, never behavior.
    """

    def __init__(self, inner: FederationReceiver) -> None:
        self._inner = inner
        self.captured: list[dict] = []

    def receive(self, raw):  # type: ignore[override]
        receipt = self._inner.receive(raw)
        if receipt.status == "ACCEPTED":
            self.captured.append(receipt.message)
        return receipt


class DemoNode:
    """One ephemeral demo node: real sender, real listener, own register."""

    def __init__(self, tmp: Path, name: str, version: str, capabilities: tuple,
                 own_key: Ed25519PrivateKey, remote_name: str,
                 remote_public_key) -> None:
        self.name = name
        self.version = version
        self.capabilities = capabilities
        self.receiver = CapturingReceiver(FederationReceiver(
            peer_keys={remote_name: remote_public_key},
            replay_store=FederationReplayStore(tmp / (name + "_replay.sqlite")),
            now_provider=lambda: NOW,
        ))
        self.listener = UdpEnvelopeListener(receiver=self.receiver).start()
        self.sender = EnvelopeSender(
            peer_id=name,
            private_key=own_key,
            sequence_store=SequenceStore(tmp / (name + "_seq.sqlite")),
            now_provider=lambda: NOW,
        )
        self.register = CooperationRegister(now_provider=lambda: float(NOW))
        self.remote_name = remote_name

    def port(self) -> int:
        return self.listener.bound_address()[1]

    def status_payload(self) -> dict:
        return build_status_payload(
            software_version=self.version,
            capabilities=self.capabilities,
            state="READY",
        )

    def exchange_with(self, other: "DemoNode") -> None:
        wire_out = self.sender.build_envelope(self.status_payload()).wire
        wire_in = other.sender.build_envelope(other.status_payload()).wire
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(wire_out, ("127.0.0.1", other.port()))
            sock.sendto(wire_in, ("127.0.0.1", self.port()))
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.listener.counts()["accepted"] > 0 and other.listener.counts()["accepted"] > 0:
                break
            time.sleep(0.05)
        counts = self.listener.counts()
        print("  [" + self.name + "] accepted=" + str(counts["accepted"])
              + " rejected=" + str(counts["rejected"]))

    def file_and_report(self) -> None:
        if not self.receiver.captured:
            print("  [" + self.name + "] no verified observation received")
            return
        for message in self.receiver.captured:
            try:
                parsed = parse_status_payload(message["payload"])
            except StatusExchangeError as exc:
                print("  [" + self.name + "] refused invalid status: " + str(exc))
                continue
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
            print("  [" + self.name + "] " + message["peer_id"] + " -> " + outcome.status)
        view = self.register.view(self.remote_name)
        if view is None:
            print("  [" + self.name + "] register: no verified peer yet")
            return
        print("  [" + self.name + "] register view of " + self.remote_name + ":")
        print("    health            = " + str(view["health"]))
        print("    software_version  = " + str(view["software_version"]))
        print("    capabilities      = " + ", ".join(view["capabilities"]))
        print("    last_sequence     = " + str(view["last_sequence"]))
        print("    verifiedinosaurer  = " + str(view["verified_observations"]).replace("verifiedinosaurer", "verified observations"))
        overview = self.register.overview()
        print("    global status     = " + str(overview["global_status"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Two-node NODE_STATUS exchange demo")
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        key_a = Ed25519PrivateKey.generate()
        key_b = Ed25519PrivateKey.generate()
        alpha = DemoNode(tmp, "node-alpha", "v91-demo-a-20261121",
                         ("measurement", "federation"), key_a,
                         "node-beta", key_b.public_key())
        beta = DemoNode(tmp, "node-beta", "v91-demo-b-20261121",
                        ("witness", "status-exchange"), key_b,
                        "node-alpha", key_a.public_key())
        try:
            for cycle in range(args.cycles):
                print("cycle " + str(cycle + 1) + " of " + str(args.cycles))
                alpha.exchange_with(beta)
                time.sleep(0.1)
        finally:
            alpha.listener.stop()
            beta.listener.stop()
        alpha.file_and_report()
        beta.file_and_report()
    print("demo finished cleanly; nothing installed, nothing left behind.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
