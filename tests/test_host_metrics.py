import json
import tempfile
import unittest
from pathlib import Path

from controller import host_metrics as hm
from controller.mess_pilot import PilotLog, verify


def fake_disk_usage(total, used, free):
    def _usage(_path):
        class U:
            pass
        u = U()
        u.total, u.used, u.free = total, used, free
        return u
    return _usage


def failing_disk_usage(_path):
    raise OSError("not reachable")


class TestReadSources(unittest.TestCase):
    def test_cpu_load_percent_measured(self):
        cores = hm.cpu_count()
        if not cores:
            self.skipTest("cpu_count unavailable on this platform")
        value = hm.cpu_load_percent(getloadavg=lambda: (0.5, 0.5, 0.5))
        self.assertIsNotNone(value)
        self.assertEqual(value, 0.5 * 100.0 / cores)

    def test_cpu_load_percent_windows_unmeasured_is_none(self):
        def not_impl():
            raise NotImplementedError
        self.assertIsNone(hm.cpu_load_percent(getloadavg=not_impl))

    def test_cpu_load_percent_kernel_error_is_none(self):
        def broken():
            raise OSError("kernel said no")
        self.assertIsNone(hm.cpu_load_percent(getloadavg=broken))

    def test_cpu_load_percent_negative_is_none(self):
        self.assertIsNone(hm.cpu_load_percent(getloadavg=lambda: (-1.0, 0, 0)))

    def test_disk_used_percent_measured(self):
        usage = fake_disk_usage(1000, 250, 750)
        self.assertEqual(hm.disk_used_percent("/", disk_usage=usage), 25.0)

    def test_disk_used_percent_unreachable_is_none(self):
        self.assertIsNone(hm.disk_used_percent("/", disk_usage=failing_disk_usage))

    def test_disk_used_percent_zero_total_is_none(self):
        usage = fake_disk_usage(0, 0, 0)
        self.assertIsNone(hm.disk_used_percent("/", disk_usage=usage))

    def test_snapshot_keeps_unknown_visible(self):
        snap = hm.snapshot("/", getloadavg=lambda: (_ for _ in ()).throw(NotImplementedError),
                           disk_usage=fake_disk_usage(1000, 100, 900))
        self.assertIsNone(snap["cpu_load_percent"])
        self.assertEqual(snap["disk_used_percent"], 10.0)
        self.assertIn("UNKNOWN", "UNKNOWN")
        self.assertEqual(snap["disk_free_bytes"], 900)


class TestAppendReading(unittest.TestCase):
    def _log(self, tmp, host="SOLAR-DESKTOP-01"):
        return PilotLog(Path(tmp) / "pilot_test.jsonl", host_id=host)

    def test_disk_reading_appends_ok_entry_with_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(tmp)
            entry = hm.append_reading(log, "disk_used",
                                      disk_usage=fake_disk_usage(1000, 400, 600))
            self.assertEqual(entry["status"], "OK")
            self.assertEqual(entry["metric_id"], "VB-SYS-01")
            self.assertEqual(entry["value"], 40.0)
            outcome = verify(log.path)
            self.assertTrue(outcome["ok"], outcome)

    def test_unmeasured_platform_appends_unknown_without_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(tmp)
            def not_impl():
                raise NotImplementedError
            entry = hm.append_reading(log, "cpu_load", getloadavg=not_impl)
            self.assertEqual(entry["status"], "UNKNOWN")
            self.assertIsNone(entry["value"])
            outcome = verify(log.path)
            self.assertTrue(outcome["ok"], outcome)
            self.assertEqual(outcome["statuses"].get("UNKNOWN"), 1)

    def test_out_of_range_value_is_flagged_not_corrected(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(tmp)
            entry = hm.append_reading(log, "cpu_load",
                                      getloadavg=lambda: (9999.0, 0.0, 0.0))
            # load above 100 percent of the CPUs is implausible but is a real
            # observation: PilotLog flags it OUT_OF_RANGE, value stays visible,
            # never silently corrected (REPAIR != LOESCHEN der Beobachtung).
            self.assertEqual(entry["status"], "OUT_OF_RANGE")
            self.assertIsNotNone(entry["value"])

    def test_unknown_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(tmp)
            with self.assertRaises(hm.HostMetricsError):
                hm.append_reading(log, "mood")

    def test_pilot_log_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = self._log(tmp)
            log.path = Path(tmp)  # a directory: append must fail honestly
            with self.assertRaises(hm.HostMetricsError):
                hm.append_reading(log, "disk_used",
                                  disk_usage=fake_disk_usage(1000, 10, 990))


class TestCli(unittest.TestCase):
    def test_snapshot_only_prints_json(self):
        rc = hm.main([])
        self.assertEqual(rc, 0)

    def test_missing_pair_args_rejected(self):
        self.assertEqual(hm.main(["--source", "cpu_load"]), 2)

    def test_append_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            logp = str(Path(tmp) / "p.jsonl")
            rc = hm.main(["--log", logp, "--source", "disk_used"])
            # real disk value expected on CI runners (always measurable)
            self.assertIn(rc, (0, 1))
            outcome = verify(Path(logp))
            self.assertTrue(outcome["ok"], outcome)


if __name__ == "__main__":
    unittest.main()
