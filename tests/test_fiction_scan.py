#!/usr/bin/env python3
"""Tests for controller/fiction_scan.py (fail-closed fiction scan).

The scanner must catch every known fiction-marker form, must NOT flag
the honest AGATHON header, and must never scan docs/ (documentation
legitimately quotes fiction in order to reject it).
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.fiction_scan import (
    ALLOWLIST_FILENAME,
    FICTION_PATTERNS,
    FictionScanError,
    find_fiction,
    load_allowlist,
    main,
)


def _write(root, relpath, text=""):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _markered_code(field):
    # Fragments keep THIS test file itself scannable-clean.
    return "x = '" + field + "'\n"


class PatternDetectionTests(unittest.TestCase):
    def test_all_fiction_markers_detected(self) -> None:
        fields = [
            "SEQ:" + "9130",
            "V91-AUDIT-V" + "2.5",
            "FQ:" + "AKTIV",
            "FQ:" + "ZERO",
            "DRIFT:" + "0/INF",
            "VALID:" + "VERIFIED",
            "VALID:" + "1",
            "STATUS:" + "ACTIVE",
            "STATUS:" + "S",
            "Tarn" + "modus",
            "V91EnhancedGuard" + "Daemon",
            "Dual-Node-" + "Consensus",
        ]
        for field in fields:
            hits = [k for k, p in FICTION_PATTERNS if p.search(_markered_code(field))]
            self.assertTrue(hits, f"marker {field!r} must be detected")

    def test_honest_forms_stay_clean(self) -> None:
        honest_lines = [
            "STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)",
            "AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.",
            "sequence_number = 9130  # a plain integer, no marker",
            "VALIDATION_REQUIRED = True",
            "SEQ_FRAME_SIZE = 8",
        ]
        for line in honest_lines:
            hits = [k for k, p in FICTION_PATTERNS if p.search(line)]
            self.assertEqual([], hits, f"honest line must stay clean: {line!r}")


class ScanBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_tree_reports_clean(self) -> None:
        _write(self.root, "controller/x.py", "VALUE = 1\n")
        _write(self.root, "tests/test_x.py", "def test_x():\n    assert True\n")
        report = find_fiction(self.root)
        self.assertEqual("CLEAN", report["status"])
        self.assertEqual(2, report["scanned_files"])
        self.assertEqual([], report["findings"])

    def test_fiction_in_python_code_fails(self) -> None:
        _write(self.root, "controller/bad.py",
               _markered_code("SEQ:" + "9132"))
        report = find_fiction(self.root)
        self.assertEqual("FINDINGS", report["status"])
        self.assertEqual(1, len(report["findings"]))
        self.assertEqual("seq_marker", report["findings"][0]["kind"])
        self.assertEqual("bad.py", os.path.basename(report["findings"][0]["path"]))

    def test_pseudo_header_line_hits_multiple_markers(self) -> None:
        line = ("V91-AUDIT-V" + "2.5: [STATUS:" + "ACTIVE] [FQ:" + "ZERO] "
                "[DRIFT:0" + "/3] [VALID:" + "1] [SEQ: 91" + "30]")
        _write(self.root, "controller/bad.py", _markered_code(line))
        report = find_fiction(self.root)
        kinds = {f["kind"] for f in report["findings"]}
        self.assertIn("audit_series_marker", kinds)
        self.assertIn("seq_marker", kinds)

    def test_docs_dir_and_markdown_are_not_scanned(self) -> None:
        _write(self.root, "docs/FICTION-REJECTION.md",
               _markered_code("SEQ:" + "9130"))
        _write(self.root, "notes.md",
               _markered_code("STATUS:" + "ACTIVE"))
        report = find_fiction(self.root)
        self.assertEqual("CLEAN", report["status"])
        self.assertEqual(0, report["scanned_files"])

    def test_allowlist_suppresses_by_substring(self) -> None:
        _write(self.root, "controller/bad.py",
               _markered_code("SEQ:" + "9130"))
        (self.root / ALLOWLIST_FILENAME).write_text(
            "# reviewed\nSEQ:" + "9130\n", encoding="utf-8")
        allowlist = load_allowlist(self.root / ALLOWLIST_FILENAME)
        report = find_fiction(self.root, allowlist)
        self.assertEqual("CLEAN", report["status"])
        self.assertEqual(1, report["suppressed_findings"])
        self.assertEqual(0, main(["--path", str(self.root)]))

    def test_binary_and_oversize_skipped(self) -> None:
        (self.root / "controller").mkdir(parents=True)
        (self.root / "controller/blob.bin").write_bytes(
            b"SEQ:" + b"9130" + b"\x00\x01")
        report = find_fiction(self.root)
        self.assertEqual("CLEAN", report["status"])
        self.assertEqual(0, report["scanned_files"])

    def test_missing_path_fails_closed(self) -> None:
        with self.assertRaises(FictionScanError):
            find_fiction(self.root / "does-not-exist")
        self.assertEqual(2, main(["--path", str(self.root / "nope")]))

    def test_allowlist_unreadable_fails_closed(self) -> None:
        bad = self.root / "bad-allowlist.txt"
        bad.write_bytes(b"\xff\xfe\xff")
        try:
            load_allowlist(bad)
            raised = False
        except FictionScanError:
            raised = True
        self.assertTrue(raised)

    def test_real_repo_lifecycle_files_stay_clean(self) -> None:
        # Integration: the actual repo working tree (controller with
        # honest AGATHON headers) must scan CLEAN at all times.
        repo_root = Path(__file__).resolve().parent.parent
        report = find_fiction(repo_root / "controller")
        self.assertEqual("CLEAN", report["status"])


if __name__ == "__main__":
    unittest.main()
