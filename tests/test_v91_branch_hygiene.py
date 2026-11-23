#!/usr/bin/env python3
"""Tests fuer scripts/v91_branch_hygiene.py (VIBE-LXXXCI, CLAIM 7088648269):
Read-only Loeschplan fuer gemergte Branches. PLAN != LOESCHUNG."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "v91_branch_hygiene", REPO_ROOT / "scripts" / "v91_branch_hygiene.py")
bh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bh)  # noqa: E402


def git_available():
    return shutil.which("git") is not None


class PureCoreTests(unittest.TestCase):
    """Dieser Kern braucht KEIN git (Umgebung != Fehler, ENV != FAIL)."""

    def test_parse_typical_merged_output(self):
        out = "  feat/eins\n* main\n  docs/zwei\n"
        self.assertEqual(bh.parse_branch_list(out, base="main"),
                         ["feat/eins", "docs/zwei"])

    def test_parse_skips_base_and_empty_lines(self):
        out = "  main\n\n   \n  feat/x\n"
        self.assertEqual(bh.parse_branch_list(out, base="main"), ["feat/x"])

    def test_parse_rejects_invalid_names_fail_closed(self):
        with self.assertRaises(bh.BranchHygieneError):
            bh.parse_branch_list("  okay\n  ..evil\n", base="main")

    def test_validate_branch_name_rules(self):
        self.assertTrue(bh.validate_branch_name("feat/a-v1.2_x"))
        self.assertFalse(bh.validate_branch_name("a..b"))
        self.assertFalse(bh.validate_branch_name("../escape"))
        self.assertFalse(bh.validate_branch_name("-injected"))
        self.assertFalse(bh.validate_branch_name("spa ce"))
        self.assertFalse(bh.validate_branch_name("ends/"))
        self.assertFalse(bh.validate_branch_name("x.lock"))
        self.assertFalse(bh.validate_branch_name(None))
        self.assertFalse(bh.validate_branch_name(""))
        self.assertTrue(bh.validate_branch_name("docs/index-nachtrag-vibe-lxxxvi"))

    def test_build_plan_yields_operator_commands_only(self):
        plan = bh.build_plan(["feat/a", "docs/b"])
        self.assertFalse(plan["executed"])
        self.assertEqual([c["branch"] for c in plan["operator_commands"]],
                         ["feat/a", "docs/b"])
        for cmd in plan["operator_commands"]:
            self.assertEqual(cmd["local_delete"], "git branch -d " + cmd["branch"])
            self.assertTrue(cmd["remote_delete_suggestion"].startswith("git push origin --delete "))
            self.assertNotIn(" -D ", cmd["local_delete"])
        self.assertIn("PLAN != LOESCHUNG", plan["honest_notes"][0])

    def test_build_plan_rejects_invalid_input(self):
        with self.assertRaises(bh.BranchHygieneError):
            bh.build_plan(["x..y"])
        with self.assertRaises(bh.BranchHygieneError):
            bh.build_plan("notalist")
        with self.assertRaises(bh.BranchHygieneError):
            bh.build_plan(["ok"], remote_name="evil/../remote")
        with self.assertRaises(bh.BranchHygieneError):
            bh.build_plan(["ok"], remote_name="has/slash")

    def test_build_plan_empty(self):
        plan = bh.build_plan([])
        self.assertEqual(plan["operator_commands"], [])
        self.assertEqual(plan["merged_local_branches"], [])
        self.assertFalse(plan["executed"])

    def test_render_plan_names_every_branch(self):
        plan = bh.build_plan(["feat/one"])
        text = bh.render_plan(plan)
        self.assertIn("feat/one", text)
        self.assertIn("PLAN != LOESCHUNG", text)
        self.assertIn("git branch -d feat/one", text)
        self.assertIn("git push origin --delete feat/one", text)

    def test_render_plan_empty_honest(self):
        text = bh.render_plan(bh.build_plan([]))
        self.assertIn("KEINE lokal", text)
        self.assertIn("UNKNOWN", " ".join(bh.HONEST_NOTES))

    def test_run_git_rejects_mutating_command(self):
        with self.assertRaises(bh.BranchHygieneError) as ctx:
            bh._run_git(["push", "origin", "--delete", "x"], ".")
        self.assertIn("not allowed", str(ctx.exception))

    def test_honest_notes_complete(self):
        joined = " ".join(bh.HONEST_NOTES)
        self.assertIn("PLAN != LOESCHUNG", joined)
        self.assertIn("REMOTE_STATE_UNKNOWN", joined)
        self.assertIn("MERGED_LOCAL != MERGED_REMOTE", joined)


def _make_repo(tmp, base="main", merged=None, unmerged=None, same_time=None):
    """Baut ein ECHTES lokales git-Repo (Nur Tests; erfordert git)."""
    root = Path(tmp) / "repo"
    root.mkdir()
    def g(*args):
        subprocess.run(["git", *args], cwd=str(root), check=True,
                       capture_output=True, text=True)
    g("init", "-b", base)
    g("config", "user.email", "test@example.invalid")
    g("config", "user.name", "V91 Test")
    (root / "f.txt").write_text("one\n", encoding="utf-8")
    g("add", "f.txt"); g("commit", "-m", "init commit")
    for name in list(merged or []) + list(same_time or []):
        g("checkout", "-b", name)
        (root / (name.replace("/", "_") + ".txt")).write_text(name, encoding="utf-8")
        g("add", "."); g("commit", "-m", "work " + name)
        g("checkout", base)
        if name in (merged or []):
            g("merge", "--ff-only", name)
    for name in unmerged or []:
        g("checkout", "-b", name)
        (root / (name.replace("/", "_") + ".txt")).write_text(name, encoding="utf-8")
        g("add", "."); g("commit", "-m", "unmerged " + name)
        g("checkout", base)
    return root


@unittest.skipUnless(git_available(), "git in dieser Umgebung nicht verfuegbar (ENV != FAIL)")
class GitRepoTests(unittest.TestCase):
    def test_merged_only_and_base_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, merged=["feat/done"], unmerged=["feat/wip"])
            merged = bh.list_merged_branches(root)
            self.assertIn("feat/done", merged)
            self.assertNotIn("feat/wip", merged)
            self.assertNotIn("main", merged)

    def test_is_git_repo_true_and_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp)
            self.assertTrue(bh.is_git_repo(root))
            plain = Path(tmp) / "plain"
            plain.mkdir()
            (plain / "x.txt").write_text("x", encoding="utf-8")
            self.assertFalse(bh.is_git_repo(plain))

    def test_list_merged_fail_closed_on_non_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain"
            plain.mkdir()
            with self.assertRaises(bh.BranchHygieneError):
                bh.list_merged_branches(plain)

    def test_list_merged_invalid_base_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp)
            with self.assertRaises(bh.BranchHygieneError):
                bh.list_merged_branches(root, base="..evil")

    def test_main_cli_exit_ok_and_json_out_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp, merged=["feat/gone"])
            out = Path(tmp) / "plan.json"
            code = bh.main(["--repo-root", str(root), "--json-out", str(out)])
            self.assertEqual(code, bh.EXIT_OK)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["merged_local_branches"], ["feat/gone"])
            self.assertFalse(data["executed"])

    def test_main_cli_input_error_without_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain"
            plain.mkdir()
            code = bh.main(["--repo-root", str(plain)])
            self.assertEqual(code, bh.EXIT_INPUT_ERROR)

    def test_main_cli_rejects_json_out_inside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_repo(tmp)
            code = bh.main(["--repo-root", str(root), "--json-out", str(root / "plan.json")])
            self.assertEqual(code, bh.EXIT_INPUT_ERROR)
            self.assertFalse((root / "plan.json").exists())


if __name__ == "__main__":
    unittest.main()
