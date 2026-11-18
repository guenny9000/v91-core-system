#!/usr/bin/env python3
"""Tests for controller/update_promotion.py (Issue #8, promote/rollback
for signed updates). Stdlib-only; generated Ed25519 keys via stub or
real cryptography - identical logic either way."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from controller.update_gate import (
    STATUS_REJECTED as GATE_REJECTED,
    STATUS_ACCEPTED,
    TrustedUpdateKeys,
    UpdateGate,
    UpdateGateError,
    build_update_manifest,
    generate_signing_keypair,
)
from controller.update_promotion import (
    ACTIVE_POINTER,
    PAYLOAD_FILE,
    PROMOTION_LOG,
    STATUS_PROMOTED,
    STATUS_REJECTED,
    STATUS_ROLLED_BACK,
    PromotionError,
    UpdatePromotion,
)

NOW = datetime(2026, 11, 18, 19, 30, 0, tzinfo=timezone.utc)


class PromotionTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.priv, self.pub = generate_signing_keypair()
        self.other_priv, self.other_pub = generate_signing_keypair()
        self.trusted = TrustedUpdateKeys({"publisher-alpha": self.pub})
        self.gate = UpdateGate(self.trusted, now=NOW)
        self.root = Path(tempfile.mkdtemp())
        self.promo = UpdatePromotion(self.root, self.gate, now=NOW)
        self.payload_a = b"release-payload-AAA"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def stage(self, release: str, payload: bytes,
              publisher: str = "publisher-alpha",
              private: bytes | None = None) -> tuple[dict, Path]:
        manifest = build_update_manifest(
            release_name=release,
            payload=payload,
            publisher_key_id=publisher,
            private_key=private if private is not None else self.priv,
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(days=30))
        staged_dir = self.root / "staging"
        staged_dir.mkdir(parents=True, exist_ok=True)
        staged = staged_dir / (release + ".staged")
        staged.write_bytes(payload)
        return manifest, staged


class PromoteTests(PromotionTestBase):
    def test_promote_verifies_and_moves(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        verdict = self.promo.promote(manifest, staged)
        self.assertEqual(verdict.status, STATUS_PROMOTED)
        self.assertEqual(self.promo.active_release(), "rel-1")
        payload_file = self.root / "versions" / "rel-1" / PAYLOAD_FILE
        self.assertTrue(payload_file.exists())
        self.assertEqual(payload_file.read_bytes(), self.payload_a)
        self.assertFalse(staged.exists(), "staged file must be gone after move")

    def test_promote_refuses_tampered_staged_payload(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        staged.write_bytes(b"tampered-bytes")
        verdict = self.promo.promote(manifest, staged)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("digest mismatch", verdict.reason)
        self.assertIsNone(self.promo.active_release())

    def test_promote_refuses_untrusted_manifest(self) -> None:
        manifest, staged = self.stage(
            "rel-1", self.payload_a,
            publisher="publisher-beta", private=self.other_priv)
        verdict = self.promo.promote(manifest, staged)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("not trusted", verdict.reason)

    def test_promote_refuses_duplicate_release(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        self.assertEqual(self.promo.promote(manifest, staged).status,
                         STATUS_PROMOTED)
        manifest2, staged2 = self.stage("rel-1", b"other-payload")
        verdict = self.promo.promote(manifest2, staged2)
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("already promoted", verdict.reason)

    def test_promote_refuses_staged_outside_root(self) -> None:
        manifest, _ = self.stage("rel-1", self.payload_a)
        outside = Path(tempfile.mkdtemp()) / "outside.staged"
        outside.write_bytes(self.payload_a)
        try:
            verdict = self.promo.promote(manifest, outside)
            self.assertEqual(verdict.status, STATUS_REJECTED)
            self.assertIn("cross-device", verdict.reason)
        finally:
            shutil.rmtree(outside.parent, ignore_errors=True)

    def test_promote_writes_pointer_and_log(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        self.promo.promote(manifest, staged)
        pointer = json.loads(
            (self.root / ACTIVE_POINTER).read_text(encoding="utf-8"))
        self.assertEqual(pointer["release_name"], "rel-1")
        self.assertEqual(pointer["action"], "promote")
        log_lines = (self.root / PROMOTION_LOG).read_text(
            encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 1)
        entry = json.loads(log_lines[0])
        self.assertEqual(entry["action"], "promote")
        self.assertEqual(entry["release_name"], "rel-1")

    def test_verify_staged_only_does_not_move(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        verdict = self.promo.verify_staged(manifest, staged)
        self.assertEqual(verdict.status, "ACCEPTED_TRUSTED")
        self.assertTrue(staged.exists())
        self.assertEqual(self.promo.list_versions(), [])


class RollbackTests(PromotionTestBase):
    def promote_two(self) -> None:
        m1, s1 = self.stage("rel-1", self.payload_a)
        self.assertEqual(self.promo.promote(m1, s1).status, STATUS_PROMOTED)
        m2, s2 = self.stage("rel-2", b"release-payload-BBB")
        self.assertEqual(self.promo.promote(m2, s2).status, STATUS_PROMOTED)

    def test_rollback_to_unique_other_version(self) -> None:
        self.promote_two()
        verdict = self.promo.rollback()
        self.assertEqual(verdict.status, STATUS_ROLLED_BACK)
        self.assertEqual(self.promo.active_release(), "rel-1")
        self.assertIn("rel-2", self.promo.list_versions(),
                      "failed version must be retained")

    def test_rollback_explicit_target(self) -> None:
        self.promote_two()
        verdict = self.promo.rollback("rel-1")
        self.assertEqual(verdict.status, STATUS_ROLLED_BACK)
        self.assertEqual(self.promo.active_release(), "rel-1")

    def test_rollback_ambiguous_requires_target(self) -> None:
        m1, s1 = self.stage("rel-1", self.payload_a)
        self.promo.promote(m1, s1)
        m2, s2 = self.stage("rel-2", b"second-payload")
        self.promo.promote(m2, s2)
        m3, s3 = self.stage("rel-3", b"third-payload")
        self.promo.promote(m3, s3)
        verdict = self.promo.rollback()
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("ambiguous", verdict.reason)

    def test_rollback_refuses_unknown_target(self) -> None:
        self.promote_two()
        verdict = self.promo.rollback("rel-ghost")
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("not retained", verdict.reason)

    def test_rollback_refuses_tampered_target_payload(self) -> None:
        self.promote_two()
        target_payload = self.root / "versions" / "rel-1" / PAYLOAD_FILE
        target_payload.write_bytes(b"corrupted-payload")
        verdict = self.promo.rollback("rel-1")
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("digest mismatch", verdict.reason)
        self.assertEqual(self.promo.active_release(), "rel-2",
                         "pointer must not change after failed rollback")

    def test_rollback_refuses_single_version(self) -> None:
        manifest, staged = self.stage("rel-1", self.payload_a)
        self.promo.promote(manifest, staged)
        verdict = self.promo.rollback()
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("no other retained version", verdict.reason)

    def test_rollback_to_active_release_refused(self) -> None:
        self.promote_two()
        verdict = self.promo.rollback("rel-2")
        self.assertEqual(verdict.status, STATUS_REJECTED)
        self.assertIn("already the active", verdict.reason)

    def test_rollback_appends_to_log(self) -> None:
        self.promote_two()
        self.promo.rollback()
        log_lines = (self.root / PROMOTION_LOG).read_text(
            encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 3)
        actions = [json.loads(l)["action"] for l in log_lines]
        self.assertEqual(actions, ["promote", "promote", "rollback"])


class ConstructorTests(PromotionTestBase):
    def test_requires_update_gate_instance(self) -> None:
        with self.assertRaises(PromotionError):
            UpdatePromotion(self.root, gate="not-a-gate")

    def test_corrupt_active_pointer_raises_on_read(self) -> None:
        (self.root / ACTIVE_POINTER).write_text("{not json", encoding="utf-8")
        with self.assertRaises(PromotionError):
            self.promo.active_release()


if __name__ == "__main__":
    unittest.main()
