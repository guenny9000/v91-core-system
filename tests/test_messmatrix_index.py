"""Tests fuer controller/messmatrix_index (MATRIZ != WIRKUNG, fail-closed)."""
import json
import tempfile
import unittest
from pathlib import Path

from controller.messmatrix_index import MessmatrixIndexError, build_index, main
from io import StringIO
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = REPO_ROOT / "docs" / "messmatrix"


def _record(initiative_id="test-initiative", watcher="wasser", maturity="R2",
             multiplier=None):
    return {
        "initiative_id": initiative_id,
        "description": "Testinitiative fuer den Index",
        "watcher": watcher,
        "maturity": maturity,
        "indicators": [
            {"role": "WIRKUNG", "name": "Flaeche", "unit": "ha",
             "baseline": 0.0, "target": 100.0,
             "period": {"baseline_at": "2026-01-01T00:00:00Z",
                        "target_at": "2027-01-01T00:00:00Z"},
             "method": "Vermessung", "verifier": "Amt",
             "uncertainty": 1.0,
             "alternative_comparison": "Nichtstun"},
            {"role": "KOSTEN", "name": "Kosten", "unit": "EUR",
             "baseline": 0.0, "target": 1000.0,
             "period": {"baseline_at": "2026-01-01T00:00:00Z",
                        "target_at": "2027-01-01T00:00:00Z"},
             "method": "Haushaltsabgleich", "verifier": "Kasse",
             "uncertainty": 0.0},
            {"role": "RESILIENZ", "name": "Messstellen", "unit": "Stueck",
             "baseline": 0.0, "target": 3.0,
             "period": {"baseline_at": "2026-01-01T00:00:00Z",
                        "target_at": "2027-01-01T00:00:00Z"},
             "method": "Zaehlung", "verifier": "Konzept",
             "uncertainty": 0.0},
        ],
        "multiplier": multiplier,
    }


def _dataset(tmpdir, name, **overrides):
    path = Path(tmpdir) / (name + ".json")
    path.write_text(json.dumps(_record(**overrides), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


class BuildIndexTests(unittest.TestCase):
    def test_single_dataset_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "one", initiative_id="eins")
            index = build_index(Path(tmp))
            self.assertEqual(index["datasets_total"], 1)
            self.assertEqual(index["datasets"][0]["file"], "one.json")
            self.assertEqual(index["datasets"][0]["initiative_id"], "eins")
            self.assertEqual(index["by_watcher"], {"wasser": 1})

    def test_watcher_and_maturity_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a", watcher="wasser", maturity="R2")
            _dataset(tmp, "b", watcher="energie", maturity="R1")
            _dataset(tmp, "c", watcher="wasser", maturity="R2")
            index = build_index(Path(tmp))
            self.assertEqual(index["by_watcher"], {"wasser": 2, "energie": 1})
            self.assertEqual(index["by_maturity"], {"R1": 1, "R2": 2})

    def test_roles_and_indicator_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a")
            index = build_index(Path(tmp))
            self.assertEqual(index["by_role"],
                             {"KOSTEN": 1, "RESILIENZ": 1, "WIRKUNG": 1})
            self.assertEqual(index["indicators_total"], 3)

    def test_multiplier_status_unknown_without_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a", multiplier=None)
            index = build_index(Path(tmp))
            self.assertEqual(index["by_multiplier_status"], {"UNKNOWN": 1})

    def test_multiplier_status_modeled_with_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a", multiplier={"added_benefit": 10.0,
                                          "added_effort": 5.0})
            index = build_index(Path(tmp))
            self.assertEqual(index["by_multiplier_status"], {"MODELED": 1})

    def test_impact_claims_permitted_stays_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a")
            _dataset(tmp, "b")
            index = build_index(Path(tmp))
            self.assertEqual(index["impact_claims_permitted"], 0)
            self.assertTrue(all(not d["impact_claim_permitted"]
                                for d in index["datasets"]))

    def test_deterministic_two_runs_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a")
            _dataset(tmp, "b", watcher="energie", maturity="R1")
            first = build_index(Path(tmp))
            second = build_index(Path(tmp))
            self.assertEqual(first, second)

    def test_fail_closed_missing_dir(self):
        with self.assertRaises(MessmatrixIndexError):
            build_index(Path("/does/not/exist-messmatrix"))

    def test_fail_closed_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MessmatrixIndexError):
                build_index(Path(tmp))

    def test_fail_closed_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "broken.json").write_text("{not json", encoding="utf-8")
            with self.assertRaises(MessmatrixIndexError):
                build_index(Path(tmp))

    def test_fail_closed_record_rejected_by_evaluator(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bad.json").write_text(json.dumps(
                {"initiative_id": "x"}), encoding="utf-8")
            with self.assertRaises(MessmatrixIndexError):
                build_index(Path(tmp))

    def test_fail_closed_non_object_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "list.json").write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(MessmatrixIndexError):
                build_index(Path(tmp))

    def test_dataset_dir_must_be_path(self):
        with self.assertRaises(MessmatrixIndexError):
            build_index("docs/messmatrix")


class RealDatasetTests(unittest.TestCase):
    def test_real_dataset_dir_index_green(self):
        index = build_index(REAL_DIR)
        self.assertGreaterEqual(index["datasets_total"], 1)
        self.assertEqual(index["datasets_total"], len(index["datasets"]))
        self.assertEqual(sum(index["by_watcher"].values()),
                         index["datasets_total"])
        self.assertEqual(index["impact_claims_permitted"], 0)
        for dataset in index["datasets"]:
            self.assertEqual(dataset["matrix_status"], "MASSE_BESCHRIEBEN")
            self.assertIn(dataset["watcher"],
                          ("wasser", "energie", "ernaehrung", "gesundheit",
                           "natur", "frieden", "technologie"))

    def test_pilot_a_present_if_exists(self):
        if not REAL_DIR.is_dir() or not any(REAL_DIR.glob("*.json")):
            self.skipTest("noch keine echten Datasets im Verzeichnis")
        index = build_index(REAL_DIR)
        ids = [d["initiative_id"] for d in index["datasets"]]
        self.assertIn("pilot-a-moor-wasser-2026", ids)


class CliTests(unittest.TestCase):
    def test_cli_exit_zero_and_json_output(self):
        argv = ["--dataset-dir", str(REAL_DIR)]
        with mock.patch("sys.stdout", new_callable=StringIO) as out:
            code = main(argv)
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertGreaterEqual(payload["datasets_total"], 1)

    def test_cli_exit_two_on_error(self):
        code = main(["--dataset-dir", "/does/not/exist-messmatrix"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
