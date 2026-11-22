"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kreislauf-Erneute-Pruefung fuer Initiativen (VIBE-LXXIV).

Umsetzung des ERNEUTE-PRUEFUNG-Schritts aus dem verbindlichen Dokument
docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md (PR #361):
Kreislauf MOEGLICHKEIT -> PRUEFUNG -> NACHWEIS -> NUTZEN ->
MONITORING -> VERBESSERUNG -> ERNEUTE PRUEFUNG. Dieser Schritt
schliesst den Regel-Kreis (dieses Dokument, Abschnitt 1: \"Jede
Station ist Pflicht; kein UEberspringen\").

Dieses Modul prueft EINE angenommene Massnahme eines
Verbesserungsplans (PR #365) gegen NEUE, NACH dem Bewertungsschnitt
gelieferte Ledger-Evidenz (PR #363-Schema). Eine Massnahme ist nur
ERFUELLT, wenn nach dem Schnitt (--bewertet-ab) mindestens ein
messbarer Wert ihres Zielindikators den Zielwert erreicht
(MESSWERT != BEHAUPTUNG, VOLLZUG != GEMESSEN). Werte ohne
gueltiges Datum oder ohne Zahl sind KEINE Evidenz und werden
ehrlich als unbrauchbar gefuehrt (KEINE_STUMME_KORREKTUR).

Ehrliche Grenzen dieses Moduls:
- MESSWERT-WERT > ZIELWERT != URSACHE: erreicht heisst gemessen,
  nicht erklaert (TREND != URSACHE gilt weiter).
- KETTE_UNGEPRUEFT: die SHA-256-Kette des R3-Ledgers wird hier
  NICHT nachgerechnet (bleibt controller.messwerte_ingest;
  GELESEN != VERIFIZIERT).
- ERNEUTE_PRUEFUNG != FREIBRIEF: ERFUELLT schliesst keine
  Folge-Massnahme auf (REVIEW != ENTSCHEIDUNG).
- PLAN != VOLLZUG: wann die Massnahme tatsaechlich lief, weiss nur
  der Betreiber; der Beweis liegt am Datumsschnitt, nicht am Plan.
- NO_DUPLICATE_SYSTEMS: Plan-/Status-Loader und das
  Verbesserungs-Gate (ANGENOMMEN-Entscheid) werden aus
  controller.kreislauf_verbesserung, Ledger-Loader und
  KreislaufInputError aus controller.kreislauf_status REUSE
  verwendet. Keine truth-Dateien; Reports sind FIFO-Ausgabe.
- SCRIPTED != INSTALLED: kein Daemon, kein Taskplaner, kein Netz,
  keine Credentials, reine Standardbibliothek.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from controller.kreislauf_status import (
    KreislaufInputError,
    load_ledger,
)
from controller.kreislauf_verbesserung import (
    ABGELEHNT,
    ANGENOMMEN,
    assess as gate_assess,
    load_plan,
    load_status_report,
)

ERFUELLT = "ERFUELLT"
NICHT_ERFUELLT = "NICHT_ERFUELLT"
NICHT_MESSBAR = "NICHT_MESSBAR"
NICHT_PRUEFBAR = "NICHT_PRUEFBAR"

VERDICT_GESCHLOSSEN = "KREISLAUF_GESCHLOSSEN"
VERDICT_OFFEN = "KREISLAUF_OFFEN"

EXIT_GESCHLOSSEN, EXIT_OFFEN, EXIT_INPUT_ERROR = 0, 1, 3

GRENZEN = ("MESSWERT != URSACHE; VOLLZUG != GEMESSEN; KETTE_UNGEPRUEFT;"
           " ERNEUTE_PRUEFUNG != FREIBRIEF; REVIEW != ENTSCHEIDUNG;"
           " SCRIPTED != INSTALLED")


def _bewertet_ab_parsen(text: str) -> date:
    """Schnitt-Datum YYYY-MM-DD; fail-closed (SCHNITT != RATEN)."""
    try:
        stichtag = date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise KreislaufInputError(
            "bewertet-ab %r ist kein ISO-datum (YYYY-MM-DD)" % text
        ) from exc
    return stichtag


def _datum_aus_messung(text: Any) -> Optional[date]:
    """Datum einer measured_at-Angabe oder None, wenn unbrauchbar."""
    roh = str(text).strip().split("T")[0].split(" ")[0]
    try:
        return date.fromisoformat(roh)
    except ValueError:
        return None


def _neue_evidenz(entries: List[Dict[str, Any]],
                  indikator: Any,
                  stichtag: date) -> Tuple[List[float], List[str]]:
    """Nach dem Stichtag gelieferte messbare Werte EINES Indikators.

    Unbrauchbare Eintraege werden mit Grund gefuehrt, nie still
    ueberlesen (KEINE_STUMME_KORREKTUR).
    """
    werte: List[float] = []
    unbrauchbar: List[str] = []
    for entry in entries:
        if entry.get("indicator") != indikator:
            continue
        gemessen = _datum_aus_messung(entry.get("measured_at"))
        if gemessen is None:
            unbrauchbar.append(
                "eintrag %r ohne iso-datum (%r)"
                % (entry.get("value"), entry.get("measured_at")))
            continue
        if gemessen < stichtag:
            continue
        rohwert = entry.get("value")
        if isinstance(rohwert, bool) or not isinstance(rohwert, (int, float)):
            unbrauchbar.append(
                "eintrag wert %r ist keine zahl" % (rohwert,))
            continue
        werte.append(float(rohwert))
    return werte, unbrauchbar


def assess(plan: Dict[str, Any],
           status_report: Dict[str, Any],
           ledger_entries: List[Dict[str, Any]],
           stichtag: date) -> Dict[str, Any]:
    """Erneute Pruefung je Massnahme, rein aus gelieferten Daten."""
    gate = gate_assess(plan, status_report)
    massnahmen: List[Dict[str, Any]] = []
    gate_je_id = {m["id"]: m for m in gate["massnahmen"]}
    for massnahme in plan["measures"]:
        if not isinstance(massnahme, dict):
            continue
        mid = massnahme.get("id", "<ohne id>")
        gate_status = gate_je_id.get(mid, {}).get("status")
        if gate_status != ANGENOMMEN:
            massnahmen.append({
                "id": mid,
                "status": NICHT_PRUEFBAR,
                "grund": ("verbesserungs-gat lehnt die massnahme ab"
                          " (PLAN != VOLLZUG: kein ziel, keine pruefung)"),
            })
            continue
        ziel = massnahme["ziel"]
        zielwert = float(ziel["zielwert"])
        werte, unbrauchbar = _neue_evidenz(
            ledger_entries, ziel["indikator"], stichtag)
        eintrag: Dict[str, Any] = {
            "id": mid,
            "ziel_indikator": ziel["indikator"],
            "zielwert": zielwert,
            "messfenster": ziel.get("messfenster"),
            "werte_nach_stichtag": werte,
            "evidenz_stichtag": stichtag.isoformat(),
        }
        if unbrauchbar:
            eintrag["unbrauchbare_eintraege"] = unbrauchbar
        if not werte:
            eintrag["status"] = NICHT_MESSBAR
            eintrag["grund"] = (
                "kein messbarer wert nach %s (VOLLZUG != GEMESSEN)"
                % stichtag.isoformat())
        else:
            bestwert = max(werte)
            eintrag["bestwert"] = bestwert
            if bestwert >= zielwert:
                eintrag["status"] = ERFUELLT
                eintrag["grund"] = (
                    "bestwert %s >= zielwert %s nach stichtag"
                    " (MESSWERT != URSACHE)" % (bestwert, zielwert))
            else:
                eintrag["status"] = NICHT_ERFUELLT
                eintrag["grund"] = (
                    "bester messwert %s < zielwert %s"
                    % (bestwert, zielwert))
        massnahmen.append(eintrag)

    pruefbar = [m for m in massnahmen if m["status"] != NICHT_PRUEFBAR]
    erfuellt = [m for m in pruefbar if m["status"] == ERFUELLT]
    if pruefbar and len(erfuellt) == len(pruefbar):
        verdict = VERDICT_GESCHLOSSEN
    else:
        verdict = VERDICT_OFFEN
    if not pruefbar:
        grund = ("keine pruefbare massnahme: erneute pruefung ohne"
                 " angenommene massnahme ist unzulaessig"
                 " (STATION != SYMBOLIK)")
    else:
        grund = ("%d/%d massnahmen mit neuem nachweis erfuellt"
                 % (len(erfuellt), len(pruefbar)))
    return {
        "initiative_id": plan["initiative_id"],
        "verdict": verdict,
        "evidenz_stichtag": stichtag.isoformat(),
        "massnahmen_gesamt": len(massnahmen),
        "massnahmen_pruefbar": len(pruefbar),
        "massnahmen_erfuellt": len(erfuellt),
        "massnahmen": massnahmen,
        "grund": grund,
        "grenzen": GRENZEN,
    }


def format_text_report(report: Dict[str, Any]) -> str:
    """Lesbarer, ASCII-pure, deterministischer Bericht."""
    lines = [
        "V91 Kreislauf-Erneute-Pruefung (Kreislauf-Dokument PR #361)",
        "initiative : %s" % report["initiative_id"],
        "verdict    : %s" % report["verdict"],
        "stichtag   : %s" % report["evidenz_stichtag"],
        "massnahmen : %d gesamt, %d pruefbar, %d erfuellt" % (
            report["massnahmen_gesamt"],
            report["massnahmen_pruefbar"],
            report["massnahmen_erfuellt"]),
        "",
    ]
    for eintrag in report["massnahmen"]:
        lines.append("%-24s: %s" % (eintrag["id"], eintrag["status"]))
        if "grund" in eintrag:
            lines.append("    - %s" % eintrag["grund"])
        if "werte_nach_stichtag" in eintrag:
            lines.append("    - werte nach stichtag: %s" % (
                ", ".join(repr(w) for w in eintrag["werte_nach_stichtag"])
                or "keine"))
        for grund in eintrag.get("unbrauchbare_eintraege", []):
            lines.append("    - unbrauchbar: %s" % grund)
    lines.append("")
    lines.append("grund  : %s" % report["grund"])
    lines.append("grenze: %s" % report["grenzen"])
    return "\n".join(lines) + "\n"


def _write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = str(report["initiative_id"])
    (out_dir / ("kreislauf_erneute_pruefung_%s.txt" % stem)).write_text(
        format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=True) + "\n"
    (out_dir / ("kreislauf_erneute_pruefung_%s.json" % stem)).write_text(
        payload, encoding="ascii")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kreislauf-Erneute-Pruefung (advisory,"
                    " MESSWERT != URSACHE, REVIEW != ENTSCHEIDUNG)")
    parser.add_argument("plan", help="Verbesserungsplan (JSON, PR #365)")
    parser.add_argument("--status-report", required=True,
                        help="Kreislauf-Status-Report (JSON, PR #363)")
    parser.add_argument("--ledger", required=True,
                        help="R3-Ledger (JSONL) mit neuen messwerten")
    parser.add_argument("--bewertet-ab", required=True,
                        help="ISO-datum YYYY-MM-DD: erst ab diesem tag"
                             " zaehlt evidenz (VOLLZUG != GEMESSEN)")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(Path(args.plan))
        status_report = load_status_report(Path(args.status_report))
        stichtag = _bewertet_ab_parsen(args.bewertet_ab)
        entries = load_ledger(Path(args.ledger), plan["initiative_id"])
        report = assess(plan, status_report, entries, stichtag)
    except KreislaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    if report["verdict"] == VERDICT_GESCHLOSSEN:
        return EXIT_GESCHLOSSEN
    return EXIT_OFFEN


if __name__ == "__main__":
    raise SystemExit(main())
