"""
Tests for the strict M-frame measurement wire contract (mesh ingest adapter).

Proves the full chain encode -> decode -> measurement_from_frame ->
validate_measurement = VALID, and that every contract violation
(V-frames, missing/extra payload keys, bad types, MAC tampering)
fails closed instead of being silently reinterpreted.

"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Flat imports follow the repo convention (see tests/test_emergency_stop_wiring.py):
# controller/ is put on sys.path so the flat modules resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))

import controller  # noqa: F401,E402
import mesh_frame_codec  # noqa: E402
from mesh_frame_codec import DecodeResult, FrameError, MeshFrame, decode_frame  # noqa: E402
from mesh_ingest import MEASUREMENT_FRAME, MEASUREMENT_PAYLOAD_KEYS, measurement_from_frame  # noqa: E402
from measurement_ingest import (  # noqa: E402
    RawMeasurement,
    SensorSpec,
    validate_measurement,
)

SECRET = bytes(range(32))  # exactly 32 raw bytes, the documented minimum

SPECS = {
    "soil_moisture": SensorSpec(
        metric="soil_moisture",
        unit="percent",
        minimum=0.0,
        maximum=100.0,
        max_change_per_hour=50.0,
        max_gap_seconds=7200.0,
    ),
}


def make_m_frame(seq: int = 1, payload: dict | None = None) -> MeshFrame:
    if payload is None:
        payload = {
            "sensor_id": "vogelsberg-field-01",
            "metric": "soil_moisture",
            "value": 41.5,
            "unit": "percent",
            "timestamp": "2026-11-19T08:15:00+00:00",
            "source": "lora-mesh-node-3",
        }
    return MeshFrame(
        node_id="node-3", epoch=0, seq=seq, frame_type="M", payload=payload
    )


class MeasurementFromFrameTests(unittest.TestCase):
    def test_accepted_m_frame_roundtrip_to_valid_measurement(self) -> None:
        frame = make_m_frame()
        wire = mesh_frame_codec.encode_frame(frame, SECRET)
        result = decode_frame(wire, SECRET)
        self.assertEqual(result.status, "ACCEPTED")
        raw = measurement_from_frame(result.accepted_frame())
        self.assertIsInstance(raw, RawMeasurement)
        self.assertEqual(raw.sensor_id, "vogelsberg-field-01")
        self.assertEqual(raw.source, "lora-mesh-node-3")
        validation = validate_measurement(raw, SPECS)
        self.assertEqual(validation.status.value, "VALID")
        self.assertEqual(validation.timestamp_utc, "2026-11-19T08:15:00Z")

    def test_v_frame_is_rejected_not_reinterpreted(self) -> None:
        vote_frame = MeshFrame(
            node_id="node-3",
            epoch=0,
            seq=1,
            frame_type="V",
            payload={"proposal": "rotate-key", "vote": "yes"},
        )
        with self.assertRaises(FrameError):
            measurement_from_frame(vote_frame)

    def test_missing_payload_key_fails_closed(self) -> None:
        payload = {
            "sensor_id": "field-01",
            "metric": "soil_moisture",
            "value": 41.5,
            "unit": "percent",
            "timestamp": "2026-11-19T08:15:00+00:00",
        }
        with self.assertRaises(FrameError) as ctx:
            measurement_from_frame(make_m_frame(payload=payload))
        self.assertIn("missing", str(ctx.exception))

    def test_extra_payload_key_fails_closed(self) -> None:
        payload = {
            "sensor_id": "field-01",
            "metric": "soil_moisture",
            "value": 41.5,
            "unit": "percent",
            "timestamp": "2026-11-19T08:15:00+00:00",
            "source": "node-3",
            "confidence": "high",
        }
        with self.assertRaises(FrameError) as ctx:
            measurement_from_frame(make_m_frame(payload=payload))
        self.assertIn("extra", str(ctx.exception))

    def test_non_numeric_value_is_rejected(self) -> None:
        for bad in ("41.5", True, None, []):
            payload = {
                "sensor_id": "field-01",
                "metric": "soil_moisture",
                "value": bad,
                "unit": "percent",
                "timestamp": "2026-11-19T08:15:00+00:00",
                "source": "node-3",
            }
            with self.assertRaises(FrameError):
                measurement_from_frame(make_m_frame(payload=payload))

    def test_blank_string_fields_are_rejected(self) -> None:
        payload = {
            "sensor_id": "   ",
            "metric": "soil_moisture",
            "value": 41.5,
            "unit": "percent",
            "timestamp": "2026-11-19T08:15:00+00:00",
            "source": "node-3",
        }
        with self.assertRaises(FrameError):
            measurement_from_frame(make_m_frame(payload=payload))

    def test_contract_constants(self) -> None:
        self.assertEqual(MEASUREMENT_FRAME, "M")
        self.assertEqual(
            MEASUREMENT_PAYLOAD_KEYS,
            frozenset(
                {"sensor_id", "metric", "value", "unit", "timestamp", "source"}
            ),
        )

    def test_tampered_mac_stays_rejected_before_adapter(self) -> None:
        frame = make_m_frame()
        wire = bytearray(mesh_frame_codec.encode_frame(frame, SECRET))
        wire[-1] = wire[-1] ^ 0x01
        result = decode_frame(bytes(wire), SECRET)
        self.assertIsInstance(result, DecodeResult)
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reason, "MAC verification failed")

    def test_naive_timestamp_reaches_pipeline_as_quarantine(self) -> None:
        # The adapter is a contract bridge, not a validator: a naive
        # timestamp passes the wire contract (it is a non-empty string)
        # and the measurement pipeline quarantines it, exactly as for
        # every other source. The adapter must not pre-validate and
        # must not repair.
        payload = {
            "sensor_id": "field-01",
            "metric": "soil_moisture",
            "value": 41.5,
            "unit": "percent",
            "timestamp": "2026-11-19T08:15:00",
            "source": "node-3",
        }
        raw = measurement_from_frame(make_m_frame(payload=payload))
        validation = validate_measurement(raw, SPECS)
        self.assertEqual(validation.status.value, "QUARANTINE")

    def test_unknown_metric_is_quarantined_not_passed(self) -> None:
        payload = {
            "sensor_id": "field-01",
            "metric": "photon_flux",
            "value": 800.0,
            "unit": "umol",
            "timestamp": "2026-11-19T08:15:00+00:00",
            "source": "node-3",
        }
        raw = measurement_from_frame(make_m_frame(payload=payload))
        validation = validate_measurement(raw, SPECS)
        self.assertEqual(validation.status.value, "QUARANTINE")
        self.assertTrue(any("no valid sensor specification" in e for e in validation.errors))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
