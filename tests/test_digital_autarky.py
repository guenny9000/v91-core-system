'''Tests for controller.digital_autarky (Datensatz 7).

All test data remains pure ASCII (<= 0x7F) per repo convention.
'''

import unittest

from controller import digital_autarky as da


def ok_measurement(area, value="measured locally"):
    return {
        "area": area,
        "status": "OK",
        "value": value,
        "source": "local test run",
        "checked_on": "2026-11-21",
    }


def all_areas():
    return [
        ok_measurement("key_management"),
        ok_measurement("key_loss_recovery"),
        ok_measurement("cloud_dependency"),
        ok_measurement("communication"),
        ok_measurement("data_backup"),
        ok_measurement("identities"),
        ok_measurement("software_supply"),
        ok_measurement("restart_time", value="42 seconds"),
    ]


def valid_drill(name, passed=True):
    drill = {
        "drill": name,
        "kind": "simulation",
        "affected_scope": "own_node",
        "passed": passed,
        "checked_on": "2026-11-21",
    }
    if name == "key_loss":
        drill["restored_rights_verified"] = True
        drill["integrity_verified"] = True
    if name == "restart":
        drill["measured_recovery_seconds"] = 42
    if name == "compromised_identity":
        drill["revoked_by"] = "other-identity"
        drill["compromised_identity"] = "lossy-identity"
    return drill


class TestState(unittest.TestCase):
    def test_new_state_empty(self):
        state = da.new_state()
        summary = da.summarize(state)
        self.assertEqual(summary["nodes_total"], 0)
        self.assertEqual(summary["overall"], "UNMEASURED")


class TestDatasetEntries(unittest.TestCase):
    def test_dataset_entry_is_claim_not_measurement(self):
        state = da.new_state()
        status = da.register_dataset_entry(state, {
            "topic": "energy import share",
            "value": "65.6 percent",
            "source": "AG Energiebilanzen",
            "checked_on": "2026-11-21",
        })
        self.assertEqual(status, "DOCUMENTED_CLAIM_SOURCE_BOUND")
        summary = da.summarize(state)
        self.assertEqual(summary["dataset_entries_total"], 1)
        self.assertEqual(summary["dataset_entry_status"], "DOCUMENTED_CLAIM_SOURCE_BOUND")

    def test_separate_measures_stay_separate(self):
        state = da.new_state()
        da.register_dataset_entry(state, {
            "topic": "total conflict fatalities",
            "value": "238000",
            "source": "dataset",
            "checked_on": "2026-11-21",
        })
        da.register_dataset_entry(state, {
            "topic": "civilian conflict fatalities",
            "value": "37163",
            "source": "dataset",
            "checked_on": "2026-11-21",
        })
        self.assertEqual(len(state["dataset_entries"]), 2)
        topics = [e["topic"] for e in state["dataset_entries"]]
        self.assertIn("civilian conflict fatalities", topics)
        self.assertIn("total conflict fatalities", topics)

    def test_dataset_entry_needs_source(self):
        state = da.new_state()
        with self.assertRaises(da.DigitalAutarkyError):
            da.register_dataset_entry(state, {
                "topic": "t",
                "value": "1",
                "source": " ",
                "checked_on": "2026-11-21",
            })


class TestMeasurements(unittest.TestCase):
    def test_unknown_area_rejected(self):
        state = da.new_state()
        measurement = ok_measurement("quantum_vibes")
        with self.assertRaises(da.DigitalAutarkyError):
            da.register_measurement(state, "node-a", measurement)

    def test_ok_without_value_rejected(self):
        state = da.new_state()
        measurement = ok_measurement("communication")
        measurement["value"] = None
        with self.assertRaises(da.DigitalAutarkyError):
            da.register_measurement(state, "node-a", measurement)

    def test_unknown_without_value_allowed(self):
        state = da.new_state()
        measurement = ok_measurement("communication")
        measurement["status"] = "UNKNOWN"
        measurement["value"] = None
        self.assertEqual(da.register_measurement(state, "node-a", measurement), "UNKNOWN")

    def test_bad_status_rejected(self):
        state = da.new_state()
        measurement = ok_measurement("data_backup")
        measurement["status"] = "FINE"
        with self.assertRaises(da.DigitalAutarkyError):
            da.register_measurement(state, "node-a", measurement)

    def test_unknown_never_passes_in_area_summary(self):
        state = da.new_state()
        measurement = ok_measurement("cloud_dependency")
        measurement["status"] = "UNKNOWN"
        measurement["value"] = None
        da.register_measurement(state, "node-a", measurement)
        da.register_measurement(state, "node-a", ok_measurement("data_backup"))
        summary = da.summarize_node(state, "node-a")
        self.assertEqual(summary["by_area"]["cloud_dependency"], "UNKNOWN")
        self.assertEqual(summary["overall"], "MEASURED_PARTIALLY")
        self.assertIn("cloud_dependency", summary["unmeasured_or_unknown"])


