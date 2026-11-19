"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Wächter-Registry: setzt die 11 Wächterrollen der Global Federation
Directive (docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md) in prüfbare,
ehrliche Fähigkeitsmeldungen um. Jede Rolle wird gegen die echten
Repository-Dateien geprüft (Existenznachweis, kein Blind-Import);
Rollen ohne Implementierung bleiben ehrlich UNKNOWN ([VISION]), nie
"aktiv". Kein Daemon, kein Netzwerk, keine Ausführung von Modulen.
REGISTER != FÄHIGKEIT; FILES_PRESENT != INSTALLIERT.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


class WatcherRegistryError(Exception):
    """Fail-closed Fehler der Wächter-Registry."""


@dataclass(frozen=True)
class WatcherRole:
    role_id: str
    description: str
    module_files: tuple  # relative Pfade ab Repo-Wurzel


SECURITY = (
    "controller/secret_scan.py",
    "controller/fiction_scan.py",
    "controller/emergency_stop.py",
    "controller/update_gate.py",
)
HUMAN_RIGHTS = (
    "controller/emergency_protocol.py",
    "controller/use_policy.py",
)
FACTS = (
    "controller/evidence_report.py",
    "controller/fiction_scan.py",
    "v99/filter/source_quality.py",
)
ENERGY = (
    "controller/autarky_metrics.py",
    "controller/autarky_report.py",
    "controller/resource_admission.py",
)
ENVIRONMENT = (
    "controller/resilience_monitors.py",
    "controller/seed_inventory.py",
)
PEACE = (
    "controller/use_policy.py",
    "controller/agent_consensus.py",
)
INFRASTRUCTURE = (
    "controller/startup_check.py",
    "controller/resilience_mesh.py",
    "controller/measurement_monitor.py",
    "controller/ledger_recovery.py",
)
SELF_DIAGNOSIS = (
    "controller/startup_check.py",
    "controller/ledger_recovery.py",
    "controller/update_promotion.py",
)
FEDERATION_KNOWLEDGE = (
    "controller/peer_directory.py",
    "controller/cooperation_register.py",
    "controller/signed_heartbeat.py",
    "controller/federation_receiver.py",
    "controller/evidence_report.py",
)

# 11 Rollen exakt nach docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md Abschnitt 4.
# Leere module_files = ehrliche Lücke ([VISION]), keine Behauptung.
WATCHER_ROLES: tuple = (
    WatcherRole(
        role_id="sicherheitswaechter",
        description="Sicherheit: geheime Fundstellen, Fiktions-Marker, Notaus, signierte Updates.",
        module_files=SECURITY,
    ),
    WatcherRole(
        role_id="menschenrechtswaechter",
        description="Menschenrechte als Prüf- und Entscheidungslogik (Notfall-Rangfolge, Policy-Gate).",
        module_files=HUMAN_RIGHTS,
    ),
    WatcherRole(
        role_id="fakten_und_quellenpruefung",
        description="Fakten- und Quellenprüfung: Evidenzverträge, Fiktions-Scan, Quellen-Register.",
        module_files=FACTS,
    ),
    WatcherRole(
        role_id="energie_und_ressourcenoptimierung",
        description="Energie- und Ressourcenoptimierung aus Messwerten, nie interpoliert.",
        module_files=ENERGY,
    ),
    WatcherRole(
        role_id="wissenschafts_und_forschungsbeobachtung",
        description="Wissenschafts-/Forschungsbeobachtung: noch kein ehrlicher Baustein.",
        module_files=(),
    ),
    WatcherRole(
        role_id="umwelt_und_biodiversitaetsbeobachtung",
        description="Umwelt-/Biodiversität: Resilienz-Monitore, Saatgut-Inventar.",
        module_files=ENVIRONMENT,
    ),
    WatcherRole(
        role_id="friedens_und_diplomatiebeobachtung",
        description="Frieden: Non-Military-Policy-Gate, Konsensprüfung; Abrüstungs-Monitoring.",
        module_files=PEACE,
    ),
    WatcherRole(
        role_id="wirtschafts_und_korruptionsanalyse",
        description="Wirtschafts-/Korruptionsanalyse: noch kein ehrlicher Baustein.",
        module_files=(),
    ),
    WatcherRole(
        role_id="infrastruktur_und_ausfallschutz",
        description="Infrastruktur-/Ausfallschutz: Startup-Check, Restart-Verifier, Monitor, Recovery.",
        module_files=INFRASTRUCTURE,
    ),
    WatcherRole(
        role_id="selbstdiagnose_und_wiederherstellung",
        description="Selbstdiagnose/-Wiederherstellung: Startup-Check, Ledger-Recovery, Rollback.",
        module_files=SELF_DIAGNOSIS,
    ),
    WatcherRole(
        role_id="wissensmanagement_und_foederationskommunikation",
        description="Wissen/Föderation: Peer-Directory, Register, Heartbeats, Receiver, Evidence.",
        module_files=FEDERATION_KNOWLEDGE,
    ),
)

