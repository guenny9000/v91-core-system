import pytest

from v99.filter.source_quality import (
    EVIDENCE_INDEPENDENCE_UNKNOWN,
    SourceTrustRegistry,
    _is_valid_reference,
)

CONFIG = {"sources": {
    "gut.example": {"trust": "TRUSTED"},
    "schlecht.example": {"trust": "BLOCKED_LOCAL"},
}}


@pytest.fixture
def registry():
    return SourceTrustRegistry(CONFIG)


# --- Legacy-Vertrag (validate_evidence=False) bleibt unangetastet ---

def test_legacy_trusted_with_any_evidence_still_accepts(registry):
    verdict = registry.classify("gut.example", evidence=["quellenangabe"])
    assert verdict.verdict == "ACCEPT_LOCAL"
    assert verdict.has_evidence is True


def test_legacy_trusted_without_evidence_requires_review(registry):
    assert registry.classify("gut.example").verdict == "REVIEW_REQUIRED"


def test_legacy_blocked_still_quarantines(registry):
    verdict = registry.classify(
        "schlecht.example", evidence=["https://x.example"]
    )
    assert verdict.verdict == "QUARANTINE_LOCAL"


# --- Referenzstruktur-Pruefung ---

@pytest.mark.parametrize("entry,expected", [
    ("https://example.com/beleg", True),
    ("http://example.com/x", True),
    ("doi:10.1234/beleg", True),
    ("/pfad/zur/datei.json", True),
    ("a" * 64, True),
    ("ledger::abcd-1234", True),
    ({"kind": "url", "value": "https://example.com"}, True),
    ({"kind": "sha256", "value": "b" * 64}, True),
    ("quellenangabe", False),
    ("", False),
    ("   ", False),
    ({"kind": "url", "value": ""}, False),
    ({"kind": "ungueltig", "value": "x"}, False),
    ({"value": "https://example.com"}, False),
    (None, False),
    (123, False),
])
def test_reference_structure(entry, expected):
    assert _is_valid_reference(entry) is expected


# --- Evidenz-Vertrag v2 (validate_evidence=True) ---

def test_bare_word_evidence_is_review_in_strict_mode(registry):
    verdict = registry.classify("gut.example", evidence=["quellenangabe"],
                                 validate_evidence=True)
    assert verdict.verdict == "REVIEW_REQUIRED"
    assert verdict.evidence_supplied is True
    assert verdict.evidence_reference_valid is False


def test_structured_reference_is_accepted_in_strict_mode(registry):
    verdict = registry.classify("gut.example", evidence=["https://example.com/beleg"],
                                 validate_evidence=True)
    assert verdict.verdict == "ACCEPT_LOCAL"
    assert verdict.evidence_reference_valid is True


def test_mixed_validity_evidence_is_review_in_strict_mode(registry):
    verdict = registry.classify("gut.example",
                                 evidence=["https://example.com/beleg", "quellenangabe"],
                                 validate_evidence=True)
    assert verdict.verdict == "REVIEW_REQUIRED"


def test_dict_reference_is_accepted_in_strict_mode(registry):
    verdict = registry.classify("gut.example",
                                 evidence=[{"kind": "doi", "value": "doi:10.1/x"}],
                                 validate_evidence=True)
    assert verdict.verdict == "ACCEPT_LOCAL"


def test_trusted_without_evidence_still_review_in_strict_mode(registry):
    verdict = registry.classify("gut.example", validate_evidence=True)
    assert verdict.verdict == "REVIEW_REQUIRED"
    assert verdict.evidence_supplied is False


def test_independence_is_always_unknown_and_honest():
    registry = SourceTrustRegistry(CONFIG)
    verdict = registry.classify("gut.example", evidence=["https://example.com"],
                                 validate_evidence=True)
    assert verdict.evidence_independent == EVIDENCE_INDEPENDENCE_UNKNOWN


def test_to_dict_contains_versioned_fields(registry):
    d = registry.classify("gut.example", evidence=["https://example.com"],
                           validate_evidence=True).to_dict()
    assert d["has_evidence"] is True
    assert d["evidence_supplied"] is True
    assert d["evidence_reference_valid"] is True
    assert d["evidence_independent"] == EVIDENCE_INDEPENDENCE_UNKNOWN


def test_filter_stream_strict_mode_buckets_bare_words():
    registry = SourceTrustRegistry(CONFIG)
    result = registry.filter_stream(
        [{"source": "gut.example", "evidence": "quellenangabe"},
         {"source": "gut.example", "evidence": "https://example.com"}],
        validate_evidence=True)
    assert len(result["accepted_local"]) == 1
    assert len(result["review_required"]) == 1
