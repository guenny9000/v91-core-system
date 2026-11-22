"""Tests fuer scripts/v91_tagesbericht.py (VIBE-LXXXVII, CLAIM 7085425998):
Erstaufruf-Verkabelung auf der ECHTEN Modulkette evidence_bridge -> daily_report."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "v91_tagesbericht", REPO_ROOT / "scripts" / "v91_tagesbericht.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # noqa: E402

from controller import evidence_bridge as eb  # noqa: E402


def _real_agent_run(root):
    return eb._default_runner()(str(root))


def _fake_run_factory(fake_root):
    def run(_root):
        my_root = Path(fake_root)
        return eb._default_runner()(str(my_root))
    return run


SHA1 = "e" * 40
SHA1B = "f" * 40


class BuildTagesberichtTest(unittest.TestCase):
    def _mk_git_tmp(self, with_head=True):
        tmp = tempfile.mkdtemp()
        root = Path(tmp) / "repo"
        root.mkdir()
        if with_head:
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text(SHA1 + "\n", encoding="utf-8")
        return root

    def test_assembled_report_has_real_teil_c_and_never_green_with_unknowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, unknown, exit_code = _mod.build_tagesbericht(
                tmp, runner=_real_agent_run, head_resolver=lambda _r: SHA1)
            # echter Agent auf leeres Verzeichnis -> Pflichtdoks fehlen -> FAIL/RED ehrlich
            self.assertEqual(unknown, [])
            self.assertTrue(report["teil_c_technical"]["checks"],
                            "Teil C muss den echten Bridge-Check tragen")
            self.assertIn(report["teil_c_technical"]["ci_status"], ("AMBER", "RED"))
            self.assertEqual(report["teil_c_technical"]["ci_status"], "RED")
            self.assertIn(exit_code, (_mod.EXIT_OK, _mod.EXIT_FAIL))

    def test_passing_check_yields_amber_not_green(self):
        good = {"violations": [], "unknown_keys": ["x"]}, 0

        def runner(_root):
            return good
        with tempfile.TemporaryDirectory() as tmp:
            report, _, exit_code = _mod.build_tagesbericht(
                tmp, runner=runner, head_resolver=lambda _r: SHA1B)
        self.assertEqual(report["teil_c_technical"]["ci_status"], "AMBER")
        self.assertIn("SKRIPT != BETRIEB", report["generated_by"])
        self.assertIn(exit_code, (_mod.EXIT_OK, _mod.EXIT_FAIL))

    def test_no_head_sha_is_honest_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, _, exit_code = _mod.build_tagesbericht(
                tmp, runner=_real_agent_run, head_resolver=lambda _r: None)
        self.assertEqual(report["teil_c_technical"]["checks"], [])
        self.assertEqual(report["teil_c_technical"]["ci_status"], "UNKNOWN")
        self.assertEqual(exit_code, _mod.EXIT_FAIL)

    def test_entries_rejection_is_visible_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, _, _ = _mod.build_tagesbericht(
                tmp,
                entries={
                    "global_entries": [{"claim": "x"}],
                    "_unknown_top_keys": ["fantasie_key"],
                },
                runner=_real_agent_run, head_resolver=lambda _r: SHA1)
        self.assertTrue(any("teil_a:entry_rejected_no_claim_source_date" in v for v in report["violations"]),
                        "ungueltiger Teil-A-Eintrag muss visible rejected werden: " + str(report["violations"]))
        self.assertTrue(any("entries:unknown_top_key:fantasie_key" in v for v in report["violations"]))

    def test_generated_by_labels_script_not_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, _, _ = _mod.build_tagesbericht(
                tmp, runner=_real_agent_run, head_resolver=lambda _r: SHA1)
        self.assertIn("SKRIPT != BETRIEB", report["generated_by"])


class CliTest(unittest.TestCase):
    def test_main_rejects_out_inside_repo(self):
        exit_code = _mod.main([
            "--repo-root", str(REPO_ROOT), "--out", str(REPO_ROOT / "bericht.json")])
        self.assertEqual(exit_code, _mod.EXIT_INPUT_ERROR)
        self.assertFalse((REPO_ROOT / "bericht.json").exists(),
                         "Laufzeit-Artefakt darf NIE ins Repo geschrieben werden")

    def test_main_writes_report_only_to_explicit_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "bericht.json"
            exit_code = _mod.main(["--repo-root", str(tmp), "--out", str(out)])
            self.assertIn(exit_code, (_mod.EXIT_OK, _mod.EXIT_FAIL, _mod.EXIT_INPUT_ERROR))
            if out.exists():
                parsed = json.loads(out.read_text(encoding="utf-8"))
                self.assertIn("teil_c_technical", parsed)

    def test_main_bad_entries_json_is_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{kein gueltiges json", encoding="utf-8")
            exit_code = _mod.main(["--repo-root", str(tmp), "--entries", str(bad)])
        self.assertEqual(exit_code, _mod.EXIT_INPUT_ERROR)

    def test_main_missing_repo_root_is_input_error(self):
        exit_code = _mod.main(["--repo-root", "/gibt/es/nicht"])
        self.assertEqual(exit_code, _mod.EXIT_INPUT_ERROR)


class IntegrationTest(unittest.TestCase):
    def test_real_repo_checkout_real_chain(self):
        if not (REPO_ROOT / ".git").exists():
            self.skipTest("kein Git-Checkout in dieser Umgebung (CI checkout hat .git)")
        report, _, exit_code = _mod.build_tagesbericht(str(REPO_ROOT))
        self.assertTrue(report["teil_c_technical"]["checks"])
        self.assertIn(report["teil_c_technical"]["ci_status"], ("AMBER", "RED"))
        self.assertTrue(report["teil_c_technical"]["repo_head_sha"])
        self.assertIn(exit_code, (_mod.EXIT_OK, _mod.EXIT_FAIL))


if __name__ == "__main__":
    unittest.main()
