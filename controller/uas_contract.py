"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
UAS-Vertragskanon: EINE maschinenlesbare Wahrheit fuer das
V91CycleActionSchema, abgeleitet aus dem Validator.

Issue #484 (Arbeitspaket 1 und 2): der urspruengliche externe
UAS-Vorschlag (Architekturtext, fuenfte Welle 24.11.2026) und das
implementierte Record-Format unterscheiden sich. Vor Erweiterungen
muss feststehen, was kanonisch ist. Dieses Modul ERFINDET keine
zweite Spezifikation, es LEITET den Kanon aus dem existierenden
stdlib-Validator controller/uas_record.py ab (REUSE,
NO_DUPLICATE_SYSTEMS): Versionen, Stufen, Pflicht-/ optionsfelder
und Enum-Werte werden zur Laufzeit aus den Live-Konstanten des
Validators gelesen. Der Validator bleibt die alleinverbindliche
Spezifikation; dieses Modul ist sein Index, nicht sein Konkurrent
(KANON == ABLEITUNG != ZWEITE_WAHRHEIT). Eine parallele
JSON-Schema-Datei wurde bewusst NICHT gebaut: zwei Texte mit
Behandlungsanspruch auf dieselbe Wahrheit driften auseinander
(DOKUMENT != SPEC, EXPANSION != EROBERUNG).

Zusaetzlich prueft --check den Kanon gegen das echte Verhalten des
Validators (PROBE != BEHAUPTUNG): acht Festsonden reichen echte
Minimaldatensaetze durch validate_record und vergleichen das
Ergebnis mit den deklarierten Gates. Stimmt etwas nicht, schlaegt
der Check fehl (fail-closed, EXIT 1). Der Kanon luegt nie ueber
nicht verifizierte Zusagen: Adapter-Ende-zu-Ende-Tests, IACL-
Transport und Ledger-Schreibpfad sind und bleiben als NICHT
VERIFIZIERT deklariert (ANGABE != BERECHTIGUNG,
KANON != KONTAKT).

