"""Evidence-Bridge-Tests (VIBE-LXXXVI, CLAIM 7085192096; Review-Fixes 7085274526):
Orchestrator-Nachweis, Fail-Closed (auch bei Runner-Ausfaellen), strenge
SHA-/Ref-Validierung, UNKNOWN-Semantik bis in den Tagesbericht (AMBER)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller import evidence_bridge as eb  # noqa: E402
from controller import daily_report as dr  # noqa: E402

SHA1 = "a" * 39 + "1"  # 40 Hex
SHA1B = "b" * 40
SHA1C = "c" * 40


def _ok_run(report_tuple):
    return lambda root: report_tuple


class ResolveHeadShaTest(unittest.TestCase):
    def test_reads_sha_from_plain_head_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (root / ".git" / "refs" / "heads").mkdir(parents=True)
            (root / ".git" / "refs" / "heads" / "main").write_text(SHA1 + "\n", encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), SHA1)

    def test_reads_detached_64hex_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("d" * 64 + "\n", encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), "d" * 64)

    def test_short_sha_is_rejected_not_guessed(self):
        # Fix 3: 6-Zeichen-SHA war frueher akzeptiert - jetzt None (UNKNOWN).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("abc123\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))

    def test_ref_with_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/../../etc/passwd\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))

    def test_packed_refs_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (root / ".git" / "packed-refs").write_text(
                "# pack-refs\n" + SHA1B + " refs/heads/main\n" + SHA1C + " refs/heads/other\n",
                encoding="utf-8")
            self.assertEqual(eb.resolve_head_sha(root), SHA1B)

    def test_packed_refs_short_sha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (root / ".git" / "packed-refs").write_text("111aaa refs/heads/main\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))

    def test_no_git_dir_is_unknown_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(eb.resolve_head_sha(Path(tmp)))

    def test_dangling_ref_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/missing\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))

    def test_worktree_commondir_is_explicit_unknown(self):
        # Fix 4: commondir ohne eigene belegbare refs bleibt UNKNOWN, kein Raten.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "main"
            wt = root / "wt"
            main.mkdir(); wt.mkdir()
            (main / ".git").mkdir()
            (wt / ".git").write_text("gitdir: " + str(main / ".git") + "/worktrees/wt\n", encoding="utf-8")
            wt_git = main / ".git" / "worktrees" / "wt"
            wt_git.mkdir(parents=True)
            (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
            (wt_git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(wt))

    def test_gitdir_file_missing_target_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").write_text("gitdir: /gibt/es/nicht\n", encoding="utf-8")
            self.assertIsNone(eb.resolve_head_sha(root))


class BuildSnapshotTest(unittest.TestCase):
    def _report(self, violations=None, exit_code=0, unknowns=None):
        return ({
            "violations": list(violations or []),
            "unknown_keys": list(unknowns if unknowns is not None else ["ci_state_of_latest_prs", "open_issue_count"]),
        }, exit_code)

    def test_fail_closed_on_runner_exception(self):
        def boom(_root):
            raise RuntimeError("Kaputt")
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=boom, head_resolver=lambda _r: SHA1)
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertEqual(snapshot["status"], "FAIL")
        self.assertIn("RUNNER_EXCEPTION", snapshot["reason"])
        self.assertIsNone(snapshot["check"])

    def test_fail_closed_on_none_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=lambda _r: None, head_resolver=lambda _r: SHA1)
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertIn("RUNNER_INVALID_RETURN", snapshot["reason"])

    def test_fail_closed_on_non_dict_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=lambda _r: ("x", 0), head_resolver=lambda _r: SHA1)
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertIn("RUNNER_INVALID_RETURN", snapshot["reason"])

    def test_fail_closed_on_bad_exit_code_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(
                tmp, runner=lambda _r: (self._report()[0], "0"), head_resolver=lambda _r: SHA1)
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertIn("exit_code", snapshot["reason"])

    def test_fail_closed_on_bad_violations_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = ({"violations": "kaputt", "unknown_keys": []}, 0)
            snapshot, exit_code = eb.build_snapshot(tmp, runner=lambda _x: r, head_resolver=lambda _r: SHA1)
        self.assertEqual(exit_code, eb.EXIT_FAIL)
        self.assertIn("violations", snapshot["reason"])

    def test_pass_without_unknowns_renders_green_teil_c(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(
                tmp, runner=_ok_run(self._report(unknowns=[])), head_resolver=lambda _r: SHA1)
        self.assertEqual(snapshot["status"], "PASS")
        self.assertEqual(exit_code, eb.EXIT_OK)
        daily = dr.assemble_daily_report({
            "report_id": "r1", "date": "2026-11-23", "repo_head_sha": SHA1,
            "checks": [snapshot["check"]],
        })
        self.assertEqual(daily["violations"], [])
        self.assertEqual(daily["teil_c_technical"]["ci_status"], "GREEN")

    def test_unknown_notes_never_green_only_amber(self):
        # Fix 1: UNKNOWN-Felder verschlucken kein GREEN; AMBER bleibt sichtbar.
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: SHA1)
        self.assertEqual(snapshot["status"], "PASS")
        self.assertEqual(exit_code, eb.EXIT_OK)
        daily = dr.assemble_daily_report({
            "report_id": "r2", "date": "2026-11-24", "repo_head_sha": SHA1,
            "checks": [snapshot["check"]],
        })
        self.assertEqual(daily["teil_c_technical"]["ci_status"], "AMBER")
        rendered = daily["teil_c_technical"]["checks"][0]
        self.assertEqual(rendered["unknown_notes"], ["ci_state_of_latest_prs", "open_issue_count"])

    def test_fail_keeps_violations_and_marks_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, exit_code = eb.build_snapshot(
                tmp,
                runner=_ok_run(self._report(violations=[{"rule": "REQUIRED_DOC_MISSING"}])),
                head_resolver=lambda _r: SHA1)
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
        daily = dr.assemble_daily_report({
            "report_id": "r3", "date": "2026-11-23", "repo_head_sha": SHA1,
            "checks": [],
        })
        self.assertEqual(daily["teil_c_technical"]["ci_status"], "UNKNOWN")

    def test_invalid_repo_root_is_input_error(self):
        snapshot, exit_code = eb.build_snapshot("/gibt/es/nicht/hier", runner=_ok_run(self._report()))
        self.assertEqual(exit_code, eb.EXIT_INPUT_ERROR)
        self.assertEqual(snapshot["status"], "FAIL")
        self.assertIn("INPUT_ERROR", snapshot["reason"])
        self.assertIsNone(snapshot["check"])

    def test_json_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot, _ = eb.build_snapshot(tmp, runner=_ok_run(self._report()), head_resolver=lambda _r: SHA1)
        parsed = json.loads(eb.export_snapshot_json(snapshot))
        self.assertEqual(parsed["task_id"], "VIBE-LXXXVI")
        self.assertEqual(parsed["check"]["head_sha"], SHA1)
        self.assertEqual(parsed["check"]["unknown_notes"], ["ci_state_of_latest_prs", "open_issue_count"])


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

    def test_scripted_integration_pending_labelled_honestly(self):
        # Fix 5: kein automatischer Betrieb behauptet: INTEGRATION_PENDING dokumentiert.
        doc = Path(eb.__file__).read_text(encoding="utf-8")[:2200]
        self.assertIn("INTEGRATION_PENDING", doc)
        self.assertIn("SCRIPTED != INSTALLED", doc)


class IntegrationTest(unittest.TestCase):
    def test_real_repo_root_real_agent(self):
        repo_root = Path(__file__).resolve().parents[1]
        if not (repo_root / ".git").exists():
            self.skipTest("kein Git-Checkout in dieser Umgebung (CI checkout hat .git)")
        snapshot, exit_code = eb.build_snapshot(str(repo_root))
        self.assertIn(snapshot["status"], ("PASS", "FAIL"))
        self.assertIsNotNone(snapshot["check"])
        self.assertTrue(eb._valid_sha(snapshot["check"]["head_sha"]))
        self.assertIn("repo_report_agent", snapshot["check"]["name"])


if __name__ == "__main__":
    unittest.main()
