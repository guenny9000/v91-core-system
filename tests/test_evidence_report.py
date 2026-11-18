"""Tests for the Stage B evidence exchange format (controller/evidence_report.py).

Checks checksum integrity, fail-closed rules, the version chain and the
file roundtrip. A verified report is a well-formed report, never a
proven truth (VALIDATED != INDEPENDENT).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from controller.evidence_report import (
    EvidenceReportError,
    build_report,
    load_report,
    save_report,
    verify_report,
)


def sample_items() -> list:
    return [
        {
            "claim": "Notaus-Runtime-Verkabelung ist auf main gemergt",
            "status": "BELEGT",
            "evidence": "https://github.com/guenny9000/v91-core-system/pull/132",
        },
        {
            "claim": "Alsfeld-Node laeuft",
            "status": "UNKNOWN",
        },
    ]


class BuildAndVerifyTests(unittest.TestCase):
    def test_roundtrip_verifies(self) -> None:
        report = build_report(producer="modell-drill", subject="V91-Kern", items=sample_items())
        ok, reason = verify_report(report)
        self.assertTrue(ok, reason)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(len(report["checksum"]), 64)
        self.assertEqual(len(report["report_id"]), 16)

    def test_checksum_detects_tampering(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        report["items"][0]["claim"] = "Notaus wurde NICHT gemergt (manipuliert)"
        ok, reason = verify_report(report)
        self.assertFalse(ok)
        self.assertIn("Pruefsumme", reason)

    def test_status_change_without_checksum_update_detected(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        report["items"][1]["status"] = "BELEGT"
        ok, _ = verify_report(report)
        self.assertFalse(ok)

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer="m", subject="s", items=[{"claim": "x", "status": "FEHLERFREI"}])

    def test_belegt_without_evidence_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer="m", subject="s", items=[{"claim": "x", "status": "BELEGT"}])

    def test_belegt_with_invalid_reference_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(
                producer="m",
                subject="s",
                items=[{"claim": "x", "status": "BELEGT", "evidence": "nackter Text ist kein Beleg"}],
            )

    def test_unknown_claim_without_evidence_is_valid(self) -> None:
        report = build_report(producer="m", subject="s", items=[{"claim": "Zustand Alsfeld", "status": "UNKNOWN"}])
        self.assertTrue(verify_report(report)[0])

    def test_naive_timestamp_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer="m", subject="s", items=sample_items(), created_at="2026-11-19T10:00:00")

    def test_empty_producer_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer=" ", subject="s", items=sample_items())

    def test_extra_top_level_key_rejected_by_verify(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        report["global_sync"] = True
        ok, _ = verify_report(report)
        self.assertFalse(ok)

    def test_unknown_item_field_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer="m", subject="s", items=[{"claim": "x", "status": "UNKNOWN", "selbstheilung": True}])

    def test_version_chain_links_reports(self) -> None:
        first = build_report(producer="m", subject="s", items=sample_items())
        second = build_report(producer="m", subject="s", items=sample_items(), previous_checksum=first["checksum"])
        self.assertEqual(second["previous_checksum"], first["checksum"])
        self.assertTrue(verify_report(second)[0])

    def test_invalid_previous_checksum_rejected(self) -> None:
        with self.assertRaises(EvidenceReportError):
            build_report(producer="m", subject="s", items=sample_items(), previous_checksum="kurz")

    def test_save_and_load_file_roundtrip(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            save_report(report, path)
            loaded = load_report(path)
            ok, reason = verify_report(loaded)
            self.assertTrue(ok, reason)
            self.assertEqual(loaded, report)

    def test_save_refuses_tampered_report(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        report["items"][1]["status"] = "VORSCHLAG"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EvidenceReportError):
                save_report(report, Path(tmp) / "report.json")

    def test_json_stable_across_serialization(self) -> None:
        report = build_report(producer="m", subject="s", items=sample_items())
        restored = json.loads(json.dumps(report, sort_keys=True, ensure_ascii=False))
        self.assertTrue(verify_report(restored)[0])


if __name__ == "__main__":
    unittest.main()
