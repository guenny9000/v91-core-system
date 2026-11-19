"""Tests für controller/review_index (Index != Bewertung, fail-closed)."""
import json
import unittest
from pathlib import Path

from controller.review_index import ReviewIndexError, build_index, main

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = REPO_ROOT / "docs" / "structure-reviews"


def _dataset(tmpdir, name, *, statuses=None, structure_id=None):
    """Schreibt ein valides Struktur-Review-Dataset ins Tempverzeichnis.

    statuses: Mapping Kriteriumsname -> Status (BELEGT / PROBLEM_BELEGT /
    NICHT_GEPRUEFT); fehlende Kriterien default auf BELEGT.
    """
    from controller.structure_review import CRITERIA

    statuses = statuses or {}
    criteria = {}
    for criterion in CRITERIA:
        status = statuses.get(criterion, "BELEGT")
        if status == "NICHT_GEPRUEFT":
            criteria[criterion] = {"status": status}
        else:
            criteria[criterion] = {
                "status": status,
                "evidence": "pruefung bestanden",
                "source": "https://example.org/quelle",
                "assessed_at": "2026-11-19T00:00:00Z",
            }
    review = {
        "schema_version": 1,
        "structure_id": structure_id or ("test-" + name),
        "assessor": "review-index-tests",
        "criteria": criteria,
    }
    path = Path(tmpdir) / (name + ".json")
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class BuildIndexTests(unittest.TestCase):
    def test_single_dataset_index(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "one")
            index = build_index(Path(tmp))
            self.assertEqual(index["datasets_total"], 1)
            self.assertEqual(index["datasets"][0]["file"], "one.json")
            self.assertIn(index["datasets"][0]["verdict"], index["by_verdict"])

    def test_mixed_verdicts_and_counts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "a")
            _dataset(tmp, "b", statuses={"kosten_und_ressourcenverbrauch": "PROBLEM_BELEGT"})
            index = build_index(Path(tmp))
            self.assertEqual(index["datasets_total"], 2)
            self.assertEqual(sum(index["by_verdict"].values()), 2)
            self.assertTrue(
                all(count > 0 for count in index["problems_by_criterion"].values())
            )
            entry_b = next(item for item in index["datasets"] if item["file"] == "b.json")
            self.assertEqual(entry_b["problems"], ["kosten_und_ressourcenverbrauch"])

    def test_empty_dir_fail_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ReviewIndexError):
                build_index(Path(tmp))

    def test_missing_dir_fail_closed(self):
        with self.assertRaises(ReviewIndexError):
            build_index(Path("/nonexistent/review/dir"))

    def test_invalid_json_fail_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "broken.json").write_text("{ nope", encoding="utf-8")
            with self.assertRaises(ReviewIndexError) as ctx:
                build_index(Path(tmp))
            self.assertIn("broken.json", str(ctx.exception))

    def test_invalid_dataset_fail_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "wrong.json").write_text(
                json.dumps({"schema_version": 9}), encoding="utf-8"
            )
            with self.assertRaises(ReviewIndexError) as ctx:
                build_index(Path(tmp))
            self.assertIn("wrong.json", str(ctx.exception))

    def test_not_a_path_argument(self):
        with self.assertRaises(ReviewIndexError):
            build_index("docs/structure-reviews")

    def test_deterministic_no_timestamps(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "x")
            first = build_index(Path(tmp))
            second = build_index(Path(tmp))
            self.assertEqual(first, second)
            dumped = json.dumps(first)
            for key in ("generated_at", "timestamp", "created_at", "run_at"):
                self.assertNotIn(key, dumped)

    def test_problem_filter_zero_counts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _dataset(tmp, "clean")
            index = build_index(Path(tmp))
            self.assertEqual(index["problems_by_criterion"], {})
            self.assertEqual(index["ungeprueft_by_criterion"], {})


@unittest.skipUnless(REAL_DIR.is_dir() and any(REAL_DIR.glob("*.json")), "checkout fehlt")
class RealDatasetsIntegrationTests(unittest.TestCase):
    def test_real_nine_datasets(self):
        index = build_index(REAL_DIR)
        self.assertGreaterEqual(index["datasets_total"], 9)
        self.assertEqual(sum(index["by_verdict"].values()), index["datasets_total"])
        files = {item["file"] for item in index["datasets"]}
        self.assertIn("de-breg-stromsteuersenkung-2027.json", files)
        self.assertTrue(all(item["structure_id"] for item in index["datasets"]))

    def test_cli_real_dir_exit_zero(self):
        rc = main(["--dataset-dir", str(REAL_DIR)])
        self.assertEqual(rc, 0)

    def test_cli_missing_dir_exit_two(self):
        rc = main(["--dataset-dir", "/nonexistent/review/dir"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
