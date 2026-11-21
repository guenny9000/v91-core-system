#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Digitale und kryptografische Autarkie (MAX-BEST Datensatz 7, VIBE-XXVIII).

SIMULATION_ONLY: Dieses Modul bewertet reine Beschreibungs-Snapshots
(NodeSnapshot) und fuehrt NIE echte Eingriffe aus: keine Schluessel-
loeschung, keine Sperrung produktiver Zugaenge, keine Fremdsysteme.

REUSE (NO_DUPLICATE_SYSTEMS): Statusmodell und Bericht kommen aus
controller/impact_area_registry.py (BELEGT / NICHT_GEPRUEFT /
NICHT_VERFUEGBAR). Lokale Autarkie-Kennzahlen bleiben in
autarky_metrics.py (Issue #83); Wiederherstellung im Feld zielt auf
ledger_recovery.py und encrypted_store.py. Dieses Modul ordnet nur ein.

Fuer Max-Best-Regeln kodiert:
- Jeder Knoten verwaltet seine eigenen Schluessel und Ressourcen.
- Kein zentraler Schluessel darf alle Knoten beherrschen.
- Schluesselrotation und Widerruf muessen getestet sein.
- Wiederherstellung darf keine alten Rechte unkontrolliert
  wiederherstellen.
- Ein erfolgreicher Test ist kein Beweis fuer globale Autarkie
  (SIMULATION != BETRIEB; TEST != PROOF; UNKNOWN != PASS).

Honest limits: BELEGT ist Beleg-Nachweis, kein Wahrheitsbeweis
(SOURCE != TRUTH); ASSESSMENT != AUTHORIZATION.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from controller.impact_area_registry import (
    Area,
    EvidenceBundle,
    IndicatorDefinition,
    IndicatorStatus,
    MeasurementClaim,
    MeasurementScope,
    UnavailableClaim,
    registry_report,
)


class DigitalAutarkyError(RuntimeError):
    """Fail-closed: unzulaessige Nutzung des Pruefmoduls."""


@dataclass(frozen=True)
class NodeSnapshot:
    """Reine Beschreibung eines Knotens. Keine Secrets (PII-Gate)."""
    node_id: str
    offline_core_functions: tuple[str, ...] = ()
    cloud_dependencies: tuple[str, ...] = ()
    owns_keys: bool = False
    key_rotation_tested: bool = False
    recovery_plan: str = ""
    recovery_preserves_revocations: bool = False
    alt_comm_channels: tuple[str, ...] = ()
    restored_backup_evidence: tuple[str, ...] = ()
    identity_revocation_path: bool = False
    node_isolation_possible: bool = False
    software_supply_verification: bool = False
    measured_recovery_seconds: Optional[float] = None


@dataclass(frozen=True)
class ProbeResult:
    probe: str
    status: IndicatorStatus
    problems: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def _node_ok(snapshot: NodeSnapshot) -> None:
    if not isinstance(snapshot, NodeSnapshot):
        raise DigitalAutarkyError("snapshot must be a NodeSnapshot")
    if not isinstance(snapshot.node_id, str) or not snapshot.node_id.strip():
        raise DigitalAutarkyError("node_id missing (anonym, kein Secret)")


def probe_cloud_outage(snapshot: NodeSnapshot) -> ProbeResult:
    """Dry-Run 1: Laeuft der Knoten ohne externe Cloud weiter?"""
    _node_ok(snapshot)
    problems: list[str] = []
    if not snapshot.offline_core_functions:
        problems.append("keine offline-faehigen Kernfunktionen beschrieben")
    if not snapshot.owns_keys:
        problems.append("Kernfunktionen haengen an fremder Schluesselverwaltung")
    if problems:
        return ProbeResult("cloud_outage", IndicatorStatus.NICHT_GEPRUEFT, tuple(problems))
    return ProbeResult("cloud_outage", IndicatorStatus.BELEGT,
                       notes=tuple(snapshot.offline_core_functions))


def probe_key_loss(snapshot: NodeSnapshot) -> ProbeResult:
    """Dry-Run 2: Geprueftes Wiederherstellungsverfahren nach Schluesselverlust."""
    _node_ok(snapshot)
    problems: list[str] = []
    if not snapshot.owns_keys:
        problems.append("Knoten verwaltet keine eigenen Schluessel")
    if not snapshot.key_rotation_tested:
        problems.append("Schluesselrotation nicht getestet")
    if not snapshot.recovery_plan.strip():
        problems.append("kein dokumentiertes Wiederherstellungsverfahren")
    if not snapshot.recovery_preserves_revocations:
        problems.append("Rueckstellung unkontrolliert (KEINE_ALTE_RECHTE)")
    if problems:
        return ProbeResult("key_loss", IndicatorStatus.NICHT_GEPRUEFT, tuple(problems))
    return ProbeResult("key_loss", IndicatorStatus.BELEGT)


def probe_network_isolation(snapshot: NodeSnapshot) -> ProbeResult:
    """Dry-Run 3: Lokale Entscheidungen und Ausweichkommunikation."""
    _node_ok(snapshot)
    problems: list[str] = []
    if not snapshot.offline_core_functions:
        problems.append("keine lokalen Entscheidungen ohne Netz")
    if not snapshot.alt_comm_channels:
        problems.append("keine alternativen Kommunikationswege")
    if problems:
        return ProbeResult("network_isolation", IndicatorStatus.NICHT_GEPRUEFT, tuple(problems))
    return ProbeResult("network_isolation", IndicatorStatus.BELEGT,
                       notes=tuple(snapshot.alt_comm_channels))


def probe_compromised_identity(snapshot: NodeSnapshot) -> ProbeResult:
    """Dry-Run 4: Isolation EINES Knotens ohne unnoetige Beeintraechtigung."""
    _node_ok(snapshot)
    problems: list[str] = []
    if not snapshot.identity_revocation_path:
        problems.append("kein unabhaengiger Widerrufs- und Pruefpfad")
    if not snapshot.node_isolation_possible:
        problems.append("Knoten nicht isolierbar")
    if problems:
        return ProbeResult("compromised_identity", IndicatorStatus.NICHT_GEPRUEFT, tuple(problems))
    return ProbeResult("compromised_identity", IndicatorStatus.BELEGT)


def probe_restart_integrity(snapshot: NodeSnapshot) -> ProbeResult:
    """Dry-Run 5: Wiederanlauf mit Datenintegritaet und getesteten Backups."""
    _node_ok(snapshot)
    problems: list[str] = []
    if not snapshot.restored_backup_evidence:
        problems.append("keine geprueften (wiederhergestellten) Sicherungskopien")
    if not snapshot.recovery_preserves_revocations:
        problems.append("Wiederherstellung ohne Revocations-Pruefung")
    secs = snapshot.measured_recovery_seconds
    if secs is None or isinstance(secs, bool) or not isinstance(secs, (int, float)) \
            or not math.isfinite(float(secs)) or float(secs) < 0:
        problems.append("keine tatsaechlich gemessene Wiederanlaufzeit")
    if problems:
        return ProbeResult("restart_integrity", IndicatorStatus.NICHT_GEPRUEFT, tuple(problems))
    return ProbeResult("restart_integrity", IndicatorStatus.BELEGT,
                       notes=("measured_recovery_seconds=%.3f" % float(secs),))


DIGITAL_AUTARKY_REGISTRY: tuple[IndicatorDefinition, ...] = (
    IndicatorDefinition("key_custody_independence_share", Area.AUTARKIE,
                        "Anteil unabhaengig verwalteter Schluessel je Knoten",
                        "share_0_1", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("key_loss_recovery_proven", Area.AUTARKIE,
                        "Erfolgreiche Wiederherstellung nach simuliertem Schluesselverlust",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("core_functions_without_cloud", Area.AUTARKIE,
                        "Kritische Funktionen ohne externe Cloud",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("alt_comm_availability", Area.AUTARKIE,
                        "Verfuegbarkeit alternativer Kommunikationswege",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("restored_backup_proven", Area.AUTARKIE,
                        "Wiederherstellung gepruefter Sicherungskopien",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("identity_revocation_independent", Area.AUTARKIE,
                        "Unabhaengige Pruefung und Widerruf kompromittierter Identitaeten",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("software_supply_verifiable", Area.AUTARKIE,
                        "Verifizierbare Herkunft, Signaturen und Aktualisierungen",
                        "boolean", MeasurementScope.LOCAL_HOST),
    IndicatorDefinition("measured_restart_time", Area.AUTARKIE,
                        "Tatsaechlich gemessene Wiederherstellungszeit",
                        "seconds", MeasurementScope.LOCAL_HOST),
)


def assert_no_master_key(custody: Mapping[str, Sequence[str]]) -> None:
    """Kein zentraler Schluessel darf alle Knoten beherrschen (fail-closed)."""
    if not isinstance(custody, Mapping) or not custody:
        raise DigitalAutarkyError("custody must be a non-empty mapping")
    holders: dict[str, int] = {}
    for node, keys in custody.items():
        if not isinstance(node, str) or not node.strip():
            raise DigitalAutarkyError("node names must be non-empty strings")
        if not isinstance(keys, (list, tuple)) or not keys:
            raise DigitalAutarkyError("each node must reference at least one key")
        for key in keys:
            if not isinstance(key, str) or not key.strip():
                raise DigitalAutarkyError("key ids must be non-empty strings")
            holders[key] = holders.get(key, 0) + 1
    total = len(custody)
    shared = [key for key, count in holders.items() if count == total]
    if shared:
        raise DigitalAutarkyError(
            "central master key(s) control every node: %s" % sorted(shared))


def digital_autarky_report(snapshot: NodeSnapshot) -> dict:
    """Vollstaendiger Bericht nach dem gemeinsamen Statusmodell (REUSE).

    Alle Werte stammen aus dem SIMULATION_ONLY-Dry-Run; nichts hier wurde
    am laufenden System veraendert (SIMULATION != BETRIEB).
    """
    _node_ok(snapshot)
    evidence = EvidenceBundle(
        source="node:" + snapshot.node_id.strip(),
        method="simulation_only:dry_run_snapshot",
        period_start="2026-11-21T00:00:00Z",
        period_end="2026-11-21T23:59:59Z",
        reference="MAX-BEST Datensatz 7",
    )
    cloud = probe_cloud_outage(snapshot)
    keys = probe_key_loss(snapshot)
    net = probe_network_isolation(snapshot)
    ident = probe_compromised_identity(snapshot)
    restart = probe_restart_integrity(snapshot)

    def belegt() -> MeasurementClaim:
        return MeasurementClaim(1.0, "boolean", evidence)
    def open_() -> UnavailableClaim:
        return UnavailableClaim("nicht simuliert-lieferbar; Pruefling fehlt")

    submissions = {
        "key_custody_independence_share":
            belegt() if snapshot.owns_keys else open_(),
        "key_loss_recovery_proven":
            belegt() if keys.status == IndicatorStatus.BELEGT else open_(),
        "core_functions_without_cloud":
            belegt() if cloud.status == IndicatorStatus.BELEGT else open_(),
        "alt_comm_availability":
            belegt() if net.status == IndicatorStatus.BELEGT else open_(),
        "restored_backup_proven":
            belegt() if restart.status == IndicatorStatus.BELEGT else open_(),
        "identity_revocation_independent":
            belegt() if ident.status == IndicatorStatus.BELEGT else open_(),
        "software_supply_verifiable":
            belegt() if snapshot.software_supply_verification else open_(),
        "measured_restart_time":
            MeasurementClaim(float(snapshot.measured_recovery_seconds), "seconds", evidence)
            if restart.status == IndicatorStatus.BELEGT else open_(),
    }
    report = registry_report(list(DIGITAL_AUTARKY_REGISTRY), submissions)
    report["probes"] = {
        result.probe: {"status": result.status.value,
                      "problems": list(result.problems),
                      "notes": list(result.notes)}
        for result in (cloud, keys, net, ident, restart)
    }
    report["simulation_only"] = True
    report["honest_limits"] = report["honest_limits"] + (
        "SIMULATION != BETRIEB: Dry-Run-Snapshot, kein reales Systemereignis.",
        "Erfolgreicher Test ist kein Beweis globaler Autarkie (TEST != PROOF).",
    )
    return report
