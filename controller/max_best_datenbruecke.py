"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
MAX-BEST-Datenbruecke: verbindet ECHTE Messdatenquellen mit dem
MAX-BEST-Rechner (#525), ohne den Rechner zu veraendern.

Basis-Abgrenzung (NO_DUPLICATE_SYSTEMS):
- controller/impact.py bleibt alleinverbindlich fuer das Einlesen und
  Bewerten echter CSV-Messreihen (GEMESSEN != ANGEGEBEN).
- controller/legacy_radar.py bleibt alleinverbindlich fuer proaktive
  Arbeitsauftraege aus dem echten Node-Inventar.
- controller/max_best_rechner.py bleibt alleinverbindlich fuer die
  Kernformeln (FORMEL != MESSUNG).
- Diese Bruecke ERZEUGT nur Rechner-Auftraege plus ehrliche Metadaten;
  sie rechnet und misst NICHTS selbst (BRUECKE != ZWEITE_WAHRHEIT).

Verbindliche Regeln der Bruecke:
- Nur VALID-bewertete Messreihen werden als Zahl weitergereicht;
  jede andere Bewertung wird als UNKNOWN (None) weitergereicht und
  bleibt im Ergebnis NICHT_GEPRUEFT (UNKNOWN != PASS, KEINE_STUMME_
  KORREKTUR, NIEMALS 0 als Ersatzwert).
- Der Legacy-Radar liefert KEINE Wahrscheinlichkeiten; ohne vom
  Betreiber angegebene Wahrscheinlichkeiten bleibt Risiko
  NICHT_GEPRUEFT (KLASSIFIKATION != MESSUNG).
- ANNAHME-Eingaben werden metadatisch als ANNAHME gefuehrt und
  koennen sich niemals als MESSUNG ausgeben (ANNAHME != MESSUNG,
  EINGABE == ANGABE != BEWEIS).
- Ergebnistrennung: RECHNEN (results, Zahlen) und ENTSCHEIDEN
  (constraints, unhandhabare Leitplanken) sind GETRENNNTE Felder
  (RECHNEN != ENTSCHEIDEN, ZAHLEN_BINDEN_NICHT).

Ehrliche Grenzen:
- BRUECKE == VERKABELUNG != BETRIEB: kein Daemon, kein Netz, kein
  Sensor, SCRIPTED != RUNNING.
- Meta-Angaben (Verantwortlicher, Zeitraum, Ziel) sind ANGABEN des
  Aufrufers, keine geprueften Fakten (METASUM == ANGABE != BEWEIS).
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Optional

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller import impact  # REUSE: alleinverbindlich fuer CSV
from controller import legacy_radar  # REUSE: alleinverbindlich fuer Radar
from controller import max_best_rechner  # REUSE: alleinverbindlich fuer Formeln

NICHT_GEPRUEFT = "NICHT_GEPRUEFT"

QUANTIFIED_SOURCE = "quantified_source"
# Leitplanken aus dem Kern (Abschnitt 1): unhandhabbar, nicht simuliert.
CONSTRAINTS = {
    "menschenwuerde_vorrang": True,
    "sicherheit_vorrang": True,
    "rechte_vorrang": True,
    "lexikographisch_nicht_handelbar": True,
    "hinweis": ("Nebenbedingungen stehen VOR jeder Nutzenrechnung; "
                "numbers cannot weaken them (RECHNEN != ENTSCHEIDEN)"),
}


def csv_nutzen(csv_baseline: str, csv_after: str, unit: str,
               ziel: str, verantwortlicher: str, zeitraum: str,
               annahme: bool = False,
               schaden: Any = None, aufwand: Any = None,
               **impact_kwargs: Any) -> dict[str, Any]:
    """Erzeugt einen gesamtnutzen-Auftrag aus ECHTEN CSV-Messreihen.

    Zwei Zeitfenster gegen impact.compute_impact; nur VALID wird zur
    Zahl. Alles andere bleibt UNKNOWN -> NICHT_GEPRUEFT. Schaden und
    Aufwand sind separate Betreiber-ANGABEN (kein CSV-Ergebnis).
    """
    base_rows = impact.load_csv(csv_baseline)
    after_rows = impact.load_csv(csv_after)
    result = impact.compute_impact(
        measure=str(impact_kwargs.pop("measure", "csv-bridge")),
        baseline_rows=base_rows, after_rows=after_rows,
        unit=unit, **impact_kwargs)
    saved = result.get("saved_per_sample")
    if result.get("status") != "VALID" or not isinstance(saved, (int, float)):
        nutzen = None  # NICHT_GEPRUEFT, NIEMALS 0-Ersatz
    else:
        nutzen = float(saved)
    return {
        "auftrag": {"gesamtnutzen": {"nutzen": nutzen,
                                      "schaden": schaden,
                                      "aufwand": aufwand}},
        "meta": {
            "ziel": ziel,
            "verantwortlicher": verantwortlicher,
            "zeitraum": zeitraum,
            "quelle": "controller/impact.py csv_messreihe",
            "quellen_status": str(result.get("status")),
            "quellen_flags": list(result.get("flags", [])),
            "dqi": result.get("dqi"),
            "abgelehnte_zeilen": result.get("rejected_rows"),
            "annahme": bool(annahme),
        },
    }


def radar_risiko(inventar: Any,
                 wahrscheinlichkeiten: Optional[dict[str, Any]] = None,
                 schadenshoehen: Optional[dict[str, Any]] = None,
                 ziel: str = "", verantwortlicher: str = "",
                 zeitraum: str = "", annahme: bool = False) -> dict[str, Any]:
    """Erzeugt Risiko-/Restrisiko-Auftrag aus ECHTEM Radar-Bericht.

    Ohne Betreiber-Wahrscheinlichkeiten bleibt alles NICHT_GEPRUEFT:
    der Radar klassifiziert, er misst keine Eintrittswahrscheinlichkeit
    (KLASSIFIKATION != MESSUNG). WiRksamkeit wird NIE aus der
    Klassifikation abgeleitet.
    """
    report = legacy_radar.radar_report(inventar)
    auftrag: dict[str, Any] = {}
    wkeiten = wahrscheinlichkeiten or {}
    schaeden = schadenshoehen or {}
    p_werte: list[float] = []
    s_werte: list[float] = []
    items = report.get("items", [])
    for item in items:
        cid = item.get("component_id")
        p = wkeiten.get(cid) if cid is not None else None
        s = schaeden.get(cid) if cid is not None else None
        if isinstance(p, (int, float)) and not isinstance(p, bool):
            p_werte.append(float(p))
        if isinstance(s, (int, float)) and not isinstance(s, bool) and s >= 0:
            s_werte.append(float(s))
    if p_werte and len(p_werte) == len(items):
        # ehrliches Aggregat: arithmetische Mittelung ueber ALLE Items,
        # nur tragfaehig wenn der Betreiber JEDES Item versorgt hat
        wahrscheinlichkeit = sum(p_werte) / len(p_werte)
    else:
        wahrscheinlichkeit = None  # teils/ungenau versorgt -> NICHT_GEPRUEFT
    if s_werte and len(s_werte) == len(items):
        schadenshoehe = sum(s_werte) / len(s_werte)
    else:
        schadenshoehe = None
    auftrag["risiko"] = {"wahrscheinlichkeit": wahrscheinlichkeit,
                         "schadenshoehe": schadenshoehe}
    auftrag["restrisiko"] = {"risiko": None, "wirksamkeit": None}
    return {
        "auftrag": auftrag,
        "meta": {
            "ziel": ziel,
            "verantwortlicher": verantwortlicher,
            "zeitraum": zeitraum,
            "quelle": "controller/legacy_radar radar_report",
            "radar_state": str(report.get("state")),
            "items_gesamt": len(report.get("items", [])),
            "wahrscheinlichkeiten_von_betreiber": len(p_werte),
            "schadenshoehen_von_betreiber": len(s_werte),
            "aggregat": ("arithmetisches Mittel ueber alle Radar-Items; "
                         "nur tragfaehig wenn JEDES Item versorgt ist"),
            "annahme": bool(annahme),
            "annahme_hinweis": ("Betreiber-Wahrscheinlichkeiten sind "
                                "ANGABEN, keine Messungen"),
            "annahme_hinweis": ("Betreiber-Wahrscheinlichkeiten und "
                                "-schadenshoehen sind ANGABEN, keine "
                                "Messungen (EINGABE == ANGABE != BEWEIS)"),
        },
    }


def rechnen(bruecke: dict[str, Any]) -> dict[str, Any]:
    """Trennt RECHNEN (results) von ENTSCHEIDEN (constraints).

    meta wird unveraendert durchgereicht; ANNAHME-Bits koennen im
    Ergebnis nie als MESSUNG erscheinen (meta ist gekennzeichnet).
    """
    if not isinstance(bruecke, dict) or "auftrag" not in bruecke \
            or "meta" not in bruecke:
        raise max_best_rechner.MaxBestInputError(
            "bruecke muss {'auftrag': ..., 'meta': ...} sein")
    report = max_best_rechner.berechne(bruecke["auftrag"])
    results = {k: v for k, v in report.items() if k != "bilanz"}
    fehlend = sum(1 for v in results.values()
                  if v["status"] == NICHT_GEPRUEFT)
    return {
        "results": report,
        "constraints": dict(CONSTRAINTS),  # nie aus Zahlen abgeleitet
        "meta": dict(bruecke["meta"]),
        "bilanz": {"formeln": report["bilanz"]["formeln"],
                   "nicht_geprueft": fehlend},
    }


HONESTY_LIMITS = (
    "BRUECKE != ZWEITE_WAHRHEIT/MESSUMG, ANNAHME != MESSUNG, "
    "UNKNOWN != PASS, KEINE_STUMME_KORREKTUR, RECHNEN != ENTSCHEIDEN, "
    "KLASSIFIKATION != MESSUNG, SCRIPTED != RUNNING"
)
