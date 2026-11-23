"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Raeumlicher Verlagerungs-Rebound (VIBE-LXXXCV).

Frage: Ist eine behauptete Reduktion eine echte Verminderung oder nur
eine VERLAGERUNG (Inland reduziert, Ausland nimmt belegt zu)?
SHUTDOWN != AVOIDED_IMPACT: eine Abschaltung (oder Reduktion) an einem
Ort ist keine vermiedene Wirkung, wenn dieselbe Wirkungskategorie
woanders belegt zunimmt.

REUSE (NO_DUPLICATE_SYSTEMS): Das Wirkungsrichtungs-Wertesystem und
das NEUTRAL-Verdict kommen aus controller/rebound_conflict_check.py
(Direction.REDUCES/NEUTRAL/INCREASES, VERDICT_NICHT_ENTSCHEIDBAR).
Dort werden DIMENSIONALE Konflikte EINER Massnahmensicht geprueft
(Effizienzgewinn ohne Netto-Reduktion = Jevons-Direktrebound); HIER
wird die RAEUMLICHE Verlagerung geprueft. Keine Duplikat-Bewertung.

Ehrlichkeitsregeln (UNKNOWN != PASS, CLAIM != EVIDENCE):

1. Eine INCREASES-Wirkung der Ziel-Kategorie im Raum AUSLAND macht
   das Verdict VERLAGERT_NICHT_VERMIEDEN - egal wie gut die
   Inlandsbilanz aussieht. Das ist der Fall des fremden
   Office-Agenten-Beispiels (Inlandsreduktion + Exportanstieg).
2. Eine INCREASES-Wirkung der Ziel-Kategorie mit Raum RAUM_UNBEKANNT
   macht NICHT_ENTSCHEIDBAR - ungepruefter Raum wird nie als
   vertraeglich geraten.
3. Ohne AUSLAND/RAUM_UNBEKANNT-Befunde gilt hoechstens
   VERMIEDEN_SICHTBAR: belegt ist das NUR fuer den geprueften
   Sichtbereich (VERMIEDEN != GLOBAL, SICHT != WELT).
4. Querwirkungen (INCREASES in anderen Kategorien) werden gefuehrt
   und sichtbar gemacht, nie gedroppt; sie aendern das Verdict
   nicht (Kategorien bleiben getrennt, keine Saldo-Verrechnung).
5. Evidenz ist eine Angabe, keine gepruefte Messung
   (ANGABE != GEPRUEFTE_MESSUNG). Fail-closed: malformed Eingabe =
   EXIT_INPUT_ERROR; Befunde = EXIT_BEFUND; saubere Sicht = EXIT_OK.
6. stdlib-only, kein Netz, kein Betrieb. SCRIPTED != BETRIEB,
   LINT != WAHRHEIT, print != Nachweis.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from controller.rebound_conflict_check import (  # REUSE, keine Zweitsysteme
    Direction,
    ReboundConflictError,
    VERDICT_NICHT_ENTSCHEIDBAR,
)

EXIT_OK = 0
EXIT_BEFUND = 1
EXIT_INPUT_ERROR = 3

VERDICT_VERLAGERT = "VERLAGERT_NICHT_VERMIEDEN"
VERDICT_VERMIEDEN_SICHTBAR = "VERMIEDEN_SICHTBAR"

RAEUME = ("INLAND", "AUSLAND", "RAUM_UNBEKANNT")


class Raum(str, Enum):
    """Raeumlicher Geltungsbereich EINER Wirkung (keine Werte erfunden)."""

    INLAND = "INLAND"
    AUSLAND = "AUSLAND"
    RAUM_UNBEKANNT = "RAUM_UNBEKANNT"


@dataclass(frozen=True)
class Wirkung:
    """Eine dokumentierte Wirkung einer Massnahme, mit Raumangabe."""

    kategorie: str
    raum: Raum
    richtung: Direction
    evidenz: str


