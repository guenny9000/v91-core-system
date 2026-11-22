"""
Tests fuer den Repo-Report-Agenten (VIBE-LXXXV).

Diese Tests pruefen, dass der Agent:
- existierende Bestandsmodule (index_lint) orchestriert statt sie zu duplizieren,
- ehrliche UNKNOWN-Werte fuer nicht belegbare Sachverhalte ausstellt,
- nur Lese-Zugriff nutzt und FAIL-CLOSED reagiert.
Test-Philosophie des Repos: SCRIPTED != RUNNING, WARN != FAIL, LINT_OK != INHALT_GEPRUEFT.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller import repo_report_agent as rra  # noqa: E402


def _write_minimal_repo(root: Path, index_lines: list, extra_doc: str = None) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    for name in rra.REQUIRED_DOCS:
        if name != "V91-ARCHITEKTUR-INDEX.md":
            (root / "docs" / name).write_text("# %s\n" % name, encoding="utf-8")
    if extra_doc:
        (root / "docs" / extra_doc).write_text("# zusaetzlich\n", encoding="utf-8")


class TestRepoReportAgent(unittest.TestCase):

    def test_reports_unhappy_path_on_missing_repo_root(self):
        report, exit_code = rra.build_report("/nicht_vorhanden_ort_987654321")
        self.assertEqual(exit_code, rra.EXIT_INPUT_ERROR)
        self.assertEqual(report["violations"][0]["rule"], "REPO_ROOT_NOT_FOUND")

    def test_missing_docs_dir_is_fail_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            report, exit_code = rra.build_report(td)
            self.assertEqual(rra.EXIT_FAIL, exit_code)
            self.assertIn("MISSING_DOCS_DIR", report["violations"][0]["rule"] + report["docs_inventory"]["status"])

    def test_orchestrates_index_lint_and_reports_clean_mini_repo(self):
        import tempfile
        good_index = [
            "- 01.01.2026 #352 (VIBE-LXVII) Demo Zeile sauber. [VIBE-LXVII]",
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root, good_index, extra_doc="V91-DEMO-EXTRA.md")
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_OK, msg=str(report["violations"]))
            self.assertEqual(report["docs_inventory"]["docs_md_total"], 4)
            self.assertEqual(len(report["unknown_keys"]), 5)
            self.assertIn("unknown", str(report["unknown_value"]).lower()[:10])

    def test_detects_index_lint_error(self):
        import tempfile
        bad_index = [
            "- 01.01.2026 #352 (VIBE-LXVII) Demo Zeile defekt end-tag. [VIBE-LXVIII]",
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root, bad_index)
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_FAIL)
            self.assertEqual(report["violations"][0]["rule"], "INDEX_LINT_ERRORS")

    def test_detects_missing_required_doc(self):
        import tempfile
        good_index = ["- 01.01.2026 #352 (VIBE-LXVII) Demo. [VIBE-LXVII]"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root, good_index)
            (root / "docs" / "V91-GRUNDSATZ-KEIN-TOETEN.md").unlink()
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_FAIL)
            self.assertEqual(report["violations"][0]["rule"], "REQUIRED_DOC_MISSING")
            self.assertIn("V91-GRUNDSATZ-KEIN-TOETEN.md", report["violations"][0]["detail"])

    def test_did_not_reimplement_lint(self):
        # Der Agent orchestriert index_lint (kein Zweit-Lint): importiert statt dupliziert.
        self.assertIsNotNone(rra._lint_check_file)
        self.assertIsNotNone(rra._lint_build_report)

    def test_integration_against_real_repo(self):
        # ECHTER Repostand: Integration gegen den echten Index und echte docs/.
        report, exit_code = rra.build_report(str(REPO_ROOT))
        self.assertEqual(exit_code, rra.EXIT_OK, msg=json.dumps(report["violations"], indent=2))
        self.assertGreaterEqual(report["index_lint"]["entries"], 30)
        self.assertGreaterEqual(report["docs_inventory"]["docs_md_total"], 40)
        self.assertEqual(report["docs_inventory"]["status"], "OK")
        for key in rra.UNKNOWN_KEYS:
            self.assertTrue(any(key in u for u in [json.dumps(report)]), msg=key)


if __name__ == "__main__":
    unittest.main()
