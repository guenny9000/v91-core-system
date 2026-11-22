"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
MAX-BEST Legacy-Inventar, erste Stufe (VIBE-LXXVII).

Umsetzung von Akzeptanzkriterium 2 aus Issue #276 (MAX-BEST:
decentralized digital hygiene): ein READ-ONLY-Inventar und
Evidenz-Aufzeichnung VOR jeder automatisierten Remediation.
Dieses Modul inventarisiert und klassifiziert Komponenten einer
Lieferung, es fuehrt KEINE Massnahme aus (INVENTAR != REMEDIATION,
REVIEW != ENTSCHEIDUNG, REQUEST != AUTHORIZATION).

Je Komponente werden erfasst: Komponente, Kategorie (Software,
Firmware, Protokoll, Dienst, Identitaet, Privileg, Schluessel,
Datenfluss, Speicher, Abhaengigkeit, Energie, Wartung), Owner
(Pflicht), Lifecycle-Klassifikation (SUPPORTED, REPLACE, ISOLATE,
RETIRED-kandidat), Evidenz-Status (CLAIM, OBSERVED, VERIFIED,
UNKNOWN, DISPUTED) mit Quelle und Zeitpunkt sowie Grenzen.

Ehrliche Grenzen dieses Moduls:
- UNKNOWN != PASS: ein Eintrag mit Evidenz-Status UNKNOWN darf
  KEINE Lifecycle-Aussage ausser UNKNOWN treffen. Wer nichts
  belegt hat, entscheidet nichts (BEHAUPTUNG != BEFUND).
- CLAIM != VERIFIED und DISPUTED != VERIFIED: das Inventar spiegelt
  gelieferte Evidenz-Grade, es authentifiziert sie nicht
  (GELESEN != VERIFIZIERT).
- KRITISCHE_DIENSTE: Eintraege mit kritischer_dienst=JA und
  Lifecycle ISOLATE/RETIRE werden NICHT abgelehnt (das Inventar
  verhindert keine Buchung), aber als KRITISCH_WARNUNG gefuehrt.
  Isolation/Stilllegung kritischer Dienste ist ausschliesslich
  Betreiberentscheidung (HUMAN_DIGNITY und FUNDAMENTAL_RIGHTS
  bleiben harte Grenzen; ISOLATE_NOT_DESTROY).
- INVENTAR != REMEDIATION: dieses Modul enthaelt bewusst KEINE
  Ausfuehrungs-, Loesch-, Isolations- oder Aenderungsfunktion.
  Unterstuetzung liefert es nur als Struktur-Gate und Report.
- KEINE_STUMME_KORREKTUR: unbrauchbare Eintraege werden mit
  Grund gefuehrt, nie still ueberlesen oder korrigiert.
- NO_DUPLICATE_SYSTEMS: KreislaufInputError wird aus
  controller.kreislauf_status REUSE verwendet; es gibt keine
  truth-Dateien, Reports sind FIFO-Ausgabe.
- SCRIPTED != INSTALLED: kein Daemon, kein Taskplaner, kein Netz,
  keine Credentials, reine Standardbibliothek.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from controller.kreislauf_status import KreislaufInputError

FELDER = ("id", "komponente", "kategorie", "owner", "evidenz_status",
          "evidenz_quelle", "evidenz_zeitpunkt", "lifecycle",
          "kritischer_dienst", "grenzen")

# Reihenfolge: id ... grenzen; kritischer_dienst ist Pflichtfeld.

KATEGORIEN = ("SOFTWARE", "FIRMWARE", "PROTOKOLL", "DIENST",
              "IDENTITAET", "PRIVILEG", "SCHLUESSEL", "DATENFLUSS",
              "SPEICHER", "ABHAENGIGKEIT", "ENERGIE", "WARTUNG")

LIFECYCLES = ("UNKNOWN", "SUPPORTED", "REPLACE", "ISOLATE", "RETIRE")

# RETIRE ist hier nur eine Klassifikation (Kandidat), keine Aktion.

EVIDENZ_STATUSSE = ("CLAIM", "OBSERVED", "VERIFIED", "UNKNOWN",
                    "DISPUTED")

KRITISCHE_WERTE = ("JA", "NEIN")

VERDICT_INVENTARISIERT = "INVENTARISIERT"
VERDICT_ABGELEHNT = "ABGELEHNT"

WARNUNG_KRITISCH = "KRITISCH_WARNUNG"

EXIT_INVENTARISIERT, EXIT_ABGELEHNT, EXIT_INPUT_ERROR = 0, 1, 3

GRENZEN = ("UNKNOWN != PASS; CLAIM != VERIFIED; DISPUTED != VERIFIED;"
           " INVENTAR != REMEDIATION; REVIEW != ENTSCHEIDUNG;"
           " ISOLATE_NOT_DESTROY; SCRIPTED != INSTALLED")


