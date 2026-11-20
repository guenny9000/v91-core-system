"""Unit tests for controller.lora_range_eval (LoRa range field-test log)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.lora_range_eval import (  # noqa: E402
    RangeEvaluation,
    RangeLog,
    RangeLogError,
    main,
    validate_record,
)


def _record(**overrides):
    base = {
        "rx_ts": 1000,
        "node_id": "node-01",
        "seq": 10,
        "ok": True,
        "rssi_dbm": -78.0,
        "snr_db": 8.5,
        "note": "hof_nah",
    }
    base.update(overrides)
    return base


class ValidateRecordTests(unittest.TestCase):
    def test_valid_record_normalizes_numbers(self):
        normalized = validate_record(_record())
        self.assertEqual(normalized["rssi_dbm"], -78.0)
        self.assertIsInstance(normalized["rssi_dbm"], float)

    def test_missing_and_unknown_keys_fail_closed(self):
        with self.assertRaises(RangeLogError):
            validate_record({k: v for k, v in _record().items() if k != "seq"})
        with self.assertRaises(RangeLogError):
            validate_record(_record(extra=1))

    def test_bool_seq_and_negative_seq_fail(self):
        with self.assertRaises(RangeLogError):
            validate_record(_record(seq=True))
        with self.assertRaises(RangeLogError):
            validate_record(_record(seq=-1))

    def test_bool_rx_ts_and_missing_fields_fail(self):
        with self.assertRaises(RangeLogError):
            validate_record(_record(rx_ts=False))
        with self.assertRaises(RangeLogError):
            validate_record(_record(node_id=""))
        with self.assertRaises(RangeLogError):
            validate_record(_record(note=" "))
        with self.assertRaises(RangeLogError):
            validate_record(_record(ok=None))

    def test_nan_inf_and_string_rssi_fail(self):
        with self.assertRaises(RangeLogError):
            validate_record(_record(rssi_dbm=float("nan")))
        with self.assertRaises(RangeLogError):
            validate_record(_record(rssi_dbm=float("inf")))
        with self.assertRaises(RangeLogError):
            validate_record(_record(snr_db="-7.0"))

    def test_none_rssi_snr_is_unknown_not_fake(self):
        normalized = validate_record(_record(rssi_dbm=None, snr_db=None))
        self.assertIsNone(normalized["rssi_dbm"])
        self.assertIsNone(normalized["snr_db"])


class RangeLogAppendTests(unittest.TestCase):
    def test_append_writes_validated_line_with_missed_zero(self):
        written = RangeLog(Path(self.mktemp_path("a1"))).append(
            node_id="node-01", seq=10, ok=True,
            rssi_dbm=-78.0, snr_db=8.5, note="hof_nah", rx_ts=1000,
        )
        self.assertEqual(written["missed_packets_since_last"], 0)

    def test_gap_between_accepted_packets_counts_missed(self):
        path = Path(self.mktemp_path("a2"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=-78.0,
                   snr_db=8.5, note="hof_nah", rx_ts=1000)
        written = log.append(node_id="node-01", seq=12, ok=True, rssi_dbm=-104.0,
                             snr_db=-3.5, note="hecke_mitte", rx_ts=1100)
        self.assertEqual(written["missed_packets_since_last"], 1)

    def test_replay_and_backwards_seq_refused(self):
        path = Path(self.mktemp_path("a3"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=None,
                   snr_db=None, note="hof_nah", rx_ts=1000)
        with self.assertRaises(RangeLogError):
            log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=None,
                       snr_db=None, note="hof_nah", rx_ts=1100)
        with self.assertRaises(RangeLogError):
            log.append(node_id="node-01", seq=9, ok=True, rssi_dbm=None,
                       snr_db=None, note="hof_nah", rx_ts=1200)

    def test_rejected_records_never_raise_the_floor(self):
        path = Path(self.mktemp_path("a4"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=None,
                   snr_db=None, note="hof_nah", rx_ts=1000)
        # two unverified frames claim higher seq and must not block seq=11
        log.append(node_id="node-01", seq=17, ok=False, rssi_dbm=None,
                   snr_db=None, note="senke_rand", rx_ts=1050)
        log.append(node_id="node-01", seq=99, ok=False, rssi_dbm=None,
                   snr_db=None, note="senke_rand", rx_ts=1060)
        written = log.append(node_id="node-01", seq=11, ok=True, rssi_dbm=None,
                             snr_db=None, note="hof_nah", rx_ts=1100)
        self.assertEqual(written["missed_packets_since_last"], 0)

    def test_per_node_floors_are_independent(self):
        path = Path(self.mktemp_path("a5"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=50, ok=True, rssi_dbm=None,
                   snr_db=None, note="hof_nah", rx_ts=1000)
        written = log.append(node_id="node-02", seq=3, ok=True, rssi_dbm=None,
                             snr_db=None, note="hecke_mitte", rx_ts=1200)
        self.assertEqual(written["missed_packets_since_last"], 0)

    def test_rx_ts_not_ascending_refused(self):
        path = Path(self.mktemp_path("a6"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=None,
                   snr_db=None, note="hof_nah", rx_ts=1000)
        with self.assertRaises(RangeLogError):
            log.append(node_id="node-01", seq=11, ok=True, rssi_dbm=None,
                       snr_db=None, note="hof_nah", rx_ts=1000)

    @staticmethod
    def mktemp_path(tag):
        import tempfile
        import os
        directory = tempfile.mkdtemp(prefix="v91_range_")
        return os.path.join(directory, f"{tag}.jsonl")


class RangeEvaluationTests(unittest.TestCase):
    @staticmethod
    def _build_log():
        import tempfile
        import os
        directory = tempfile.mkdtemp(prefix="v91_range_eval_")
        path = Path(os.path.join(directory, "log.jsonl"))
        log = RangeLog(path)
        log.append(node_id="node-01", seq=10, ok=True, rssi_dbm=-78.0,
                   snr_db=8.5, note="hof_nah", rx_ts=1000)
        log.append(node_id="node-01", seq=12, ok=True, rssi_dbm=-104.0,
                   snr_db=-3.5, note="hecke_mitte", rx_ts=1100)
        log.append(node_id="node-01", seq=13, ok=False, rssi_dbm=-112.0,
                   snr_db=-7.0, note="senke_rand", rx_ts=1200)
        log.append(node_id="node-01", seq=14, ok=True, rssi_dbm=None,
                   snr_db=None, note="senke_rand", rx_ts=1300)
        return path

    def test_per_spot_grouping_and_gap_loss(self):
        path = self._build_log()
        evaluation = RangeLog(path).evaluate()
        by_note = {s.note: s for s in evaluation.spots}
        self.assertEqual(by_note["hof_nah"].accepted, 1)
        self.assertEqual(by_note["hecke_mitte"].accepted, 1)
        # gap (10 -> 12) is booked at the spot where the next packet landed
        self.assertEqual(by_note["hecke_mitte"].missed_packets, 1)
        self.assertAlmostEqual(by_note["hecke_mitte"].loss_percent, 50.0)
        self.assertEqual(by_note["senke_rand"].accepted, 1)
        self.assertEqual(by_note["senke_rand"].rejected, 1)

    def test_unknown_rssi_snr_counted_not_faked(self):
        path = self._build_log()
        by_note = {s.note: s for s in RangeLog(path).evaluate().spots}
        senke = by_note["senke_rand"]
        self.assertEqual(senke.rssi_missing, 1)
        self.assertEqual(senke.snr_missing, 1)
        # the rejected frame still had a real radio reception: its RSSI/SNR
        # are channel observations, not trust claims, and hence count
        self.assertAlmostEqual(senke.rssi_mean_dbm, -112.0)
        self.assertAlmostEqual(senke.snr_mean_db, -7.0)

    def test_totals_and_tamper_counting_fail_closed_in_append(self):
        path = self._build_log()
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        with self.assertRaises(RangeLogError):
            RangeLog(path).append(node_id="node-01", seq=20, ok=True,
                                  rssi_dbm=None, snr_db=None,
                                  note="hof_nah", rx_ts=2000)

    def test_unparseable_and_invalid_lines_counted_in_evaluation(self):
        path = self._build_log()
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{not json\n")
            handle.write(json.dumps({"rx_ts": "x"}) + "\n")
        evaluation = RangeLog(path).evaluate()
        self.assertEqual(evaluation.unparseable_lines, 1)
        self.assertEqual(evaluation.invalid_lines, 1)
        self.assertEqual(evaluation.total_accepted, 3)
        self.assertEqual(evaluation.total_rejected, 1)

    def test_missing_log_fails_closed(self):
        with self.assertRaises(RangeLogError):
            RangeLog(Path("/nonexistent/v91_range_missing.jsonl")).evaluate()


class CliTests(unittest.TestCase):
    def test_append_then_evaluate_exit_codes(self):
        import tempfile
        import os
        directory = tempfile.mkdtemp(prefix="v91_range_cli_")
        path = os.path.join(directory, "log.jsonl")
        args_append = [
            "append", path, "--node", "node-01", "--seq", "5",
            "--rx-ts", "1700000000", "--note", "hof_nah",
            "--rssi", "-80.5", "--snr", "7.0",
        ]
        self.assertEqual(main(args_append), 0)
        self.assertEqual(main(["evaluate", path]), 0)
        evaluation = RangeLog(path).evaluate()
        spot = evaluation.spots[0]
        self.assertAlmostEqual(spot.rssi_mean_dbm, -80.5)
        self.assertAlmostEqual(spot.snr_mean_db, 7.0)
        self.assertAlmostEqual(spot.loss_percent, 0.0)  # 1 accepted, 0 missed

    def test_cli_failures_exit_two(self):
        with open("/dev/null", "w"):
            pass
        self.assertEqual(main(["evaluate", "/nonexistent/x.jsonl"]), 2)
        self.assertEqual(main(["bogus"]), 2)
        self.assertEqual(main(["append", "/tmp/should_not_exist.jsonl"]), 2)


if __name__ == "__main__":
    unittest.main()
