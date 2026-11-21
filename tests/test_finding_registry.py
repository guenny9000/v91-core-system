'''Tests for controller.finding_registry (Issue #276, capability 3).

All test data remains pure ASCII (<= 0x7F) per repo convention.
'''

import unittest

from controller import finding_registry as fr


def valid_finding(fid="F-001", claim="service retries too often"):
    return {
        "finding_id": fid,
        "claim": claim,
        "raised_by": "alice@example",
        "evidence": {"source": "log sample", "checked_on": "2026-11-21"},
    }


def valid_evidence():
    return {"source": "monitoring", "checked_on": "2026-11-21"}


class TestRegistration(unittest.TestCase):
    def test_register_with_evidence_is_claimed(self):
        reg = fr.new_registry()
        self.assertEqual(fr.register_finding(reg, valid_finding()), "CLAIMED")

    def test_register_without_evidence_is_unknown(self):
        reg = fr.new_registry()
        finding = valid_finding()
        finding["evidence"] = None
        self.assertEqual(fr.register_finding(reg, finding), "UNKNOWN")

    def test_register_malformed_evidence_rejected(self):
        reg = fr.new_registry()
        finding = valid_finding()
        finding["evidence"] = {"source": "x"}
        with self.assertRaises(fr.FindingRegistryError):
            fr.register_finding(reg, finding)

    def test_register_missing_claim_rejected(self):
        reg = fr.new_registry()
        finding = valid_finding()
        finding["claim"] = " "
        with self.assertRaises(fr.FindingRegistryError):
            fr.register_finding(reg, finding)

    def test_duplicate_id_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.register_finding(reg, valid_finding())


class TestVerification(unittest.TestCase):
    def test_verification_makes_verified(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        status = fr.add_verification(
            reg,
            "F-001",
            {"verified_by": "bob@example", "method": "reproduced", "evidence": valid_evidence()},
        )
        self.assertEqual(status, "VERIFIED")

    def test_verification_same_person_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_verification(
                reg,
                "F-001",
                {"verified_by": "alice@example", "method": "x", "evidence": valid_evidence()},
            )

    def test_verification_duplicate_person_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        v = {"verified_by": "bob@example", "method": "x", "evidence": valid_evidence()}
        fr.add_verification(reg, "F-001", v)
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_verification(reg, "F-001", v)

    def test_verification_without_evidence_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_verification(
                reg, "F-001", {"verified_by": "bob@example", "method": "x", "evidence": {}}
            )

    def test_verification_blocked_while_disputed(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "sample too small"})
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_verification(
                reg, "F-001", {"verified_by": "carol@example", "method": "x", "evidence": valid_evidence()}
            )


class TestDisputes(unittest.TestCase):
    def test_dispute_marks_status(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        status = fr.raise_dispute(
            reg, "F-001", {"disputed_by": "bob@example", "reason": "sample too small"}
        )
        self.assertEqual(status, "DISPUTED")

    def test_disputed_never_verified_in_summary(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        summary = fr.summarize(reg)
        self.assertEqual(summary["verified_count"], 0)
        self.assertEqual(summary["disputes_open"], 1)

    def test_cannot_dispute_own_finding(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.raise_dispute(reg, "F-001", {"disputed_by": "alice@example", "reason": "r"})

    def test_resolution_upheld_restores_verified(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        status = fr.resolve_dispute(
            reg,
            "F-001",
            {"resolved_by": "carol@example", "resolution": "upheld", "resolved_on": "2026-11-21"},
        )
        self.assertEqual(status, "VERIFIED")

    def test_resolution_by_disputer_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        with self.assertRaises(fr.FindingRegistryError):
            fr.resolve_dispute(
                reg,
                "F-001",
                {"resolved_by": "bob@example", "resolution": "upheld", "resolved_on": "2026-11-21"},
            )

    def test_refutation_requires_evidence(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        with self.assertRaises(fr.FindingRegistryError):
            fr.resolve_dispute(
                reg,
                "F-001",
                {"resolved_by": "carol@example", "resolution": "refuted", "resolved_on": "2026-11-21"},
            )

    def test_refutation_with_evidence_sets_false_positive(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        status = fr.resolve_dispute(
            reg,
            "F-001",
            {
                "resolved_by": "carol@example",
                "resolution": "refuted",
                "resolved_on": "2026-11-21",
                "refutation_evidence": valid_evidence(),
            },
        )
        self.assertEqual(status, "FALSE_POSITIVE")
        summary = fr.summarize(reg)
        self.assertEqual(summary["by_status"]["FALSE_POSITIVE"], 1)
        self.assertEqual(summary["false_positive_rate"], 1.0)

    def test_no_open_dispute_resolution_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.resolve_dispute(
                reg,
                "F-001",
                {"resolved_by": "carol@example", "resolution": "upheld", "resolved_on": "2026-11-21"},
            )

    def test_unknown_resolution_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        with self.assertRaises(fr.FindingRegistryError):
            fr.resolve_dispute(
                reg,
                "F-001",
                {"resolved_by": "carol@example", "resolution": "ignored", "resolved_on": "2026-11-21"},
            )


class TestCorrections(unittest.TestCase):
    def test_correction_appends_keeps_original(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        status = fr.add_correction(
            reg,
            "F-001",
            {
                "corrected_by": "carol@example",
                "corrected_claim": "service retries exactly as configured",
                "evidence": valid_evidence(),
                "corrected_on": "2026-11-21",
            },
        )
        entry = reg["findings"]["F-001"]
        self.assertEqual(status, "CORRECTED")
        self.assertEqual(entry["claim"], "service retries too often")
        self.assertEqual(len(entry["corrections"]), 1)

    def test_correction_without_evidence_rejected(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_correction(
                reg,
                "F-001",
                {"corrected_by": "carol@example", "corrected_claim": "x", "evidence": None},
            )

    def test_correction_blocked_while_disputed(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding())
        fr.raise_dispute(reg, "F-001", {"disputed_by": "bob@example", "reason": "r"})
        with self.assertRaises(fr.FindingRegistryError):
            fr.add_correction(
                reg,
                "F-001",
                {
                    "corrected_by": "carol@example",
                    "corrected_claim": "x",
                    "evidence": valid_evidence(),
                },
            )


class TestSummary(unittest.TestCase):
    def test_empty_registry_rates_are_none_or_zero(self):
        summary = fr.summarize(fr.new_registry())
        self.assertEqual(summary["findings_total"], 0)
        self.assertIsNone(summary["false_positive_rate"])
        self.assertEqual(summary["verified_count"], 0)

    def test_summary_counts_statuses(self):
        reg = fr.new_registry()
        fr.register_finding(reg, valid_finding("F-001"))
        fr.register_finding(reg, valid_finding("F-002"))
        finding3 = valid_finding("F-003")
        finding3["evidence"] = None
        fr.register_finding(reg, finding3)
        summary = fr.summarize(reg)
        self.assertEqual(summary["by_status"]["CLAIMED"], 2)
        self.assertEqual(summary["by_status"]["UNKNOWN"], 1)

    def test_malformed_registry_raises(self):
        with self.assertRaises(fr.FindingRegistryError):
            fr.summarize({"nope": []})

    def test_honesty_limits_present(self):
        summary = fr.summarize(fr.new_registry())
        self.assertIn("DISPUTED != WIDERLEGT", summary["honesty_limits"])
        self.assertIn("KORREKTUR != LOESCHUNG", summary["honesty_limits"])


if __name__ == "__main__":
    unittest.main()
