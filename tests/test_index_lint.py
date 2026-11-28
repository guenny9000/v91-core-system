#!/usr/bin/env python3
"""Tests fuer controller/index_lint.py (Regel-#138-Konsistenzlint).

pytest-kompatibel und ohne pytest lauffaehig (unittest-Runner unten).
LINT != WAHRHEIT: Diese Tests pruefen Strukturregeln, nicht Inhalte.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))

from index_lint import (  # noqa: E402
    build_report,
    check_file,
    lint_text,
    parse_entry,
)

CLEAN_LINE = (
    "- 22.11.2026 #359 (VIBE-LXVIII) Kurzlauf-Validierer Wirkungsregister; "
    "Mehrere Fachbegriffe im Text; SCRIPTED != INSTALLED. [VIBE-LXVIII]"
)

# Eckiges Einzel-Tag-Format (Format-Drift ab #593, z. B. reale Zeile #629):
SQUARE_LINE = (
    "- 28.11.2026 #629 [VIBE-CLVI] NACHWEIS-CHECK-EHRLICH "
    "(Inhalt; UNKNOWN != PASS.)"
)


def test_clean_entry_parses():
    entry = parse_entry(CLEAN_LINE, 1)
    assert entry is not None
    assert entry.date == "22.11.2026"
    assert entry.prs == "#359"
    assert entry.start_tag == "LXVIII"
    assert entry.end_tag == "LXVIII"


def test_multi_pr_line_parses_primary():
    line = (
        "- 22.11.2026 #352/#355 (VIBE-LXV) Index-Nachzugs-Reparatur; "
        "Inhalt; SCRIPTED != INSTALLED. [VIBE-LXV]"
    )
    entry = parse_entry(line, 1)
    assert entry is not None
    assert entry.prs == "#352/#355"


def test_tag_mismatch_is_error():
    text = CLEAN_LINE.replace("[VIBE-LXVIII]", "[VIBE-XXXVIII]")
    result = lint_text(text)
    assert not result.ok
    assert result.errors[0]["rule"] == "TAG_START_END_MISMATCH"


def test_bad_date_is_error():
    text = CLEAN_LINE.replace("22.11.2026", "30.02.2026")
    result = lint_text(text)
    assert not result.ok
    assert any(e["rule"] == "BAD_DATE" for e in result.errors)


def test_year_out_of_range_is_error():
    text = CLEAN_LINE.replace("22.11.2026", "22.11.1999")
    result = lint_text(text)
    assert any(e["rule"] == "YEAR_OUT_OF_RANGE" for e in result.errors)


def test_duplicate_primary_pr_is_error():
    text = (
        CLEAN_LINE
        + "\n"
        + CLEAN_LINE.replace("#359", "#359").replace("(VIBE-LXVIII)", "(VIBE-LXVIX)").replace(
            "[VIBE-LXVIII]", "[VIBE-LXVIX]"
        )
    )
    result = lint_text(text)
    assert any(e["rule"] == "DUPLICATE_PRIMARY_PR" for e in result.errors)


def test_square_entry_parses():
    entry = parse_entry(SQUARE_LINE, 1)
    assert entry is not None
    assert entry.date == "28.11.2026"
    assert entry.prs == "#629"
    assert entry.start_tag == "CLVI"
    # Einzel-Tag: Start == End per Definition (kein MISMATCH moeglich).
    assert entry.end_tag == "CLVI"


def test_square_line_is_linted_not_ignored():
    result = lint_text(SQUARE_LINE)
    assert result.ok
    assert len(result.entries) == 1
    assert not result.warnings


def test_square_future_date_is_error():
    text = SQUARE_LINE.replace("28.11.2026", "29.11.2026")
    result = lint_text(text, today=datetime(2026, 11, 28))
    assert not result.ok
    assert any(e["rule"] == "DATUM_IN_ZUKUNFT" for e in result.errors)


def test_duplicate_across_formats_is_error():
    square_dup = SQUARE_LINE.replace("#629", "#359")
    result = lint_text(CLEAN_LINE + "\n" + square_dup)
    assert any(e["rule"] == "DUPLICATE_PRIMARY_PR" for e in result.errors)


def test_square_mixed_with_klammer_counts_both():
    result = lint_text(CLEAN_LINE + "\n" + SQUARE_LINE)
    assert result.ok
    assert len(result.entries) == 2


def test_start_tag_without_end_tag_is_warning_not_error():
    line = "- 21.11.2026 #305 (VIBE-XL) XL-Annahmematrix: 15 Annahmetests."
    result = lint_text(line)
    assert result.ok
    assert result.warnings
    assert result.warnings[0]["rule"] == "START_TAG_WITHOUT_END_TAG"


def test_plain_lines_are_ignored():
    text = (
        "# V91 Architektur-Index (Bindende Uebersicht, verweisend)\n"
        "\n"
        "- 18.11.2026 #138 Architektur-Index angelegt (verweisend).\n"
        + CLEAN_LINE
    )
    result = lint_text(text)
    assert result.ok
    assert len(result.entries) == 1


def test_empty_text_is_clean():
    result = lint_text("")
    assert result.ok
    assert result.entries == []


def test_marker_texts_do_not_fool_end_tag_detection():
    # [VIBE-...] im Fliesstext, aber kein Start-Muster: keine Session-Zeile.
    result = lint_text("Siehe auch [VIBE-LVII] im Text ohne Muster.")
    assert result.ok
    assert result.entries == []


def test_check_file_exit_codes():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(CLEAN_LINE)
        path = handle.name
    result, code = check_file(path)
    assert code == 0
    assert result.ok
    os.unlink(path)

    result, code = check_file("/dieser/pfad/existiert/nicht.md")
    assert code == 3


def test_report_counts():
    text = CLEAN_LINE + "\n- 21.11.2026 #305 (VIBE-XL) xl-annahmematrix."
    result = lint_text(text)
    report = build_report(result, "x.md")
    assert report["entries"] == 1
    assert report["warnings"] == 1
    assert report["ok"] is True


def test_real_index_lint_clean():
    """Integration: der echte Index auf main muss fehlerfrei sein.

    SKIP != PASS: Fehlt die Datei (z. B. Ausfuerung ausserhalb des
    Repos), wird ehrlich uebersprungen. Seit der Archiv-Ueberfuehrung
    (#521-Nachfolge) zaehlt der Bestandsschutz gegen die leere
    Rekonstruktion aus #173 Index PLUS Archiv-Datei zusammen.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    index_path = os.path.join(repo_root, "docs", "V91-ARCHITEKTUR-INDEX.md")
    if not os.path.isfile(index_path):
        print("SKIP: Index-Datei nicht gefunden")
        return
    text = open(index_path, encoding="utf-8").read()
    result = lint_text(text)
    assert result.ok, "Index-Verstoesse: %s" % result.errors
    archive_path = os.path.join(
        repo_root, "docs", "archive", "V91-ARCHITEKTUR-AENDERUNGSLOG.md"
    )
    if not os.path.isfile(archive_path):
        assert len(result.entries) > 20, "Unerwartet wenige Session-Eintraege"
        return
    archive_result = lint_text(open(archive_path, encoding="utf-8").read())
    assert archive_result.ok, "Archiv-Verstoesse: %s" % archive_result.errors
    combined = len(result.entries) + len(archive_result.entries)
    assert combined > 20, (
        "Unerwartet wenige Session-Eintraege (Index + Archiv): %d" % combined
    )


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
    print("\n%d lint tests passed" % len(tests))


if __name__ == "__main__":
    _run_all()
