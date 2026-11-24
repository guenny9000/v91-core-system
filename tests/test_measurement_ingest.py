import pytest

from controller.measurement_ingest import (
    MeasurementStatus,
    PreviousMeasurement,
    RawMeasurement,
    SensorSpec,
    validate_measurement,
)


@pytest.fixture
def specs():
    return {
        "soil_moisture": SensorSpec(
            metric="soil_moisture",
            unit="%",
            minimum=0,
            maximum=100,
            max_change_per_hour=15,
            max_gap_seconds=3600,
        )
    }


def reading(value=42.3, **kwargs):
    data = {
        "sensor_id": "sensor-01",
        "metric": "soil_moisture",
        "value": value,
        "unit": "%",
        "timestamp": "2026-11-17T08:00:00Z",
    }
    data.update(kwargs)
    return RawMeasurement(**data)


def test_valid_measurement_is_normalized_to_utc(specs):
    result = validate_measurement(reading(), specs)
    assert result.status is MeasurementStatus.VALID
    assert result.normalized_value == 42.3
    assert result.timestamp_utc == "2026-11-17T08:00:00Z"


def test_missing_calibration_reference_is_explicit_and_not_pass(specs):
    result = validate_measurement(reading(), specs)
    assert result.status is MeasurementStatus.VALID
    assert result.calibration_status == "MISSING_REFERENCE"
    assert any("does not establish calibration" in warning for warning in result.warnings)


def test_calibration_reference_presence_is_not_independent_verification(specs):
    result = validate_measurement(
        reading(calibration_ref="evidence://sensor-01/calibration/2026-01"), specs
    )
    assert result.status is MeasurementStatus.VALID
    assert result.calibration_status == "REFERENCE_PRESENT_NOT_VERIFIED"


@pytest.mark.parametrize("calibration_ref", ["", "   ", 42, True, {}])
def test_invalid_calibration_reference_is_quarantined(specs, calibration_ref):
    result = validate_measurement(reading(calibration_ref=calibration_ref), specs)
    assert result.status is MeasurementStatus.QUARANTINE
    assert result.calibration_status == "INVALID_REFERENCE"
    assert "calibration_ref must be a non-empty opaque reference when provided" in result.errors


@pytest.mark.parametrize("value", [None, -999, 9999, float("inf"), float("-inf"), float("nan"), -1, 101])
def test_invalid_or_sentinel_values_are_quarantined(specs, value):
    result = validate_measurement(reading(value), specs)
    assert result.status is MeasurementStatus.QUARANTINE
    assert result.normalized_value is None


@pytest.mark.parametrize("value", [True, "42.3", "42,3"])
def test_wrong_value_types_are_rejected(specs, value):
    result = validate_measurement(reading(value), specs)
    assert result.status is MeasurementStatus.REJECTED


def test_unknown_metric_and_unit_mismatch_fail_closed(specs):
    unknown = validate_measurement(reading(metric="unknown"), specs)
    mismatch = validate_measurement(reading(unit="°F"), specs)
    assert unknown.status is MeasurementStatus.QUARANTINE
    assert mismatch.status is MeasurementStatus.QUARANTINE


@pytest.mark.parametrize("timestamp", ["", "not-a-date", "2026-11-17T08:00:00"])
def test_invalid_or_naive_timestamps_are_quarantined(specs, timestamp):
    result = validate_measurement(reading(timestamp=timestamp), specs)
    assert result.status is MeasurementStatus.QUARANTINE


def test_out_of_order_timestamp_is_quarantined(specs):
    previous = PreviousMeasurement(40.0, "2026-11-17T08:00:00Z")
    result = validate_measurement(
        reading(timestamp="2026-11-17T07:59:00Z"), specs, previous
    )
    assert result.status is MeasurementStatus.QUARANTINE
    assert any("not later" in error for error in result.errors)


def test_gap_and_rate_are_warnings_not_silent_corrections(specs):
    previous = PreviousMeasurement(10.0, "2026-11-17T06:00:00Z")
    result = validate_measurement(reading(42.0), specs, previous)
    assert result.status is MeasurementStatus.VALID
    assert any("gap" in warning for warning in result.warnings)
    assert any("change rate" in warning for warning in result.warnings)


def test_sensor_spec_rejects_invalid_limits():
    with pytest.raises(ValueError):
        SensorSpec("soil_moisture", "%", 100, 0)
    with pytest.raises(ValueError):
        SensorSpec("soil_moisture", "%", 0, 100, max_gap_seconds=float("inf"))


def test_input_is_not_mutated_and_no_storage_is_created(specs, tmp_path, monkeypatch):
    item = reading()
    before = item
    result = validate_measurement(item, specs)
    assert result.original is before
    assert result.status is MeasurementStatus.VALID
    assert list(tmp_path.iterdir()) == []
