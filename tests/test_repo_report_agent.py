"""
Tests fuer den Repo-Report-Agenten (VIBE-LXXXV, CLAIM 7084922874).

Der Agent:
- orchestriert index_lint (kein Zweit-Lint, NO_DUPLICATE_SYSTEMS),
- stellt ehrliche UNKNOWN fuer nicht belegbare Sachverhalte aus,
- ist read-only und FAIL-CLOSED.
Limits: SCRIPTED != RUNNING, WARN != FAIL, LINT_OK != INHALT_GEPRUEFT.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from controller import repo_report_agent as rra  # noqa: E402


def _write_minimal_repo(root):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    for name in rra.REQUIRED_DOCS:
        (root / "docs" / name).write_text("# %s\n" % name, encoding="utf-8")


class TestRepoReportAgent(unittest.TestCase):

    def test_reports_input_error_on_missing_repo_root(self):
        report, exit_code = rra.build_report("/nicht_vorhanden_ort_987654321")
        self.assertEqual(exit_code, rra.EXIT_INPUT_ERROR)
        self.assertEqual(report["violations"][0]["rule"], "REPO_ROOT_NOT_FOUND")

    def test_missing_docs_dir_is_fail_closed(self):
        # Ohne lesbaren Index ist der Report Input-Fehler (3), nie OK: FAIL-CLOSED.
        with tempfile.TemporaryDirectory() as td:
            report, exit_code = rra.build_report(td)
            self.assertIn(exit_code, (rra.EXIT_FAIL, rra.EXIT_INPUT_ERROR))
            self.assertNotEqual(exit_code, rra.EXIT_OK)
            self.assertIn(report["violations"][0]["rule"], ("REQUIRED_DOC_MISSING", "INDEX_NOT_READABLE"))

    def test_ok_on_clean_mini_repo_and_counts_docs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root)
            (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").write_text(
                "- 01.01.2026 #352 (VIBE-LXVII) Demo Zeile sauber. [VIBE-LXVII]\n",
                encoding="utf-8",
            )
            (root / "docs" / "V91-DEMO-EXTRA.md").write_text("# extra\n", encoding="utf-8")
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_OK, msg=str(report["violations"]))
            self.assertEqual(report["docs_inventory"]["docs_md_total"], 5)
            self.assertEqual(len(report["unknown_keys"]), 5)
            self.assertEqual(report["index_lint"]["entries"], 1)

    def test_detects_index_lint_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root)
            (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").write_text(
                "- 01.01.2026 #352 (VIBE-LXVII) Demo defekt. [VIBE-LXVIII]\n",
                encoding="utf-8",
            )
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_FAIL)
            self.assertEqual(report["violations"][0]["rule"], "INDEX_LINT_ERRORS")

    def test_detects_duplicate_primary_pr_via_orchestrated_lint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root)
            (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").write_text(
                "- 01.01.2026 #352 (VIBE-LXVII) Erste. [VIBE-LXVII]\n"
                "- 02.01.2026 #352 (VIBE-LXVIII) Duplikat. [VIBE-LXVIII]\n",
                encoding="utf-8",
            )
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_FAIL)

    def test_detects_missing_required_doc(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root)
            (root / "docs" / "V91-GRUNDSATZ-KEIN-TOETEN.md").unlink()
            (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").write_text(
                "- 01.01.2026 #352 (VIBE-LXVII) Demo. [VIBE-LXVII]\n", encoding="utf-8"
            )
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_FAIL)
            self.assertEqual(report["violations"][0]["rule"], "REQUIRED_DOC_MISSING")
            self.assertIn("V91-GRUNDSATZ-KEIN-TOETEN.md", report["violations"][0]["detail"])

    def test_orchestrates_lint_instead_of_reimplementing(self):
        self.assertIsNotNone(rra._lint_check_file)
        self.assertIsNotNone(rra._lint_build_report)

    def test_unreadable_index_is_input_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_minimal_repo(root)
            (root / "docs" / "V91-ARCHITEKTUR-INDEX.md").unlink()
            report, exit_code = rra.build_report(str(root))
            self.assertEqual(exit_code, rra.EXIT_INPUT_ERROR)
            self.assertEqual(report["violations"][0]["rule"], "INDEX_NOT_READABLE")

    def test_integration_against_real_repo(self):
        # ECHTER Repostand: gegen den echten Index und echte docs/ im Checkout.
        report, exit_code = rra.build_report(str(REPO_ROOT))
        self.assertEqual(exit_code, rra.EXIT_OK, msg=json.dumps(report.get("violations"), indent=2))
        # #532: Session-Historie verlustfrei ins Archiv ausgelagert.
        # Der schlanke Index darf 0 Session-Eintraege haben; der
        # Bestandsschutz wandert zum Archiv (AENDERUNGSLOG), das hier
        # fuer den ECHTEN Repostand mitgeprueft wird (SKIP != PASS).
        self.assertEqual(report["index_lint"]["errors"], 0)
        archive = REPO_ROOT / "docs" / "archive" / "V91-ARCHITEKTUR-AENDERUNGSLOG.md"
        self.assertTrue(archive.is_file(), "Archiv fehlt: " + str(archive))
        from controller.index_lint import build_report as lint_build_report
        from controller.index_lint import check_file as lint_check_file
        arch_result, arch_code = lint_check_file(str(archive))
        self.assertNotEqual(arch_code, 3, "Archiv nicht lesbar")
        arch_report = lint_build_report(arch_result, str(archive))
        self.assertEqual(arch_report["errors"], 0)
        self.assertGreaterEqual(arch_report["entries"], 100)
        self.assertGreaterEqual(report["docs_inventory"]["docs_md_total"], 40)
        self.assertEqual(report["docs_inventory"]["status"], "OK")
        dump = json.dumps(report)
        for key in rra.UNKNOWN_KEYS:
            self.assertIn(key, dump)


if __name__ == "__main__":
    unittest.main()