_ROLE_MAP: Dict = {r.role_id: r for r in WATCHER_ROLES}


def get_role(role_id: str) -> WatcherRole:
    """Rolle nach Id, fail-closed bei unbekannter Id."""
    role = _ROLE_MAP.get(role_id)
    if role is None:
        raise WatcherRegistryError(f"unknown watcher role: {role_id!r}")
    return role


def probe_role(role: WatcherRole, repo_root: Path) -> Dict:
    """Ehrliche Fähigkeitsmeldung EINER Rolle gegen den echten Dateibestand."""
    if not isinstance(repo_root, Path):
        raise WatcherRegistryError("repo_root must be a Path")
    if not role.module_files:
        return {
            "role_id": role.role_id,
            "description": role.description,
            "capability": "VISION_UNIMPLEMENTED",
            "modules_present": [],
            "modules_missing": [],
            "honest_note": "[VISION] laut Direktive; kein Baustein vorhanden, nie als aktiv melden.",
        }
    present: List = []
    missing: List = []
    for rel in role.module_files:
        target = repo_root / rel
        if target.is_file():
            present.append(rel)
        else:
            missing.append(rel)
    capability = "IMPLEMENTED_FILES_PRESENT" if present else "VISION_UNIMPLEMENTED"
    return {
        "role_id": role.role_id,
        "description": role.description,
        "capability": capability,
        "modules_present": sorted(present),
        "modules_missing": sorted(missing),
        "honest_note": (
            "FILES_PRESENT != INSTALLIERT; REGISTER != FÄHIGKEIT."
            if capability == "IMPLEMENTED_FILES_PRESENT"
            else "Kein Baustein vorhanden; ehrliche Lücke, kein Zustandsspruch."
        ),
    }


def build_report(repo_root: Path) -> Dict:
    """Gesamtbericht über alle 11 Rollen, ohne Gesund-Ansprüche."""
    roles = [probe_role(role, repo_root) for role in WATCHER_ROLES]
    unknown = [entry["role_id"] for entry in roles if entry["capability"] == "VISION_UNIMPLEMENTED"]
    return {
        "schema_version": 1,
        "directive": "docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md",
        "roles_total": len(WATCHER_ROLES),
        "roles": roles,
        "roles_unimplemented": sorted(unknown),
        "overall": (
            "PARTIAL_SOME_ROLES_UNIMPLEMENTED"
            if unknown
            else "ALL_ROLES_HAVE_FILES_PRESENT"
        ),
        "honest_limits": [
            "REGISTER != FÄHIGKEIT; Existenz einer Datei beweist keinen Betrieb.",
            "FILES_PRESENT != INSTALLIERT; SCRIPTED != INSTALLED.",
            "UNKNOWN != PASS; [VISION]-Rollen werden nie als aktiv gemeldet.",
        ],
    }


def main(argv: Optional[List] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Wächter-Registry: ehrliche Fähigkeitsmeldung der 11 Direktivrollen"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo-Wurzel (Default: zwei Ebenen über diesem Modul)",
    )
    parser.add_argument("--role", type=str, default=None, help="nur eine Rolle ausgeben")
    args = parser.parse_args(argv)

    root = args.repo_root
    if args.role is not None:
        report = probe_role(get_role(args.role), root)
    else:
        report = build_report(root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
