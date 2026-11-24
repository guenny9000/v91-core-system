"""Tests fuer controller.capability_intake (Issue #47, Receiver-Verkabelung).

Verbindet controller.signed_manifest (Stage 1) mit
controller.peer_directory (Trust-Registry) und erzwingt die
node_id/key-Bindung. STRICT-Modus schliesst die key_id-Luecke ueber
controller.trusted_peer_registry (REUSE). Ehrliche Grenzen:
ADVERTISEMENT != AUTORISIERUNG, VERIFIZIERT != VERFUEGBAR.
"""
import base64
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from controller.capability_intake import (
    ACCEPTED_ADVERTISEMENT,
    HONESTY_NOTE,
    HONESTY_NOTE_KEY_BOUND,
    REJECTED,
    admit_capability_manifest,
    main as cli_main,
)
from controller.crypto_receipts import generate_signing_keypair
from controller.peer_directory import PeerDirectory
from controller.signed_manifest import sign_manifest

NOW_ISO = "2026-11-24T12:00:00+00:00"
NOW_EPOCH = int(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).timestamp())
PEER = "node-alpha"


def base_manifest(**overrides):
    manifest = {
        "schema_version": 1,
        "node_id": PEER,
        "key_id": "key-1",
        "software_version": "0.1.0",
        "issued_at": "2026-11-24T10:00:00+00:00",
        "expires_at": "2026-11-24T18:00:00+00:00",
        "resources": {
            "cpu_cores_available": 8,
            "ram_mb_available": 16000,
            "vram_mb_available": 0,
            "disk_mb_available": 500000,
        },
        "contributions": {
            "compute": True,
            "verification": False,
            "encrypted_storage": False,
            "metadata_index": True,
        },
        "policy_version": "v1",
    }
    manifest.update(overrides)
    return manifest


@pytest.fixture
def keypair():
    return generate_signing_keypair()


@pytest.fixture
def directory(tmp_path):
    path = tmp_path / "peers.sqlite"
    return PeerDirectory(path, now_provider=lambda: NOW_EPOCH)


def _register(directory, keypair_or_hex, peer_id=PEER):
    pub_hex = (keypair_or_hex[1].hex()
               if isinstance(keypair_or_hex, tuple) else keypair_or_hex)
    directory.add_peer(peer_id=peer_id, public_key_hex=pub_hex,
                       expires_at=NOW_EPOCH + 3600)
    return pub_hex


# ---------- Happy Path ----------

