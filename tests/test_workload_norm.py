"""Tests fuer controller/workload_norm.py (Issue #419: Workload-Nenner).

Es wird nur geprueft, was das Modul tut: Normalisierung EINER
berechneten Groesse, fail-closed, keine Aggregation. NORMALIZED != GEMESSEN.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from controller.workload_norm import (
    MIN_WORKLOAD_SAMPLES,
    NOT_NORMALIZED,
    NORMALIZED,
    WorkloadNormError,
    normalize_impact,
)

ROOT = Path(__file__).resolve().parents[1]

WS = "2026-11-24T10:00:00+00:00"
WE = "2026-11-24T12:00:00+00:00"

IMPACT = {
    "measure": "generator_fuel",
    "unit": "kWh",
    "status": "VALID",
    "saved_per_sample": 12.0,
    "co2_change_kg_per_sample": 6.0,
}

def _rows(*values, ts="2026-11-24T11:00:00+00:00", source="direct_sensor"):
    return [{"timestamp": ts, "value": v, "source_type": source} for v in values]


class TestHappyPath:
    def test_normalized_baseline(self):
        r = normalize_impact(IMPACT, _rows(4.0, 6.0), "operating_hours",
                             "standort_alsfeld_generator_1", WS, WE)
        assert r["status"] == NORMALIZED
        assert r["flags"] == []
        assert r["workload_mean"] == 5.0
        assert r["saved_per_workload_unit"] == pytest.approx(2.4)
        assert r["co2_change_kg_per_workload_unit"] == pytest.approx(1.2)
        assert r["normalized_unit"] == "kWh/operating_hours"

    def test_single_value_series_with_min_one(self):
        r = normalize_impact(IMPACT, _rows(2.0), "units", "b", WS, WE, min_workload_samples=1)
        assert r["status"] == NORMALIZED
        assert r["saved_per_workload_unit"] == pytest.approx(6.0)

    def test_negative_saved_normalizes_negative(self):
        impact = dict(IMPACT, status="NO_IMPROVEMENT", saved_per_sample=-3.0)
        r = normalize_impact(impact, _rows(1.5, 1.5), "h", "sys", WS, WE)
        assert r["status"] == NORMALIZED
        assert r["saved_per_workload_unit"] == pytest.approx(-2.0)

    def test_no_improvement_status_is_preserved_when_normalized(self):
        impact = dict(IMPACT, status="NO_IMPROVEMENT", saved_per_sample=-3.0)
        r = normalize_impact(impact, _rows(1.5, 1.5), "h", "sys", WS, WE)
        assert r["status"] == NORMALIZED
        assert r["impact_status"] == "NO_IMPROVEMENT"
        assert r["saved_per_workload_unit"] == pytest.approx(-2.0)

    def test_status_and_counts_reported(self):
        r = normalize_impact(IMPACT, _rows(1.0, 2.0, 3.0), "u", "sys", WS, WE)
        assert r["n_workload_samples"] == 3
        assert r["rejected_workload_rows"] == 0
        assert r["workload_dqi"] == 1.0
        assert r["system_boundary"] == "sys"


class TestFailClosed:
    def test_too_few_samples_flags(self):
        r = normalize_impact(IMPACT, [], "u", "sys", WS, WE)
        assert r["status"] == NOT_NORMALIZED
        assert r["flags"] == ["TOO_FEW_WORKLOAD_SAMPLES"]
        assert "saved_per_workload_unit" not in r

    def test_naive_timestamp_rejected(self):
        r = normalize_impact(IMPACT, _rows(1.0, 2.0, ts="2026-11-24T11:00:00"), "u", "s", WS, WE)
        assert r["status"] == NOT_NORMALIZED
        assert r["rejected_workload_rows"] == 2

    def test_naive_window_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0), "u", "s", "2026-11-24T10:00:00", WE)

    def test_zero_denominator_rejected(self):
        rows = [{"timestamp": WS, "value": 0.0, "source_type": "direct_sensor"}]
        r = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        assert r["status"] == NOT_NORMALIZED
        assert r["n_workload_samples"] == 0
        assert r["rejected_workload_rows"] == 1

    def test_negative_denominator_rejected(self):
        rows = [{"timestamp": WS, "value": -2.0, "source_type": "estimated"}]
        r = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        assert r["status"] == NOT_NORMALIZED

    def test_non_finite_denominator_rejected(self):
        rows = [{"timestamp": WS, "value": "inf", "source_type": "direct_sensor"}]
        r = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        assert r["status"] == NOT_NORMALIZED

    def test_unknown_source_type_rejected(self):
        r = normalize_impact(IMPACT, _rows(1.5, 2.5, source="guessed"), "u", "s", WS, WE)
        assert r["status"] == NOT_NORMALIZED
        assert r["rejected_workload_rows"] == 2

    def test_out_of_window_rejected(self):
        rows_in_1 = {"timestamp": "2026-11-24T11:00:00+00:00", "value": 3.0, "source_type": "calculated"}
        rows_in_2 = {"timestamp": "2026-11-24T11:30:00+00:00", "value": 5.0, "source_type": "calculated"}
        rows_out = {"timestamp": "2026-11-24T13:00:00+00:00", "value": 5.0, "source_type": "calculated"}
        r = normalize_impact(IMPACT, [rows_in_1, rows_in_2, rows_out], "u", "s", WS, WE)
        assert r["n_workload_samples"] == 2
        assert r["rejected_workload_rows"] == 1
        assert r["status"] == NORMALIZED

    def test_empty_workload_unit_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0, 2.0), "  ", "s", WS, WE)

    def test_empty_boundary_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0, 2.0), "u", "", WS, WE)

    def test_invalid_window_order_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0, 2.0), "u", "s", WE, WS)

    def test_bad_min_samples_param_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0, 2.0), "u", "s", WS, WE, min_workload_samples=0)
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, _rows(1.0, 2.0), "u", "s", WS, WE, min_workload_samples=True)

    def test_min_samples_param_respected(self):
        rows = _rows(1.0)
        r_default = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        assert r_default["status"] == NOT_NORMALIZED
        r_small = normalize_impact(IMPACT, rows, "u", "s", WS, WE, min_workload_samples=1)
        assert r_small["status"] == NORMALIZED
        assert r_small["min_workload_samples"] == 1
        assert MIN_WORKLOAD_SAMPLES == 2
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, rows, "u", "s", WS, WE, min_workload_samples=0)

    def test_impact_not_dict_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact([IMPACT], _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_impact_missing_saved_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact({"unit": "kWh"}, _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_quarantined_impact_cannot_be_normalized(self):
        impact = dict(IMPACT, status="QUARANTINE")
        with pytest.raises(WorkloadNormError, match="cannot be normalized"):
            normalize_impact(impact, _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_unknown_or_missing_impact_status_cannot_be_normalized(self):
        for status in (None, "UNKNOWN", "INDEPENDENTLY_VERIFIED"):
            impact = dict(IMPACT, status=status)
            with pytest.raises(WorkloadNormError, match="cannot be normalized"):
                normalize_impact(impact, _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_impact_status_must_match_direction(self):
        valid_with_nonpositive = dict(IMPACT, status="VALID", saved_per_sample=0.0)
        no_improvement_with_positive = dict(IMPACT, status="NO_IMPROVEMENT", saved_per_sample=1.0)
        with pytest.raises(WorkloadNormError, match="VALID impact"):
            normalize_impact(valid_with_nonpositive, _rows(1.0, 2.0), "u", "s", WS, WE)
        with pytest.raises(WorkloadNormError, match="NO_IMPROVEMENT impact"):
            normalize_impact(no_improvement_with_positive, _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_impact_bool_saved_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(dict(IMPACT, saved_per_sample=True), _rows(1.0, 2.0), "u", "s", WS, WE)

    def test_workload_rows_not_list_rejected(self):
        with pytest.raises(WorkloadNormError):
            normalize_impact(IMPACT, "nope", "u", "s", WS, WE)

    def test_no_aggregation_only_single_record(self):
        r = normalize_impact(IMPACT, _rows(2.0, 2.0), "u", "s", WS, WE)
        assert isinstance(r.get("saved_per_workload_unit"), float)
        assert "sum" not in json.dumps(r).lower()


class TestDqiReuse:
    def test_mixed_source_confidence_lowers_dqi(self):
        rows = [
            {"timestamp": WS, "value": 2.0, "source_type": "direct_sensor"},
            {"timestamp": WE, "value": 4.0, "source_type": "estimated"},
        ]
        r = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        # completeness 1.0, confidence mean (1.00 + 0.70) / 2 = 0.85
        assert r["workload_dqi"] == pytest.approx(0.85)

    def test_rejected_rows_lower_dqi(self):
        rows = [
            {"timestamp": WS, "value": 2.0, "source_type": "direct_sensor"},
            {"timestamp": WS, "value": "bad", "source_type": "direct_sensor"},
        ]
        r = normalize_impact(IMPACT, rows, "u", "s", WS, WE)
        assert r["workload_dqi"] == pytest.approx(0.5)


class TestCli:
    def _run(self, tmp_path, impact, workload_csv, extra):
        impact_file = tmp_path / "impact.json"
        impact_file.write_text(json.dumps(impact), encoding="utf-8")
        wl_file = tmp_path / "wl.csv"
        wl_file.write_text(workload_csv, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "controller" / "workload_norm.py"),
             "--impact-json", str(impact_file), "--workload-csv", str(wl_file),
             "--workload-unit", "h", "--system-boundary", "sys",
             "--window-start", WS, "--window-end", WE] + extra,
            capture_output=True, text=True, cwd=str(ROOT),
        )
        return proc

    def test_cli_exit0_valid(self, tmp_path):
        csv_data = "timestamp,value,source_type\n2026-11-24T11:00:00+00:00,5.0,direct_sensor\n2026-11-24T11:30:00+00:00,5.0,direct_sensor\n"
        proc = self._run(tmp_path, IMPACT, csv_data, [])
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["status"] == NORMALIZED
        assert payload["saved_per_workload_unit"] == pytest.approx(2.4)

    def test_cli_exit1_too_few(self, tmp_path):
        csv_data = "timestamp,value,source_type\n"
        proc = self._run(tmp_path, IMPACT, csv_data, [])
        assert proc.returncode == 1

    def test_cli_exit2_on_bad_json(self, tmp_path):
        impact_file = tmp_path / "impact.json"
        impact_file.write_text("{not json", encoding="utf-8")
        wl_file = tmp_path / "wl.csv"
        wl_file.write_text("timestamp,value,source_type\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "controller" / "workload_norm.py"),
             "--impact-json", str(impact_file), "--workload-csv", str(wl_file),
             "--workload-unit", "h", "--system-boundary", "s",
             "--window-start", WS, "--window-end", WE],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert proc.returncode == 2

    def test_cli_script_shadow_survives(self, tmp_path):
        """Direkter Skriptstart aus dem controller/-Ordner (#460-Lektion)."""
        csv_data = "timestamp,value,source_type\n2026-11-24T11:00:00+00:00,6.0,direct_sensor\n2026-11-24T11:30:00+00:00,6.0,direct_sensor\n"
        impact_file = tmp_path / "impact.json"
        impact_file.write_text(json.dumps(IMPACT), encoding="utf-8")
        wl_file = tmp_path / "wl.csv"
        wl_file.write_text(csv_data, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "workload_norm.py",
             "--impact-json", str(impact_file), "--workload-csv", str(wl_file),
             "--workload-unit", "h", "--system-boundary", "s",
             "--window-start", WS, "--window-end", WE],
            capture_output=True, text=True, cwd=str(ROOT / "controller"),
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["status"] == NORMALIZED
