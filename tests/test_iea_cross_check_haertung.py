"""
Zahlenhaertungs-Pins fuer cross_check (controller/iea_stats_adapter.py,
Haertung 25.11.2026, Fremdbefund-Nachmessung).

Verriegelt wird fail-closed gegen die zwei nachgemessenen Lücken:
1. inf-Claim gegen inf-Evidenz: abs(inf - inf) > toleranz ist False,
   haette KATALOG_KONGRUENT geloggt -> KEINE Freigabe aus Unendlich.
2. toleranz=NaN: jeder Vergleich gegen NaN ist False -> alles haette
   als kongruent durchgelassen -> NaN verboten, ValueError.
Selbstcontained: KEINE Dateien, kein Netz, KEIN Mock.
"""
from __future__ import annotations

import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from controller import iea_stats_adapter as iea


class CrossCheckZahlenhaertungTest(unittest.TestCase):
    def test_inf_claim_is_not_kongruent(self):
        befund = iea.cross_check(math.inf, {"katalog": 1.0})
        self.assertEqual(befund["status"], iea.NICHT_GEPRUEFT)
        self.assertIn("nicht endlich", befund["grund"])

    def test_inf_evidenz_zaehlt_als_fehlend_nicht_als_zahl(self):
        befund = iea.cross_check(1.0, {"katalog": math.inf})
        self.assertEqual(befund["status"], iea.NICHT_GEPRUEFT)
        self.assertIn("katalog", befund["evidenz_fehlend"])

    def test_nan_evidenz_zaehlt_als_fehlend(self):
        befund = iea.cross_check(1.0, {"katalog": math.nan})
        self.assertEqual(befund["status"], iea.NICHT_GEPRUEFT)
        self.assertIn("katalog", befund["evidenz_fehlend"])

    def test_nan_toleranz_is_rejected_fail_closed(self):
        with self.assertRaises(ValueError):
            iea.cross_check(1.0, {"katalog": 1.0}, toleranz=math.nan)

    def test_inf_toleranz_is_rejected_fail_closed(self):
        with self.assertRaises(ValueError):
            iea.cross_check(1.0, {"katalog": 1.0}, toleranz=math.inf)

    def test_finite_values_still_work_unaffected(self):
        befund = iea.cross_check(0.45, {"katalog": 0.45})
        self.assertEqual(befund["status"], iea.KATALOG_KONGRUENT)
        befund = iea.cross_check(0.45, {"katalog": 0.55}, toleranz=0.05)
        self.assertEqual(befund["status"], iea.KATALOG_DIVERGENT)
        self.assertEqual(befund["abweichungen"], {"katalog": 0.55})

    def test_intolerant_default_zero_unchanged(self):
        befund = iea.cross_check(0.451, {"katalog": 0.450})
        self.assertEqual(befund["status"], iea.KATALOG_DIVERGENT)


if __name__ == "__main__":
    unittest.main()
