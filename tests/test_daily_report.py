"""Tests for controller/daily_report.py (Tagesbericht-Standard #130).

The assembler fails closed: Teil A/B entries without claim, source and
date are rejected and collected; Teil C only shows supplied checks with
their own head SHAs (STALE_HEAD on mismatch); CI is GREEN only when
every check succeeds against the current head; no checks means CI stays
UNKNOWN, never GREEN or RED. The report labels itself as a script, not as
an operating system's output.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.daily_report import (
    DailyReportError,
    assemble_daily_report,
)


def valid_data() -> dict:
    return {
        "report_id": "TB-2026-11-21",
        "date": "2026-11-21",
        "repo_head_sha": "9c3cc4fa7ca99bf5f3164e0afceabc382da005d8",
        "global_entries": [
            {
                "claim": "no new WHO mpox report with data after 14.11.",
                "source": "WHO situation reports, checked 21.11.2026",
                "date": "2026-11-21",
            }
        ],
        "local_entries": [
            {
                "claim": "0 VB-Identifikations-Messpunkte ohne Ticket",
                "source": "runtime/metrics-Identifikation.json, leer 21.11.2026",
                "date": "2026-11-21",
            }
        ],
        "local_next_step": "Issue #101 Alsfeld Messpfad",
        "checks": [
            {
                "name": "audit-checks",
                "head_sha": "9c3cc4fa7ca99bf5f3164e0afceabc382da005d8",
                "conclusion": "success",
            },
            {
                "name": "disarmament-tests",
                "head_sha": "9c3cc4fa7ca99bf5f3164e0afceabc382da005d8",
                "conclusion": "success",
            },
        ],
    }


class DailyReportTest(unittest.TestCase):
    def test_valid_report_passes(self):
        out = assemble_daily_report(valid_data())
        self.assertEqual(out["violations"], [])
        self.assertEqual(out["teil_c_technical"]["ci_status"], "GREEN")
        self.assertEqual(out["report_id"], "TB-2026-11-21")

    def test_non_dict_fails_closed(self):
        with self.assertRaises(DailyReportError):
            assemble_daily_report(None)

    def test_missing_report_id_violation(self):
        data = valid_data()
        del data["report_id"]
        out = assemble_daily_report(data)
        self.assertIn("report:report_id_missing", out["violations"])

    def test_teil_a_entry_without_source_rejected(self):
        data = valid_data()
        data["global_entries"][0]["source"] = ""
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_a_global"], [])
        self.assertTrue(
            any(v.startswith("teil_a:entry_rejected") for v in out["violations"])
        )

    def test_teil_b_entry_without_date_rejected(self):
        data = valid_data()
        del data["local_entries"][0]["date"]
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_b_local"]["entries"], [])
        self.assertTrue(
            any(v.startswith("teil_b:entry_rejected") for v in out["violations"])
        )

    def test_empty_teil_a_and_b_are_honest_valid(self):
        data = valid_data()
        data["global_entries"] = []
        data["local_entries"] = []
        out = assemble_daily_report(data)
        self.assertEqual(out["violations"], [])
        self.assertEqual(out["teil_a_global"], [])

    def test_no_checks_means_ci_unknown(self):
        data = valid_data()
        data["checks"] = []
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_c_technical"]["ci_status"], "UNKNOWN")
        self.assertEqual(out["violations"], [])

    def test_failed_check_means_ci_red(self):
        data = valid_data()
        data["checks"][1]["conclusion"] = "failure"
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_c_technical"]["ci_status"], "RED")

    def test_stale_head_check_marked_and_red(self):
        data = valid_data()
        data["checks"][1]["head_sha"] = "olddifferenthead"
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_c_technical"]["ci_status"], "RED")
        stale = out["teil_c_technical"]["checks"][1]
        self.assertTrue(stale["stale_head"])
        self.assertFalse(stale["head_match"])

    def test_skipped_check_means_red(self):
        data = valid_data()
        data["checks"][0]["conclusion"] = "skipped"
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_c_technical"]["ci_status"], "RED")

    def test_malformed_check_rejected_with_violation(self):
        data = valid_data()
        data["checks"][0]["name"] = ""
        out = assemble_daily_report(data)
        self.assertTrue(
            any(v.startswith("teil_c:malformed_check") for v in out["violations"])
        )
        self.assertEqual(len(out["teil_c_technical"]["checks"]), 1)

    def test_unknown_conclusion_rejected(self):
        data = valid_data()
        data["checks"][0]["conclusion"] = "basically_fine"
        out = assemble_daily_report(data)
        self.assertTrue(
            any(v.startswith("teil_c:malformed_check") for v in out["violations"])
        )

    def test_empty_next_step_flagged(self):
        data = valid_data()
        data["local_next_step"] = "  "
        out = assemble_daily_report(data)
        self.assertIn("teil_b:empty_next_step_supplied", out["violations"])

    def test_self_label_no_operating_claim(self):
        out = assemble_daily_report(valid_data())
        self.assertIn("SKRIPT != BETRIEB", out["generated_by"])
        self.assertIn("SCRIPTED != INSTALLED", out["generated_by"])

    def test_claims_trimmed_in_output(self):
        data = valid_data()
        data["global_entries"][0]["claim"] = "  trimmed claim  "
        out = assemble_daily_report(data)
        self.assertEqual(out["teil_a_global"][0]["claim"], "trimmed claim")


if __name__ == "__main__":
    unittest.main()
