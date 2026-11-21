#!/usr/bin/env python3
"""Tests: controller/public_reporting.py (MAX-BEST, VIBE-XXXI).

Fail-closed, UNKNOWN nie PASS, keine Erfolgsquoten, keine Prozente.
Alle Beispiele sind neutral-synthetisch.
"""
from __future__ import annotations

import pytest

from controller.impact_area_registry import EvidenceBundle
from controller.public_reporting import (
    ALLOWED_LABELS,
    FORBIDDEN_TEXT_MARKERS,
    LABEL_DEPLOYED,
    LABEL_DOCUMENTED,
    LABEL_IMPLEMENTED,
    LABEL_TESTED,
    LABEL_VERIFIED,
    LABEL_ORDER,
    PublicMetric,
    PublicReportingError,
    build_public_report,
    validate_metric,
)


def _evidence(source="quelle-r", method="verfahren-r"):
    return EvidenceBundle(
        source=source,
        method=method,
        period_start="2026-11-01T00:00:00Z",
        period_end="2026-11-21T00:00:00Z",
        reference="MAX-BEST VIBE-XXXI",
    )


def _metric(**kwargs):
    defaults = dict(
        name="inventory_entries",
        value=12.0,
        unit="entries",
        label=LABEL_DOCUMENTED,
        basis="node_inventory Bestandsaufnahme (Beispiel)",
        evidence=None,
    )
    defaults.update(kwargs)
    return PublicMetric(**defaults)


def _report(metrics, limitations=("Bericht ist ein Aggregat (Beispiel)",), **kwargs):
    return build_public_report(metrics, limitations, **kwargs)


# ------------------------------------------------------------------ Guards
def test_non_sequence_metrics_raises():
    with pytest.raises(PublicReportingError):
        _report("metrics")


def test_empty_metrics_raises():
    with pytest.raises(PublicReportingError):
        _report([])


def test_empty_limitations_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric()], limitations=[])


def test_blank_limitation_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric()], limitations=[" "])


def test_non_metric_entry_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(), "eintrag"])


def test_non_numeric_value_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(value="x")])


def test_bool_value_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(value=True)])


def test_negative_value_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(value=-1.0)])


# ------------------------------------------------------------------ Labels
def test_unknown_label_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(label="SUPER")])


def test_label_order_is_honest_ladder():
    assert LABEL_ORDER == (LABEL_DOCUMENTED, LABEL_IMPLEMENTED,
                           LABEL_TESTED, LABEL_VERIFIED, LABEL_DEPLOYED)
    assert ALLOWED_LABELS == frozenset(LABEL_ORDER)


def test_verified_without_evidence_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_VERIFIED)])


def test_deployed_without_metric_evidence_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_DEPLOYED)])


def test_deployed_without_report_evidence_raises():
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_DEPLOYED, evidence=_evidence())])


def test_deployed_with_full_evidence_is_allowed():
    r = _report([_metric(label=LABEL_DEPLOYED, evidence=_evidence())],
                deployment_evidence=_evidence(source="betriebs-log"))
    assert r["metrics"][0]["label"] == LABEL_DEPLOYED
    assert r["deployment"]["claimed"] is True


def test_label_counts_separate_all_labels():
    r = _report([
        _metric(name="a", label=LABEL_DOCUMENTED),
        _metric(name="b", label=LABEL_DOCUMENTED),
        _metric(name="c", label=LABEL_IMPLEMENTED),
        _metric(name="d", label=LABEL_TESTED),
    ])
    assert r["label_counts"] == {
        LABEL_DOCUMENTED: 2, LABEL_IMPLEMENTED: 1, LABEL_TESTED: 1,
        LABEL_VERIFIED: 0, LABEL_DEPLOYED: 0,
    }


# ------------------------------------------------------------------ Privacy
def test_secret_marker_in_name_is_refused():
    with pytest.raises(PublicReportingError):
        _report([_metric(name="api_key_count")])


def test_credential_marker_in_basis_is_refused():
    with pytest.raises(PublicReportingError):
        _report([_metric(name="login_field", basis="feld enthaelt password")])


def test_email_like_identifier_in_basis_is_refused():
    with pytest.raises(PublicReportingError):
        _report([_metric(basis="kontakt unter admin@example.example")])


def test_secret_marker_in_evidence_source_is_refused():
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_VERIFIED,
                         evidence=_evidence(source="token-log"))])


# ------------------------------------------------------------------ Evidenz
def test_thin_evidence_on_verified_is_refused():
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_VERIFIED, evidence=_evidence(source=" "))])


def test_invalid_evidence_period_is_refused():
    bad = EvidenceBundle(source="q", method="v",
                         period_start="2099-01-01T00:00:00Z",
                         period_end="2000-01-01T00:00:00Z")
    with pytest.raises(PublicReportingError):
        _report([_metric(label=LABEL_VERIFIED, evidence=bad)])


def test_valid_report_has_evidence_fields_for_verified():
    r = _report([_metric(label=LABEL_VERIFIED, evidence=_evidence())])
    assert r["metrics"][0]["evidence_source"] == "quelle-r"
    assert r["metrics"][0]["evidence_method"] == "verfahren-r"


# ------------------------------------------------------------------ Inhalt
def test_report_pins_honest_limits():
    r = _report([_metric()])
    blob = str(r)
    assert "DOCUMENTED != IMPLEMENTED" in blob
    assert "VERIFIED != DEPLOYED" in blob
    assert "COUNT != IMPACT" in blob
    assert "REPORT != FREIGABE" in blob


def test_report_never_contains_success_quota_words():
    r = _report([_metric()])
    blob = str(r)
    for forbidden in ("Erfolgsquote", "erfolgsrate", "progress", "%"):
        assert forbidden not in blob
    # Der einzige erlaubte Erwaehnungsort fuer 'Zielerreichung' ist der
    # ehrliche Disclaimer, nie eine Metrik oder ein Label-Zaehler.
    for metric in r["metrics"]:
        assert "zielerreichung" not in str(metric).lower()


def test_deployment_defaults_to_not_claimed():
    r = _report([_metric()])
    assert r["deployment"] == {"claimed": False, "evidence": None}


def test_schema_is_pinned():
    assert _report([_metric()])["schema"] == "v91.public_reporting.v1"


def test_validate_metric_is_reusable():
    assert validate_metric(_metric(), None) == []
    assert validate_metric(_metric(label=LABEL_VERIFIED), None) != []


def test_deterministic_report():
    m = [_metric(), _metric(name="retired_components", value=2.0,
                            label=LABEL_TESTED)]
    assert _report(m) == _report(m)
