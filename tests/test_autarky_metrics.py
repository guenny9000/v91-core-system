"""Tests for the local autarky and resilience metrics (Issue #83)."""
import json

import pytest

from controller.autarky_metrics import (
    AutarkyMetricError,
    BiodiversityLog,
    EnergyAutarky,
    RegionalLoopIndicator,
)


def test_energy_autarky_measured_share():
    records = [
        {"solar_w": 300, "grid_w": 100},
        {"solar_w": 100, "grid_w": 300},
    ]
    result = EnergyAutarky(records).compute()
    assert result["status"] == "MEASURED"
    assert result["self_sufficiency_share"] == 0.5
    assert result["measured_intervals"] == 2


def test_energy_autarky_missing_values_are_never_interpolated():
    records = [
        {"solar_w": 300, "grid_w": None},   # unmeasurbed interval excluded
        {"solar_w": 100, "grid_w": 100},
    ]
    result = EnergyAutarky(records).compute()
    assert result["status"] == "MEASURED"
    assert result["self_sufficiency_share"] == 0.5
    assert result["unmeasured_intervals"] == 1


def test_energy_autarky_no_data_is_unknown_not_healthy():
    result = EnergyAutarky([{"solar_w": None, "grid_w": None}]).compute()
    assert result["status"] == "UNKNOWN"
    assert result["self_sufficiency_share"] is None


def test_energy_autarky_rejects_non_sequence():
    with pytest.raises(AutarkyMetricError):
        EnergyAutarky("not-a-list")


def test_energy_autarky_negative_values_are_invalid():
    result = EnergyAutarky([{"solar_w": -5, "grid_w": 100}]).compute()
    assert result["status"] == "UNKNOWN"


def test_regional_loop_measured_and_capped_at_one():
    ok = RegionalLoopIndicator({"local_produced": 80, "local_consumed": 100}).compute()
    assert ok == {"status": "MEASURED", "local_loop_share": 0.8,
                  "local_produced": 80.0, "local_consumed": 100.0}
    capped = RegionalLoopIndicator({"local_produced": 150, "local_consumed": 100}).compute()
    assert capped["local_loop_share"] == 1.0


def test_regional_loop_unknown_on_missing_or_bad_config():
    assert RegionalLoopIndicator({}).compute()["status"] == "UNKNOWN"
    assert RegionalLoopIndicator({"local_produced": -1, "local_consumed": 10}).compute()["status"] == "UNKNOWN"
    assert RegionalLoopIndicator({"local_produced": 10, "local_consumed": 0}).compute()["status"] == "UNKNOWN"


def test_biodiversity_log_append_and_verify(tmp_path):
    log = BiodiversityLog(tmp_path / "bio.jsonl")
    log.add_observation("Feldlerche", 3, note="Ostfeld")
    log.add_observation("Igel", 1)
    assert log.verify_chain() is True
    assert log.totals() == {"observations": 2, "totals": {"Feldlerche": 3, "Igel": 1}}


def test_biodiversity_log_detects_tampering(tmp_path):
    log = BiodiversityLog(tmp_path / "bio.jsonl")
    log.add_observation("Feldlerche", 3)
    path = tmp_path / "bio.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["count"] = 99
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert log.verify_chain() is False

def test_biodiversity_log_refuses_append_after_tampering(tmp_path):
    path = tmp_path / "bio.jsonl"
    log = BiodiversityLog(path)
    log.add_observation("Feldlerche", 3)
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["count"] = 99
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with pytest.raises(AutarkyMetricError, match="chain is invalid"):
        log.add_observation("Igel", 1)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert log.verify_chain() is False


def test_biodiversity_log_validates_input(tmp_path):
    log = BiodiversityLog(tmp_path / "bio.jsonl")
    with pytest.raises(AutarkyMetricError):
        log.add_observation("", 1)
    with pytest.raises(AutarkyMetricError):
        log.add_observation("Igel", True)
    with pytest.raises(AutarkyMetricError):
        log.add_observation("Igel", -1)


def test_biodiversity_log_corrupt_line_fails_closed(tmp_path):
    path = tmp_path / "bio.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    log = BiodiversityLog(path)
    with pytest.raises(AutarkyMetricError, match="corrupt"):
        log.totals()
