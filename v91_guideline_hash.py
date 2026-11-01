"""Deterministic SHA-256 for the canonical V91 guideline payload.

This hashes the versioned guideline data defined below. It is not a digital
signature, an external timestamp, WORM storage, or proof that a runtime uses
these guidelines. Update the version and payload deliberately when guidelines
change.
"""
from __future__ import annotations

import hashlib
import json

GUIDELINES_DATA = {
    "version": "3.1",
    "axioms": [
        "Schutz menschlichen Lebens und friedliche Zusammenarbeit haben Vorrang.",
        "Dankbarkeit gegenüber Natur und Schöpfung ist ein dokumentierter Leitwert.",
        "Ökologische Entscheidungen benötigen vergleichbare Messwerte.",
        "CLAIM != EVIDENCE; REQUEST != AUTHORIZATION; DETECTION != AUTHORIZATION.",
    ],
    "operational_rules": (
        "Keine unaufgeforderte Änderung an externen Systemen, "
        "keine automatischen irreversiblen Aktionen."
    ),
}


def canonical_guideline_bytes() -> bytes:
    """Return the UTF-8 canonical JSON bytes for the declared guideline payload."""
    canonical_string = json.dumps(
        GUIDELINES_DATA,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return canonical_string.encode("utf-8")


def get_canonical_guideline_hash() -> str:
    """Return the SHA-256 hex digest of the canonical guideline payload."""
    return hashlib.sha256(canonical_guideline_bytes()).hexdigest()


if __name__ == "__main__":
    print(f"[V91-HASH] Canonical guideline SHA-256: {get_canonical_guideline_hash()}")
