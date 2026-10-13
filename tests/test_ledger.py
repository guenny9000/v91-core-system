"""Regression tests for the local V91 tamper-detecting ledger."""
import json
import math
import tempfile
import unittest
from pathlib import Path

import ledger


class TestLedgerIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = ledger.LEDGER_FILE
        ledger.LEDGER_FILE = Path(self.tmp.name) / "test-ledger.jsonl"

    def tearDown(self):
        ledger.LEDGER_FILE = self.original_path
        self.tmp.cleanup()

    def test_empty_ledger(self):
        state = ledger.verify_ledger_chain()
        self.assertEqual(state, {
            "valid": True, "entries": 0, "last_hash": ledger.GENESIS_HASH
        })

    def test_valid_multiple_appends(self):
        first = ledger.append_ledger_entry({"action": "init", "value": 42})
        second = ledger.append_ledger_entry({"action": "update", "value": 100})
        state = ledger.verify_ledger_chain()
        self.assertEqual((first["seq"], second["seq"]), (1, 2))
        self.assertEqual(state["entries"], 2)
        self.assertEqual(state["last_hash"], second["hash"])

    def test_tampered_content_detected(self):
        ledger.append_ledger_entry({"data": "alpha"})
        lines = ledger.LEDGER_FILE.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["event"]["data"] = "tampered"
        ledger.LEDGER_FILE.write_text(
            json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Hashfehler"):
            ledger.verify_ledger_chain()

    def test_sequence_jump_detected(self):
        first = ledger.append_ledger_entry({"data": "one"})
        bad = {
            "seq": 3,
            "timestamp": first["timestamp"],
            "event": {"data": "two"},
            "prev_hash": first["hash"],
        }
        bad["hash"] = ledger.compute_hash(bad)
        with ledger.LEDGER_FILE.open("a", encoding="utf-8") as stream:
            stream.write(ledger.canonical_json(bad) + "\n")
        with self.assertRaisesRegex(ValueError, "Sequenznummer"):
            ledger.verify_ledger_chain()

    def test_duplicate_sequence_detected(self):
        first = ledger.append_ledger_entry({"n": 1})
        second = ledger.append_ledger_entry({"n": 2})
        lines = ledger.LEDGER_FILE.read_text(encoding="utf-8").splitlines()
        duplicate = json.loads(lines[1])
        duplicate["seq"] = 1
        duplicate["hash"] = ledger.compute_hash(duplicate)
        lines[1] = ledger.canonical_json(duplicate)
        ledger.LEDGER_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Sequenznummer"):
            ledger.verify_ledger_chain()

    def test_invalid_json_detected(self):
        ledger.append_ledger_entry({"ok": True})
        with ledger.LEDGER_FILE.open("a", encoding="utf-8") as stream:
            stream.write('{"seq":2, invalid}\n')
        with self.assertRaisesRegex(ValueError, "JSON"):
            ledger.verify_ledger_chain()

    def test_truncated_last_line_detected(self):
        ledger.append_ledger_entry({"ok": True})
        with ledger.LEDGER_FILE.open("ab") as stream:
            stream.write(b'{"seq":2')
        with self.assertRaisesRegex(ValueError, "Unvollst"):
            ledger.verify_ledger_chain()

    def test_corrupt_chain_blocks_append(self):
        ledger.append_ledger_entry({"ok": True})
        ledger.LEDGER_FILE.write_text("not-json\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            ledger.append_ledger_entry({"should": "not be written"})
        self.assertEqual(ledger.LEDGER_FILE.read_text(encoding="utf-8"), "not-json\n")

    def test_non_dict_rejected(self):
        with self.assertRaises(TypeError):
            ledger.append_ledger_entry("not a dict")

    def test_non_finite_json_rejected_before_write(self):
        with self.assertRaises(ValueError):
            ledger.append_ledger_entry({"value": math.nan})
        self.assertFalse(ledger.LEDGER_FILE.exists())

    def test_boolean_sequence_not_accepted(self):
        ledger.append_ledger_entry({"ok": True})
        lines = ledger.LEDGER_FILE.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["seq"] = True
        entry["hash"] = ledger.compute_hash(entry)
        ledger.LEDGER_FILE.write_text(ledger.canonical_json(entry) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Sequenznummer"):
            ledger.verify_ledger_chain()


if __name__ == "__main__":
    unittest.main()
