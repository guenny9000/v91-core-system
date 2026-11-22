"""Evidence-Bridge-Tests (VIBE-LXXXVI): Orchestrator-Nachweis, Fail-Closed, Teil-C-Kompatibilitaet."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import evidence_bridge as eb  # noqa: E402
from controller import daily_report as dr  # noqa: E402


def _ok_run(report_tuple):
    return lambda root: report_tuple


class ResolveHeadShaTest(unittest.TestCase):
    def test_reads_sha_from_plain_head_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (root / ".git" / "refs" / "heads").mkdir(parents=True)
            (root / ".git" / "refs" / "heads" / "main").write_text("abc123\n", encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), "abc123")

    def test_reads_detached_sha_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("deadbeef\n", encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), "deadbeef")

    def test_packed_refs_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (root / ".git" / "packed-refs").write_text(
                "# pack-refs\n111aaa refs/heads/main\n222bbb refs/heads/other\n", encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), "111aaa")

    def test_no_git_dir_is_unknown_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(eb.resolve_head_sha(Path(tmp)))

    def test_dangling_ref_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/missing\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))


class BuildSnapshotTest(unittest.TestCase):
    def _report(self, violations=None, exit_code=0):
        return ({
            "violations": list(violations or []),
            "unknown_keys": ["ci_state_of_latest_prs", "open_issue_count"],
        }, exit_code)

    def test_pass_check_is_daily_report_teil_c_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: "cafe1234")
        self.assertEqual(snapshot["status"], "PASS")
        self.assertEqual(exit_code, eb.EXIT_OK)
        check = snapshot["check"]
        self.assertEqual(check["head_sha"], "cafe1234")
        self.assertEqual(check["conclusion"], "success")
        # End-to-End gegen den ECHTEN daily_report-Vertrag:
        daily = dr.assemble_daily_report({
            "report_id": "r1",
            "date": "2026-11-23",
            "repo_head_sha": "cafe1234",
            "checks": [check],
        })
        self.assertEqual(daily["violations"], [])
        self.assertEqual(daily["teil_c_technical"]["ci_status"], "GREEN")
        self.assertFalse(daily["teil_c_technical"]["checks"][0]["stale_head"])

    def test_fail_keeps_violations_and_marks_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(
                tmp,
                runner=_ok_run(self._report(violations=[{"rule": "REQUIRED_DOC_MISSING"}])),
                head_resolver=lambda _r: "cafe1234")
        self.assertEqual(snapshot["status"], "FAIL")
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertEqual(snapshot["check"]["conclusion"], "failure")
        self.assertEqual(snapshot["check"]["violations"][0]["rule"], "REQUIRED_DOC_MISSING")

    def test_no_head_sha_means_unknown_no_fabricated_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: None)
        self.assertEqual(snapshot["status"], "UNKNOWN")
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertIsNone(snapshot["check"])
        self.assertIsNone(snapshot["head_sha"])
        self.assertIn("repo_head_sha", snapshot["unknown_keys"])
        # Teil C wuerde ohne checks ehrlich UNKNOWN bleiben:
        daily = dr.assemble_daily_report({
            "report_id": "r2", "date": "2026-11-23", "repo_head_sha": "x1",
            "checks": [],
        })
        self.assertEqual(daily["teil_c_technical"]["ci_status"], "UNKNOWN")

    def test_invalid_repo_root_is_input_error(self):
        snapshot, exit_code = eb.build_snapshot("/gibt/es/nicht/hier", runner=_ok_run(self._report()))
        self.assertEqual(exit_code, eb.EXIT_INPUT_ERROR)
        self.assertEqual(snapshot["status"], "FAIL")
        self.assertIn("INPUT_ERROR", snapshot["reason"])
        self.assertIsNone(snapshot["check"])

    def test_unknown_keys_pass_through_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, _ = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: "h1")
        self.assertEqual(snapshot["unknown_keys"], ["ci_state_of_latest_prs", "open_issue_count"])

    def test_json_export_roundtrip(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, _ = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: "h2")
        text = eb.export_snapshot_json(snapshot)
        parsed = json.loads(text)
        self.assertEqual(parsed["task_id"], "VIBE-LXXXVI")
        self.assertEqual(parsed["check"]["head_sha"], "h2")


class OrchestratorTest(unittest.TestCase):
    def test_bridge_does_not_reimplement_but_delegates(self):
        self.assertNotEqual(eb._default_runner(), None)
        runner = eb._default_runner()
        self.assertTrue(hasattr(runner, "__call__"))
        self.assertEqual(
            sys.modules["controller.repo_report_agent"].build_report, runner,
            "Bridge muss den ECHTEN repo_report_agent aufrufen, nicht kopieren")

    def test_no_lint_logik_in_bridge(self):
        src = Path(eb.__file__).read_text(encoding="utf-8")
        for forbidden in ("index_lint", "lint_errors"):
            self.assertNotIn(forbidden, src,
                             "Bridge enthaelt Prueflogik-Reste (%s) - NO_DUPLICATE_SYSTEMS verletzt" % forbidden)
        self.assertNotIn("violations.append", src)


class IntegrationTest(unittest.TestCase):
    def test_real_repo_root_real_agent(self):
        repo_root = Path(__file__).resolve().parents[1]
        if not (repo_root / ".git").exists():
            self.skipTest("kein Git-Checkout in dieser Umgebung (CI checkout hat .git)")
        snapshot, exit_code = eb.build_snapshot(str(repo_root))
        self.assertIn(snapshot["status"], ("PASS", "FAIL"))
        self.assertIsNotNone(snapshot["check"])
        self.assertTrue(snapshot["check"]["head_sha"])
        self.assertIn("repo_report_agent", snapshot["check"]["name"])


if __name__ == "__main__":
    unittest.main()
