#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Mesh frame codec for compact radio transports (LoRa-class, Issue #103).

Pure encode/verify layer for bounded, canonically serialized frames:
- fixed schema: node_id, epoch, seq, frame_type, payload
- canonical JSON (sort_keys=True, separators=(",", ":")) so both sides
  produce byte-identical payloads before MAC computation
- hard frame-size limit (MAX_FRAME_BYTES, default 222 for LoRa-class
  radios), fail-closed on encode and decode
- HMAC-SHA256 over the exact frame bytes, compared in constant time

Honest limits (DOCUMENTED != IMPLEMENTED elsewhere):
- NO radio, SDR, serial port, or network transport: this module turns
  dicts into bounded verified frames and back; wiring to a radio is a
  separately reviewed phase (SHIPPING != INSTALLATION).
- NO replay protection here: replay floors live in the durable
  receivers (federation_receiver.FederationReplayStore); a codec cannot
  and must not pretend to have persistent state.
- The 16-byte truncated MAC from the chat specification (32 hex chars)
  is deliberately NOT implemented: truncation halves collision
  resistance for zero benefit inside a 222-byte budget that easily
  fits a full 64-hex MAC. Full 32-byte MACs only.
- HMAC with pre-shared secrets identifies nodes inside a closed mesh;
  it is NOT a substitute for the Ed25519 peer identities used by the
  open federation receiver.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

FRAME_TYPES = frozenset({"M", "V"})  # M = measurement, V = vote/consensus
MAX_FRAME_BYTES = 222  # LoRa-class payload budget
_MAC_HEX_LEN = 64  # full HMAC-SHA256, never truncated
_FRAME_SEPARATOR = b"|"
_REQUIRED_KEYS = frozenset({"node_id", "epoch", "seq", "frame_type", "payload"})


class FrameError(ValueError):
    """Raised when a frame violates the codec contract (fail-closed)."""


@dataclass(frozen=True)
class MeshFrame:
    node_id: str
    epoch: int
    seq: int
    frame_type: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id or len(self.node_id) > 32:
            raise FrameError("node_id must be a non-empty string of at most 32 chars")
        if type(self.epoch) is not int or self.epoch < 0:
            raise FrameError("epoch must be a non-negative int (bool is not accepted)")
        if type(self.seq) is not int or self.seq < 1:
            raise FrameError("seq must be a positive int starting at 1 (bool is not accepted)")
        if self.frame_type not in FRAME_TYPES:
            raise FrameError(f"frame_type must be one of {sorted(FRAME_TYPES)}")
        if not isinstance(self.payload, dict):
            raise FrameError("payload must be a JSON object")


def _canonical_bytes(frame: MeshFrame) -> bytes:
    body = {
        "node_id": frame.node_id,
        "epoch": frame.epoch,
        "seq": frame.seq,
        "frame_type": frame.frame_type,
        "payload": frame.payload,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def encode_frame(frame: MeshFrame, secret: bytes) -> bytes:
    """Encode a frame into bounded wire bytes: canonical JSON + '|' + MAC hex.

    Fails closed (FrameError) on any schema violation or if the result
    would exceed MAX_FRAME_BYTES.
    """
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise FrameError("shared secret must be >= 32 raw bytes (fail-closed)")
    body = _canonical_bytes(frame)
    if len(body) > MAX_FRAME_BYTES - len(_FRAME_SEPARATOR) - _MAC_HEX_LEN:
        raise FrameError(
            f"frame body too large: {len(body)} bytes exceeds budget "
            f"{MAX_FRAME_BYTES - len(_FRAME_SEPARATOR) - _MAC_HEX_LEN}")
    mac = hmac.new(secret, body, hashlib.sha256).hexdigest()
    wire = body + _FRAME_SEPARATOR + mac.encode("ascii")
    if len(wire) > MAX_FRAME_BYTES:
        raise FrameError("frame exceeds MAX_FRAME_BYTES after MAC append")
    return wire


@dataclass(frozen=True)
class DecodeResult:
    status: str  # "ACCEPTED" or "REJECTED"
    frame: MeshFrame | None
    reason: str

    def accepted_frame(self) -> MeshFrame:
        if self.frame is None:
            raise FrameError(f"no accepted frame: {self.status} ({self.reason})")
        return self.frame


def decode_frame(wire: bytes, secret: bytes) -> DecodeResult:
    """Verify and decode a wire frame. MAC check happens FIRST, then parsing.

    Returns a DecodeResult; never raises for rejected frames (the caller
    decides where to quarantine the raw bytes, ISOLATE_NOT_DESTROY).
    """

    def reject(reason: str) -> DecodeResult:
        return DecodeResult("REJECTED", None, reason)

    if not isinstance(secret, bytes) or len(secret) < 32:
        return reject("secret not configured (fail-closed)")
    if not isinstance(wire, bytes) or not wire:
        return reject("empty or non-bytes frame")
    if len(wire) > MAX_FRAME_BYTES:
        return reject(f"frame larger than MAX_FRAME_BYTES ({len(wire)} > {MAX_FRAME_BYTES})")
    sep_index = wire.rfind(_FRAME_SEPARATOR)
    if sep_index < 0 or len(wire) - sep_index - 1 != _MAC_HEX_LEN:
        return reject("malformed frame: missing or wrong-length MAC")
    body, mac_bytes = wire[:sep_index], wire[sep_index + 1:]
    try:
        mac = mac_bytes.decode("ascii")
    except UnicodeDecodeError:
        return reject("MAC is not ASCII hex")
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        return reject("MAC verification failed")
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return reject("body is not valid UTF-8 JSON")
    if not isinstance(parsed, dict) or set(parsed.keys()) != set(_REQUIRED_KEYS):
        return reject("body schema mismatch (exact key set required)")
    if json.dumps(parsed, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=False, allow_nan=False).encode("utf-8") != body:
        return reject("body is not in canonical form")
    try:
        frame = MeshFrame(node_id=parsed["node_id"], epoch=parsed["epoch"],
                          seq=parsed["seq"], frame_type=parsed["frame_type"],
                          payload=parsed["payload"])
    except FrameError as exc:
        return reject(f"field validation failed: {exc}")
    return DecodeResult("ACCEPTED", frame, "ok")
