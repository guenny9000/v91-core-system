"""Tests for the bounded mesh frame codec (LoRa-class, no transport)."""
import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.mesh_frame_codec import (  # noqa: E402
    FrameError, MAX_FRAME_BYTES, MeshFrame, decode_frame, encode_frame,
)

SECRET = b"0123456789abcdef0123456789abcdef"  # 32 bytes
SHORT_SECRET = b"too-short-secret"


def make_frame(**overrides) -> MeshFrame:
    fields = {"node_id": "node_alsfeld_01", "epoch": 1, "seq": 1,
              "frame_type": "M", "payload": {"temperature_c": 21.5}}
    fields.update(overrides)
    return MeshFrame(**fields)


class MeshFrameCodecTest(unittest.TestCase):
    def test_roundtrip_accepted(self):
        frame = make_frame()
        wire = encode_frame(frame, SECRET)
        result = decode_frame(wire, SECRET)
        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(result.frame, frame)

    def test_wire_format_is_canonical_and_bounded(self):
        wire = encode_frame(make_frame(), SECRET)
        self.assertLessEqual(len(wire), MAX_FRAME_BYTES)
        body, mac = wire.rsplit(b"|", 1)
        parsed = json.loads(body.decode("utf-8"))
        recanonical = json.dumps(parsed, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")
        self.assertEqual(body, recanonical)
        self.assertEqual(len(mac), 64)

    def test_wrong_secret_rejected(self):
        wire = encode_frame(make_frame(), SECRET)
        result = decode_frame(wire, b"Z" * 32)
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("MAC", result.reason)

    def test_tampered_body_rejected(self):
        wire = bytearray(encode_frame(make_frame(), SECRET))
        wire[0] = wire[0] ^ 0x01
        result = decode_frame(bytes(wire), SECRET)
        self.assertEqual(result.status, "REJECTED")

    def test_truncated_mac_spec_rejected_by_design(self):
        # The chat spec (16-byte truncated MAC) must not verify here.
        frame = make_frame()
        body = json.dumps({"node_id": frame.node_id, "epoch": frame.epoch,
                           "seq": frame.seq, "frame_type": frame.frame_type,
                           "payload": frame.payload},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        full_mac = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        truncated = (body + b"|" + full_mac[:32].encode("ascii"))
        result = decode_frame(truncated, SECRET)
        self.assertEqual(result.status, "REJECTED")

    def test_oversize_payload_refused_on_encode(self):
        big_payload = {f"k{i}": i for i in range(200)}
        with self.assertRaises(FrameError):
            encode_frame(make_frame(payload=big_payload), SECRET)

    def test_oversized_wire_rejected_on_decode(self):
        result = decode_frame(b"x" * (MAX_FRAME_BYTES + 1), SECRET)
        self.assertEqual(result.status, "REJECTED")

    def test_schema_violations_refused_on_encode(self):
        with self.assertRaises(FrameError):
            MeshFrame(node_id="", epoch=1, seq=1, frame_type="M", payload={})
        with self.assertRaises(FrameError):
            MeshFrame(node_id="n", epoch=True, seq=1, frame_type="M", payload={})
        with self.assertRaises(FrameError):
            MeshFrame(node_id="n", epoch=1, seq=0, frame_type="M", payload={})
        with self.assertRaises(FrameError):
            MeshFrame(node_id="n", epoch=1, seq=1, frame_type="X", payload={})
        with self.assertRaises(FrameError):
            MeshFrame(node_id="n", epoch=1, seq=1, frame_type="M", payload=[])

    def test_extra_keys_rejected_on_decode(self):
        body = json.dumps({"node_id": "n", "epoch": 1, "seq": 1,
                           "frame_type": "M", "payload": {}, "extra": 1},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        mac = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        result = decode_frame(body + b"|" + mac.encode("ascii"), SECRET)
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("schema", result.reason)

    def test_non_canonical_body_rejected_on_decode(self):
        body = json.dumps({"node_id": "n", "epoch": 1, "seq": 1,
                           "frame_type": "M", "payload": {}},
                          separators=(",", ": ")).encode("utf-8")  # non-canonical spacing
        mac = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        result = decode_frame(body + b"|" + mac.encode("ascii"), SECRET)
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("canonical", result.reason)

    def test_short_secret_fail_closed(self):
        with self.assertRaises(FrameError):
            encode_frame(make_frame(), SHORT_SECRET)
        result = decode_frame(encode_frame(make_frame(), SECRET), SHORT_SECRET)
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("fail-closed", result.reason)

    def test_accepted_frame_accessor_and_rejection_guard(self):
        ok = decode_frame(encode_frame(make_frame(), SECRET), SECRET)
        self.assertEqual(ok.accepted_frame().node_id, "node_alsfeld_01")
        bad = decode_frame(b"", SECRET)
        with self.assertRaises(FrameError):
            bad.accepted_frame()

    def test_replay_is_explicitly_out_of_scope(self):
        # The codec is stateless by design: replaying a wire frame must
        # still verify (durable floors live in federation_receiver).
        wire = encode_frame(make_frame(seq=7), SECRET)
        first = decode_frame(wire, SECRET)
        second = decode_frame(wire, SECRET)
        self.assertEqual(first.status, "ACCEPTED")
        self.assertEqual(second.status, "ACCEPTED")


if __name__ == "__main__":
    unittest.main()
