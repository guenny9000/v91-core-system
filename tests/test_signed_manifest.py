import pytest

from controller.crypto_receipts import generate_signing_keypair
from controller.signed_manifest import ManifestError, sign_manifest, verify_manifest

NOW = '2026-11-07T12:00:00+00:00'


@pytest.fixture
def keypair():
    return generate_signing_keypair()


def base_manifest(**overrides):
    manifest = {
        'schema_version': 1,
        'node_id': 'node-alpha',
        'key_id': 'key-1',
        'software_version': '0.1.0',
        'issued_at': '2026-11-07T10:00:00+00:00',
        'expires_at': '2026-11-07T14:00:00+00:00',
        'resources': {
            'cpu_cores_available': 8,
            'ram_mb_available': 16000,
            'vram_mb_available': 0,
            'disk_mb_available': 500000,
        },
        'contributions': {
            'compute': True,
            'verification': True,
            'encrypted_storage': False,
            'metadata_index': False,
        },
        'policy_version': 'v1',
    }
    manifest.update(overrides)
    return manifest


def test_sign_and_verify_roundtrip(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    valid, reason = verify_manifest(signed, public_key, now=NOW)
    assert valid is True
    assert signed['signature']['algorithm'] == 'Ed25519'


def test_tampered_manifest_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    signed['resources']['cpu_cores_available'] = 999
    valid, reason = verify_manifest(signed, public_key, now=NOW)
    assert valid is False
    assert 'signature verification failed' in reason


def test_wrong_key_fails(keypair):
    private_key, _ = keypair
    _, other_public = generate_signing_keypair()
    signed = sign_manifest(base_manifest(), private_key)
    assert verify_manifest(signed, other_public, now=NOW)[0] is False


def test_expired_manifest_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    valid, reason = verify_manifest(signed, public_key, now='2026-11-08T12:00:00+00:00')
    assert valid is False
    assert 'expired' in reason


def test_not_yet_valid_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    valid, reason = verify_manifest(signed, public_key, now='2026-11-07T08:00:00+00:00')
    assert valid is False
    assert 'not yet valid' in reason


def test_revoked_node_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    valid, reason = verify_manifest(signed, public_key, now=NOW, revoked_node_ids={'node-alpha'})
    assert valid is False
    assert 'revoked' in reason


def test_revoked_key_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    valid, reason = verify_manifest(signed, public_key, now=NOW, revoked_key_ids={'key-1'})
    assert valid is False
    assert 'revoked' in reason


def test_missing_required_field_fails_to_sign(keypair):
    private_key, _ = keypair
    manifest = base_manifest()
    del manifest['policy_version']
    with pytest.raises(ManifestError, match='policy_version'):
        sign_manifest(manifest, private_key)


def test_naive_timestamps_are_rejected(keypair):
    private_key, _ = keypair
    manifest = base_manifest(issued_at='2026-11-07T10:00:00')
    with pytest.raises(ManifestError, match='timezone'):
        sign_manifest(manifest, private_key)


def test_negative_resources_are_rejected(keypair):
    private_key, _ = keypair
    manifest = base_manifest()
    manifest['resources']['ram_mb_available'] = -1
    with pytest.raises(ManifestError, match='ram_mb_available'):
        sign_manifest(manifest, private_key)


def test_resigning_a_signed_manifest_is_refused(keypair):
    private_key, _ = keypair
    signed = sign_manifest(base_manifest(), private_key)
    with pytest.raises(ManifestError, match='already'):
        sign_manifest(signed, private_key)


def test_unsupported_schema_version_is_rejected(keypair):
    private_key, _ = keypair
    with pytest.raises(ManifestError, match='schema_version'):
        sign_manifest(base_manifest(schema_version=2), private_key)


def test_unsupported_signature_algorithm_fails(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    signed['signature']['algorithm'] = 'MD5'
    valid, reason = verify_manifest(signed, public_key, now=NOW)
    assert valid is False
    assert 'algorithm' in reason


def test_verification_reason_names_the_limits(keypair):
    private_key, public_key = keypair
    signed = sign_manifest(base_manifest(), private_key)
    _, reason = verify_manifest(signed, public_key, now=NOW)
    assert 'no authorization' in reason
