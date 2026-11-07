"""V99 Quellen-Qualitaet Regressionstests (advisorisch, nur stdlib)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v99.filter.source_quality import (
    SourceTrustRegistry, VERDICT_ACCEPT, VERDICT_QUARANTINE, VERDICT_REVIEW,
)


def registry_dict():
    return {
        "sources": {
            "gute-quelle.example": {"trust": "TRUSTED"},
            "rausch-quelle.example": {"trust": "BLOCKED_LOCAL"},
        }
    }


class TestSourceTrustRegistry(unittest.TestCase):
    def test_missing_sources_fails_closed(self):
        with self.assertRaises(ValueError):
            SourceTrustRegistry({})

    def test_invalid_trust_level_rejected(self):
        with self.assertRaises(ValueError):
            SourceTrustRegistry({"sources": {"x": {"trust": "ABSOLUT_WAHR"}}})

    def test_unknown_source_is_unverified_never_trusted(self):
        reg = SourceTrustRegistry(registry_dict())
        self.assertEqual(reg.trust_of("unbekannt.example"), "UNVERIFIED")

    def test_source_lookup_case_insensitive_and_trimmed(self):
        reg = SourceTrustRegistry(registry_dict())
        self.assertEqual(reg.trust_of("  Gute-Quelle.Example  "), "TRUSTED")

    def test_blocked_source_quarantined_even_with_evidence(self):
        reg = SourceTrustRegistry(registry_dict())
        verdict = reg.classify("rausch-quelle.example", evidence=["beleg"])
        self.assertEqual(verdict.verdict, VERDICT_QUARANTINE)

    def test_trusted_without_evidence_requires_review(self):
        reg = SourceTrustRegistry(registry_dict())
        verdict = reg.classify("gute-quelle.example")
        self.assertEqual(verdict.verdict, VERDICT_REVIEW)
        self.assertIn("CLAIM != EVIDENCE", verdict.reason)

    def test_trusted_with_evidence_accepted_locally(self):
        reg = SourceTrustRegistry(registry_dict())
        verdict = reg.classify("gute-quelle.example", evidence=["quellenangabe"])
        self.assertEqual(verdict.verdict, VERDICT_ACCEPT)

    def test_unverified_source_never_accepted(self):
        reg = SourceTrustRegistry(registry_dict())
        verdict = reg.classify("unbekannt.example", evidence=["irgendwas"])
        self.assertEqual(verdict.verdict, VERDICT_REVIEW)

    def test_empty_evidence_counts_as_no_evidence(self):
        reg = SourceTrustRegistry(registry_dict())
        verdict = reg.classify("gute-quelle.example", evidence=[])
        self.assertFalse(verdict.has_evidence)
        self.assertEqual(verdict.verdict, VERDICT_REVIEW)

    def test_filter_stream_sorts_into_three_buckets(self):
        reg = SourceTrustRegistry(registry_dict())
        result = reg.filter_stream([
            {"source": "gute-quelle.example", "evidence": ["b"]},
            {"source": "rausch-quelle.example"},
            {"source": "unbekannt.example"},
        ])
        self.assertEqual(len(result["accepted_local"]), 1)
        self.assertEqual(len(result["quarantined_local"]), 1)
        self.assertEqual(len(result["review_required"]), 1)

    def test_filter_stream_malformed_item_goes_to_review(self):
        reg = SourceTrustRegistry(registry_dict())
        result = reg.filter_stream([{"kein_source": True}, "kein-dict"])
        self.assertEqual(len(result["review_required"]), 2)

    def test_no_external_side_effects(self):
        # Der Filter bewertet nur Daten, die ihm übergeben werden;
        # er hat keinerlei Methode für Netzwerk- oder Fremdzugriffe.
        methods = [m for m in dir(SourceTrustRegistry) if not m.startswith("_")]
        self.assertEqual(methods, ["classify", "filter_stream", "from_file",
                                    "note_of", "trust_of"])


if __name__ == "__main__":
    unittest.main()