def _non_empty(wert: Any) -> bool:
    """Nicht-leerer ASCII-String ist gegebenen Textes."""
    return isinstance(wert, str) and wert.strip() != ""


def _ascii_ok(text: str) -> bool:
    """ASCII-Gate ueber ALLE Zeichen (32..126 plus Newline)."""
    return all(32 <= ord(z) <= 126 or z == "\n" for z in text)


def pruefe(eintraege: List[Any]) -> Dict[str, Any]:
    """Struktur-Gate fuer EINE Inventar-Lieferung.

    Sammelt je Eintrag Gruende statt still zu korrigieren
    (KEINE_STUMME_KORREKTUR). Nur Gate-bestandene Eintraege
    gelangen in report["eintraege"] (GATE != SPEICHER: das
    Original bleibt unveraendert, der report verfaelscht nichts).
    """
    fehlerhafte: List[Dict[str, Any]] = []
    gueltige_eintraege: List[Dict[str, Any]] = []
    warnungen: List[str] = []
    if not isinstance(eintraege, list):
        raise KreislaufInputError(
            "inventar ist keine liste (geliefert: %s)" % type(eintraege).__name__)
    gesehene_ids = set()
    for position, eintrag in enumerate(eintraege):
        gruende: List[str] = []
        if isinstance(eintrag, (bool, int, float)) or eintrag is None:
            gruende.append("bare json-konstante statt objekt")
        elif not isinstance(eintrag, dict):
            gruende.append("eintrag ist kein json-objekt (%s)" % type(eintrag).__name__)
        else:
            eid = eintrag.get("id", "<fehlt>") if isinstance(eintrag.get("id"), str) else "<fehlt>"
            for feld in FELDER:
                if feld not in eintrag or not _non_empty(eintrag.get(feld)):
                    gruende.append("feld %r fehlt oder ist leer" % feld)
            for feld in FELDER:
                if feld in eintrag and not _ascii_ok(str(eintrag[feld])):
                    gruende.append("feld %r enthaelt non-ascii" % feld)
            kategorie = eintrag.get("kategorie")
            if _non_empty(kategorie) and kategorie not in KATEGORIEN:
                gruende.append("kategorie %r ausserhalb des wertebereichs (%s)" % (
                    kategorie, "|".join(KATEGORIEN)))
            lifecycle = eintrag.get("lifecycle")
            if _non_empty(lifecycle) and lifecycle not in LIFECYCLES:
                gruende.append("lifecycle %r ausserhalb des wertebereichs (%s)" % (
                    lifecycle, "|".join(LIFECYCLES)))
            status = eintrag.get("evidenz_status")
            if _non_empty(status) and status not in EVIDENZ_STATUSSE:
                gruende.append("evidenz_status %r ausserhalb des wertebereichs (%s)" % (
                    status, "|".join(EVIDENZ_STATUSSE)))
            kritisch = eintrag.get("kritischer_dienst")
            if _non_empty(kritisch) and kritisch not in KRITISCHE_WERTE:
                gruende.append("kritischer_dienst %r ausserhalb des wertebereichs (%s)" % (
                    kritisch, "|".join(KRITISCHE_WERTE)))
            if (_non_empty(status) and _non_empty(lifecycle)
                    and status in ("UNKNOWN", "CLAIM", "DISPUTED")
                    and lifecycle != "UNKNOWN"):
                gruende.append(
                    "evidenz_status %r erlaubt keine lifecycle-aussage"
                    " ausser UNKNOWN (UNKNOWN != PASS)" % status)
            if eid in gesehene_ids:
                gruende.append("id %r mehrfach vergeben" % eid)
            if isinstance(eintrag.get("id"), str) and eintrag["id"].strip():
                gesehene_ids.add(eintrag["id"].strip())
            if not gruende and _non_empty(kritisch) and kritisch == "JA" \
                    and lifecycle in ("ISOLATE", "RETIRE"):
                warnungen.append(
                    "%s: kritischer dienst mit lifecycle %s;"
                    " isolierung/retirement ist BETREIBERENTSCHEIDUNG"
                    " (ISOLATE_NOT_DESTROY)" % (eid, lifecycle))
        if gruende:
            fehlerhafte.append({
                "id": (eintrag.get("id", "<fehlt>")
                       if isinstance(eintrag, dict) else "<ohne id>"),
                "position": position,
                "gruende": gruende,
            })
        else:
            gueltige_eintraege.append(
                {feld: eintrag[feld] for feld in FELDER})
    if fehlerhafte or not gueltige_eintraege:
        verdict = VERDICT_ABGELEHNT
    else:
        verdict = VERDICT_INVENTARISIERT
    report: Dict[str, Any] = {
        "eintraege_gesamt": len(eintraege),
        "eintraege_gueltig": len(gueltige_eintraege),
        "eintraege_ungueltig": len(fehlerhafte),
        "verdict": verdict,
        "grenzen": GRENZEN,
        "eintraege": gueltige_eintraege,
        "warnungen": warnungen,
    }
    if fehlerhafte:
        report["fehlerhafte"] = fehlerhafte
    if gueltige_eintraege:
        report["lifecycle_verteilung"] = _verteilung(gueltige_eintraege, "lifecycle", LIFECYCLES)
        report["evidenz_verteilung"] = _verteilung(gueltige_eintraege, "evidenz_status", EVIDENZ_STATUSSE)
        report["kategorie_verteilung"] = _verteilung(gueltige_eintraege, "kategorie", KATEGORIEN)
    return report


