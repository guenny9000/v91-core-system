import hashlib
import json

from v91_guideline_hash import (
    GUIDELINES_DATA,
    canonical_guideline_bytes,
    get_canonical_guideline_hash,
)


def test_guideline_hash_matches_canonical_utf8_json():
    expected_bytes = json.dumps(
        GUIDELINES_DATA,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert canonical_guideline_bytes() == expected_bytes
    assert get_canonical_guideline_hash() == hashlib.sha256(expected_bytes).hexdigest()


def test_guideline_hash_is_sha256_and_not_empty_content_hash():
    digest = get_canonical_guideline_hash()
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
    assert digest != hashlib.sha256(b"").hexdigest()


def test_guideline_hash_is_deterministic():
    assert get_canonical_guideline_hash() == get_canonical_guideline_hash()


def test_guideline_payload_has_explicit_version_and_safety_rules():
    assert GUIDELINES_DATA["version"] == "3.1"
    assert any("menschlichen Lebens" in axiom for axiom in GUIDELINES_DATA["axioms"])
    assert "irreversiblen Aktionen" in GUIDELINES_DATA["operational_rules"]
