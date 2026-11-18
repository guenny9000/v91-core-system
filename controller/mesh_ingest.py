"""V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Strict adapter: accepted M-frames to the measurement ingest contract.

This module closes the gap between mesh_frame_codec (bounded verified
wire frames) and the measurement pipeline: it gives M-frame payload
dicts an exact wire contract and turns them into RawMeasurement
objects without inventing, duplicating, or repairing anything.

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

# Exact M-frame payload wire contract (MEASUREMENT_FRAME == frame_type 'M');
# no extra keys, no missing keys, no silent renames: a producer that
# changes the payload schema must fail loudly on every consumer.
MEASUREMENT_FRAME = "M"
MEASUREMENT_PAYLOAD_KEYS = frozenset(
    {"sensor_id", "metric", "value", "unit", "timestamp", "source"}
)


def measurement_from_frame(frame: MeshFrame) -> RawMeasurement:
    """Turn an accepted M-frame into a RawMeasurement, fail-closed.

    Raises FrameError for anything that violates the strict measurement
    wire contract; never guesses, defaults, or repairs payload fields.
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
    if set(payload.keys()) != set(MEASUREMENT_PAYLOAD_KEYS):
        missing = sorted(set(MEASUREMENT_PAYLOAD_KEYS) - set(payload.keys()))
        extra = sorted(set(payload.keys()) - set(MEASUREMENT_PAYLOAD_KEYS))
        raise FrameError(
            "M-frame payload schema mismatch (exact key set required); "
            f"missing={missing}, extra={extra}"
        )
    for key in ("sensor_id", "metric", "unit", "timestamp", "source"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise FrameError(f"payload field {key!r} must be a non-empty string")
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
        source=payload["source"],
    )
