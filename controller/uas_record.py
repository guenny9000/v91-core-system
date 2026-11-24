"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
UAS-Record: Validierung universeller Aktions-Datensaetze
(V91CycleActionSchema 112.0.0 und 113.0.0) als exekutierbarer Vertrag.

Erweiterung 113.0.0 (externe fuenfte/sechste Welle, Versionierung mit
Rueckwaertskompatibilitaet): zusaetzliche optionale Felder origin
(Herkunft/Urheber), authorization (mutmassliche Berechtigung als
ANGABE, nie als Zugang), risk_level und rollback. Zusaetzliche
Zyklenstufen INPUT/AUTHORIZATION/EXECUTION/FEEDBACK. Drei fail-closed
Gates nur fuer 113.0.0: RECOVERY_FIRST (HIGH/CRITICAL verlangt einen
verfuegbaren, beschriebenen Wiederherstellungsweg),
KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG (Stufen ab AUTHORIZATION verlangen
auth_verified, SYNTAX_ERTEILT_KEINE_BERECHTIGUNG) und
EVIDENCE_BEFORE_COMMITMENT (COMMIT/LEDGER verlangen CI-PASS und mind.
einen Beleg). 112.0.0-Datensaetze bleiben unveraendert gueltig; eine
unbekannte schema_version wird abgelehnt (bisherige Luecke: jede
beliebige Versionsangabe wurde akzeptiert).

Anlass ist der externe Bericht V112.0.0 'THE UNIVERSAL ACTION
SCHEMA' vom 24.11.2026 (fuenfte Welle). Tragfaehige Kernidee:
Uebergaben zwischen Agenten/Laeufen laufen nicht als freier
Fliesstext mit stillen Annahmen, sondern als schema-konformes,
maschinenpruefbares Paket (Pflichtfelder, Enum-Zustaende, getrennte
evidence/unknowns, PR-/VIBE-/CI-/Drift-Nachweise).