def _reject_constant(value: str):
    raise ReboundConflictError("bare " + value + " ist INPUT_ERROR (parse_constant)")


def _ascii_nicht_leer(text, feld: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ReboundConflictError(feld + " fehlt oder leer")
    text = text.strip()
    if any(ord(c) < 32 or ord(c) > 126 for c in text):
        raise ReboundConflictError(feld + " muss ASCII sein")


def parse_wirkungen(data) -> list:
    """Fail-closed-Parsing der Wirkungsliste."""
    if not isinstance(data, list) or not data:
        raise ReboundConflictError("wirkungen muessen nicht-leere liste sein")
    wirkungen = []
    for item in data:
        if not isinstance(item, dict):
            raise ReboundConflictError("wirkung muss objekt sein")
        for feld in ("kategorie", "evidenz"):
            _ascii_nicht_leer(item.get(feld), "wirkung." + feld)
        raum = item.get("raum")
        if not isinstance(raum, str) or raum not in RAEUME:
            raise ReboundConflictError("raum muss INLAND/AUSLAND/RAUM_UNBEKANNT sein")
        richtung = item.get("richtung")
        if not isinstance(richtung, str) or richtung not in Direction.__members__:
            raise ReboundConflictError(
                "richtung muss REDUCES/NEUTRAL/INCREASES sein (BEWERTUNG != FAKT)"
            )
        wirkungen.append(
            Wirkung(
                kategorie=item["kategorie"].strip(),
                raum=Raum(raum),
                richtung=Direction(richtung),
                evidenz=item["evidenz"],
            )
        )
    return wirkungen


def load_massnahme(text: str) -> dict:
    """Parst die Eingabe fail-closed (kein stilles NaN/Infinity)."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ReboundConflictError("json ungueltig: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise ReboundConflictError("wurzel muss objekt sein")
    _ascii_nicht_leer(data.get("massnahme_id"), "massnahme_id")
    _ascii_nicht_leer(data.get("ziel_kategorie"), "ziel_kategorie")
    data["wirkungen"] = parse_wirkungen(data.get("wirkungen"))
    return data


def bewerte_verlagerung(massnahme: dict) -> dict:
    """Raeumlicher Verlagerungs-Befund, ehrlich statt gemittelt."""
    ziel = massnahme["ziel_kategorie"].strip() if isinstance(
        massnahme.get("ziel_kategorie"), str) else None
    if not ziel:
        raise ReboundConflictError("ziel_kategorie fehlt oder leer")
    rohwirkungen = massnahme.get("wirkungen")
    if any(isinstance(w, dict) for w in (rohwirkungen or [])):
        wirkungen = parse_wirkungen(rohwirkungen)
    else:
        wirkungen = rohwirkungen or []
    zielsicht = [w for w in wirkungen if w.kategorie == ziel]
    quer = [w for w in wirkungen if w.kategorie != ziel]

    verlagert = [
        w for w in zielsicht
        if w.richtung == Direction.INCREASES and w.raum == Raum.AUSLAND
    ]
    raum_offen = [
        w for w in zielsicht
        if w.richtung == Direction.INCREASES and w.raum == Raum.RAUM_UNBEKANNT
    ]
    inlands_reduktion = [
        w for w in zielsicht
        if w.richtung == Direction.REDUCES and w.raum == Raum.INLAND
    ]
    quer_kritisch = [w for w in quer if w.richtung == Direction.INCREASES]

    if verlagert:
        verdict = VERDICT_VERLAGERT
        begruendung = (
            "INCREASES der Ziel-Kategorie im Raum AUSLAND belegt: "
            "Wirkung ist verlagert, nicht vermieden "
            "(SHUTDOWN != AVOIDED_IMPACT)"
        )
    elif raum_offen:
        verdict = VERDICT_NICHT_ENTSCHEIDBAR
        begruendung = (
            "INCREASES der Ziel-Kategorie im Raum RAUM_UNBEKANNT: "
            "ungepruefter Raum wird nie als vertraeglich geraten"
        )
    elif inlands_reduktion:
        verdict = VERDICT_VERMIEDEN_SICHTBAR
        begruendung = (
            "Nur fuer den geprueften Sichtbereich belegt REDUCES: "
            "VERMIEDEN != GLOBAL, SICHT != WELT"
        )
    else:
        verdict = VERDICT_NICHT_ENTSCHEIDBAR
        begruendung = (
            "keine REDUCES-Sicht der Ziel-Kategorie vorhanden: "
            "UNKNOWN ist nie PASS"
        )

    return {
        "massnahme_id": (massnahme.get("massnahme_id") or "?").strip() if isinstance(massnahme.get("massnahme_id"), str) else "?",
        "ziel_kategorie": ziel,
        "verdict": verdict,
        "begruendung": begruendung,
        "verlagert_belege": [(w.raum.value, w.evidenz) for w in verlagert],
        "raum_unbekannt_belege": [(w.evidenz) for w in raum_offen],
        "inlands_reduktionen": [(w.evidenz) for w in inlands_reduktion],
        "querwirkungen": [
            (w.kategorie, w.raum.value, w.evidenz) for w in quer_kritisch
        ],
        "honesty": (
            "ANGABE != GEPRUEFTE_MESSUNG; VERMIEDEN != GLOBAL; "
            "Kategorien werden nicht verrechnet"
        ),
    }


def format_text_report(report: dict) -> str:
    lines = [
        "V91 VERLAGERUNGS-REBOUND " + str(report.get("massnahme_id", "?")),
        "=================================================",
        "Ziel-Kategorie: " + str(report.get("ziel_kategorie", "?")),
        "VERDICT: " + str(report.get("verdict", "?")),
        "Begruendung: " + str(report.get("begruendung", "")),
    ]
    if report.get("verlagert_belege"):
        for raum, evidenz in report["verlagert_belege"]:
            lines.append("Verlagert-Beleg [" + raum + "]: " + evidenz)
    if report.get("raum_unbekannt_belege"):
        for evidenz in report["raum_unbekannt_belege"]:
            lines.append("Raum-unbekannt-Beleg: " + evidenz)
    if report.get("inlands_reduktionen"):
        for evidenz in report["inlands_reduktionen"]:
            lines.append("Inlands-Reduktion: " + evidenz)
    if report.get("querwirkungen"):
        lines.append("--- Querwirkungen (andere Kategorien, gefuehrt) ---")
        for kategorie, raum, evidenz in report["querwirkungen"]:
            lines.append(kategorie + " [" + raum + "]: " + evidenz)
    lines.append("GRENZE: " + str(report.get("honesty", "")))
    return "\n".join(lines)


def check_datei(pfad: Path) -> tuple:
    """Liest und bewertet eine Eingabedatei. Gibt (report, exit_code)."""
    try:
        massnahme = load_massnahme(pfad.read_text(encoding="utf-8"))
    except OSError as exc:
        return ({"error": str(exc)}, EXIT_INPUT_ERROR)
    except ReboundConflictError as exc:
        return ({"error": str(exc)}, EXIT_INPUT_ERROR)
    report = bewerte_verlagerung(massnahme)
    if report["verdict"] == VERDICT_VERMIEDEN_SICHTBAR:
        return (report, EXIT_OK)
    return (report, EXIT_BEFUND)


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Raeumlicher Verlagerungs-Rebound (SHUTDOWN != AVOIDED_IMPACT)"
    )
    parser.add_argument("eingabe", help="Pfad zur Massnahmen-JSON-Datei")
    args = parser.parse_args(argv)
    report, code = check_datei(Path(args.eingabe))
    if "error" in report:
        print("INPUT_ERROR: " + report["error"])
        return EXIT_INPUT_ERROR
    print(format_text_report(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
