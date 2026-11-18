"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Strict adapter: accepted M-frames to the measurement ingest contract.

This module gives M-frame payload dicts an exact wire contract and
turns them into RawMeasurement objects without inventing, duplicating,
or repairing anything.

Capacity finding (measured, not assumed): a strict measurement
payload with a full RFC-3339 timestamp is ~150-175 canonical bytes;
the LoRa-class frame budget (MAX_FRAME_BYTES 222 minus separator and
full 64-hex MAC) leaves 157 bytes for the frame body. Consequences,
documented honestly instead of silently weakened:
- producers MUST choose compact identifiers (short node/sensor ids,
  short metric names, unit symbols) to stay inside the budget;
- "source" is OPTIONAL in the wire contract: a bandwidth-constrained
  radio node may omit it (RawMeasurement then carries the explicit
  default "unknown"), but a PRESENT source must be a non-empty
  string. Omission is a visible fact in the data, never a guess.

Honest limits (ADAPTER != TRANSPORT):
- No radio, no network, no persistence, no ledger write: the caller
  owns transport and storage (SHIPPING != INSTALLATION).
- Only frames already ACCEPTED by decode_frame are meaningful here;
  acceptance proves the MAC matched, not that the sensor is real.
- V-frames are rejected: their payload semantics (votes/consensus)
  are a separate contract, never silently reinterpreted.
- Sensor specification validation stays in measurement_ingest; this
  adapter cannot bless a metric (UNKNOWN != PASS).
"""
from __future__ import annotations

from mesh_frame_codec import FrameError, MeshFrame

from measurement_ingest import RawMeasurement

# Exact M-frame payload wire contract (MEASUREMENT_FRAME == frame_type 'M').
# Required keys are exact: no extra keys, no missing keys, no silent
# renames. 'source' is the one bandwidth exemption (see module docstring).
MEASUREMENT_FRAME = "M"
MEASUREMENT_PAYLOAD_KEYS = frozenset(
    {"sensor_id", "metric", "value", "unit", "timestamp"}
)
OPTIONAL_PAYLOAD_KEYS = frozenset({"source"})


def measurement_from_frame(frame: MeshFrame) -> RawMeasurement:
    """Turn an accepted M-frame into a RawMeasurement, fail-closed.

    Raises FrameError for anything that violates the strict measurement
    wire contract; never guesses, defaults silently, or repairs fields.
    """
    if not isinstance(frame, MeshFrame):
        raise FrameError("frame must be a MeshFrame (fail-closed)")
    if frame.frame_type != MEASUREMENT_FRAME:
        raise FrameError(
            f"frame_type must be {MEASUREMENT_FRAME!r} for measurement "
            f"ingest; got {frame.frame_type!r}"
        )
    payload = frame.payload
    if not isinstance(payload, dict):
        raise FrameError("M-frame payload must be a JSON object")
    keys = frozenset(payload.keys())
    allowed = set(MEASUREMENT_PAYLOAD_KEYS) | set(OPTIONAL_PAYLOAD_KEYS)
    if not set(MEASUREMENT_PAYLOAD_KEYS) <= keys:
        missing = sorted(set(MEASUREMENT_PAYLOAD_KEYS) - keys)
        raise FrameError(
            "M-frame payload schema mismatch (required keys missing); "
            f"missing={missing}"
        )
    extra = sorted(keys - allowed)
    if extra:
        raise FrameError(
            "M-frame payload schema mismatch (unknown keys rejected); "
            f"extra={extra}"
        )
    required_strings = ("sensor_id", "metric", "unit", "timestamp")
    for key in required_strings:
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise FrameError(f"payload field {key!r} must be a non-empty string")
    if "source" in payload:
        if not isinstance(payload["source"], str) or not payload["source"].strip():
            raise FrameError(
                "payload field 'source' must be a non-empty string when present"
            )
    value = payload["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FrameError(
            "payload field 'value' must be a numeric int or float "
            "(booleans and strings are rejected)"
        )
    return RawMeasurement(
        sensor_id=payload["sensor_id"],
        metric=payload["metric"],
        value=value,
        unit=payload["unit"],
        timestamp=payload["timestamp"],
        source=payload.get("source", "unknown"),
    )
