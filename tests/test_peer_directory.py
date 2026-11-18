"""Tests for the durable peer directory (revocation, rotation, expiry)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.peer_directory import (  # noqa: E402
    PeerDirectory, PeerDirectoryError,
)

NOW = 1800000000
FAR_FUTURE = NOW + 31_536_000
KEY_A = "11" * 32
KEY_B = "22" * 32


def make_dir(tmp_path) -> PeerDirectory:
    return PeerDirectory(tmp_path / "peers.sqlite", now_provider=lambda: NOW)


class PeerDirectoryTest(unittest.TestCase):
    def test_add_lookup_active(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="peer-alpha", public_key_hex=KEY_A,
                       expires_at=FAR_FUTURE)
            rec = d.lookup("peer-alpha")
            self.assertIsNotNone(rec)
            self.assertTrue(rec.active)
            self.assertEqual(rec.public_key_hex, KEY_A)
            self.assertEqual(d.active_keys(), {"peer-alpha": KEY_A})

    def test_duplicate_add_refused(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            with self.assertRaises(PeerDirectoryError):
                d.add_peer(peer_id="p", public_key_hex=KEY_B, expires_at=FAR_FUTURE)

    def test_revoke_makes_inactive_and_is_logged(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            d.revoke_peer(peer_id="p", reason="key compromise suspected")
            rec = d.lookup("p")
            self.assertFalse(rec.active)
            self.assertEqual(rec.reason, "revoked")
            self.assertEqual(d.active_keys(), {})
            # Revocation is permanent and idempotent-refusing.
            with self.assertRaises(PeerDirectoryError):
                d.revoke_peer(peer_id="p", reason="again")

    def test_revoked_peer_cannot_rotate(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            d.revoke_peer(peer_id="p", reason="compromised")
            with self.assertRaises(PeerDirectoryError):
                d.rotate_key(peer_id="p", new_public_key_hex=KEY_B)

    def test_rotation_archives_old_key(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            d.rotate_key(peer_id="p", new_public_key_hex=KEY_B)
            self.assertEqual(d.rotation_count("p"), 1)
            rec = d.lookup("p")
            self.assertEqual(rec.public_key_hex, KEY_B)
            self.assertTrue(rec.active)
            with d._connect() as db:  # archive exists (ISOLATE_NOT_DESTROY)
                hist = db.execute("SELECT old_key_hex, new_key_hex FROM rotation_history").fetchall()
            self.assertEqual(hist, [(KEY_A, KEY_B)])
            with self.assertRaises(PeerDirectoryError):
                d.rotate_key(peer_id="p", new_public_key_hex=KEY_B)  # same key refused

    def test_expiry_evaluated_at_query_time(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=NOW + 100)
            self.assertTrue(d.lookup("p").active)
            expired_dir = PeerDirectory(Path(td) / "peers.sqlite",
                                       now_provider=lambda: NOW + 101)
            rec = expired_dir.lookup("p")
            self.assertFalse(rec.active)
            self.assertIn("expired", rec.reason)
            self.assertEqual(expired_dir.active_keys(), {})

    def test_restart_safety(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            d.rotate_key(peer_id="p", new_public_key_hex=KEY_B)
            reopened = PeerDirectory(Path(td) / "peers.sqlite",
                                     now_provider=lambda: NOW)
            rec = reopened.lookup("p")
            self.assertTrue(rec.active)
            self.assertEqual(rec.public_key_hex, KEY_B)
            self.assertEqual(reopened.rotation_count("p"), 1)

    def test_fail_closed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            d = make_dir(Path(td))
            for kwargs in (
                {"peer_id": "", "public_key_hex": KEY_A, "expires_at": FAR_FUTURE},
                {"peer_id": "p", "public_key_hex": "zz" * 32, "expires_at": FAR_FUTURE},
                {"peer_id": "p", "public_key_hex": "ab" * 31, "expires_at": FAR_FUTURE},
                {"peer_id": "p", "public_key_hex": KEY_A, "expires_at": -1},
                {"peer_id": "p", "public_key_hex": KEY_A, "expires_at": True},
            ):
                with self.assertRaises(PeerDirectoryError, msg=str(kwargs)):
                    d.add_peer(**kwargs)
            d.add_peer(peer_id="p", public_key_hex=KEY_A, expires_at=FAR_FUTURE)
            with self.assertRaises(PeerDirectoryError):
                d.revoke_peer(peer_id="p", reason="   ")  # blank reason refused
            with self.assertRaises(PeerDirectoryError):
                d.revoke_peer(peer_id="unknown", reason="x")
            self.assertIsNone(d.lookup("unknown"))


if __name__ == "__main__":
    unittest.main()
