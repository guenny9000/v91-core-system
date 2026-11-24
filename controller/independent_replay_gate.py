"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------

Independent replay verification gate (Issue #47, Stage 2 completion).

model_run_manifest.verify_exact_replay compares two run records but has
no notion of WHO produced and WHO replayed them. The capability-aware
model autonomy specification requires that a model cannot verify itself.
This gate closes that gap: it binds a producer_id and a verifier_id to
the comparison and refuses self-verification outright.

Limits, stated plainly: matching digests under pinned conditions are
evidence of byte-identical output, not of truth. Identity strings here
are caller-supplied labels, not cryptographic identities; binding them
to registry keys is the job of capability_intake and the trusted peer
registry (Issue #47 work), not of this module. UNKNOWN stays UNKNOWN.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Optional

from controller.model_run_manifest import verify_exact_replay  # REUSE

GATE_VERSION = 1
STATUS_VERIFIED = "VERIFIED_EXACT_INDEPENDENT"


class IndependentReplayError(ValueError):
    """Raised when an independent replay verdict cannot be safely issued."""


def _require_id(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise IndependentReplayError(f"{name} must be a non-empty trimmed identifier string")
    if len(value) > 128:
        raise IndependentReplayError(f"{name} exceeds the 128-character limit")
    return value


def verify_independent_replay(
    reference: Mapping[str, object],
    replay: Mapping[str, object],
    *,
    producer_id: str,
    verifier_id: str,
) -> dict[str, object]:
    """Compare two run records and bind the verdict to distinct nodes.

    Fail-closed: the producer of a run record may not act as the replay
    verifier. Anything less than exact replay keeps the run unverified.
    """
    producer = _require_id("producer_id", producer_id)
    verifier = _require_id("verifier_id", verifier_id)
    if producer == verifier:
        raise IndependentReplayError(
            "SELF_VERIFICATION_FORBIDDEN: the producer of a run record "
            "cannot be its own replay verifier"
        )
    result = verify_exact_replay(reference, replay)
    if result["status"] == "VERIFIED_EXACT":
        return {
            "gate_version": GATE_VERSION,
            "status": STATUS_VERIFIED,
            "reason": result["reason"],
            "producer_id": producer,
            "verifier_id": verifier,
        }
    return {
        "gate_version": GATE_VERSION,
        "status": result["status"],
        "reason": result["reason"],
        "producer_id": producer,
        "verifier_id": verifier,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: exit 0 = VERIFIED_EXACT_INDEPENDENT, 1 = anderer Pruef-Befund, 2 = ungueltige Eingabe."""
    parser = argparse.ArgumentParser(
        prog="independent_replay_gate",
        description="Issue an independent replay verdict for two pinned "
                    "run records; refuses self-verification.")
    parser.add_argument("--reference", required=True,
                        help="Pfad zur Referenz-Run-JSON (Produzent)")
    parser.add_argument("--replay", required=True,
                        help="Pfad zur Replay-Run-JSON (verifizierender Knoten)")
    parser.add_argument("--producer-id", required=True,
                        help="node_id des Produzenten der Referenz")
    parser.add_argument("--verifier-id", required=True,
                        help="node_id des verifizierenden Replay-Knotens")
    args = parser.parse_args(argv)

    records = []
    for path in (args.reference, args.replay):
        try:
            with open(path, encoding="utf-8") as fh:
                records.append(json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"independent_replay_gate: I/O error: {exc}", file=sys.stderr)
            return 2

    try:
        verdict = verify_independent_replay(
            records[0], records[1],
            producer_id=args.producer_id, verifier_id=args.verifier_id)
    except (IndependentReplayError, ValueError) as exc:
        print(f"independent_replay_gate: rejected input: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(verdict, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if verdict["status"] == STATUS_VERIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
