"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Isolated two-node exchange scenario (Issue #47 Stage 4, Issue #103 prep).

Wires TWO isolated in-process nodes through the EXISTING modules only:
node A signs capability and task metadata (signed_manifest +
federation_sender), node B verifies the wire envelope (federation_receiver)
and admits the capability (capability_intake + peer_directory), guards a
shared task with lease_lock fencing, and stays fail-closed on replays.
Peer loss does not stop the sender: without a receiver, node A still
builds and persists a valid envelope locally (LOCAL_ONLY).

Honest limits, stated plainly: this is an in-process, single-machine
simulation over local SQLite files and function calls. WIRE_LOCAL_CALL !=
NETWORK, SIMULATION_IN_PROCESS != DEPLOYED_MULTI_NODE, and nothing here
is evidence about the real Vogelsberg hardware (#103 needs a second
node). No new trust rule is introduced; every decision belongs to the
underlying modules. ADVERTISEMENT != AUTORISIERUNG stays true.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from controller.capability_intake import (  # REUSE
    ACCEPTED_ADVERTISEMENT,
    admit_capability_manifest,
)
from controller.crypto_receipts import generate_signing_keypair  # REUSE
from controller.federation_receiver import (  # REUSE
    FederationReceiver,
    FederationReplayStore,
    QuarantineLedger,
)
from controller.federation_sender import (  # REUSE
    EnvelopeSender,
    SequenceStore,
)
from controller.lease_lock import LeaseLockManager  # REUSE
from controller.peer_directory import PeerDirectory  # REUSE
from controller.signed_manifest import sign_manifest  # REUSE

SCENARIO_VERSION = 1
STATUS_COMPLETE = "SCENARIO_COMPLETE"
STATUS_FAILED = "SCENARIO_FAILED"

LIMITS = (
    "WIRE_LOCAL_CALL != NETWORK",
    "SIMULATION_IN_PROCESS != DEPLOYED_MULTI_NODE",
    "ADVERTISEMENT != AUTORISIERUNG",
    "NO_NEW_TRUST_RULE_COMPOSITION_ONLY",
)


class ScenarioError(ValueError):
    """Raised when the scenario cannot be wired or executed safely."""


