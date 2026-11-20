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
    "ledger_anchor.py",
    "peer_sync.py", "real_metrics.py",
    "replay_db_unification.py", "replay_session.py", "replay_state_provider.py",
    "resource_admission.py", "resilience_mesh.py",
    "self_study_metrics.py", "signed_manifest.py", "state_monotonicity.py",
    "stewardship_report.py", "task_ingress_gate.py",
    "trusted_peer_registry.py", "use_policy.py", "v91_cli.py",
    "v91_listener.py", "witness_client.py",
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

    def test_migrated_modules_keep_their_original_module_docstrings(self):
        from controller import anomaly, chaos, collector, feedback

        self.assertIn("Anomaly Detector", anomaly.__doc__ or "")
        self.assertIn("Chaos Mode", chaos.__doc__ or "")
        self.assertIn("Real local measurements", collector.__doc__ or "")
        self.assertIn("Feedback Loop", feedback.__doc__ or "")

        # Flat imports follow the repo convention (see
        # tests/test_worker_observer.py): controller/ itself goes on sys.path
        # because worker/enforcement use flat in-package imports.
        controller_dir = Path(__file__).resolve().parents[1] / "controller"
        sys.path.insert(0, str(controller_dir))
        import enforcement  # noqa: E402
        import observer  # noqa: E402
        import worker  # noqa: E402

        self.assertIn("Stewardship Gate", enforcement.__doc__ or "")
        self.assertIn("Real local observer", observer.__doc__ or "")
        self.assertIn("Offline V91 task worker", worker.__doc__ or "")

        # Batch 3: ledger, controller, telemetry_server
        import importlib.util  # noqa: E402

        import ledger  # noqa: E402
        import telemetry_server  # noqa: E402
        # controller.py cannot be imported flat under the name "controller"
        # because the package is already in sys.modules (conftest preload);
        # load the file explicitly instead (flat convention, no shadowing).
        spec = importlib.util.spec_from_file_location(
            "v91_flat_controller_under_test", controller_dir / "controller.py")
        flat_controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flat_controller)

        self.assertIn("hash-chain ledger", ledger.__doc__ or "")
        self.assertIn("V91 Control Plane", flat_controller.__doc__ or "")
        self.assertIn("Read-only telemetry endpoint", telemetry_server.__doc__ or "")

        # Batch 4: model_gate, model_run_manifest, model_runner, emergency_stop, worm_ledger
        import emergency_stop as flat_stop  # noqa: E402
        import model_gate  # noqa: E402
        import model_run_manifest  # noqa: E402
        import model_runner  # noqa: E402
        import worm_ledger  # noqa: E402

        assert "availability/safety gate" in (model_gate.__doc__ or "")
        assert "replay comparison" in (model_run_manifest.__doc__ or "")
        assert "model runner" in (model_runner.__doc__ or "")
        assert "emergency stop" in (flat_stop.__doc__ or "")
        assert "resource-flow ledger" in (worm_ledger.__doc__ or "")

        # Batch 5: runtime_control, encrypted_store, legacy_gate, lease_lock, impact
        import encrypted_store  # noqa: E402
        import impact  # noqa: E402
        import lease_lock  # noqa: E402
        import legacy_gate  # noqa: E402
        import runtime_control  # noqa: E402

        assert "bounded Docker Compose controller" in (runtime_control.__doc__ or "")
        assert "peer object storage" in (encrypted_store.__doc__ or "")
        assert "legacy transformation release gate" in (legacy_gate.__doc__ or "")
        assert "Expiring lease locks" in (lease_lock.__doc__ or "")
        assert "Impact measurement from REAL measurements" in (impact.__doc__ or "")

        # Batch 6: autarky_metrics, autarky_report, crypto_receipts,
        # measurement_core, peer_store. These modules use controller.*-imports
        # internally, so they are loaded via the (conftest-preloaded) package
        # instead of flat imports (see conftest.py shadowing note).
        from controller import (  # noqa: E402
            autarky_metrics, autarky_report, crypto_receipts,
            measurement_core, peer_store,
        )

        assert "Local autarky and resilience metrics" in (autarky_metrics.__doc__ or "")
        assert "Autarky report wiring" in (autarky_report.__doc__ or "")
        assert "Ed25519-signed receipts" in (crypto_receipts.__doc__ or "")
        assert "read-only measurement core" in (measurement_core.__doc__ or "")
        assert "content-addressed peer object storage" in (peer_store.__doc__ or "")


if __name__ == "__main__":
    unittest.main()
