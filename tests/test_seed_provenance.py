"""Tests for documented germination provenance (seed Feinabstimmung).

Die Keimprobe macht aus einer behaupteten Rate eine gezählte Evidenz:
Rate ohne passenden Zaehlbefund wird verweigert (CLAIM != EVIDENCE).
"""
from __future__ import annotations

import unittest

from controller.seed_inventory import (
    GerminationTest,
    MIN_SAMPLE_SIZE,
    SeedInventoryError,
    evaluate_seed_batch,
)


def valid_test(sample: int = 20, germinated: int = 18) -> GerminationTest:
    return GerminationTest(
        sample_size=sample,
        germinated_count=germinated,
        tested_at="2026-11-01T09:30:00+01:00",
        conditions="20 Samen auf Filterpapier, 20 Grad C, 14 Tage",
    )


class GerminationTestValidationTests(unittest.TestCase):
    def test_valid_test_constructs(self) -> None:
        t = valid_test()
        self.assertEqual(t.computed_rate_pct(), 90.0)

    def test_sample_size_below_minimum_rejected(self) -> None:
        with self.assertRaises(SeedInventoryError):
            GerminationTest(sample_size=5, germinated_count=5, tested_at="2026-11-01T09:30:00+01:00", conditions="x")

    def test_germinated_exceeding_sample_rejected(self) -> None:
        with self.assertRaises(SeedInventoryError):
            GerminationTest(sample_size=30, germinated_count=31, tested_at="2026-11-01T09:30:00+01:00", conditions="x")

    def test_bool_counts_rejected(self) -> None:
        with self.assertRaises(SeedInventoryError):
            GerminationTest(sample_size=True, germinated_count=20, tested_at="2026-11-01T09:30:00+01:00", conditions="x")

    def test_naive_timestamp_rejected(self) -> None:
        with self.assertRaises(SeedInventoryError):
            GerminationTest(sample_size=20, germinated_count=18, tested_at="2026-11-01T09:30:00", conditions="x")

    def test_empty_conditions_rejected(self) -> None:
        with self.assertRaises(SeedInventoryError):
            GerminationTest(sample_size=20, germinated_count=18, tested_at="2026-11-01T09:30:00+01:00", conditions=" ")


class EvaluateWithProvenanceTests(unittest.TestCase):
    def test_matching_test_confirms_rate(self) -> None:
        status = evaluate_seed_batch(
            batch_id="B-2026-01", crop_name="Tomate", open_pollinated=True,
            germination_rate_pct=90.0, germination_test=valid_test(),
        )
        self.assertTrue(status.viable)
        self.assertIn("dokumentierter Keimprobe", status.status_message)

    def test_fabricated_rate_mismatch_refused(self) -> None:
        with self.assertRaises(SeedInventoryError):
            evaluate_seed_batch(
                batch_id="B-2026-02", crop_name="Kuerbis", open_pollinated=True,
                germination_rate_pct=95.0, germination_test=valid_test(),
            )

    def test_low_rate_with_matching_test_stays_warning(self) -> None:
        low = valid_test(sample=40, germinated=20)  # 50 %
        status = evaluate_seed_batch(
            batch_id="B-2026-03", crop_name="Bohne", open_pollinated=True,
            germination_rate_pct=50.0, germination_test=low,
        )
        self.assertFalse(status.viable)
        self.assertIn("WARNUNG", status.status_message)

    def test_without_test_behaviour_unchanged(self) -> None:
        status = evaluate_seed_batch(
            batch_id="B-2026-04", crop_name="Erbsen", open_pollinated=True,
            germination_rate_pct=88.0,
        )
        self.assertTrue(status.viable)
        self.assertIn("Bewertung der Angaben", status.status_message)

    def test_documented_zero_germination_is_honest(self) -> None:
        zero = valid_test(sample=25, germinated=0)
        status = evaluate_seed_batch(
            batch_id="B-2026-05", crop_name="Loewenzahn", open_pollinated=True,
            germination_rate_pct=0.0, germination_test=zero,
        )
        self.assertFalse(status.viable)


if __name__ == "__main__":
    unittest.main()