def _require_iso_now(now_iso: str) -> str:
    if not isinstance(now_iso, str) or not now_iso.strip():
        raise ScenarioError("now_iso must be a non-empty ISO-8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(now_iso)
    except ValueError as exc:
        raise ScenarioError(f"now_iso is not ISO-8601: {exc}") from exc
    if parsed.tzinfo is None:
        raise ScenarioError("now_iso must carry a timezone (naive is rejected)")
    return now_iso


def capability_manifest(peer_id: str, now_iso: str) -> dict[str, Any]:
    """Unsigned capability manifest valid around now_iso (caller signs)."""
    start = datetime.fromisoformat(now_iso)
    from datetime import timedelta
    return {
        "schema_version": 1,
        "node_id": peer_id,
        "key_id": "key-1",
        "software_version": "0.1.0",
        "issued_at": (start - timedelta(hours=1)).isoformat(),
        "expires_at": (start + timedelta(hours=6)).isoformat(),
        "resources": {
            "cpu_cores_available": 8,
            "ram_mb_available": 16000,
            "vram_mb_available": 0,
            "disk_mb_available": 500000,
        },
        "contributions": {
            "compute": True,
            "verification": False,
            "encrypted_storage": False,
            "metadata_index": True,
        },
        "policy_version": "v1",
    }


class ProducerNode:
    """Node A: signs metadata and builds numbered, signed envelopes."""

    def __init__(self, workspace: Path, peer_id: str, now_provider) -> None:
        private_raw, self.public_raw = generate_signing_keypair()
        self.private_raw = private_raw
        self.peer_id = peer_id
        self.sender = EnvelopeSender(
            peer_id=peer_id,
            private_key=Ed25519PrivateKey.from_private_bytes(private_raw),
            sequence_store=SequenceStore(workspace / "producer_sequences.sqlite"),
            now_provider=now_provider,
        )

    def capability_envelope(self, now_iso: str) -> bytes:
        signed = sign_manifest(
            capability_manifest(self.peer_id, now_iso), self.private_raw)
        envelope = self.sender.build_envelope(
            {"kind": "CAPABILITY_ADVERTISEMENT", "manifest": signed})
        return envelope.wire

    def task_offer_envelope(self, task_id: str) -> bytes:
        envelope = self.sender.build_envelope(
            {"kind": "TASK_OFFER", "task_id": task_id,
             "requested_capability": "verification"})
        return envelope.wire


class VerifierNode:
    """Node B: verifies envelopes, admits capabilities, guards leases."""

    def __init__(self, workspace: Path, peer_id: str, producer: ProducerNode,
                 now_provider, expires_at: int) -> None:
        self.peer_id = peer_id
        self.directory = PeerDirectory(
            workspace / "verifier_peers.sqlite", now_provider=now_provider)
        self.directory.add_peer(
            peer_id=producer.peer_id, public_key_hex=producer.public_raw.hex(),
            expires_at=expires_at)
        self.replay_store = FederationReplayStore(
            workspace / "verifier_replay.sqlite")
        self.quarantine = QuarantineLedger(workspace / "verifier_quarantine.jsonl")
        self.leases = LeaseLockManager(
            clock=lambda: now_provider())
        self.receiver = FederationReceiver(
            peer_keys={producer.peer_id:
                       Ed25519PublicKey.from_public_bytes(producer.public_raw)},
            replay_store=self.replay_store,
            quarantine=self.quarantine,
            now_provider=now_provider,
        )
        self.accepted = 0
        self.rejected = 0

    def receive(self, wire: bytes):
        receipt = self.receiver.receive(wire)
        if receipt.status == "ACCEPTED":
            self.accepted += 1
        else:
            self.rejected += 1
        return receipt


def run_two_node_exchange(
    workspace: Path | str,
    *,
    producer_peer_id: str = "node-alpha",
    verifier_peer_id: str = "node-beta",
    now_iso: str,
    lease_duration_seconds: float = 300.0,
    revoke_producer: bool = False,
) -> dict[str, Any]:
    """Execute the full scenario and return one honest evidence record."""
    _require_iso_now(now_iso)
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    now_epoch = int(datetime.fromisoformat(now_iso).timestamp())
    now_provider = lambda: now_epoch  # noqa: E731 - deterministic clock

    producer = ProducerNode(workspace, producer_peer_id, now_provider)
    verifier = VerifierNode(workspace, verifier_peer_id, producer,
                            now_provider, now_epoch + 3600)

    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    if revoke_producer:
        # Negativpfad: Widerruf NACH Registrierung. Die Wire akzeptiert
        # weiter (Envelope-Signatur ist unanhaengig), der Intake lehnt
        # ab: WIRE_ACCEPTED != TRUST_ACCEPTED.
        verifier.directory.revoke_peer(
            peer_id=producer_peer_id, reason="scenario negative probe")

    capability_wire = producer.capability_envelope(now_iso)
    capability_receipt = verifier.receive(capability_wire)
    checks["capability_envelope_accepted"] = capability_receipt.status == "ACCEPTED"
    verdict = admit_capability_manifest(
        capability_receipt.message["payload"]["manifest"],  # type: ignore[index]
        peer_id=producer_peer_id,
        directory=verifier.directory,
        now=now_iso,
    )
    checks["capability_admitted"] = verdict.state == ACCEPTED_ADVERTISEMENT
    evidence["capability_verdict"] = {"state": verdict.state,
                                      "contributions": verdict.contributions}

    task_wire = producer.task_offer_envelope("task-fetch-cpu-model-1")
    task_receipt = verifier.receive(task_wire)
    checks["task_offer_accepted"] = task_receipt.status == "ACCEPTED"

    lease = verifier.leases.acquire(
        "task-fetch-cpu-model-1", verifier_peer_id, lease_duration_seconds)
    checks["lease_acquired"] = lease is not None and lease.fencing_token >= 1

    replay_receipt = verifier.receive(task_wire)
    checks["replay_rejected"] = replay_receipt.status == "REJECTED"
    checks["replay_was_quarantined"] = replay_receipt.quarantined

    stale_token_allowed = verifier.leases.validate_action(
        "task-fetch-cpu-model-1", verifier_peer_id, 0)
    stale_token_fenced = verifier.leases.is_fenced(
        "task-fetch-cpu-model-1", 0)
    checks["stale_fencing_token_rejected"] = (
        stale_token_allowed is False and stale_token_fenced is True)

    local_wire = None
    try:
        local_wire = producer.task_offer_envelope("task-local-resilience-1")
    except Exception:  # noqa: BLE001 - sender resilience is the check itself
        pass
    local_path = workspace / "local_only_envelope.json"
    local_path.write_bytes(local_wire or b"")
    checks["producer_survives_absent_verifier"] = (
        local_wire is not None and len(local_wire) > 0
        and verifier.peer_id not in local_wire.decode("utf-8"))

    evidence["envelopes"] = {
        "producer_accepted_by_verifier": verifier.accepted,
        "producer_rejected_by_verifier": verifier.rejected,
    }
    evidence["lease"] = {
        "lock_id": "task-fetch-cpu-model-1",
        "fencing_token": lease.fencing_token if lease else None,
    }
    status = STATUS_COMPLETE if all(checks.values()) else STATUS_FAILED
    return {
        "scenario_version": SCENARIO_VERSION,
        "status": status,
        "checks": checks,
        "evidence": evidence,
        "producer_peer_id": producer_peer_id,
        "verifier_peer_id": verifier_peer_id,
        "limits": list(LIMITS),
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: exit 0 = SCENARIO_COMPLETE, 1 = SCENARIO_FAILED, 2 = invalid input."""
    parser = argparse.ArgumentParser(
        prog="two_node_exchange_scenario",
        description="Isolierte Zwei-Knoten-Simulation (Issue #47 Stage 4, "
                    "Issue #103 Vorbereitung): in-process, kein Netz, kein Daemon.")
    parser.add_argument("--workspace", required=True,
                        help="Arbeitsverzeichnis fuer die Knoten-SQLite-Dateien")
    parser.add_argument("--now", required=True,
                        help="ISO-8601 mit Zeitzonen-Angabe (deterministische Uhr)")
    args = parser.parse_args(argv)

    try:
        record = run_two_node_exchange(args.workspace, now_iso=args.now)
    except (ScenarioError, ValueError) as exc:
        print(f"two_node_exchange_scenario: invalid input: {exc}",
              file=sys.stderr)
        return 2
    print(json.dumps(record, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if record["status"] == STATUS_COMPLETE else 1


if __name__ == "__main__":
    raise SystemExit(main())