class TestDrills(unittest.TestCase):
    def test_all_five_drills_recorded(self):
        state = da.new_state()
        for name in da.ALLOWED_DRILLS:
            self.assertEqual(
                da.record_drill(state, "node-a", valid_drill(name)),
                "DRY_RUN_RECORDED",
            )
        summary = da.summarize_node(state, "node-a")
        self.assertEqual(summary["drills_recorded"], 5)
        self.assertEqual(summary["drills_passed"], 5)

    def test_production_kind_refused(self):
        state = da.new_state()
        drill = valid_drill("cloud_outage")
        drill["kind"] = "production"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_foreign_scope_refused(self):
        state = da.new_state()
        drill = valid_drill("network_outage")
        drill["affected_scope"] = "whole_cluster"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_unknown_drill_refused(self):
        state = da.new_state()
        drill = valid_drill("cloud_outage")
        drill["drill"] = "delete_keys_for_real"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_key_loss_needs_rights_reverification(self):
        state = da.new_state()
        drill = valid_drill("key_loss")
        drill["restored_rights_verified"] = False
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_key_loss_needs_integrity_verification(self):
        state = da.new_state()
        drill = valid_drill("key_loss")
        del drill["integrity_verified"]
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_key_loss_failed_drill_needs_no_fields(self):
        state = da.new_state()
        drill = valid_drill("key_loss", passed=False)
        drill.pop("restored_rights_verified", None)
        drill.pop("integrity_verified", None)
        self.assertEqual(da.record_drill(state, "node-a", drill), "DRY_RUN_RECORDED")

    def test_restart_needs_real_seconds(self):
        state = da.new_state()
        drill = valid_drill("restart")
        drill["measured_recovery_seconds"] = "fast"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_restart_negative_seconds_rejected(self):
        state = da.new_state()
        drill = valid_drill("restart")
        drill["measured_recovery_seconds"] = -1
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_revocation_must_be_independent(self):
        state = da.new_state()
        drill = valid_drill("compromised_identity")
        drill["revoked_by"] = "lossy-identity"
        drill["compromised_identity"] = "lossy-identity"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)

    def test_passed_must_be_bool(self):
        state = da.new_state()
        drill = valid_drill("cloud_outage")
        drill["passed"] = "yes"
        with self.assertRaises(da.DigitalAutarkyError):
            da.record_drill(state, "node-a", drill)


class TestNodeSummary(unittest.TestCase):
    def test_unmeasured_node_never_fully_measured(self):
        state = da.new_state()
        da.register_measurement(state, "node-a", ok_measurement("communication"))
        summary = da.summarize_node(state, "node-a")
        self.assertEqual(summary["measured_areas"], 1)
        self.assertEqual(summary["overall"], "MEASURED_PARTIALLY")
        self.assertIn("key_management", summary["unmeasured_or_unknown"])

    def test_all_areas_measured_fully(self):
        state = da.new_state()
        for measurement in all_areas():
            da.register_measurement(state, "node-a", measurement)
        summary = da.summarize_node(state, "node-a")
        self.assertEqual(summary["overall"], "MEASURED_FULLY")
        self.assertEqual(summary["measured_areas"], 8)
        self.assertEqual(summary["unmeasured_or_unknown"], [])

    def test_failed_area_blocks_fullly(self):
        state = da.new_state()
        for measurement in all_areas():
            da.register_measurement(state, "node-a", measurement)
        failing = ok_measurement("identities")
        failing["status"] = "FAIL"
        da.register_measurement(state, "node-a", failing)
        summary = da.summarize_node(state, "node-a")
        self.assertEqual(summary["by_area"]["identities"], "FAIL")
        self.assertEqual(summary["overall"], "MEASURED_FULLY")

    def test_unknown_node_rejected(self):
        state = da.new_state()
        with self.assertRaises(da.DigitalAutarkyError):
            da.summarize_node(state, "node-void")


class TestGlobalSummary(unittest.TestCase):
    def test_one_node_measured_one_not(self):
        state = da.new_state()
        for measurement in all_areas():
            da.register_measurement(state, "node-a", measurement)
        da.register_measurement(state, "node-b", ok_measurement("communication"))
        summary = da.summarize(state)
        self.assertEqual(summary["overall"], "MEASURED_PARTIALLY")
        self.assertEqual(summary["nodes_total"], 2)

    def test_all_nodes_measured(self):
        state = da.new_state()
        for node in ("node-a", "node-b"):
            for measurement in all_areas():
                da.register_measurement(state, node, measurement)
        summary = da.summarize(state)
        self.assertEqual(summary["overall"], "MEASURED_ALL_NODES")
        self.assertNotIn("AUTARK", summary["overall"])

    def test_drill_success_does_not_create_measurement(self):
        state = da.new_state()
        da.record_drill(state, "node-a", valid_drill("cloud_outage"))
        summary = da.summarize(state)
        self.assertEqual(summary["overall"], "UNMEASURED")
        node_summary = da.summarize_node(state, "node-a")
        self.assertEqual(node_summary["drills_passed"], 1)
        self.assertEqual(node_summary["measured_areas"], 0)

    def test_honesty_limits_present(self):
        summary = da.summarize(da.new_state())
        self.assertIn("TEST != AUTARKIE", summary["honesty_limits"])
        self.assertIn("DATENSATZ != MESSWERT", summary["honesty_limits"])

    def test_node_summary_limits_mention_recovery(self):
        state = da.new_state()
        da.register_measurement(state, "node-a", ok_measurement("communication"))
        summary = da.summarize_node(state, "node-a")
        self.assertIn("WIEDERHERSTELLUNG != ALTE RECHTE", summary["honesty_limits"])

    def test_malformed_state_rejected(self):
        with self.assertRaises(da.DigitalAutarkyError):
            da.summarize({"nodes": {}})


if __name__ == "__main__":
    unittest.main()
