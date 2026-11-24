"""
Tests fuer die DATUM_IN_ZUKUNFT-Regel in controller/index_lint.

Anlass: vier Index-Zeilen trugen 25.11.2026, obwohl ihre PRs
nachweislich am 24.11.2026 gemergt wurden (Merge-Stempel 19:15-20:37
UTC). Der Lint hatte keine Zukunftspruefung - diese Luecke wird hier
geschlossen und verriegelt. LINT != WAHRHEIT: geprueft wird die Form
der Chronologie, nicht die Echtheit des Merges (das bleibt Git-Audit).
Determinismus: today-Parameter ersetzt die Referenz komplett; nur der
Default (CLI/CI) traegt das 2-Stunden-Toleranzfenster (UTC vs. Berlin).
"""
from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller.index_lint import lint_text


def _line(date: str, pr: int, mark: str = "ZZTEST") -> str:
    return "- %s #%d (VIBE-%s) Regel-#138-Testzeile ohne Fictionsmuster. [VIBE-%s]\n" % (
        date, pr, mark, mark)


class FutureDateRuleTest(unittest.TestCase):
    def test_today_entry_passes(self):
        r = lint_text(_line("24.11.2026", 901), today=datetime(2026, 11, 24, 21, 0, 0))
        self.assertTrue(r.ok, r.errors)

    def test_past_entry_passes(self):
        r = lint_text(_line("22.11.2026", 902), today=datetime(2026, 11, 24, 21, 0, 0))
        self.assertTrue(r.ok, r.errors)

    def test_next_day_entry_is_rejected(self):
        r = lint_text(_line("25.11.2026", 903), today=datetime(2026, 11, 24, 21, 0, 0))
        self.assertFalse(r.ok)
        self.assertEqual([e["rule"] for e in r.errors], ["DATUM_IN_ZUKUNFT"])

    def test_far_future_entry_is_rejected(self):
        r = lint_text(_line("30.11.2026", 904), today=datetime(2026, 11, 24, 21, 0, 0))
        self.assertFalse(r.ok)
        self.assertIn("DATUM_IN_ZUKUNFT", [e["rule"] for e in r.errors])

    def test_rule_reports_line_number_and_detail(self):
        r = lint_text(
            _line("24.11.2026", 905) + _line("25.11.2026", 906, "ZZTEST2"),
            today=datetime(2026, 11, 24, 21, 0, 0))
        self.assertEqual(len(r.entries), 2)
        err = [e for e in r.errors if e["rule"] == "DATUM_IN_ZUKUNFT"]
        self.assertEqual(len(err), 1)
        self.assertEqual(err[0]["line"], 2)
        self.assertIn("MERGE-STEMPEL", err[0]["detail"])

    def test_injected_today_is_used_raw_without_tolerance(self):
        # Injected today ersetzt die Referenz komplett: auch 23:59 UTC
        # bleibt Referenztag 24.11 -> 25.11-Eintrag wird abgelehnt.
        r = lint_text(_line("25.11.2026", 907), today=datetime(2026, 11, 24, 23, 59, 0))
        self.assertFalse(r.ok)

    def test_neutral_library_date_not_session_date(self):
        # Nur Session-Zeilen tragen Daten; Fliesstext-Daten werden
        # nicht geprueft (Regel #138 gilt fuer Eintraege).
        r = lint_text("Besprechung am 99.99.9999 ist Fliesstext.\n")
        self.assertTrue(r.ok)
        self.assertEqual(len(r.entries), 0)


if __name__ == "__main__":
    unittest.main()
