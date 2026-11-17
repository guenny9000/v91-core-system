"""Tests for the fail-closed governance gate (stdlib only)."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from controller.governance_gate import (
    CHECK_KEYS,
    GOVERNANCE_KEY_ENV,
    GovernanceGateError,
    GovernanceLedger,
    evaluate_checks,
    resolve_key,
)

KEY = "k" * 32
GOOD = {k: True for k in CHECK_KEYS}


class EvaluateChecksTest(unittest.TestCase):
    def test_all_true_is_approved(self):
        self.assertEqual(evaluate_checks(GOOD)["decision"], "APPROVED")

    def test_missing_check_is_blocked_not_true(self):
        metrics = dict(GOOD)
        del metrics["rollback_possible"]
        result = evaluate_checks(metrics)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any("rollback_possible" in r for r in result["reasons"]))

    def test_false_check_is_blocked(self):
        metrics = dict(GOOD, risks_assessed=False)
        self.assertEqual(evaluate_checks(metrics)["decision"], "BLOCKED")

    def test_non_boolean_check_is_rejected(self):
        metrics = dict(GOOD, metric_defined="yes")
        result = evaluate_checks(metrics)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(any("metric_defined" in r for r in result["reasons"]))

    def test_non_dict_input_raises(self):
        with self.assertRaises(GovernanceGateError):
            evaluate_checks(["goal_defined", True])


class KeyResolutionTest(unittest.TestCase):
    def test_missing_key_fails_closed(self):
        old = os.environ.pop(GOVERNANCE_KEY_ENV, None)
        try:
            with self.assertRaises(GovernanceGateError):
                resolve_key()
        finally:
            if old is not None:
                os.environ[GOVERNANCE_KEY_ENV] = old

    def test_short_key_fails_closed(self):
        old = os.environ.get(GOVERNANCE_KEY_ENV)
        os.environ[GOVERNANCE_KEY_ENV] = "short"
        try:
            with self.assertRaises(GovernanceGateError):
                resolve_key()
        finally:
            if old is not None:
                os.environ[GOVERNANCE_KEY_ENV] = old
            else:
                os.environ.pop(GOVERNANCE_KEY_ENV, None)


class GovernanceLedgerTest(unittest.TestCase):
    def _ledger(self, tmp: Path) -> GovernanceLedger:
        return GovernanceLedger(tmp / "gov.jsonl", key=KEY.encode())

    def test_append_and_verify_chain(self):
        with TemporaryDirectory() as d:
            ledger = self._ledger(Path(d))
            record = ledger.append_decision(GOOD)
            self.assertEqual(record["seq"], 1)
            self.assertEqual(record["decision"], "APPROVED")
            ledger.append_decision(dict(GOOD, goal_defined=False))
            self.assertTrue(ledger.verify_chain())

    def test_blocked_decision_is_still_recorded(self):
        with TemporaryDirectory() as d:
            ledger = self._ledger(Path(d))
            record = ledger.append_decision({"goal_defined": True})
            self.assertEqual(record["decision"], "BLOCKED")
            self.assertTrue(ledger.verify_chain())

    def test_tampered_entry_breaks_chain(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "gov.jsonl"
            ledger = GovernanceLedger(path, key=KEY.encode())
            ledger.append_decision(GOOD)
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["decision"] = "APPROVED"
            path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
            self.assertFalse(ledger.verify_chain())
            with self.assertRaises(GovernanceGateError):
                ledger.append_decision(GOOD)

    def test_corrupt_line_fails_closed(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "gov.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            ledger = GovernanceLedger(path, key=KEY.encode())
            with self.assertRaises(GovernanceGateError):
                ledger.verify_chain()

    def test_verify_decision_detects_forgery(self):
        with TemporaryDirectory() as d:
            ledger = self._ledger(Path(d))
            record = ledger.append_decision(GOOD)
            self.assertTrue(ledger.verify_decision(record))
            forged = dict(record, decision="APPROVED_FORGED")
            self.assertFalse(ledger.verify_decision(forged))

    def test_short_constructor_key_fails_closed(self):
        with self.assertRaises(GovernanceGateError):
            GovernanceLedger(Path("x.jsonl"), key=b"short")


if __name__ == "__main__":
    unittest.main()