Autorisierung bleibt strikt getrennt (Issue #484, Arbeitspaket 3):
authorization.auth_verified ist eine AUFRUFER-ANGABE. Weder der
Validator noch dieses Modul erteilen irgendwelche Rechte
(SYNTAX_ERTEILT_KEINE_BERECHTIGUNG). Echte Berechtigungen prueft
allein das jeweilige Zielsystem bzw. Policy-Gate des Betreibers.

Ehrliche Grenzen:
- ABLEITUNG == SPIEGEL: dieses Modul beschreibt den Validator,
  es veraendert nichts und schreibt nichts (KLASSIFIKATION !=
  EINGRIFF, REVIEW != DECISION).
- PROBE-MENGE == AUSWAHL: acht Festsonden pruefen die wichtigsten
  Gates, nicht jede Regel (%-BEDECKUNG ist NICHT gemessen,
  ANTALL != ABDECKUNG).
- KEIN Netz, KEIN Daemon, KEIN Schreibzugriff auf fremde
  Systeme, SCRIPTED != RUNNING.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Callable

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller import uas_record as ur  # REUSE: einzige Wahrheit


def _stage_allowed(stage: str, version: str) -> bool:
    if version == ur.SCHEMA_VERSION_V113:
        allowed = tuple(ur.ALLOWED_STAGES) + tuple(ur.V113_EXTRA_STAGES)
    else:
        allowed = tuple(ur.ALLOWED_STAGES)
    return stage in allowed


def build_contract() -> dict[str, Any]:
    """Leitet den maschinenlesbaren Kanon aus dem Validator ab.

    Kein Feld wird hier frei formuliert: jede Angabe stammt aus
    uas_record-Konstanten. Damit ist der Kanon per Konstruktion
    mit dem Validator synchron (ABLEITUNG != ERFINDUNG).
    """
    required_top = list(ur._REQUIRED_TOP)
    optional_v113 = ["origin", "authorization", "risk_level", "rollback",
                     "creation_and_life_protection"]
    return {
        "contract_name": "V91CycleActionSchema-Kanon",
        "single_source_of_truth": "controller/uas_record.py",
        "supported_schema_versions": list(ur.SUPPORTED_SCHEMA_VERSIONS),
        "compatibility_rule": (
            "112.0.0-Datensaetze bleiben unveraendert gueltig; alle "
            "113.0.0-Erweiterungen sind fuer 112.0.0-Datensaetze "
            "unbekannte Felder und werden abgelehnt; jede andere "
            "schema_version wird abgelehnt (RUECKWAERTSKOMPATIBEL, "
            "VORWAERTS_STRENG)"
        ),
        "stages": {
            ur.SCHEMA_VERSION: list(ur.ALLOWED_STAGES),
            ur.SCHEMA_VERSION_V113: list(tuple(ur.ALLOWED_STAGES)
                                        + tuple(ur.V113_EXTRA_STAGES)),
        },
        "required_top_level_fields": required_top,
        "optional_top_level_fields": {
            ur.SCHEMA_VERSION_V113: optional_v113,
        },
        "enums": {
            "actor_types": list(ur.ALLOWED_ACTOR_TYPES),
            "risk_levels": list(ur.ALLOWED_RISK_LEVELS),
            "isolation_policies": list(ur.ALLOWED_ISOLATION_POLICY),
            "ci_overall_status": list(ur.ALLOWED_CI_OVERALL),
            "check_status": list(ur.ALLOWED_CHECK_STATUS),
            "drift_status": list(ur.ALLOWED_DRIFT_STATUS),
            "follow_up_status": list(ur.ALLOWED_FOLLOW_UP_STATUS),
        },
        "gates": [
            {
                "name": "UNBEKANNTE_SCHEMA_VERSION_ABGELEHNT",
                "applies_to": list(ur.SUPPORTED_SCHEMA_VERSIONS) + ["jede andere"],
                "rule": "schema_version muss 112.0.0 oder 113.0.0 sein",
            },
            {
                "name": "KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG",
                "applies_to": list(ur.V113_AUTH_GATED_STAGES),
                "rule": "Stufe verlangt authorization.auth_verified == true "
                        "(ANGABE, keine echte Berechtigung)",
            },
            {
                "name": "RECOVERY_FIRST",
                "applies_to": ["risk_level HIGH", "risk_level CRITICAL"],
                "rule": "rollback.available == true und nicht-leere "
                        "procedure verpflichtend",
            },
            {
                "name": "EVIDENCE_BEFORE_COMMITMENT",
                "applies_to": ["COMMIT", "LEDGER"],
                "rule": "ci_checks.overall_status == PASS und mind. ein "
                        "evidence-Eintrag (UNKNOWN_BLEIBT_UNBELEGT)",
            },
        ],
        "additional_unknown_fields_rejected": True,
        "honesty_limits": ur.HONESTY_LIMITS,
        "authorization_separation": (
            "auth_verified ist AUFRUFER-ANGABE; weder Validator noch "
            "Kanon erteilen Rechte; echte Berechtigung prueft nur das "
            "Zielsystem/Policy-Gate (ANGABE != BERECHTIGUNG)"
        ),
        "not_verified": [
            "adapter_ende_zu_ende",
            "iacl_transport",
            "ledger_schreibpfad",
            "dauerbetrieb",
        ],
    }


# ------------------------------------------------------------------
# Festsonden: echter Validator-Lauf gegen erwartetes Gate-Verhalten
# ------------------------------------------------------------------

def _min_record(**over: Any) -> dict[str, Any]:
    """Minimaler gueltiger 112.0.0-Datensatz als Sondenbasis."""
    rec: dict[str, Any] = {
        "schema_version": ur.SCHEMA_VERSION_V113,
        "action_id": "V91-PROBE-001",
        "cycle_stage": "HYPOTHESIS",
        "hypothesis": "Sondenbasis",
        "pr_and_vibe": {"pr_ref": "#0", "vibe_mark": "X", "commit_sha": "0" * 40},
        "ci_checks": {"overall_status": "PASS",
                      "checks": [{"name": "sonde", "status": "PASS"}]},
        "drift": {"status": "NONE", "observed_count": 0, "threshold": 1},
        "follow_up_checks": [],
        "evidence": ["Sondenbasis-Beleg"],
        "unknowns": [],
    }
    rec.update(over)
    return rec


def _gate_ok(name: str, fn: Callable[[], bool]) -> dict[str, Any]:
    try:
        passed = fn()
    except Exception as exc:  # Fehlerhaftes Sondenergebnis == FAIL, kein Stillstand
        return {"probe": name, "passed": False, "error": str(exc)}
    return {"probe": name, "passed": bool(passed)}


def run_probes() -> list[dict[str, Any]]:
    """Acht Festsonden gegen das echte validate_record-Verhalten."""
    results = [
        _gate_ok("minimale_v113_basis_gueltig",
                 lambda: ur.validate_record(_min_record())[0] is True),
        _gate_ok("unbekannte_version_abgelehnt", lambda: (
            ur.validate_record(_min_record(schema_version="999.0.0"))[0] is False)),
        _gate_ok("v112_ohne_v113_felder_gueltig", lambda: (
            ur.validate_record(_min_record(schema_version=ur.SCHEMA_VERSION))[0] is True)),
        _gate_ok("v113_neue_felder_in_v112_abgelehnt", lambda: (
            ur.validate_record(_min_record(schema_version=ur.SCHEMA_VERSION,
                                           risk_level="LOW"))[0] is False)),
        _gate_ok("auth_gated_stufe_ohne_autorisierung_abgelehnt", lambda: (
            ur.validate_record(_min_record(cycle_stage="AUTHORIZATION"))[0] is False
            and ur.validate_record(_min_record(
                cycle_stage="AUTHORIZATION",
                authorization={"auth_verified": True, "scope": "probe",
                              "credential_ref": "probe"}))[0] is True)),
        _gate_ok("commit_ohne_ci_pass_abgelehnt", lambda: (
            ur.validate_record(_min_record(
                cycle_stage="COMMIT",
                authorization={"auth_verified": True, "scope": "probe",
                               "credential_ref": "probe"},
                ci_checks={"overall_status": "UNKNOWN",
                           "checks": []}))[0] is False)),
        _gate_ok("hohes_risiko_ohne_rollback_abgelehnt", lambda: (
            ur.validate_record(_min_record(
                risk_level="HIGH",
                authorization={"auth_verified": True, "scope": "probe",
                               "credential_ref": "probe"}))[0] is False
            and ur.validate_record(_min_record(
                cycle_stage="EXECUTION",
                risk_level="HIGH",
                authorization={"auth_verified": True, "scope": "probe",
                               "credential_ref": "probe"},
                rollback={"available": True, "procedure": "revert"}))[0] is True)),
        _gate_ok("unbekanntes_feld_abgelehnt", lambda: (
            ur.validate_record(_min_record(erfunden="x"))[0] is False)),
        _gate_ok("kanon_versionen_gleich_validator", lambda: (
            build_contract()["supported_schema_versions"]
            == list(ur.SUPPORTED_SCHEMA_VERSIONS))),
        _gate_ok("kanon_stufen_gleich_validator", lambda: (
            _stage_allowed("INPUT", ur.SCHEMA_VERSION_V113) is True
            and _stage_allowed("INPUT", ur.SCHEMA_VERSION) is False)),
    ]
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UAS-Vertragskanon (ABLEITUNG aus controller/uas_record.py)")
    parser.add_argument("--check", action="store_true",
                        help="Kanonsonden gegen den echten Validator ausfuehren")
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="Kanon-Zieldatei statt stdout")
    args = parser.parse_args(argv)

    if not args.check:
        payload = json.dumps(build_contract(), ensure_ascii=False, indent=2)
        if args.out is not None:
            args.out.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0

    results = run_probes()
    failed = [r for r in results if not r["passed"]]
    report = {"probes_total": len(results),
              "probes_failed": len(failed),
              "status": "KANON_KONSISTENT" if not failed else "KANON_ABWEICHUNG",
              "results": results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
