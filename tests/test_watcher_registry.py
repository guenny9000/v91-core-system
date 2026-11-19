"""
Tests fuer controller/watcher_registry: die 11 Direktiv-Rollen,
Existenzpruefung gegen den echten Dateibestand, fail-closed,
ehrliche VISION-Kennzeichnung fuer Rollen ohne Bausteine und
ehrliche PARTIAL-Kennzeichnung fuer Rollen mit fehlenden Modulen.
"""
import json
import tempfile
import unittest
from pathlib import Path

from controller.watcher_registry import (
    WATCHER_ROLES,
    WatcherRole,
    WatcherRegistryError,
    build_report,
    get_role,
    main as registry_main,
    probe_role,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class WatcherRegistryTests(unittest.TestCase):

    def test_exactly_eleven_roles_with_unique_ids(self):
        roles = [r.role_id for r in WATCHER_ROLES]
        self.assertEqual(11, len(roles))
        self.assertEqual(11, len(set(roles)))

    def test_every_role_has_description(self):
        for role in WATCHER_ROLES:
            self.assertTrue(role.description.strip(), role.role_id)

    def test_implemented_roles_reference_existing_files(self):
        for role in WATCHER_ROLES:
            for rel in role.module_files:
                self.assertTrue(
                    (REPO_ROOT / rel).is_file(),
                    f"referenced module missing: {rel} (role {role.role_id})",
                )

    def test_all_leben_roles_now_have_files(self):
        report = build_report(REPO_ROOT)
        self.assertEqual([], report["roles_unimplemented"])
        self.assertEqual([], report["roles_partial"])
        self.assertEqual("ALL_ROLES_HAVE_FILES_PRESENT", report["overall"])

    def test_sicherheitswaechter_is_implemented_against_repo(self):
        report = probe_role(get_role("sicherheitswaechter"), REPO_ROOT)
        self.assertEqual("IMPLEMENTED_FILES_PRESENT", report["capability"])
        self.assertGreater(len(report["modules_present"]), 0)
        self.assertEqual([], report["modules_missing"])

    def test_wissenschafts_role_now_implemented(self):
        report = probe_role(get_role("wissenschafts_und_forschungsbeobachtung"), REPO_ROOT)
        self.assertEqual("IMPLEMENTED_FILES_PRESENT", report["capability"])
        self.assertIn("controller/research_watch.py", report["modules_present"])

    def test_empty_role_reports_vision(self):
        empty = WatcherRole(role_id="zukunftsvision", description="noch nicht gebaut", module_files=())
        report = probe_role(empty, REPO_ROOT)
        self.assertEqual("VISION_UNIMPLEMENTED", report["capability"])
        self.assertIn("VISION", report["honest_note"])

    def test_partial_role_lists_missing_files(self):
        role = get_role("infrastruktur_und_ausfallschutz")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in role.module_files:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# stub\n", encoding="utf-8")
            (root / role.module_files[0]).unlink()
            report = probe_role(role, root)
            self.assertIn(role.module_files[0], report["modules_missing"])
            self.assertEqual("IMPLEMENTATION_PARTIAL", report["capability"])
            self.assertIn("Teilweise vorhanden", report["honest_note"])

    def test_partial_report_lists_partial_role(self):
        role = get_role("infrastruktur_und_ausfallschutz")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in role.module_files:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# stub\n", encoding="utf-8")
            (root / role.module_files[0]).unlink()
            report = build_report(root)
            self.assertIn(role.role_id, report["roles_partial"])
            self.assertEqual("PARTIAL_ROLES_INCOMPLETE", report["overall"])

    def test_unknown_role_fails_closed(self):
        with self.assertRaises(WatcherRegistryError):
            get_role("gibts_nicht")

    def test_non_path_root_fails_closed(self):
        with self.assertRaises(WatcherRegistryError):
            probe_role(get_role("sicherheitswaechter"), "kein-pfad")

    def test_report_honest_limits_persist(self):
        report = build_report(REPO_ROOT)
        self.assertEqual(11, report["roles_total"])
        self.assertTrue(len(report["honest_limits"]) >= 3)

    def test_report_json_serializable(self):
        report = build_report(REPO_ROOT)
        text = json.dumps(report, ensure_ascii=False, sort_keys=True)
        parsed = json.loads(text)
        self.assertEqual(11, parsed["roles_total"])

    def test_cli_exit_zero_on_repo_root(self):
        self.assertEqual(0, registry_main(["--repo-root", str(REPO_ROOT)]))

    def test_cli_single_role(self):
        self.assertEqual(0, registry_main(["--repo-root", str(REPO_ROOT), "--role", "fakten_und_quellenpruefung"]))

    def test_cli_unknown_role_raises(self):
        with self.assertRaises(WatcherRegistryError):
            registry_main(["--repo-root", str(REPO_ROOT), "--role", "gibts_nicht"])


if __name__ == "__main__":
    unittest.main()
