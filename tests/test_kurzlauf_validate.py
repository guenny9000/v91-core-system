"""
Tests fuer controller/kurzlauf_validate.py (VIBE-LXVIII):
Kurzlauf-Validierer des Wirkungsregisters. Behauptete Tragfaehigkeit
wird nur geprueft, nie behauptet (CLAIM != EVIDENCE). Kernpflichten:
IQR/Z-Score-Statistik, Drift gegen Vorgaenger, UNKNOWN != PASS,
fail-closed bei unbrauchbarer Eingabe, deterministische ASCII-Reports,
VALID != EINTRAG (kein Ledger-Schreibaufruf im Modul).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from controller import kurzlauf_validate as kv


def _write_csv(directory: Path, name: str, rows, header=True):
    path = directory / name
    lines = []
    if header:
        lines.append("metric_id,value")
    lines.extend("%s,%s" % (mid, val) for mid, val in rows)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def _good_rows(mean=0.15, n=10):
    return [("VB-ENERGIE-01", "%.4f" % (mean + 0.01 * (i % 5 - 2)))
            for i in range(n)]


class DescribeStats(unittest.TestCase):
    def test_quartiles_and_stats_are_plausible(self):
        values = [float(i) for i in range(1, 11)]
        stats = kv.describe(values)
        self.assertEqual(stats["n"], 10)
        self.assertAlmostEqual(stats["mean"], 5.5)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 10.0)
        self.assertLess(stats["q1"], stats["median"])
        self.assertLess(stats["median"], stats["q3"])

    def test_iqr_outlier_detected(self):
        values = [10.0] * 9 + [1000.0]
        stats = kv.describe(values)
        self.assertGreater(stats["outlier_fraction"], 0.0)

    def test_zero_std_does_not_crash(self):
        stats = kv.describe([2.0, 2.0, 2.0])
        self.assertEqual(stats["std"], 0.0)
        self.assertEqual(stats["outliers_iqr"], 0)


class ParseCsv(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_header_and_semicolon_tolerated(self):
        path = self.dir / "k.csv"
        path.write_text("metric_id;value\nVB-NETZ-01,12.5\n",
                        encoding="ascii")
        data = kv.parse_kurzlauf_csv(path)
        self.assertEqual(data, {"VB-NETZ-01": [12.5]})

    def test_unknown_metric_fail_closed(self):
        path = _write_csv(self.dir, "k.csv", [("VB-GHOST-01", 1.0)])
        with self.assertRaises(kv.KurzlaufInputError):
            kv.parse_kurzlauf_csv(path)

    def test_non_numeric_fail_closed(self):
        path = _write_csv(self.dir, "k.csv", [("VB-NETZ-01", "abc")])
        with self.assertRaises(kv.KurzlaufInputError):
            kv.parse_kurzlauf_csv(path)

    def test_missing_file_fail_closed(self):
        with self.assertRaises(kv.KurzlaufInputError):
            kv.parse_kurzlauf_csv(self.dir / "nope.csv")

    def test_empty_file_fail_closed(self):
        path = _write_csv(self.dir, "leer.csv", [], header=False)
        path.write_text("", encoding="ascii")
        with self.assertRaises(kv.KurzlaufInputError):
            kv.parse_kurzlauf_csv(path)


class ClassifyVerdicts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _classify(self, rows, prev_rows):
        path = _write_csv(self.dir, "cur.csv", rows)
        prev = _write_csv(self.dir, "prev.csv", prev_rows)
        current = kv.parse_kurzlauf_csv(path)
        previous = kv.parse_kurzlauf_csv(prev)
        first = sorted(current)[0]
        return kv.classify(first, current[first], previous.get(first))

    def test_valid_when_drift_small(self):
        result = self._classify(_good_rows(), _good_rows())
        self.assertEqual(result["verdict"], kv.VALID)
        self.assertLess(result["drift_percent"], 0.1)

    def test_unknown_cold_start(self):
        result = self._classify(_good_rows(), None) if False else \
            kv.classify("VB-ENERGIE-01",
                        [0.15] * 10, None)
        self.assertEqual(result["verdict"], kv.UNKNOWN)
        self.assertTrue(any("COLD_START" in r for r in result["reasons"]))

    def test_unknown_short_vorgaenger(self):
        result = kv.classify(
            "VB-ENERGIE-01", [0.15] * 10, [0.15] * 3)
        self.assertEqual(result["verdict"], kv.UNKNOWN)
        self.assertTrue(any("VORGAENGER_UNVOLLLSTAENDIG" in r
                            for r in result["reasons"]))

    def test_unknown_cold_start_with_outliers_becomes_drift(self):
        values = [0.15] * 9 + [0.5, 0.8, 1.0]
        result = kv.classify("VB-ENERGIE-01", values, None)
        self.assertEqual(result["verdict"], kv.DRIFT)

    def test_drift_when_mean_shifts(self):
        result = self._classify(_good_rows(mean=0.25), _good_rows(mean=0.15))
        self.assertEqual(result["verdict"], kv.DRIFT)
        self.assertGreater(result["drift_percent"], 10.0)

    def test_out_of_range_never_silently_corrected(self):
        result = kv.classify("VB-SYS-01", [50.0] * 9 + [150.0], None)
        self.assertEqual(result["verdict"], kv.DRIFT)
        self.assertTrue(any("OUT_OF_RANGE" in r for r in result["reasons"]))

    def test_prev_mean_zero_is_drift_not_crash(self):
        result = kv.classify("VB-UMWELT-01", [1.0] * 10, [0.0] * 10)
        self.assertEqual(result["verdict"], kv.DRIFT)
        self.assertTrue(any("DRIFT_NICHT_BERECHENBAR" in r
                            for r in result["reasons"]))


class ValidateRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_overall_drift_wins_over_unknown(self):
        cur = _write_csv(self.dir, "cur.csv",
                         _good_rows() + [("VB-SYS-01", 150.0)])
        report = kv.validate(cur, None)
        self.assertEqual(report["overall"], kv.DRIFT)

    def test_overall_unknown_when_only_cold_start(self):
        cur = _write_csv(self.dir, "cur.csv", _good_rows())
        report = kv.validate(cur, None)
        self.assertEqual(report["overall"], kv.UNKNOWN)

    def test_reports_are_ascii_and_deterministic(self):
        cur = _write_csv(self.dir, "k212.csv", _good_rows())
        rpt_dir = self.dir / "out"
        rc1 = kv.main(["cur", "--report-dir", "x"][:0] +
                      [str(cur), "--report-dir", str(rpt_dir)])
        rc2 = kv.main([str(cur), "--report-dir", str(rpt_dir)])
        self.assertEqual(rc1, rc2)
        txt = (rpt_dir / "validierung_k212.txt").read_text("ascii")
        payload = (rpt_dir / "validierung_k212.json").read_text("ascii")
        data = json.loads(payload)
        self.assertEqual(data["overall"], kv.UNKNOWN)
        self.assertIn("VALID != EINTRAG", txt)
        for ch in txt + payload:
            self.assertLess(ord(ch), 128)

    def test_exit_codes_via_main(self):
        cur = _write_csv(self.dir, "v.csv", _good_rows())
        prev = _write_csv(self.dir, "p.csv", _good_rows())
        self.assertEqual(kv.main([str(cur)]), kv.EXIT_UNKNOWN)
        self.assertEqual(kv.main([str(cur), "--vorgaenger", str(prev)]),
                         kv.EXIT_VALID)
        bad = _write_csv(self.dir, "bad.csv", [("VB-NOPE", 1.0)])
        self.assertEqual(kv.main([str(bad)]), kv.EXIT_INPUT_ERROR)

    def test_no_ledger_write_path_in_module(self):
        source = Path(kv.__file__).read_text(encoding="utf-8")
        self.assertNotIn("MesswertLedger.append(", source)
        self.assertNotIn("from controller.messwerte_ingest", source)
        self.assertNotIn("import messwerte_ingest", source)
        self.assertNotIn(".jsonl", source)


if __name__ == "__main__":
    unittest.main()
