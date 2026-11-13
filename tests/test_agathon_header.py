"""Agathon system-header policy: every new controller/ module carries the header.

Die LEGACY_EXEMPTIONS-Liste darf nur schrumpfen, nie wachsen:
jeder neue Eintrag ist ein Review-Stopper.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REQUIRED_HEADER_LINES = (
    "V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)",
    "STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)",
    "AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.",
)

LEGACY_EXEMPTIONS = frozenset({
    "__init__.py",
    "autarky_metrics.py", "autarky_report.py",
    "controller.py", "crypto_receipts.py", "emergency_stop.py",
    "encrypted_store.py", "enforcement.py", "impact.py",
    "lease_lock.py", "ledger.py", "ledger_anchor.py", "legacy_gate.py",
    "measurement_core.py", "model_gate.py",
    "model_run_manifest.py", "model_runner.py", "observer.py",
    "peer_store.py", "peer_sync.py", "real_metrics.py",
    "replay_db_unification.py", "replay_session.py", "replay_state_provider.py",
    "resource_admission.py", "resilience_mesh.py", "runtime_control.py",
    "self_study_metrics.py", "signed_manifest.py", "state_monotonicity.py",
    "stewardship_report.py", "task_ingress_gate.py", "telemetry_server.py",
    "trusted_peer_registry.py", "use_policy.py", "v91_cli.py",
    "v91_listener.py", "witness_client.py", "worker.py", "worm_ledger.py",
})


def find_missing_headers(directory: Path, exemptions=frozenset()) -> list[str]:
    missing = []
    for file_path in sorted(directory.glob("*.py")):
        if file_path.name in exemptions:
            continue
        content = file_path.read_text(encoding="utf-8")
        head = "\n".join(content.splitlines()[:15])
        if not all(line in head for line in REQUIRED_HEADER_LINES):
            missing.append(file_path.name)
    return missing


class AgathonHeaderPolicyTest(unittest.TestCase):
    def test_repository_modules_comply(self):
        controller_dir = Path(__file__).resolve().parents[1] / "controller"
        self.assertTrue(controller_dir.exists(), "Verzeichnis controller/ nicht gefunden.")
        missing = find_missing_headers(controller_dir, LEGACY_EXEMPTIONS)
        self.assertEqual(missing, [],
                         f"Neue Module ohne V91-System-Header: {missing}")

    def test_template_module_carries_header(self):
        template = Path(__file__).resolve().parents[1] / "controller" / "template_module.py"
        self.assertTrue(template.exists(), "controller/template_module.py fehlt.")
        head = "\n".join(template.read_text(encoding="utf-8").splitlines()[:15])
        for line in REQUIRED_HEADER_LINES:
            self.assertIn(line, head)

    def test_new_module_without_header_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad_module.py"
            bad.write_text("import os\n", encoding="utf-8")
            self.assertEqual(find_missing_headers(Path(tmp)), ["bad_module.py"])

    def test_new_module_with_header_passes(self):
        header = "\n".join([
            '"""',
            *REQUIRED_HEADER_LINES,
            '---------------------------------------------------------------------',
            '"""',
            "import os",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good_module.py"
            good.write_text(header + "\n", encoding="utf-8")
            self.assertEqual(find_missing_headers(Path(tmp)), [])

    def test_header_must_be_in_the_first_lines(self):
        filler = "\n".join(f"# filler line {i} to push the header past the window" for i in range(20))
        header_late = filler + "\n\n" + "\n".join([
            '"""',
            *REQUIRED_HEADER_LINES,
            '"""',
        ])
        with tempfile.TemporaryDirectory() as tmp:
            late = Path(tmp) / "late_header.py"
            late.write_text(header_late + "\n", encoding="utf-8")
            self.assertEqual(find_missing_headers(Path(tmp)), ["late_header.py"])


if __name__ == "__main__":
    unittest.main()
