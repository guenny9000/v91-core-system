import json
import sys
import tempfile
import unittest
from pathlib import Path

# The existing repository test configuration does not always add the project
# root to sys.path. Make this standalone package import deterministic.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from global_guard.feedback import append_feedback, make_feedback_record, summarize_feedback
from global_guard.scenario_runner import load_scenarios, run_scenarios, write_report


def request(**overrides):
    value = {
        "action_id": "test-learning-001",
        "action_class": "read_only",
        "purpose": "Lokaler Test",
        "expected_effect": "Prüfbericht",
        "steps": 1,
        "external_calls": 0,
        "cost_units": 1,
        "output_bytes": 100,
    }
    value.update(overrides)
    return value


class LearningAndEvaluationTests(unittest.TestCase):
    def test_scenario_runner_produces_pass_report(self):
        report = run_scenarios([
            {"name": "allow", "request": request(), "expected_allowed": True},
            {"name": "deny", "request": request(action_class="autonomous_attack"),
             "expected_allowed": False},
        ])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["passed"], 2)
        self.assertEqual(report["execution_mode"], "POLICY_EVALUATION_ONLY_NO_TOOLS_EXECUTED")

    def test_invalid_scenario_fails_report(self):
        report = run_scenarios([{"name": "broken", "request": [], "expected_allowed": True}])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["summary"]["invalid"], 1)

    def test_jsonl_load_and_report_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            output = root / "report.json"
            source.write_text(json.dumps({
                "name": "allowed",
                "request": request(),
                "expected_allowed": True,
            }) + "\n", encoding="utf-8")
            report = run_scenarios(load_scenarios(source))
            write_report(report, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "PASS")

    def test_feedback_is_reviewed_data_not_automatic_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feedback.jsonl"
            record = make_feedback_record(
                case_id="case-001", request=request(), decision_code="ALLOW_WITHIN_POLICY",
                actual_allowed=True, expected_allowed=True, label="correct_allow",
                reviewer="human-reviewer", note="Expected behavior.",
            )
            append_feedback(path, record)
            summary = summarize_feedback(path)
            self.assertEqual(summary["total_records"], 1)
            self.assertEqual(summary["training_status"], "DATASET_ONLY_NO_MODEL_TRAINED")
            self.assertFalse(summary["production_policy_changed"])

    def test_unknown_feedback_label_rejected(self):
        with self.assertRaises(ValueError):
            make_feedback_record(
                case_id="case-002", request=request(), decision_code="DENY",
                actual_allowed=False, expected_allowed=False, label="magic",
                reviewer="human-reviewer",
            )


if __name__ == "__main__":
    unittest.main()
