import base64
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "controller" / "trusted_peer_registry.py"
SPEC = importlib.util.spec_from_file_location("v91_trusted_peer_registry_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load V91 trusted peer registry from {MODULE_PATH}")
registry_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = registry_module
SPEC.loader.exec_module(registry_module)
resolve_trusted_ed25519_key = registry_module.resolve_trusted_ed25519_key


class TrustedPeerRegistryTests(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))
        self.registry = {
            "peers": {
                "peer-a": {
                    "keys": {
                        "key-1": {
                            "algorithm": "Ed25519",
                            "public_key_b64": base64.b64encode(self.key).decode("ascii"),
                            "status": "active",
                        }
                    }
                }
            }
        }

    def test_active_registered_key_resolves(self):
        self.assertEqual(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="key-1"),
            self.key,
        )

    def test_unknown_peer_or_key_fails_closed(self):
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="attacker", key_id="key-1")
        )
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="unknown")
        )

    def test_revoked_key_fails_closed(self):
        self.registry["peers"]["peer-a"]["keys"]["key-1"]["status"] = "revoked"
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="key-1")
        )

    def test_wrong_algorithm_or_malformed_key_fails_closed(self):
        entry = self.registry["peers"]["peer-a"]["keys"]["key-1"]
        entry["algorithm"] = "RSA"
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="key-1")
        )
        entry["algorithm"] = "Ed25519"
        entry["public_key_b64"] = "not base64!"
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="key-1")
        )

    def test_wrong_key_length_fails_closed(self):
        self.registry["peers"]["peer-a"]["keys"]["key-1"]["public_key_b64"] = base64.b64encode(b"short").decode("ascii")
        self.assertIsNone(
            resolve_trusted_ed25519_key(self.registry, peer_id="peer-a", key_id="key-1")
        )

    def test_peer_cannot_be_implicitly_trusted(self):
        self.assertIsNone(
            resolve_trusted_ed25519_key({"peers": {}}, peer_id="peer-a", key_id="key-1")
        )


if __name__ == "__main__":
    unittest.main()