PRUEFBFUND vor dem Bau (CLAIM != EVIDENCE): Die Kopfzeilen des
Berichts beanspruchen perfekte Systemzustaende (Bedingung 100 %,
null Fehlerqualitaet, Software OPTIMAL, null von drei Abweichungen,
'VALID verifiziert', 'Harmonie', 'Das System ist perfekt', 'nicht
mehr an GitHub-Tokens gebunden, sondern an Syntax gebunden') - das
sind STATUS-BEHAUPTUNGEN ohne Beleg; sie werden NICHT erzeugt,
NICHT bestaetigt und NICHT als Zustand uebernommen (STATUSZEILE !=
EVIDENZ, SYNTAX ERSETZT KEINE PRUEFUNG). Der IACL-Teil (Agent A
stuetzt sich auf das Schema von Agent B) ist hier als VALIDIERER
umgesetzt; ein netzwerkfaehiger Kommunikations-Layer existiert
NICHT (KEIN ICL-TRANSPORT).

Vertrag (schema 112.0.0, exakt nach externem Entwurf):
- Pflichtfelder: schema_version, action_id, cycle_stage
  (HYPOTHESIS|SCHEMA|CODE|TEST|COMMIT|LEDGER), hypothesis,
  pr_and_vibe {pr_ref, vibe_mark, commit_sha, [next_free_vibe_mark]},
  ci_checks {overall_status PASS|FAIL|PARTIAL|PENDING|UNKNOWN,
  [head_sha], checks[{name, status PASS|FAIL|SKIPPED|UNKNOWN,
  [details]}]}, drift {status NONE|DETECTED|ISOLATED|UNKNOWN,
  observed_count int >= 0, threshold int >= 1, [affected_targets]},
  follow_up_checks[{check_id, description, status OPEN|IN_PROGRESS|
  BLOCKED|DONE, [owner], [recheck_trigger]}], evidence[], unknowns[].
- additionalProperties-fail-closed: unbekannte Felder werden auf
  JEDER Ebene REJIZIERT, leere evidence-Eintraege abgelehnt
  (BEWEIS OHNE INHALT == KEIN BEWEIS).
- Kein 'jsonschema'-Paket (pip verboten in Sandbox): die Regeln sind
  als gepruefter stdlib-Code implementiert.

Ehrliche Grenzen:
- SCHEMA-KONFORM != WAHR: Syntax-Validitaet bestaetigt NUR die Form
  des Pakets, niemals ob ein Test gruen war oder ein Dienst laeuft.
- METADATEN == AUFRUFER-ANGABE: pr_ref/commit_sha/vibe_mark werden
  formal geprueft, NICHT gegen GitHub verifiziert (keine Netz-
  Runtime, kein Daemon, SCRIPTED != RUNNING, ANGABE != BEWEIS).
- LEDGER: dieses Modul schreibt nichts, es validiert und berichtet
  (KLASSIFIKATION != EINGRIFF, REVIEW != DECISION).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

# Skript-Modus: controller/ auf sys.path[0] laesst "controller" auf
# controller/controller.py schatten (#460-Lektion).
_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SCHEMA_VERSION = "112.0.0"
SCHEMA_VERSION_V113 = "113.0.0"
SUPPORTED_SCHEMA_VERSIONS = (SCHEMA_VERSION, SCHEMA_VERSION_V113)

ALLOWED_STAGES = ("HYPOTHESIS", "SCHEMA", "CODE", "TEST", "COMMIT", "LEDGER")
V113_EXTRA_STAGES = ("INPUT", "AUTHORIZATION", "EXECUTION", "FEEDBACK")
ALLOWED_ACTOR_TYPES = ("HUMAN", "AGENT", "SYSTEM", "PIPELINE")
ALLOWED_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ALLOWED_ISOLATION_POLICY = ("ISOLATE_NOT_DESTROY", "HALT_STAGE", "RETRY_ISOLATED")
V113_AUTH_GATED_STAGES = ("AUTHORIZATION", "EXECUTION", "TEST", "COMMIT", "LEDGER")
ALLOWED_CI_OVERALL = ("PASS", "FAIL", "PARTIAL", "PENDING", "UNKNOWN")
ALLOWED_CHECK_STATUS = ("PASS", "FAIL", "SKIPPED", "UNKNOWN")
ALLOWED_DRIFT_STATUS = ("NONE", "DETECTED", "ISOLATED", "UNKNOWN")
ALLOWED_FOLLOW_UP_STATUS = ("OPEN", "IN_PROGRESS", "BLOCKED", "DONE")

_REQUIRED_TOP = (
    "schema_version",
    "action_id",
    "cycle_stage",
    "hypothesis",
    "pr_and_vibe",
    "ci_checks",
    "drift",
    "follow_up_checks",
    "evidence",
    "unknowns",
)

HONESTY_LIMITS = (
    "SCHEMA_KONFORM != WAHR, SYNTAX_ERSETZT_KEINE_PRUEFUNG, "
    "METADATEN == AUFRUFER_ANGABE != BEWEIS, STATUSZEILE != EVIDENZ, "
    "BEWEIS_OHNE_INHALT_ABGELEHNT, UNKNOWN != PASS, KEIN_ICL_TRANSPORT, "
    "KLASSIFIKATION != EINGRIFF, SCRIPTED != RUNNING, REVIEW != DECISION"
)


def _is_str(value: Any, non_empty: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    return bool(value.strip()) if non_empty else True


def _check_str(obj: dict[str, Any], key: str, errors: list[str], src: str, non_empty: bool = False) -> None:
    if not _is_str(obj.get(key), non_empty):
        errors.append(src + "." + key + " muss ein " + ("nicht-leeres " if non_empty else "") + "string sein")


def _check_str_list(obj: dict[str, Any], key: str, errors: list[str], src: str, non_empty_items: bool = False) -> None:
    val = obj.get(key)
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        errors.append(src + "." + key + " muss eine Liste aus strings sein")
        return
    if non_empty_items and any(not x.strip() for x in val):
        errors.append(src + "." + key + " enthaelt leere Eintraege (BEWEIS_OHNE_INHALT_ABGELEHNT)")


def _reject_unknown_fields(obj: dict[str, Any], allowed: set[str], errors: list[str], src: str) -> None:
    extra = set(obj.keys()) - allowed
    if extra:
        errors.append("unbekannte Felder in " + src + ": " + ", ".join(sorted(extra)))


def _validate_v113_fields(data: dict[str, Any], errors: list[str]) -> None:
    """Erweiterungen 113.0.0: Herkunft, Autorisierung, Risiko, Rueckweg.

    Gates (fail-closed, nur fuer 113.0.0-Datensaetze):
    - RECOVERY_FIRST: risk_level HIGH/CRITICAL verlangt einen
      verfuegbaren, beschriebenen Wiederherstellungsweg.
    - KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG: die Stufen ab AUTHORIZATION
      verlangen authorization.auth_verified == true (die Form eines
      Feldes erteilt keine Rechte, SYNTAX_ERTEILT_KEINE_BERECHTIGUNG;
      der Wert bleibt AUFRUFER_ANGABE, das Modul prueft keine echten
      Zugriffe).
    - EVIDENCE_BEFORE_COMMITMENT: COMMIT/LEDGER verlangen
      ci_checks.overall_status == PASS und mind. einen evidence-Eintrag
      (UNKNOWN_BLEIBT_UNBELEGT, kein Commit-Status ohne Beleg).
    """
    origin = data.get("origin")
    if origin is not None:
        if not isinstance(origin, dict):
            errors.append("root.origin muss ein Objekt sein")
        else:
            _check_str(origin, "actor_id", errors, "origin", non_empty=True)
            if origin.get("actor_type") not in ALLOWED_ACTOR_TYPES:
                errors.append("origin.actor_type ungueltig: " + repr(origin.get("actor_type")))
            _check_str(origin, "source", errors, "origin", non_empty=True)
            if "timestamp_utc" in origin:
                _check_str(origin, "timestamp_utc", errors, "origin", non_empty=True)
            _reject_unknown_fields(origin, {"actor_id", "actor_type", "source", "timestamp_utc"}, errors, "origin")

    auth = data.get("authorization")
    if auth is not None and not isinstance(auth, dict):
        errors.append("root.authorization muss ein Objekt sein")
        auth = None
    auth_verified = None
    if isinstance(auth, dict):
        auth_verified = auth.get("auth_verified")
        if not isinstance(auth_verified, bool):
            errors.append("authorization.auth_verified muss ein bool sein")
            auth_verified = None
        _check_str(auth, "scope", errors, "authorization", non_empty=True)
        _check_str(auth, "credential_ref", errors, "authorization", non_empty=True)
        if "isolation_policy" in auth and auth.get("isolation_policy") not in ALLOWED_ISOLATION_POLICY:
            errors.append("authorization.isolation_policy ungueltig: " + repr(auth.get("isolation_policy")))
        _reject_unknown_fields(auth, {"auth_verified", "scope", "credential_ref", "isolation_policy"}, errors, "authorization")

    risk = data.get("risk_level")
    if risk is not None and risk not in ALLOWED_RISK_LEVELS:
        errors.append("root.risk_level ungueltig: " + repr(risk))

    rollback = data.get("rollback")
    if rollback is not None and not isinstance(rollback, dict):
        errors.append("root.rollback muss ein Objekt sein")
        rollback = None
    if isinstance(rollback, dict):
        if not isinstance(rollback.get("available"), bool):
            errors.append("rollback.available muss ein bool sein")
        _check_str(rollback, "procedure", errors, "rollback", non_empty=True)
        _reject_unknown_fields(rollback, {"available", "procedure"}, errors, "rollback")

    if risk in ("HIGH", "CRITICAL"):
        has_recovery = (
            isinstance(rollback, dict)
            and rollback.get("available") is True
            and _is_str(rollback.get("procedure"), non_empty=True)
        )
        if not has_recovery:
            errors.append(
                "RECOVERY_FIRST: risk_level " + repr(risk) +
                " verlangt rollback.available == true und eine nicht-leere procedure")

    stage = data.get("cycle_stage")
    if stage in V113_AUTH_GATED_STAGES:
        if not isinstance(auth, dict):
            errors.append(
                "KEINE_AUSFUEHRUNG_OHNE_AUTORISIERUNG: Stufe " + repr(stage) +
                " verlangt ein authorization-Objekt")
        elif auth_verified is not True:
            errors.append(
                "SYNTAX_ERTEILT_KEINE_BERECHTIGUNG: Stufe " + repr(stage) +
                " verlangt authorization.auth_verified == true")
    if stage in ("COMMIT", "LEDGER"):
        ci = data.get("ci_checks") if isinstance(data.get("ci_checks"), dict) else {}
        if ci.get("overall_status") != "PASS":
            errors.append(
                "EVIDENCE_BEFORE_COMMITMENT: Stufe " + repr(stage) +
                " verlangt ci_checks.overall_status == PASS (UNKNOWN_BLEIBT_UNBELEGT)")
        evidence = data.get("evidence")
        if not isinstance(evidence, list) or len(evidence) == 0:
            errors.append(
                "EVIDENCE_BEFORE_COMMITMENT: Stufe " + repr(stage) +
                " verlangt mindestens einen evidence-Eintrag")


def validate_record(data: Any) -> tuple[bool, list[str]]:
    """Validiert EINEN UAS-Datensatz gegen das V91CycleActionSchema."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["root muss ein JSON-Objekt sein"]

    for field in _REQUIRED_TOP:
        if field not in data:
            errors.append("Pflichtfeld fehlt: " + field)

    _check_str(data, "schema_version", errors, "root", non_empty=True)
    schema_version = data.get("schema_version")
    is_v113 = schema_version == SCHEMA_VERSION_V113
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append("root.schema_version ungueltig (nur 112.0.0/113.0.0): " + repr(schema_version))
    allowed_top = set(_REQUIRED_TOP)
    allowed_stages = ALLOWED_STAGES
    if is_v113:
        allowed_top |= {"origin", "authorization", "risk_level", "rollback"}
        allowed_stages = ALLOWED_STAGES + V113_EXTRA_STAGES
    _reject_unknown_fields(data, allowed_top, errors, "root")

    _check_str(data, "action_id", errors, "root", non_empty=True)
    _check_str(data, "hypothesis", errors, "root", non_empty=True)
    if data.get("cycle_stage") not in allowed_stages:
        errors.append("root.cycle_stage ungueltig: " + repr(data.get("cycle_stage")))
    if is_v113:
        _validate_v113_fields(data, errors)

    prv = data.get("pr_and_vibe")
    if not isinstance(prv, dict):
        errors.append("root.pr_and_vibe muss ein Objekt sein")
    else:
        for req in ("pr_ref", "vibe_mark", "commit_sha"):
            if req not in prv:
                errors.append("pr_and_vibe." + req + " fehlt")
            else:
                _check_str(prv, req, errors, "pr_and_vibe")
        if "next_free_vibe_mark" in prv:
            _check_str(prv, "next_free_vibe_mark", errors, "pr_and_vibe")
        _reject_unknown_fields(prv, {"pr_ref", "vibe_mark", "commit_sha", "next_free_vibe_mark"}, errors, "pr_and_vibe")

    ci = data.get("ci_checks")
    if not isinstance(ci, dict):
        errors.append("root.ci_checks muss ein Objekt sein")
    else:
        if ci.get("overall_status") not in ALLOWED_CI_OVERALL:
            errors.append("ci_checks.overall_status ungueltig: " + repr(ci.get("overall_status")))
        if "head_sha" in ci:
            _check_str(ci, "head_sha", errors, "ci_checks")
        checks = ci.get("checks")
        if not isinstance(checks, list):
            errors.append("ci_checks.checks muss eine Liste sein")
        else:
            for idx, chk in enumerate(checks):
                src = "ci_checks.checks[" + str(idx) + "]"
                if not isinstance(chk, dict):
                    errors.append(src + " muss ein Objekt sein")
                    continue
                _check_str(chk, "name", errors, src, non_empty=True)
                if chk.get("status") not in ALLOWED_CHECK_STATUS:
                    errors.append(src + ".status ungueltig: " + repr(chk.get("status")))
                if "details" in chk:
                    _check_str(chk, "details", errors, src)
                _reject_unknown_fields(chk, {"name", "status", "details"}, errors, src)
        _reject_unknown_fields(ci, {"overall_status", "head_sha", "checks"}, errors, "ci_checks")

    drift = data.get("drift")
    if not isinstance(drift, dict):
        errors.append("root.drift muss ein Objekt sein")
    else:
        if drift.get("status") not in ALLOWED_DRIFT_STATUS:
            errors.append("drift.status ungueltig: " + repr(drift.get("status")))
        obs = drift.get("observed_count")
        thr = drift.get("threshold")
        if type(obs) is not int or isinstance(obs, bool) or obs < 0:
            errors.append("drift.observed_count muss int >= 0 sein")
        if type(thr) is not int or isinstance(thr, bool) or thr < 1:
            errors.append("drift.threshold muss int >= 1 sein")
        if "affected_targets" in drift:
            _check_str_list(drift, "affected_targets", errors, "drift")
        _reject_unknown_fields(drift, {"status", "observed_count", "threshold", "affected_targets"}, errors, "drift")

    fups = data.get("follow_up_checks")
    if not isinstance(fups, list):
        errors.append("root.follow_up_checks muss eine Liste sein")
    else:
        for idx, item in enumerate(fups):
            src = "follow_up_checks[" + str(idx) + "]"
            if not isinstance(item, dict):
                errors.append(src + " muss ein Objekt sein")
                continue
            _check_str(item, "check_id", errors, src, non_empty=True)
            _check_str(item, "description", errors, src, non_empty=True)
            if item.get("status") not in ALLOWED_FOLLOW_UP_STATUS:
                errors.append(src + ".status ungueltig: " + repr(item.get("status")))
            for opt in ("owner", "recheck_trigger"):
                if opt in item:
                    _check_str(item, opt, errors, src)
            _reject_unknown_fields(item, {"check_id", "description", "status", "owner", "recheck_trigger"}, errors, src)

    _check_str_list(data, "evidence", errors, "root", non_empty_items=True)
    _check_str_list(data, "unknowns", errors, "root")

    return len(errors) == 0, errors


def _iter_records(path: pathlib.Path) -> list[tuple[str, Any, str | None]]:
    """Liefert (quelle, payload, parse_fehler) je Datensatz einer Datei."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [(str(path), None, "Lesefehler: " + str(exc))]
    if path.suffix.lower() == ".jsonl":
        out: list[tuple[str, Any, str | None]] = []
        for line_no, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            src = str(path) + ":L" + str(line_no)
            try:
                out.append((src, json.loads(line), None))
            except json.JSONDecodeError as exc:
                out.append((src, None, "JSONL-Parsefehler: " + str(exc)))
        return out
    try:
        return [(str(path), json.loads(raw), None)]
    except json.JSONDecodeError as exc:
        return [(str(path), None, "JSON-Parsefehler: " + str(exc))]


def collect_target_files(target: pathlib.Path) -> list[pathlib.Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in (".json", ".jsonl"))
    return []


def batch_report(target: pathlib.Path) -> tuple[int, dict[str, Any]]:
    """Prueft Datei oder Verzeichnis, sammelt Drift + offene Punkte."""
    files = collect_target_files(target)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "target": str(target),
        "files_scanned": len(files),
        "records_total": 0,
        "records_valid": 0,
        "records_invalid": 0,
        "drift_counts": {k: 0 for k in ALLOWED_DRIFT_STATUS},
        "drift_events": [],
        "open_follow_ups": [],
        "validation_errors": [],
        "honesty_limits": HONESTY_LIMITS,
    }
    if not files:
        report["validation_errors"].append("keine .json/.jsonl-Dateien unter " + str(target))
        return 2, report

    for path in files:
        for src, payload, parse_err in _iter_records(path):
            report["records_total"] += 1
            if parse_err is not None:
                report["records_invalid"] += 1
                report["validation_errors"].append(src + " -> " + parse_err)
                continue
            ok, errs = validate_record(payload)
            if not ok:
                report["records_invalid"] += 1
                for err in errs:
                    report["validation_errors"].append(src + " -> " + err)
                continue
            report["records_valid"] += 1
            action_id = payload["action_id"]
            drift = payload["drift"]
            status = drift["status"]
            report["drift_counts"][status] = report["drift_counts"].get(status, 0) + 1
            if status != "NONE" or drift["observed_count"] > 0:
                report["drift_events"].append(
                    {"action_id": action_id, "source": src, "status": status,
                     "observed_count": drift["observed_count"], "threshold": drift["threshold"],
                     "affected_targets": drift.get("affected_targets") or []}
                )
            for chk in payload["follow_up_checks"]:
                if chk["status"] != "DONE":
                    report["open_follow_ups"].append({
                        "action_id": action_id, "check_id": chk["check_id"],
                        "status": chk["status"],
                        "owner": chk.get("owner"),
                        "description": chk["description"],
                    })
    return (0 if report["records_invalid"] == 0 else 1), report


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Validiert UAS-Datensaetze (V91CycleActionSchema 112.0.0/113.0.0), fail-closed.")
    parser.add_argument("target", help="Pfad zu .json, .jsonl oder einem Verzeichnis")
    parser.add_argument("--output", default=None, help="Optionaler JSON-Bericht-Ausgabepfad")
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    code, report = batch_report(target)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    # exit 2: Ziel unbrauchbar/leer; 1: mind. ein ungueltiger Datensatz; 0: alle konform.
    # SCHEMA_KONFORM != WAHR: der Exit-Code sagt nichts ueber die REALITAET aus.
    return code


if __name__ == "__main__":
    raise SystemExit(_cli())
