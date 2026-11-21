#!/usr/bin/env python3
"""Tests: controller/digital_autarky_assessment.py (Datensatz 7, VIBE-XXVIII).

SIMULATION_ONLY: Alle Tests pruefen reine Snapshots, fail-closed,
UNKNOWN nie PASS, keine Erfolgsquoten.
"""
from __future__ import annotations

import pytest

from controller.digital_autarky_assessment import (
    DIGITAL_AUTARKY_REGISTRY,
    DigitalAutarkyError,
    NodeSnapshot,
    assert_no_master_key,
    digital_autarky_report,
    probe_cloud_outage,
    probe_compromised_identity,
    probe_key_loss,
    probe_network_isolation,
    probe_restart_integrity,
)
from controller.impact_area_registry import IndicatorStatus


def _full(node_id="node-a"):
    return NodeSnapshot(
        node_id=node_id,
        offline_core_functions=("ledger_verify", "quorum_eval"),
        cloud_dependencies=("none",) ,
        owns_keys=True,
        key_rotation_tested=True,
        recovery_plan="geprueftes 3-Party-Recovery, Revocations bleiben",
        recovery_preserves_revocations=True,
        alt_comm_channels=("lora", "usb-transport"),
        restored_backup_evidence=("restore-2026-11-20.log",),
        identity_revocation_path=True,
        node_isolation_possible=True,
        software_supply_verification=True,
        measured_recovery_seconds=42.5,
    )


# ------------------------------------------------------------------ Guards
def test_missing_node_id_raises():
    with pytest.raises(DigitalAutarkyError):
        probe_cloud_outage(NodeSnapshot(node_id="  "))


def test_non_snapshot_raises():
    with pytest.raises(DigitalAutarkyError):
        probe_key_loss("knoten")


# ------------------------------------------------------------- Probe 1
def test_cloud_outage_belegt_with_local_functions():
    r = probe_cloud_outage(_full())
    assert r.status == IndicatorStatus.BELEGT


def test_cloud_outage_open_without_local_functions():
    r = probe_cloud_outage(_full().replace(offline_core_functions=()))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT
    assert any("offline" in p for p in r.problems)


def test_cloud_outage_open_without_own_keys():
    r = probe_cloud_outage(_full().replace(owns_keys=False))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


# ------------------------------------------------------------- Probe 2
def test_key_loss_belegt():
    assert probe_key_loss(_full()).status == IndicatorStatus.BELEGT


def test_key_loss_open_without_rotation():
    r = probe_key_loss(_full().replace(key_rotation_tested=False))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT
    assert any("rotation" in p for p in r.problems)


def test_key_loss_open_when_revocations_not_preserved():
    r = probe_key_loss(_full().replace(recovery_preserves_revocations=False))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT
    assert any("kontrol" in p.lower() or "revoc" in p.lower() for p in r.problems)


# ------------------------------------------------------------- Probe 3
def test_network_isolation_belegt():
    r = probe_network_isolation(_full())
    assert r.status == IndicatorStatus.BELEGT
    assert "lora" in r.notes


def test_network_isolation_open_without_alt_channels():
    r = probe_network_isolation(_full().replace(alt_comm_channels=()))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


# ------------------------------------------------------------- Probe 4
def test_compromised_identity_belegt():
    assert probe_compromised_identity(_full()).status == IndicatorStatus.BELEGT


def test_compromised_identity_open_without_revocation():
    r = probe_compromised_identity(_full().replace(identity_revocation_path=False))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


def test_compromised_identity_open_without_isolation():
    r = probe_compromised_identity(_full().replace(node_isolation_possible=False))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


# ------------------------------------------------------------- Probe 5
def test_restart_integrity_belegt():
    r = probe_restart_integrity(_full())
    assert r.status == IndicatorStatus.BELEGT
    assert r.notes[0].endswith("42.500")


def test_restart_open_without_measured_time():
    r = probe_restart_integrity(_full().replace(measured_recovery_seconds=None))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT
    assert any("Wiederanlaufzeit" in p for p in r.problems)


def test_restart_open_with_negative_time():
    r = probe_restart_integrity(_full().replace(measured_recovery_seconds=-1.0))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


def test_restart_open_without_backup_evidence():
    r = probe_restart_integrity(_full().replace(restored_backup_evidence=()))
    assert r.status == IndicatorStatus.NICHT_GEPRUEFT


# -------------------------------------------------------- Master-Key-Regel
def test_master_key_across_all_nodes_rejected():
    with pytest.raises(DigitalAutarkyError):
        assert_no_master_key({"a": ("k1", "k2"), "b": ("k1", "k3"), "c": ("k1", "k4")})


def test_shared_but_not_total_key_allowed():
    assert_no_master_key({"a": ("k1", "k2"), "b": ("k1", "k3"), "c": ("k9", "k10")})


def test_empty_custody_rejected():
    with pytest.raises(DigitalAutarkyError):
        assert_no_master_key({})


def test_node_without_keys_rejected():
    with pytest.raises(DigitalAutarkyError):
        assert_no_master_key({"a": (), "b": ("k1",)})


# ------------------------------------------------------------------ Report
def test_full_report_all_belegt():
    report = digital_autarky_report(_full())
    assert report["overall_status"] == IndicatorStatus.BELEGT.value
    assert report["simulation_only"] is True


def test_empty_snapshot_report_is_open():
    report = digital_autarky_report(NodeSnapshot(node_id="node-b"))
    assert report["overall_status"] == IndicatorStatus.NICHT_GEPRUEFT.value


def test_report_lists_all_probe_results():
    report = digital_autarky_report(_full())
    assert set(report["probes"]) == {"cloud_outage", "key_loss", "network_isolation",
                                    "compromised_identity", "restart_integrity"}


def test_report_never_contains_success_quota():
    report = digital_autarky_report(_full())
    blob = str(report)
    for forbidden in ("progress", "percent", "erreichung"):
        assert forbidden not in blob


def test_registry_covers_eight_indicators():
    assert len(DIGITAL_AUTARKY_REGISTRY) == 8
    keys = [d.key for d in DIGITAL_AUTARKY_REGISTRY]
    assert len(keys) == len(set(keys))