def test_roundtrip_accept(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == ACCEPTED_ADVERTISEMENT
    assert verdict.node_id == PEER
    assert verdict.key_id == "key-1"
    assert verdict.contributions == {
        "compute": True, "verification": False,
        "encrypted_storage": False, "metadata_index": True}
    assert HONESTY_NOTE in verdict.reason
    assert "no authorization" in verdict.reason


# ---------- Trust-Registry-Zustaende (fail-closed) ----------

def test_unknown_peer_rejected(keypair):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        directory = PeerDirectory(str(Path(td) / "p.sqlite"),
                                   now_provider=lambda: NOW_EPOCH)
        signed = sign_manifest(base_manifest(), keypair[0])
        verdict = admit_capability_manifest(
            signed, peer_id=PEER, directory=directory, now=NOW_ISO)
        assert verdict.state == REJECTED
        assert "unknown peer" in verdict.reason
        assert "UNKNOWN != PASS" in verdict.reason


def test_revoked_peer_rejected(keypair, directory):
    _register(directory, keypair)
    directory.revoke_peer(peer_id=PEER, reason="test revocation")
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "not active" in verdict.reason
    assert "revoked" in verdict.reason


def test_expired_peer_rejected(keypair, directory):
    pub_hex = keypair[1].hex()
    directory.add_peer(peer_id=PEER, public_key_hex=pub_hex,
                       expires_at=NOW_EPOCH - 1)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "not active" in verdict.reason
    assert "expired" in verdict.reason


# ---------- KEY-BINDING (Kernregel dieses Moduls) ----------

def test_foreign_node_id_rejected(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(node_id="node-someone-else"),
                           keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "binding violation" in verdict.reason
    assert verdict.node_id == "node-someone-else"


def test_rotation_invalidates_old_key(keypair, directory):
    old_private, old_public = keypair
    _register(directory, (old_private, old_public))
    signed_old = sign_manifest(base_manifest(), old_private)
    new_private, new_public = generate_signing_keypair()
    directory.rotate_key(peer_id=PEER, new_public_key_hex=new_public.hex())
    verdict_old = admit_capability_manifest(
        signed_old, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict_old.state == REJECTED
    assert "signature verification failed" in verdict_old.reason
    signed_new = sign_manifest(base_manifest(), new_private)
    verdict_new = admit_capability_manifest(
        signed_new, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict_new.state == ACCEPTED_ADVERTISEMENT


def test_wrong_key_rejected(keypair, directory):
    _register(directory, keypair)
    other_private, _ = generate_signing_keypair()
    forged = sign_manifest(base_manifest(key_id="key-forged"), other_private)
    verdict = admit_capability_manifest(
        forged, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED


def test_tampered_payload_rejected(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    tampered = dict(signed)
    tampered["resources"] = dict(signed["resources"])
    tampered["resources"]["cpu_cores_available"] = 999
    verdict = admit_capability_manifest(
        tampered, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED


# ---------- Manifest-Fenster / Struktur ----------

def test_manifest_window_expired_rejected(keypair, directory):
    _register(directory, keypair)
    expired = base_manifest(issued_at="2026-11-24T08:00:00+00:00",
                            expires_at="2026-11-24T09:00:00+00:00")
    signed = sign_manifest(expired, keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "expired" in verdict.reason


def test_unsigned_manifest_rejected(keypair, directory):
    _register(directory, keypair)
    verdict = admit_capability_manifest(
        base_manifest(), peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "no signature" in verdict.reason


def test_non_dict_rejected(keypair, directory):
    _register(directory, keypair)
    verdict = admit_capability_manifest(
        ["kein", "dict"], peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "must be a dict" in verdict.reason


def test_naive_now_rejected_by_manifest_parse(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory,
        now="2026-11-24T12:00:00")  # naiv, ohne Zeitzone
    assert verdict.state == REJECTED


def test_empty_peer_id_rejected(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id="  ", directory=directory, now=NOW_ISO)
    assert verdict.state == REJECTED
    assert "peer_id" in verdict.reason


def test_accept_then_revoke_changes_verdict(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    first = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert first.state == ACCEPTED_ADVERTISEMENT
    directory.revoke_peer(peer_id=PEER, reason="sperrung")
    second = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert second.state == REJECTED


def test_verdict_to_dict_roundtrip(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    as_dict = verdict.to_dict()
    assert as_dict["state"] == ACCEPTED_ADVERTISEMENT
    assert as_dict["peer_id"] == PEER
    assert as_dict["contributions"]["compute"] is True
    json.dumps(as_dict)  # serialisierbar (Berichtspflicht)


# ---------- STRICT-Modus: key_id-Registry-Bindung (luecken-schliessend) ----------


def _registry_for(keypair, key_id="key-1", status="active", peer=PEER):
    return {
        "peers": {
            peer: {
                "keys": {
                    key_id: {
                        "algorithm": "Ed25519",
                        "public_key_b64": base64.b64encode(keypair[1]).decode("ascii"),
                        "status": status,
                    }
                }
            }
        }
    }


def test_strict_registry_accept(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=_registry_for(keypair))
    assert verdict.state == ACCEPTED_ADVERTISEMENT
    assert HONESTY_NOTE_KEY_BOUND in verdict.reason
    assert HONESTY_NOTE not in verdict.reason


def test_strict_unknown_key_id_rejected(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(key_id="key-other"), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=_registry_for(keypair))
    assert verdict.state == REJECTED
    assert "not registry-bound" in verdict.reason


def test_strict_revoked_registry_key_rejected(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=_registry_for(keypair, status="revoked"))
    assert verdict.state == REJECTED
    assert "not registry-bound" in verdict.reason


def test_strict_registry_directory_mismatch_rejected(keypair, directory):
    _register(directory, keypair)  # Trust-Eintrag: Key von keypair
    other = generate_signing_keypair()
    signed = sign_manifest(base_manifest(), keypair[0])
    # Registry nennt einen ANDEREN Key fuer (PEER, key-1)
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=_registry_for(other))
    assert verdict.state == REJECTED
    assert "differs from the peer_directory trust entry" in verdict.reason


def test_strict_key_bound_to_other_peer_rejected(keypair, directory):
    _register(directory, keypair, peer_id=PEER)
    signed = sign_manifest(base_manifest(), keypair[0])
    registry = _registry_for(keypair, peer="node-beta")
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=registry)
    assert verdict.state == REJECTED
    assert "not registry-bound" in verdict.reason


def test_strict_wrong_key_id_in_manifest_rejected(keypair, directory):
    _register(directory, keypair)
    # manifest behauptet key-9, registry kennt nur key-1
    signed = sign_manifest(base_manifest(key_id="key-9"), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO,
        key_registry=_registry_for(keypair))
    assert verdict.state == REJECTED
    assert "not registry-bound" in verdict.reason


def test_non_strict_path_unchanged(keypair, directory):
    _register(directory, keypair)
    signed = sign_manifest(base_manifest(key_id="key-behauptet"), keypair[0])
    verdict = admit_capability_manifest(
        signed, peer_id=PEER, directory=directory, now=NOW_ISO)
    assert verdict.state == ACCEPTED_ADVERTISEMENT
    assert HONESTY_NOTE in verdict.reason  # Luecke bleibt ehrlich benannt


def test_cli_strict_registry(tmp_path, keypair):
    real_now = int(datetime.now(tz=timezone.utc).timestamp())
    directory = PeerDirectory(tmp_path / "peers.sqlite")
    directory.add_peer(peer_id=PEER, public_key_hex=keypair[1].hex(),
                       expires_at=real_now + 3600)
    signed = sign_manifest(base_manifest(
        issued_at="2020-01-01T00:00:00+00:00",
        expires_at="2030-01-01T00:00:00+00:00"), keypair[0])
    directory_path = tmp_path / "peers.sqlite"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(signed), encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(_registry_for(keypair)),
                             encoding="utf-8")
    rc = cli_main([
        "--manifest", str(manifest_path),
        "--peer-id", PEER,
        "--directory", str(directory_path),
        "--now", "2026-11-24T12:00:00+00:00",
        "--key-registry", str(registry_path),
    ])
    assert rc == 0


def test_cli_strict_missing_registry_file_exit_two(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    rc = cli_main([
        "--manifest", str(manifest_path),
        "--peer-id", PEER,
        "--directory", str(tmp_path / "peers.sqlite"),
        "--now", NOW_ISO,
        "--key-registry", str(tmp_path / "does-not-exist.json"),
    ])
    assert rc == 2  # unverarbeitbare Registry ist kein PASS (fail-closed)


# ---------- CLI (E2E, echte Registry-Datei) ----------


def _cli(tmp_path, manifest_obj, peer_id=PEER, now=NOW_ISO):
    directory_path = tmp_path / "peers.sqlite"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_obj), encoding="utf-8")
    return cli_main([
        "--manifest", str(manifest_path),
        "--peer-id", peer_id,
        "--directory", str(directory_path),
        "--now", now,
    ])


def test_cli_accept_exit_zero(keypair, tmp_path):
    real_now = int(datetime.now(tz=timezone.utc).timestamp())
    directory = PeerDirectory(tmp_path / "peers.sqlite")  # echte Uhr
    directory.add_peer(peer_id=PEER, public_key_hex=keypair[1].hex(),
                       expires_at=real_now + 3600)
    signed = sign_manifest(base_manifest(
        issued_at="2020-01-01T00:00:00+00:00",
        expires_at="2030-01-01T00:00:00+00:00"), keypair[0])
    rc = _cli(tmp_path, signed, now=datetime.now(tz=timezone.utc).isoformat())
    assert rc == 0


def test_cli_rejected_exit_one(keypair, tmp_path):
    real_now = int(datetime.now(tz=timezone.utc).timestamp())
    directory = PeerDirectory(tmp_path / "peers.sqlite")
    directory.add_peer(peer_id=PEER, public_key_hex=keypair[1].hex(),
                       expires_at=real_now + 3600)
    signed = sign_manifest(base_manifest(node_id="node-elsewhere"),
                           keypair[0])
    rc = _cli(tmp_path, signed)
    assert rc == 1


def test_cli_missing_file_exit_two(tmp_path):
    rc = cli_main([
        "--manifest", str(tmp_path / "does-not-exist.json"),
        "--peer-id", PEER,
        "--directory", str(tmp_path / "peers.sqlite"),
        "--now", NOW_ISO,
    ])
    assert rc == 2


def test_cli_registry_without_entry_exit_one(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    rc = cli_main([
        "--manifest", str(manifest_path),
        "--peer-id", "nobody",
        "--directory", str(tmp_path / "peers.sqlite"),
        "--now", NOW_ISO,
    ])
    assert rc == 1
