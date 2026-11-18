"""Tests: fail-closed secret scan (module + CI contract).

Fixture secrets are assembled at runtime (concatenation) so the
repository itself stays CLEAN; this file contains no literals.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.secret_scan import (
    ALLOWLIST_FILENAME,
    SecretScanError,
    find_secrets,
    load_allowlist,
    main,
)

A = "A"
X = "x"


class SecretScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_tree_is_clean(self):
        (self.root / "notes.txt").write_text("plain content", encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")
        self.assertEqual(report["findings"], [])

    def test_private_key_block_is_found(self):
        head = "-----BEGIN " + "RSA PRIVATE KEY-----"
        (self.root / "key.pem").write_text(head, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "FINDINGS")
        self.assertEqual(report["findings"][0]["kind"], "private_key_block")

    def test_aws_key_is_found(self):
        aws = "AK" + "IA" + "IOSFODNN7" + "EXAMPLE"
        (self.root / "cfg.ini").write_text("key = " + aws, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["findings"][0]["kind"], "aws_access_key_id")

    def test_github_token_is_found(self):
        tok = "ghp_" + A * 36
        (self.root / "run.sh").write_text("token = " + tok, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["findings"][0]["kind"], "github_classic_token")

    def test_sk_prefixed_key_is_found(self):
        key = "sk-" + X * 24
        (self.root / "readme.txt").write_text("contains " + key, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["findings"][0]["kind"], "sk_prefixed_key")

    def test_keyword_assignment_is_found(self):
        line = "PASSWORD" + " = '" + "correcthorse" + "'"
        (self.root / "app.py").write_text(line, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["findings"][0]["kind"], "keyword_assignment")

    def test_placeholder_assignment_is_not_finding(self):
        line = "PASSWORD" + " = '" + "changeme" + "12345'"
        (self.root / "app.py").write_text(line, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")

    def test_variable_reference_and_path_values_are_not_findings(self):
        (self.root / "compose.yml").write_text(
            "secret: '${V91_SECRET}'" + NL + "token: '/app/secrets/k'", encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")

    def test_env_assignment_literal_is_found(self):
        line = "V91_" + "SECRET" + "_KEY=" + "Super" + "Geheim123"
        (self.root / ".env").write_text(line, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["findings"][0]["kind"], "env_assignment")

    def test_env_path_value_is_not_finding(self):
        (self.root / ".env.example").write_text(
            "V91_SECRET_KEY_PATH=/app/secrets/v91_secret.key" + NL, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")

    def test_allowlist_suppresses_and_counts(self):
        tok = "ghp_" + A * 36;
        (self.root / "run.sh").write_text("token = " + tok, encoding="utf-8")
        report = find_secrets(self.root, allowlist=["token = " + tok])
        self.assertEqual(report["status"], "CLEAN")
        self.assertEqual(report["suppressed_findings"], 1)

    def test_allowlist_entries_load_from_file(self):
        entry = "tag: " + "ghp_" + A * 36
        allowlist = self.root / ALLOWLIST_FILENAME
        allowlist.write_text("# justified test fixture" + NL + entry + NL, encoding="utf-8")
        self.assertEqual(load_allowlist(allowlist), [entry])
        # allowlist file itself is never a finding
        (self.root / "misc.txt").write_text(entry, encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")
        self.assertEqual(report["suppressed_findings"], 2)

    def test_binary_and_excluded_dirs_are_skipped(self):
        (self.root / "blob.bin").write_bytes(b"a\x00" + b"n" * 40)
        hidden = self.root / "runtime"
        hidden.mkdir()
        (hidden / "dump.py").write_text("PASSWORD = 'aaaa'", encoding="utf-8")
        report = find_secrets(self.root)
        self.assertEqual(report["status"], "CLEAN")

    def test_missing_root_and_unreadable_allowlist_fail_closed(self):
        with self.assertRaises(SecretScanError):
            find_secrets(self.root / "does-not-exist")
        bad = self.root / "broken-allowlist.txt"
        bad.write_bytes(b"\xff")
        try:
            load_allowlist(bad)
            self.fail("expected SecretScanError")
        except SecretScanError:
            pass

    def test_cli_exit_codes(self):
        clean = self.root / "clean"
        clean.mkdir()
        (clean / "ok.py").write_text("value = 1", encoding="utf-8")
        dirty = self.root / "dirty"
        dirty.mkdir()
        (dirty / "leak.py").write_text(
            "PASSWORD = '" + "correcthorse" + "'", encoding="utf-8")
        self.assertEqual(main(["--path", str(clean)]), 0)
        self.assertEqual(main(["--path", str(dirty)]), 2)

    def test_cli_runs_as_module(self):
        clean = self.root / "clean"
        clean.mkdir()
        (clean / "ok.py").write_text("value = 1", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "controller.secret_scan", "--path", str(clean)],
            capture_output=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "CLEAN")


if __name__ == "__main__":
    unittest.main()