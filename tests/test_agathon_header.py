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
    "v91_cli.py",
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

        # Batch 7: real_metrics, peer_sync, ledger_anchor, self_study_metrics,
        # replay_session. Loaded via the conftest-preloaded package:
        # ledger_anchor needs the cryptography runtime dependency (CI), and
        # replay_session uses controller.*-imports internally.
        from controller import (  # noqa: E402
            ledger_anchor, peer_sync, real_metrics, replay_session,
            self_study_metrics,
        )

        assert "Read-only host telemetry" in (real_metrics.__doc__ or "")
        assert "Local, transport-independent peer heartbeat validation" in (peer_sync.__doc__ or "")
        assert "Offline, signed ledger checkpoints" in (ledger_anchor.__doc__ or "")
        assert "Fail-closed efficiency measurements" in (self_study_metrics.__doc__ or "")
        assert "Two-node independent replay verification" in (replay_session.__doc__ or "")

        # Batch 8: replay_db_unification, replay_state_provider,
        # resource_admission, resilience_mesh, signed_manifest. Package
        # imports: replay_db_unification uses controller.task_ingress_gate;
        # signed_manifest uses controller.crypto_receipts (cryptography is a
        # CI/runtime dependency); resilience_mesh keeps its shebang, the
        # header lives inside its single module docstring.
        from controller import (  # noqa: E402
            replay_db_unification, replay_state_provider,
            resource_admission, resilience_mesh, signed_manifest,
        )

        assert "Transactional migration and fail-closed ingress composition" in (replay_db_unification.__doc__ or "")
        assert "Transactional SQLite provider for monotonic replay-state snapshots" in (replay_state_provider.__doc__ or "")
        assert "Local resource measurement and deterministic, bounded admission" in (resource_admission.__doc__ or "")
        assert "Local resilience mesh: peer register + restart verification" in (resilience_mesh.__doc__ or "")
        assert "Signed capability manifests: validation, Ed25519 signing, freshness, revocation" in (signed_manifest.__doc__ or "")

        # Batch 9: state_monotonicity, stewardship_report, task_ingress_gate,
        # trusted_peer_registry, use_policy. stewardship_report uses the flat
        # in-package import style ('from ledger import ...'), so it is loaded
        # flat from the controller directory already on sys.path above;
        # state_monotonicity needs the cryptography runtime dependency (CI).
        from controller import (  # noqa: E402
            state_monotonicity, task_ingress_gate,
            trusted_peer_registry, use_policy,
        )
        import stewardship_report as flat_stewardship  # noqa: E402

        assert "Verify externally signed monotonic replay-store checkpoints" in (state_monotonicity.__doc__ or "")
        assert "Summaries for stewardship decision ledgers" in (flat_stewardship.__doc__ or "")
        assert "Authenticated, fail-closed task-ingress decision primitive" in (task_ingress_gate.__doc__ or "")
        assert "Fail-closed lookup for independently provisioned V91 peer public keys" in (trusted_peer_registry.__doc__ or "")
        assert "Conservative, deterministic V91 use-domain policy classification" in (use_policy.__doc__ or "")


if __name__ == "__main__":
    unittest.main()
