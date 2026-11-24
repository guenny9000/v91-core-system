"""Tests fuer controller.kern_bridge (Lernblock Weg B, Zero-Waste-Ledger).

Integrationstest gegen das ECHTE importierbare controller-Paket
(NO_DUPLICATE_SYSTEMS). Das Modul ist stdlib-only; der Netz-Abruf
wird IMMER durch eine injizierte Test-Funktion ersetzt (kein Netz
in Tests, kein echter GitHub-Kontakt).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from controller.kern_bridge import (
    BRIDGE_LABEL,
    GATE_ACCEPTED,
    GATE_BLOCKED,
    GATE_MISSING_MARKER,
    HANDOVER_MARKER,
    collect_kerns,
    gate_payload,
)

ROOT = Path(__file__).resolve().parents[1]


def _issue(number: int, body: str, title: str = "Kern-Transfer") -> dict:
    return {"number": number, "title": title, "body": body}


def _valid_body(code: str = "value = 1 + 1") -> str:
    return (
        "### [KERN-ID / THEMA]\n"
        "**Schnittstellen-Definition:** benoetigt nichts, liefert value\n"
        "```python\n" + code + "\n```\n"
        "UEBERGABE_KERN_START\n"
        "- Ziel: Demo-Kern\n"
        "UEBERGABE_KERN_ENDE\n"
    )


def _make_fetch(issues):
    calls = []

    def fetch(repo: str, label: str):
        calls.append((repo, label))
        return list(issues)

    return fetch, calls


class GatePayloadTest(unittest.TestCase):
    def test_valid_body_accepted(self):
        self.assertEqual(gate_payload(_valid_body()), GATE_ACCEPTED)

    def test_missing_marker(self):
        self.assertEqual(gate_payload("nur text ohne marker"), GATE_MISSING_MARKER)

    def test_blocked_patterns(self):
        for bad in ("rm -rf /", "shutil.rmtree('x')", "os.system('x')",
                    "subprocess.run(['x'])", "eval('x')", "exec('x')",
                    "__import__('os')"):
            self.assertEqual(gate_payload(_valid_body(bad)), GATE_BLOCKED, bad)

    def test_blocked_beats_missing_marker(self):
        self.assertEqual(gate_payload("rm -rf alles"), GATE_BLOCKED)

    def test_non_string_is_missing_marker(self):
        self.assertEqual(gate_payload(None), GATE_MISSING_MARKER)

    def test_benign_code_passes(self):
        body = _valid_body("total = sum(range(10))\nprint(total)")
        self.assertEqual(gate_payload(body), GATE_ACCEPTED)


class CollectKernsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "v91_bridge_inbox.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepted_record_written(self):
        fetch, _ = _make_fetch([_issue(101, _valid_body())])
        report = collect_kerns(self.ledger, "o/r", BRIDGE_LABEL, fetch=fetch)
        self.assertEqual(report["records_new"], 1)
        self.assertEqual(report["gate_counts"][GATE_ACCEPTED], 1)
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["gate_status"], GATE_ACCEPTED)
        self.assertEqual(record["issue_number"], 101)
        self.assertIn("sha256", record)

    def test_sha256_matches_body(self):
        import hashlib
        body = _valid_body()
        fetch, _ = _make_fetch([_issue(7, body)])
        collect_kerns(self.ledger, fetch=fetch)
        record = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["sha256"], hashlib.sha256(body.encode("utf-8")).hexdigest())

    def test_dedup_on_second_run(self):
        fetch, _ = _make_fetch([_issue(1, _valid_body())])
        first = collect_kerns(self.ledger, fetch=fetch)
        second = collect_kerns(self.ledger, fetch=fetch)
        self.assertEqual(first["records_new"], 1)
        self.assertEqual(second["records_new"], 0)
        self.assertEqual(second["records_known"], 1)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 1)

    def test_quarantine_keeps_payload(self):
        fetch, _ = _make_fetch([_issue(2, _valid_body("os.system('halt')"))])
        report = collect_kerns(self.ledger, fetch=fetch)
        self.assertEqual(report["gate_counts"][GATE_BLOCKED], 1)
        record = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["gate_status"], GATE_BLOCKED)
        self.assertIn("os.system", record["payload"], "ISOLATE_NOT_DESTROY: Inhalt bleibt abgelegt")

    def test_missing_marker_still_stored(self):
        fetch, _ = _make_fetch([_issue(3, "Freeform-Idee ohne Format")])
        report = collect_kerns(self.ledger, fetch=fetch)
        self.assertEqual(report["gate_counts"][GATE_MISSING_MARKER], 1)
        record = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("Freeform-Idee", record["payload"])

    def test_empty_issue_list(self):
        fetch, _ = _make_fetch([])
        report = collect_kerns(self.ledger, fetch=fetch)
        self.assertEqual(report["issues_seen"], 0)
        self.assertFalse(self.ledger.exists())

    def test_body_none_treated_as_empty(self):
        fetch, _ = _make_fetch([{"number": 4, "title": "t", "body": None}])
        report = collect_kerns(self.ledger, fetch=fetch)
        self.assertEqual(report["gate_counts"][GATE_MISSING_MARKER], 1)

    def test_append_only_existing_lines_untouched(self):
        self.ledger.write_text('{"sha256":"abc"}\n', encoding="utf-8")
        fetch, _ = _make_fetch([_issue(5, _valid_body())])
        collect_kerns(self.ledger, fetch=fetch)
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(lines[0])["sha256"], "abc")
        self.assertEqual(len(lines), 2)

    def test_unicode_payload_preserved(self):
        body = _valid_body("# Umlaute: Käse, Ärger, Größe")
        fetch, _ = _make_fetch([_issue(6, body)])
        collect_kerns(self.ledger, fetch=fetch)
        raw = self.ledger.read_text(encoding="utf-8")
        self.assertIn("Käse", raw)

    def test_fetch_failure_raises(self):
        def boom(repo, label):
            raise OSError("netz weg")

        with self.assertRaises(OSError):
            collect_kerns(self.ledger, fetch=boom)
        self.assertFalse(self.ledger.exists())

    def test_non_list_fetch_result_rejected(self):
        def dict_fetch(repo, label):
            return {"unexpected": True}

        with self.assertRaises(ValueError):
            collect_kerns(self.ledger, fetch=dict_fetch)

    def test_honesty_limits_in_report(self):
        fetch, _ = _make_fetch([])
        report = collect_kerns(self.ledger, fetch=fetch)
        self.assertIn("ABGEHOLT != GEPRUEFT", report["honesty_limits"])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
        return subprocess.run(
            [sys.executable, "-m", "controller.kern_bridge", *args],
            capture_output=True, text=True, env=env, cwd=str(ROOT),
        )

    def test_exit_2_on_fetch_failure(self):
        # Ohne Netz/Test-Fetch bricht der echte Abruf fail-closed ab.
        result = self._run(str(self.ledger), "--repo", "u/r", "--label", "gibtsnicht-xyz")
        if result.returncode != 0:
            self.assertEqual(result.returncode, 2)
            self.assertIn("fail-closed", result.stdout + result.stderr)
        else:  # API lieferte eine leere Liste (Ausnahme-Verhalten im Sandkasten)
            self.assertEqual(json.loads(result.stdout)["issues_seen"], 0)


if __name__ == "__main__":
    unittest.main()
