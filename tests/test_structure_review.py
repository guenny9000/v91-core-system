"""
Tests fuer controller/structure_review: 7 Direktiv-Kriterien,
Evidenzpflicht, fail-closed, ehrliche NICHT_GEPRUEFT-Wege.
"""
import json
import tempfile
import unittest
from pathlib import Path

from controller.structure_review import (
    CRITERIA,
    STATUS_BELEGT,
    STATUS_PROBLEM,
    STATUS_UNGEPRUEFT,
    StructureReviewError,
    evaluate_structure,
    main as review_main,
)


def _entry(status, evidence=None, source=None, assessed_at=None):
    return {
        "status": status,
        "evidence": evidence,
        "source": source,
        "assessed_at": assessed_at,
    }


def _review(criteria):
    return {
        "structure_id": "beispiel-struktur",
        "assessor": "operator",
        "criteria": criteria,
    }


class StructureReviewTests(unittest.TestCase):

    def test_criteria_exactly_seven(self):
        self.assertEqual(7, len(CRITERIA))
        self.assertEqual(7, len(set(CRITERIA)))

    def test_all_belegt_yields_completed_verdict(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "AK-1", "Quelle A", "2026-11-19T08:00:00Z")
            for name in CRITERIA
        }
        result = evaluate_structure(_review(criteria))
        self.assertEqual("BEWERTUNG_ABGESCHLOSSEN_NACHWEISLICH", result["verdict"])
        self.assertEqual(7, result["criteria_belegt"])
        self.assertEqual(0, result["criteria_ungeprueft"])

    def test_problem_belegt_yields_negative_finding(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "AK-1", "Quelle A", "2026-11-19T08:00:00Z")
            for name in CRITERIA
        }
        criteria["transparenz"] = _entry(STATUS_PROBLEM, "AK-2", "Rechnungshof", "2026-11-19T09:00:00Z")
        criteria["missbrauchsrisiken"] = _entry(STATUS_PROBLEM, "AK-3", "Rechnungshof", "2026-11-19T09:00:00Z")
        result = evaluate_structure(_review(criteria))
        self.assertEqual("NEGATIVE_FINDING_PROBLEMS_BELEGT", result["verdict"])
        self.assertEqual(["missbrauchsrisiken", "transparenz"], result["problems"])

    def test_ungeprueft_yields_review_required(self):
        criteria = {
            name: _entry(STATUS_UNGEPRUEFT)
            for name in CRITERIA
        }
        result = evaluate_structure(_review(criteria))
        self.assertEqual("REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN", result["verdict"])
        self.assertEqual(7, result["criteria_ungeprueft"])
        self.assertEqual([], result["problems"])

    def test_mixed_counts_add_up(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "AK-1", "Quelle A", "2026-11-19T08:00:00Z")
            for name in CRITERIA
        }
        criteria["nachhaltigkeit"] = _entry(STATUS_UNGEPRUEFT)
        criteria["transparenz"] = _entry(STATUS_PROBLEM, "AK-2", "Quelle B", "2026-11-19T09:00:00Z")
        result = evaluate_structure(_review(criteria))
        self.assertEqual(5, result["criteria_belegt"])
        self.assertEqual(1, result["criteria_problem_belegt"])
        self.assertEqual(1, result["criteria_ungeprueft"])
        self.assertEqual(7, result["criteria_total"])

    def test_belegt_without_evidence_fails_closed(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "", "Quelle A", "2026-11-19T08:00:00Z")
            for name in CRITERIA
        }
        with self.assertRaises(StructureReviewError):
            evaluate_structure(_review(criteria))

    def test_belegt_without_source_fails_closed(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "AK-1", None, "2026-11-19T08:00:00Z")
            for name in CRITERIA
        }
        with self.assertRaises(StructureReviewError):
            evaluate_structure(_review(criteria))

    def test_belegt_without_timestamp_fails_closed(self):
        criteria = {
            name: _entry(STATUS_BELEGT, "AK-1", "Quelle A", " ")
            for name in CRITERIA
        }
        with self.assertRaises(StructureReviewError):
            evaluate_structure(_review(criteria))

    def test_unknown_criterion_fails_closed(self):
        criteria = {
            name: _entry(STATUS_UNGEPRUEFT)
            for name in CRITERIA
        }
        criteria["machtposition"] = _entry(STATUS_UNGEPRUEFT)
        with self.assertRaisesRegex(StructureReviewError, "unknown criteria"):
            evaluate_structure(_review(criteria))

    def test_invalid_status_fails_closed(self):
        criteria = {CRITERIA[0]: _entry("GUT")}
        with self.assertRaises(StructureReviewError):
            evaluate_structure(_review(criteria))

    def test_missing_metadata_fails_closed(self):
        with self.assertRaises(StructureReviewError):
            evaluate_structure({"criteria": {}})
        with self.assertRaises(StructureReviewError):
            evaluate_structure({"structure_id": " ", "assessor": "op", "criteria": {}})
        with self.assertRaises(StructureReviewError):
            evaluate_structure({"structure_id": "x", "assessor": "", "criteria": {}})
        with self.assertRaises(StructureReviewError):
            evaluate_structure("kein-dict")

    def test_cli_completed_exits_zero(self):
        review = _review({
            name: _entry(STATUS_BELEGT, "AK-1", "Quelle A", "2026-11-19T08:00:00Z")
            for name in CRITERIA
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(0, review_main(["--report-json", str(path)]))

    def test_cli_review_required_exits_one(self):
        review = _review({name: _entry(STATUS_UNGEPRUEFT) for name in CRITERIA})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(1, review_main(["--report-json", str(path)]))

    def test_cli_invalid_input_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            path.write_text("{kein json", encoding="utf-8")
            self.assertEqual(2, review_main(["--report-json", str(path)]))
            missing = Path(tmp) / "fehlt.json"
            self.assertEqual(2, review_main(["--report-json", str(missing)]))


if __name__ == "__main__":
    unittest.main()
