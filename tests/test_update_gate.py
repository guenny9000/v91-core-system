#!/usr/bin/env python3
"""Tests for controller/update_gate.py (Issue #8, signed updates +
isolation boundary). All tests are stdlib-only and use generated
Ed25519 keys; no real publisher keys or live flags are involved."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from controller.update_gate import (
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    TrustedUpdateKeys,
    UpdateGate,
    UpdateGateError,
    build_update_manifest,
    generate_signing_keypair,
)

NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)


class UpdateGateTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.priv_a, self.pub_a = generate_signing_keypair()
        self.priv_b, self.pub_b = generate_signing_keypair()
        self.trusted = TrustedUpdateKeys({"publisher-alpha": self.pub_a})
        self.gate = UpdateGate(self.trusted, now=NOW)
        self.tmp = Path(tempfile.mkdtemp())
        self.payload = b"demo-update-payload-bytes"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def manifest(self, **overrides):
        return build_update_manifest(
            release_name="demo-release",
            payload=self.payload,
            publisher_key_id="publisher-alpha",
            private_key=self.priv_a,
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=24),
            **overrides,
        )


class ManifestVerificationTests(UpdateGateTestBase):
    def test_valid_signed_manifest_accepted(self) -> None:
        verdict = self.gate.verify_manifest(self.manifest())
        self.assertEqual(verdict.status, "ACCEPTED_TRUSTED")
        self.assertEqual(verdict.key_id, "publisher-alpha")

    def test_unknown_publisher_key_rejected(self) -> None:
        manifest = build_update_manifest(
            release_name="r", payload=self.payload,
            publisher_key_id="publisher-beta", private_key=self.priv_b,
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1))
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("not trusted", verdict.reason)

    def test_revoked_publisher_key_rejected(self) -> None:
        trusted = TrustedUpdateKeys(
            {"publisher-alpha": self.pub_a},
            revoked_key_ids=("publisher-alpha",))
        gate = UpdateGate(trusted, now=NOW)
        verdict = gate.verify_manifest(self.manifest())
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("revoked", verdict.reason)

    def test_wrong_key_signature_rejected(self) -> None:
        manifest = build_update_manifest(
            release_name="r", payload=self.payload,
            publisher_key_id="publisher-alpha", private_key=self.priv_b,
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1))
        self.assertEqual(self.gate.verify_manifest(manifest).status,
                         STATUS_REJECTED)

    def test_tampered_payload_digest_rejected(self) -> None:
        manifest = self.manifest()
        manifest["payload_sha256"] = "0" * 64
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("signature invalid", verdict.reason)

    def test_unsigned_manifest_rejected(self) -> None:
        manifest = self.manifest()
        del manifest["receipt_signature"]
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("unsigned", verdict.reason)

    def test_naive_timestamps_rejected(self) -> None:
        manifest = self.manifest()
        manifest["receipt_signature"] = "0" * 128
        manifest["created_at"] = "2026-11-19T11:00:00"
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("malformed", verdict.reason)

    def test_expired_manifest_rejected(self) -> None:
        manifest = build_update_manifest(
            release_name="r", payload=self.payload,
            publisher_key_id="publisher-alpha", private_key=self.priv_a,
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=9))
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("expired", verdict.reason)

    def test_not_yet_valid_manifest_rejected(self) -> None:
        manifest = build_update_manifest(
            release_name="r", payload=self.payload,
            publisher_key_id="publisher-alpha", private_key=self.priv_a,
            created_at=NOW + timedelta(hours=1),
            expires_at=NOW + timedelta(hours=2))
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("not valid yet", verdict.reason)

    def test_bad_schema_kind_rejected(self) -> None:
        manifest = self.manifest()
        manifest["kind"] = "SOMETHING_ELSE"
        verdict = self.gate.verify_manifest(manifest)
        self.assertIn("kind", verdict.reason)

    def test_wrong_digest_format_rejected(self) -> None:
        manifest = self.manifest()
        manifest["payload_sha256"] = "nothex"
        verdict = self.gate.verify_manifest(manifest)
        self.assertEqual(verdict.status, STATUS_REJECTED)


class IsolationBoundaryTests(UpdateGateTestBase):
    def test_stage_valid_payload(self) -> None:
        verdict = self.gate.stage_payload(self.manifest(), self.payload,
                                         self.tmp / "staging")
        self.assertEqual(verdict.status, STATUS_ACCEPTED)
        staged = self.tmp / "staging" / "demo-release.staged"
        self.assertTrue(staged.exists())
        self.assertEqual(staged.read_bytes(), self.payload)

    def test_stage_refuses_payload_digest_mismatch(self) -> None:
        verdict = self.gate.stage_payload(self.manifest(), b"other",
                                         self.tmp / "staging")
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("sha256 mismatch", verdict.reason)

    def test_stage_refuses_payload_size_mismatch(self) -> None:
        manifest = dict(self.manifest())
        digest = manifest["payload_sha256"]
        body = {k: v for k, v in manifest.items()
                if k != "receipt_signature"}
        body["payload_size_bytes"] = len(self.payload) + 1
        from controller.crypto_receipts import sign_record
        manifest = body
        manifest["receipt_signature"] = sign_record(body, self.priv_a)
        self.assertEqual(manifest["payload_sha256"], digest)
        verdict = self.gate.stage_payload(manifest, self.payload,
                                         self.tmp / "staging")
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("size mismatch", verdict.reason)

    def test_stage_refuses_overwrite_of_existing_artifact(self) -> None:
        staging = self.tmp / "staging"
        self.gate.stage_payload(self.manifest(), self.payload, staging)
        verdict = self.gate.stage_payload(self.manifest(), self.payload,
                                          staging)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("already exists", verdict.reason)

    def test_stage_rejects_untrusted_publisher_before_any_write(self) -> None:
        staging = self.tmp / "staging"
        manifest = build_update_manifest(
            release_name="r2", payload=self.payload,
            publisher_key_id="publisher-unknown", private_key=self.priv_b,
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1))
        verdict = self.gate.stage_payload(manifest, self.payload, staging)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertFalse((staging / "r2.staged").exists())

    def test_no_execute_function_exists(self) -> None:
        gate_methods = [name for name in dir(UpdateGate)
                        if not name.startswith("_")]
        for forbidden in ("install", "execute", "promote", "run"):
            self.assertFalse(
                any(forbidden in name for name in gate_methods),
                f"UpdateGate must not expose '{forbidden}' functionality")


class TrustedKeysTests(UpdateGateTestBase):
    def test_empty_trusted_key_set_rejected(self) -> None:
        with self.assertRaises(UpdateGateError):
            TrustedUpdateKeys({})

    def test_revocation_of_unknown_key_rejected(self) -> None:
        with self.assertRaises(UpdateGateError):
            TrustedUpdateKeys({"publisher-alpha": self.pub_a},
                              revoked_key_ids=("ghost",))

    def test_invalid_public_key_length_rejected(self) -> None:
        with self.assertRaises(UpdateGateError):
            TrustedUpdateKeys({"publisher-alpha": b"short"})

    def test_gate_requires_timezone_aware_now(self) -> None:
        with self.assertRaises(UpdateGateError):
            UpdateGate(self.trusted, now=datetime(2026, 11, 19, 12, 0, 0))


if __name__ == "__main__":
    unittest.main()
