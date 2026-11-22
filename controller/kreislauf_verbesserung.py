"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kreislauf-Verbesserungs-Gate fuer Initiativen (VIBE-LXXI).

Umsetzung des VERBESSERUNG-Schritts aus dem verbindlichen Dokument
docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md (PR #361):
Kreislauf MOEGLICHKEIT -> PRUEFUNG -> NACHWEIS -> NUTZEN ->
MONITORING -> VERBESSERUNG -> ERNEUTE PRUEFUNG.

Dieses Modul prueft EINEN Verbesserungsplan (JSON) gegen den
gelieferten Kreislauf-Status-Report (PR #363). Eine Massnahme ist
nur ANGENOMMEN, wenn sie
(a) eine OFFENE Phase des Status-Reports adressiert (BELEGT-Phasen
    duerfen nicht luecken-erfunden werden: VALUES != URTEIL),
(b) einen Befund mit Quelle und Datum nennt (CLAIM != EVIDENCE),
(c) einen messbaren Zielindikator mit Zielwert, Messfenster und
    Zaehlmethode definiert (ZIELWERT != ERGEBNIS),
(d) eine Verantwortung benennt (PLAN != ZUFALL).
Abgelehnte Massnahmen werden mit Gruenden gesammelt, niemals
still korrigiert (KEINE_STUMME_KORREKTUR).

Ehrliche Grenzen dieses Moduls:
- PLAN != VOLLZUG: dieses Modul bewertet die STRUKTUR des Plans;
  ob die Massnahme jemals ausgefuehrt wird, ist NICHT messbar.
- REVIEW != ENTSCHEIDUNG: AKZEPTIERT autorisiert keinen Eingriff.
- NO_DUPLICATE_SYSTEMS: keine truth-Dateien; Reports sind
  FIFO-Ausgabe; Phasen-Definitionen werden aus
  controller.kreislauf_status (PR #363) REUSE-verwendet.
- SCRIPTED != INSTALLED: kein Daemon, kein Taskplaner, kein Netz,
  keine Credentials, reine Standardbibliothek.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from controller.kreislauf_status import (
    BELEGT,
    NICHT_GEPRUEFT,
    PHASEN,
    KreislaufInputError,
)

ANGENOMMEN = "ANGENOMMEN"
ABGELEHNT = "ABGELEHNT"

VERDICT_AKZEPTIERT = "AKZEPTIERT"
VERDICT_ABGELEHNT = "ABGELEHNT"

BEFUND_FIELDS = ("quelle", "datum")
ZIEL_FIELDS = ("indikator", "zielwert", "messfenster", "methode")

EXIT_AKZEPTIERT, EXIT_ABGELEHNT, EXIT_INPUT_ERROR = 0, 1, 3

GRENZEN = ("PLAN != VOLLZUG; REVIEW != ENTSCHEIDUNG; SCRIPTED != INSTALLED;"
           " KEINE_STUMME_KORREKTUR; NO_DUPLICATE_SYSTEMS")


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _load_json(path: Path, was: str) -> Any:
    """Laedt eine JSON-Datei; strikt fail-closed (SCRIPTED != GELESEN)."""
    if not path.is_file():
        raise KreislaufInputError("%s fehlt: %s" % (was, path))
    try:
        with path.open("r", encoding="ascii") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise KreislaufInputError(
            "%s kein gueltiges JSON: %s" % (was, exc)) from exc


def load_status_report(path: Path) -> Dict[str, Any]:
    """Laedt einen Kreislauf-Status-Report (PR #363); fail-closed."""
    report = _load_json(path, "status-report")
    if not isinstance(report, dict):
        raise KreislaufInputError("status-report ist kein objekt")
    if not _non_empty(report.get("initiative_id")):
        raise KreislaufInputError("status-report fehlt initiative_id")
    phasen = report.get("phasen")
    if not isinstance(phasen, dict) or not phasen:
        raise KreislaufInputError("status-report fehlt phasen")
    unbekannt = sorted(set(phasen) - set(PHASEN))
    if unbekannt:
        raise KreislaufInputError(
            "status-report enthaelt unbekannte phasen: %s"
            % ", ".join(unbekannt))
    for phase, block in sorted(phasen.items()):
        if not isinstance(block, dict) or block.get("verdict") not in (
                BELEGT, NICHT_GEPRUEFT):
            raise KreislaufInputError(
                "status-report phase %s ohne gueltiges verdict" % phase)
    return report


def load_plan(path: Path) -> Dict[str, Any]:
    """Laedt einen Verbesserungsplan; fail-closed."""
    plan = _load_json(path, "verbesserungsplan")
    if not isinstance(plan, dict):
        raise KreislaufInputError("verbesserungsplan ist kein objekt")
    if not _non_empty(plan.get("initiative_id")):
        raise KreislaufInputError("verbesserungsplan fehlt initiative_id")
    if "measures" not in plan or not isinstance(plan["measures"], list):
        raise KreislaufInputError("verbesserungsplan fehlt measures-liste")
    return plan


def _doppelte_ids(measures: List[Any]) -> set:
    """IDs, die mehrfach auftreten; KEINE zweit-registrierung."""
    zaehler: Dict[str, int] = {}
    for massnahme in measures:
        if isinstance(massnahme, dict) and _non_empty(massnahme.get("id")):
            zaehler[massnahme["id"]] = zaehler.get(
                massnahme["id"], 0) + 1
    return {mid for mid, n in zaehler.items() if n > 1}


def _pruefe_massnahme(idx: int,
                      massnahme: Any,
                      phasen: Dict[str, Any],
                      doppelte: set) -> List[str]:
    """Sammelt alle Gruende einer Ablehnung; keine stille Korrektur."""
    gruende: List[str] = []
    if not isinstance(massnahme, dict):
        return ["massnahme %d ist kein objekt" % idx]
    mid = massnahme.get("id")
    if not _non_empty(mid):
        gruende.append("massnahme %d ohne id" % idx)
        mid = "<ohne id>"
    elif mid in doppelte:
        gruende.append("doppelte id %r (keine zweit-registrierung)" % mid)

    phase = massnahme.get("phase")
    if not _non_empty(phase):
        gruende.append("%s ohne phase" % mid)
    elif phase not in PHASEN:
        gruende.append("%s phase %r nicht im kreislauf" % (mid, phase))
    elif phase not in phasen:
        gruende.append("%s phase %r nicht im status-report" % (mid, phase))
    elif phasen[phase]["verdict"] != NICHT_GEPRUEFT:
        gruende.append(
            "%s phase %r ist bereits %s: keine erfundene luecke"
            " (VALUES != URTEIL)" % (mid, phase, phasen[phase]["verdict"]))

    befund = massnahme.get("befund")
    if not isinstance(befund, dict):
        gruende.append("%s ohne befund-objekt" % mid)
    else:
        for feld in BEFUND_FIELDS:
            if not _non_empty(befund.get(feld)):
                gruende.append("%s befund ohne %s (CLAIM != EVIDENCE)"
                               % (mid, feld))

    ziel = massnahme.get("ziel")
    if not isinstance(ziel, dict):
        gruende.append("%s ohne ziel-objekt" % mid)
    else:
        for feld in ZIEL_FIELDS:
            wert = ziel.get(feld)
            if not (isinstance(wert, (int, float)) and not
                    isinstance(wert, bool)) and not _non_empty(wert):
                gruende.append("%s ziel ohne %s (ZIELWERT != ERGEBNIS)"
                               % (mid, feld))

    if not _non_empty(massnahme.get("verantwortung")):
        gruende.append("%s ohne verantwortung (PLAN != ZUFALL)" % mid)

    return gruende


def assess(plan: Dict[str, Any],
           status_report: Dict[str, Any]) -> Dict[str, Any]:
    """Verdict ueber den Verbesserungsplan, rein aus gelieferten Daten."""
    if plan["initiative_id"] != status_report["initiative_id"]:
        raise KreislaufInputError(
            "initiative_id %r passt nicht zum status-report %r"
            % (plan["initiative_id"], status_report["initiative_id"]))
    phasen = status_report["phasen"]
    doppelte = _doppelte_ids(plan["measures"])
    massnahmen: List[Dict[str, Any]] = []
    adressierte: set = set()
    for idx, massnahme in enumerate(plan["measures"]):
        gruende = _pruefe_massnahme(idx, massnahme, phasen, doppelte)
        eintrag: Dict[str, Any] = {
            "id": (massnahme.get("id") if isinstance(massnahme, dict)
                   and _non_empty(massnahme.get("id")) else
                   "<ohne id>"),
            "status": ABGELEHNT if gruende else ANGENOMMEN,
        }
        if gruende:
            eintrag["gruende"] = gruende
        else:
            adressierte.add(massnahme["phase"])
            eintrag["phase"] = massnahme["phase"]
            eintrag["ziel_indikator"] = massnahme["ziel"]["indikator"]
        massnahmen.append(eintrag)

    akzeptiert = sum(1 for m in massnahmen if m["status"] == ANGENOMMEN)
    offen_im_report = sorted(
        p for p in phasen if phasen[p]["verdict"] == NICHT_GEPRUEFT)
    unadressiert = sorted(set(offen_im_report) - adressierte)
    verdict = (VERDICT_AKZEPTIERT
               if akzeptiert == len(massnahmen) and akzeptiert > 0
               else VERDICT_ABGELEHNT)
    if not plan["measures"]:
        verdict = VERDICT_ABGELEHNT
    return {
        "initiative_id": plan["initiative_id"],
        "verdict": verdict,
        "massnahmen_gesamt": len(massnahmen),
        "massnahmen_akzeptiert": akzeptiert,
        "massnahmen": massnahmen,
        "adressierte_offene_phasen": sorted(adressierte),
        "offene_phasen_unadressiert": unadressiert,
        "grenzen": GRENZEN,
        "hinweis": ("PLAN != VOLLZUG: angenommen heisst NICHT ausgefuehrt;"
                    " ERNEUTE PRUEFUNG schuldet jeder massnahme neuen"
                    " nachweis"),
    }


def format_text_report(report: Dict[str, Any]) -> str:
    """Lesbarer, ASCII-pure, deterministischer Bericht."""
    lines = [
        "V91 Kreislauf-Verbesserungs-Gate (Kreislauf-Dokument PR #361)",
        "initiative : %s" % report["initiative_id"],
        "verdict    : %s" % report["verdict"],
        "massnahmen : %d gesamt, %d angenommen" % (
            report["massnahmen_gesamt"],
            report["massnahmen_akzeptiert"]),
        "",
    ]
    for eintrag in report["massnahmen"]:
        lines.append("%-24s: %s" % (eintrag["id"], eintrag["status"]))
        if eintrag["status"] == ABGELEHNT:
            for grund in eintrag["gruende"]:
                lines.append("    - %s" % grund)
    lines.append("")
    lines.append("adressierte offene phasen : %s" % (
        ", ".join(report["adressierte_offene_phasen"]) or "keine"))
    lines.append("offene phasen unadressiert: %s" % (
        ", ".join(report["offene_phasen_unadressiert"]) or "keine"))
    lines.append("grenze : %s" % report["grenzen"])
    lines.append("hinweis: %s" % report["hinweis"])
    return "\n".join(lines) + "\n"


def _write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = str(report["initiative_id"])
    (out_dir / ("kreislauf_verbesserung_%s.txt" % stem)).write_text(
        format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=True) + "\n"
    (out_dir / ("kreislauf_verbesserung_%s.json" % stem)).write_text(
        payload, encoding="ascii")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kreislauf-Verbesserungs-Gate (advisory,"
                    " PLAN != VOLLZUG, REVIEW != ENTSCHEIDUNG)")
    parser.add_argument("plan", help="Verbesserungsplan (JSON)")
    parser.add_argument("--status-report", required=True,
                        help="Kreislauf-Status-Report (JSON, PR #363)")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(Path(args.plan))
        status_report = load_status_report(Path(args.status_report))
        report = assess(plan, status_report)
    except KreislaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    if report["verdict"] == VERDICT_AKZEPTIERT:
        return EXIT_AKZEPTIERT
    return EXIT_ABGELEHNT


if __name__ == "__main__":
    sys.exit(main())