def _verteilung(eintraege: List[Dict[str, Any]], feld: str,
                wertebereich: Tuple[str, ...]) -> Dict[str, int]:
    """Deterministische Zaehlung je Wertebereichs-Wert."""
    return {wert: sum(1 for e in eintraege if e.get(feld) == wert)
            for wert in wertebereich}


def format_text_report(report: Dict[str, Any]) -> str:
    """Deterministischer ASCII-Textreport, fehlertolerant."""
    zeilen = [
        "MAX-BEST LEGACY-INVENTAR",
        "verdict: %s" % report.get("verdict", "<fehlt>"),
        "eintraege gesamt/gueltig/ungueltig: %s/%s/%s"
        % (report.get("eintraege_gesamt", "<fehlt>"),
           report.get("eintraege_gueltig", "<fehlt>"),
           report.get("eintraege_ungueltig", "<fehlt>")),
        "grenzen: %s" % report.get("grenzen", "<fehlt>"),
    ]
    for key in ("lifecycle_verteilung", "evidenz_verteilung",
                "kategorie_verteilung"):
        verteilung = report.get(key)
        if isinstance(verteilung, dict):
            zeilen.append(key + ": " + "; ".join(
                "%s=%s" % (k, verteilung.get(k, "<fehlt>"))
                for k in sorted(verteilung)))
    for warnung in report.get("warnungen", []):
        zeilen.append("warnung: %s" % warnung)
    for fehler in report.get("fehlerhafte", []):
        zeilen.append("fehler [%s]: %s" % (
            fehler.get("id", "<ohne id>"),
            "; ".join(fehler.get("gruende", ["<ohne grund>"]))))
    for eintrag in report.get("eintraege", []):
        zeilen.append("- [%s] %s (%s) owner=%s lifecycle=%s evidenz=%s"
                      " kritisch=%s" % (
                          eintrag.get("id", "<fehlt>"),
                          eintrag.get("komponente", "<fehlt>"),
                          eintrag.get("kategorie", "<fehlt>"),
                          eintrag.get("owner", "<fehlt>"),
                          eintrag.get("lifecycle", "<fehlt>"),
                          eintrag.get("evidenz_status", "<fehlt>"),
                          eintrag.get("kritischer_dienst", "<fehlt>")))
        zeilen.append("  quelle=%s zeitpunkt=%s"
                      " grenzen=%s" % (
                          eintrag.get("evidenz_quelle", "<fehlt>"),
                          eintrag.get("evidenz_zeitpunkt", "<fehlt>"),
                          eintrag.get("grenzen", "<fehlt>")))
    return "\n".join(zeilen) + "\n"


def _write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "legacy_inventar.txt").write_text(
        format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=True) + "\n"
    (out_dir / "legacy_inventar.json").write_text(payload,
                                                 encoding="ascii")


def lade_inventar(path: Optional[Path]) -> List[Dict[str, Any]]:
    """Laedt EINE Inventar-Lieferung (JSON); fail-closed."""
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    try:
        daten = json.loads(text)
    except ValueError as exc:
        raise KreislaufInputError(
            "inventar %s ist kein gueltiges json: %s" % (path, exc)) from exc
    if not isinstance(daten, list):
        raise KreislaufInputError(
            "inventar %s ist keine liste" % path)
    return daten


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="MAX-BEST Legacy-Inventar (advisory, read-only,"
                    " INVENTAR != REMEDIATION, UNKNOWN != PASS)")
    parser.add_argument("inventar", help="Inventar-Lieferung (JSON-Liste)")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        eintraege = lade_inventar(Path(args.inventar))
    except KreislaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    except OSError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    report = pruefe(eintraege)
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    if report["verdict"] == VERDICT_INVENTARISIERT:
        return EXIT_INVENTARISIERT
    return EXIT_ABGELEHNT


if __name__ == "__main__":
    raise SystemExit(main())
