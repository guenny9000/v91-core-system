#!/usr/bin/env python3
"""Tests fuer controller/index_transition_lint.py (VIBE-LXXXCII).

pytest-kompatibel und ohne pytest lauffaehig (unittest-Runner unten).
LINT != WAHRHEIT: Diese Tests pruefen den strukturellen Uebergang,
nicht inhaltliche Richtigkeit. Alle Tests git- und netzfrei.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from index_transition_lint import (  # noqa: E402
    DEFAULT_ALLOWED_APPENDED,
    EXIT_FAIL,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    build_report,
    check_transition_files,
    lint_transition,
    main,
)

CLEAN_LINE_LXXXCI = (
    "- 23.11.2026 #404 (VIBE-LXXXCI) Branch-Hygiene-Planer; "
    "read-only; PLAN != LOESCHUNG. [VIBE-LXXXCI]"
)
NEXT_LINE_LXXXCII = (
    "- 23.11.2026 #406 (VIBE-LXXXCII) Index-Append-Transition-Lint; "
    "Base -> Head; UNKNOWN != PASS. [VIBE-LXXXCII]"
)


def _rules(result):
    return {e["rule"] for e in result.errors}


class TestValidTransitions(unittest.TestCase):
    def test_valid_single_append(self):
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n",
                              CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n")
        self.assertTrue(res.ok, res.errors)
        self.assertEqual(res.appended_count, 1)
        self.assertEqual(res.new_entries[0].end_tag, "LXXXCII")

    def test_valid_batch_append_with_allow(self):
        extra = (
            "- 23.11.2026 #408 (VIBE-LXXXCIII) Beispiel; "
            "Batch; PLAN != LOESCHUNG. [VIBE-LXXXCIII]"
        )
        head = "\n".join([CLEAN_LINE_LXXXCI, NEXT_LINE_LXXXCII, extra]) + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head, allowed_appended=2)
        self.assertTrue(res.ok, res.errors)
        self.assertEqual(res.appended_count, 2)

    def test_exact_prefix_multiline_base(self):
        base = "# Kopf\n\n- Abschnitt\n\n" + CLEAN_LINE_LXXXCI + "\n"
        head = base + NEXT_LINE_LXXXCII + "\n"
        res = lint_transition(base, head)
        self.assertTrue(res.ok, res.errors)


class TestBlocksInvalidTransitions(unittest.TestCase):
    def test_zero_append_is_error(self):
        base = CLEAN_LINE_LXXXCI + "\n"
        res = lint_transition(base, base)
        self.assertFalse(res.ok)
        self.assertIn("EXACTLY_ONE_APPEND", _rules(res))

    def test_two_appends_error_with_default_one(self):
        head = "\n".join([CLEAN_LINE_LXXXCI, NEXT_LINE_LXXXCII,
                          NEXT_LINE_LXXXCII.replace("LXXXCII", "LXXXCIII")]) + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head)
        self.assertFalse(res.ok)
        self.assertIn("EXACTLY_ONE_APPEND", _rules(res))

    def test_duplicate_new_tag_is_error(self):
        # Der echte PR-#400/#402-Fall: Tag existiert schon in der Basis.
        head = CLEAN_LINE_LXXXCI + "\n" + CLEAN_LINE_LXXXCI + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head)
        self.assertFalse(res.ok)
        self.assertIn("DUPLICATE_NEW_TAG", _rules(res))

    def test_duplicate_tag_inside_new_group(self):
        first = NEXT_LINE_LXXXCII
        second = NEXT_LINE_LXXXCII.replace("#406", "#407")
        head = CLEAN_LINE_LXXXCI + "\n" + first + "\n" + second + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head, allowed_appended=2)
        self.assertFalse(res.ok)
        self.assertIn("DUPLICATE_NEW_TAG", _rules(res))

    def test_base_mutation_is_error(self):
        base = CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n"
        mutated_base = CLEAN_LINE_LXXXCI.replace("#404", "#404x") + "\n" + NEXT_LINE_LXXXCII + "\n"
        res = lint_transition(mutated_base, base)
        self.assertFalse(res.ok)
        self.assertIn("BASE_PREFIX_MUTATED", _rules(res))

    def test_base_reorder_is_error(self):
        base = CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n"
        reordered_base = NEXT_LINE_LXXXCII + "\n" + CLEAN_LINE_LXXXCI + "\n"
        res = lint_transition(reordered_base, base)
        self.assertFalse(res.ok)
        self.assertIn("BASE_PREFIX_MUTATED", _rules(res))

    def test_non_session_append_is_error(self):
        head = CLEAN_LINE_LXXXCI + "\n- 23.11.2026 freitext ohne Tags\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head)
        self.assertFalse(res.ok)
        self.assertIn("APPEND_NOT_SESSION", _rules(res))

    def test_new_line_lint_fail_propagates(self):
        bad_date = NEXT_LINE_LXXXCII.replace("23.11.2026", "30.02.2026")
        head = CLEAN_LINE_LXXXCI + "\n" + bad_date + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head)
        self.assertFalse(res.ok)
        self.assertIn("NEW_LINE_LINT_FAIL", _rules(res))

    def test_invalid_allowed_appended_is_input_error(self):
        res = lint_transition("a\n", "a\nb\n", allowed_appended=0)
        self.assertFalse(res.ok)
        self.assertIn("INPUT_ERROR", _rules(res))

    def test_non_string_input_is_input_error(self):
        res = lint_transition(None, "a\n")
        self.assertFalse(res.ok)
        self.assertIn("INPUT_ERROR", _rules(res))


class TestHonestLimits(unittest.TestCase):
    def test_tag_ordering_stays_warning_not_error(self):
        # Unmoeglicher 'frueherer' Tag im Append darf NICHT als Fehler
        # gelten: der Index hat keine belegbare Ordnungsregel (UNKNOWN).
        early = CLEAN_LINE_LXXXCI.replace("VIBE-LXXXCI", "VIBE-XLII")
        head = CLEAN_LINE_LXXXCI + "\n" + early + "\n"
        res = lint_transition(CLEAN_LINE_LXXXCI + "\n", head)
        self.assertTrue(res.ok, res.errors)
        warning_rules = {w["rule"] for w in res.warnings}
        self.assertIn("TAG_ORDERING_UNKNOWN", warning_rules)


class TestCliAndFiles(unittest.TestCase):
    def _write(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".md", delete=False
        )
        handle.write(content)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_cli_ok_exit_zero(self):
        base = self._write(CLEAN_LINE_LXXXCI + "\n")
        head = self._write(CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n")
        code = main([str(base), str(head)])
        self.assertEqual(code, EXIT_OK)

    def test_cli_fail_exit_one(self):
        base = self._write(CLEAN_LINE_LXXXCI + "\n")
        head = self._write(CLEAN_LINE_LXXXCI + "\n")
        code = main([str(base), str(head)])
        self.assertEqual(code, EXIT_FAIL)

    def test_cli_missing_file_exit_three(self):
        code = main(["/nicht/vorhanden/base.md", "/nicht/vorhanden/head.md"])
        self.assertEqual(code, EXIT_INPUT_ERROR)

    def test_json_out_ok(self):
        base = self._write(CLEAN_LINE_LXXXCI + "\n")
        head = self._write(CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n")
        out = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: os.unlink(out / "report.json")
                        if (out / "report.json").exists() else None)
        code = main([str(base), str(head), "--json-out", str(out / "report.json")])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue((out / "report.json").is_file())
        import json
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertEqual(report["new_tags"], ["LXXXCII"])

    def test_json_out_inside_repo_refused(self):
        base = self._write(CLEAN_LINE_LXXXCI + "\n")
        head = self._write(CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n")
        module_dir = Path(
            os.path.join(os.path.dirname(__file__), "..", "controller")
        ).resolve()
        code = main([str(base), str(head), "--json-out",
                     str(module_dir / "runtime_artifact.json")])
        self.assertEqual(code, EXIT_INPUT_ERROR)
        self.assertFalse((module_dir / "runtime_artifact.json").exists())

    def test_file_check_pair(self):
        base = self._write(CLEAN_LINE_LXXXCI + "\n")
        head = self._write(CLEAN_LINE_LXXXCI + "\n" + NEXT_LINE_LXXXCII + "\n")
        result, code = check_transition_files(str(base), str(head), DEFAULT_ALLOWED_APPENDED)
        self.assertEqual(code, EXIT_OK)
        report = build_report(result, str(base), str(head))
        self.assertTrue(report["ok"])
        self.assertEqual(report["appended_lines"], 1)


if __name__ == "__main__":
    unittest.main()
