"""Tests: offline startup self-check (Issue #8 Stage 1).

Semantics under test: READY only with every check PASS, UNKNOWN !=
PASS, fail-closed stop flag, honest no-key / missing-ledger results.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.measurement_store import MeasurementStore
from controller.startup_check import (
    NOT_READY,
    READY,
    UNKNOWN,
    StartupCheckError,
    build_startup_report,
    main,
)

TEST_KEY = b"0123456789abcdef0123456789abcdef"


def _make_store(path, records=2):
    store = MeasurementStore(Path(path), key=TEST_KEY)
    for i in range(records):
        store.record_valid(
            sensor_id="s1",
            metric="water_temp",
            normalized_value=12.0 + i,
            unit="celsius",
            timestamp_utc="2026-11-18T12:00:00+00:00",
        )
    return path


class StartupCheckTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.flag = self.root / "stop.flag"
        self.ledger = self.root / "measurements.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, ledgers=None, key="absent"):
        if ledgers is None:
            ledgers = {"main": self.ledger}
        kw = dict(ledgers=ledgers)
        if key != "absent":
            kw["key"] = key
        return build_startup_report(self.flag, **kw)

    def test_ready_when_flag_clear_and_chain_verified(self):
        _make_store(self.ledger)
        report = self._report(key=TEST_KEY)
        self.assertEqual(report["status"], READY)
        self.assertEqual([e["status"] for e in report["checklist"]], ["PASS", "PASS"])

    def test_not_ready_when_stop_flag_present(self):
        self.flag.write_text("stop", encoding="utf-8")
        report = self._report(key=TEST_KEY)
        self.assertEqual(report["status"], NOT_READY)
        self.assertEqual(report["checklist"][0]["name"], "emergency_stop")
        self.assertEqual(report["checklist"][0]["status"], "FAIL")

    def test_not_ready_when_flag_unreadable_fail_closed(self):
        directory_as_flag = self.root / "flagdir"
        directory_as_flag.mkdir()
        report = build_startup_report(directory_as_flag, {}, key=TEST_KEY)
        self.assertEqual(report["status"], NOT_READY)

    def test_unknown_when_ledger_file_missing(self):
        report = self._report(key=TEST_KEY)
        self.assertEqual(report["status"], UNKNOWN)
        names = {e["name"]: e for e in report["checklist"]}
        self.assertEqual(names["ledger:main"]["status"], UNKNOWN)

    def test_unknown_when_no_store_key(self):
        _make_store(self.ledger)
        report = self._report(key="absent")
        self.assertEqual(report["status"], UNKNOWN)

    def test_fail_when_chain_tampered(self):
        _make_store(self.ledger, records=3)
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        tampered = lines[1].replace("13.0", "55.0")
        self.assertNotEqual(tampered, lines[1])
        self.ledger.write_text(
            lines[0] + "\n" + tampered + "\n" + lines[2] + "\n", encoding="utf-8")
        report = self._report(key=TEST_KEY)
        self.assertEqual(report["status"], NOT_READY)
        self.assertEqual(report["checklist"][1]["status"], "FAIL")

    def test_fail_when_ledger_line_unparseable(self):
        _make_store(self.ledger)
        with open(self.ledger, "a", encoding="utf-8") as handle:
            handle.write("not json at all\n")
        report = self._report(key=TEST_KEY)
        self.assertEqual(report["status"], NOT_READY)

    def test_multiple_ledgers_evaluated_in_sorted_order(self):
        second = self.root / "second.jsonl"
        _make_store(self.ledger)
        _make_store(second)
        report = self._report(ledgers={"zeta": second, "main": self.ledger},
                              key=TEST_KEY)
        self.assertEqual(report["status"], READY)
        self.assertEqual([e["name"] for e in report["checklist"]],
                         ["emergency_stop", "ledger:main", "ledger:zeta"])

    def test_blank_ledger_name_rejected(self):
        with self.assertRaises(StartupCheckError):
            build_startup_report(
                self.flag, {" ": self.ledger}, key=TEST_KEY)

    def test_empty_flag_path_rejected(self):
        with self.assertRaises(StartupCheckError):
            build_startup_report("", {}, key=TEST_KEY)

    def test_short_store_key_rejected(self):
        with self.assertRaises(StartupCheckError):
            build_startup_report(self.flag, {}, key=b"short")

    def test_cli_ready_exit_zero(self):
        import io, json, os
        from contextlib import redirect_stdout
        import controller.startup_check as mod_test_env
        _make_store(self.ledger)
        old_env = os.environ.get(mod_test_env.STORE_KEY_ENV)
        try:
            os.environ[mod_test_env.STORE_KEY_ENV] = TEST_KEY.decode("ascii")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["--flag-path", str(self.flag),
                             "--ledger", "main=" + str(self.ledger)])
            self.assertEqual(code, 0)
            report = json.loads(buffer.getvalue())
            self.assertEqual(report["status"], READY)
        finally:
            if old_env is None:
                os.environ.pop(mod_test_env.STORE_KEY_ENV, None)
            else:
                os.environ[mod_test_env.STORE_KEY_ENV] = old_env

    def test_cli_not_ready_exit_two(self):
        import io, json, os
        from contextlib import redirect_stdout
        self.flag.write_text("stop", encoding="utf-8")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--flag-path", str(self.flag)])
        self.assertEqual(code, 2)

    def test_cli_unknown_exit_one(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--flag-path", str(self.flag),
                         "--ledger", "main=" + str(self.ledger)])
        self.assertEqual(code, 1)

    def test_cli_bad_ledger_argument_fail_closed(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--flag-path", str(self.flag), "--ledger", "no-sign"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
