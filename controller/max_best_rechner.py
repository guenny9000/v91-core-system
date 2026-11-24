"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
MAX-BEST-Rechner: ausfuehrbare Form des Mathematischen Gesamtkerns
(docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md, VIBE-LXXXCLXVII).

Der Kern dokumentiert Formeln; dieses Modul macht sie MASCHINEN-
PRUEFBAR: jede Formel aus Abschnitt 2 des Kerns existiert hier als
reine Funktion mit derselben Namensgebung. NEU und verbindlich ist die
UNKNOWN-Behandlung (UNKNOWN != PASS, Kern-Abschnitt 6): fehlt oder
verstuemmelt ist ein Eingabewert, ist das ERGEBNIS NICHT_GEPRUEFT
(dargestellt als None) - niemals 0, niemals ein geratener Wert
(UNBEKANNT != NULL != ERFUNDEN).

Wertebereiche sind fail-closed verriegelt (DOMAIN != MEINUNG):
- Wahrscheinlichkeiten p, Wirksamkeit w, Evidenz/Integritaet/Kontrolle
  liegen in [0, 1]; Verletzungen werfen MaxBestInputError (KEIN stilles
  Clampen, KEINE_STUMME_KORREKTUR).
- Schaden, Aufwand, Schadenshoehe sind Zahlen >= 0; Nutzen >= 0.
- Division durch Aufwand 0: NICHT_GEPRUEFT (kein Unendlich-Ergebnis).

Reihenfolge der Nebenbedingungen (Kern-Abschnitt 1) ist hier NICHT
implementiert und wird auch nicht simuliert: Gesamtnutzen ist eine
Zahl, KEINE Entscheidung (RECHNEN != ENTSCHEIDEN,
ZAHLEN_BINDEN_NICHT - Menschenwuerde > Sicherheit > Rechte stehen
lexikographisch VOR jeder Nutzenrechnung und sind nicht handelbar).

Ehrliche Grenzen:
- FORMEL != MESSUNG: dieses Modul rechnet mit ANGEGEBENEN Zahlen; es
  misst nichts selbst. Eine Zahl im Eingang ist eine ANGABE, kein
  Beleg (METASUM == ANGABE != BEWEIS).
- RECHNER != AGENT: keine Autorisierung, kein Auftrag, kein Zugriff
  auf fremde Systeme, kein Netz, kein Daemon.
- GROSSZAHLIGKEIT != GENAUIGKEIT: float-Arithmetik; Rundungsdifferenzen
  bleiben sichtbar, NICHT versteckt.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Optional

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

NICHT_GEPRUEFT = "NICHT_GEPRUEFT"
UNKNOWN_TOKENS = ("UNKNOWN", "Unbekannt", "unbekannt")


class MaxBestInputError(ValueError):
    """Struktur- oder Domainverletzung der Eingaben (fail-closed)."""


def _as_float(value: Any, name: str,
              minimum: Optional[float] = None,
              maximum: Optional[float] = None) -> Optional[float]:
    """Wandelt eine EINGABE in float ODER NICHT_GEPRUEFT-Nachricht.

    UNKNOWN-Eingaben (None, 'UNKNOWN', NaN) sind EHRLICHE Werte und
    erzeugen KEINEN Fehler: sie propagieren als NICHT_GEPRUEFT.
    Domainverletzungen ( falscher Typ, inf, ausserhalb [min, max])
    sind FEHLER: fail-closed, keine Rueckleitung.
    """
    if value is None or (isinstance(value, str)
                         and value.strip() in UNKNOWN_TOKENS):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaxBestInputError("%s muss Zahl oder UNKNOWN sein, ist %s"
                                % (name, type(value).__name__))
    number = float(value)
    if number != number:  # NaN ist UNKNOWN, kein Fehler
        return None
    if number in (float("inf"), float("-inf")):
        raise MaxBestInputError("%s ist nicht endlich: %r" % (name, value))
    if minimum is not None and number < minimum:
        raise MaxBestInputError("%s < %s verletzt den Wertebereich: %r"
                                % (name, minimum, value))
    if maximum is not None and number > maximum:
        raise MaxBestInputError("%s > %s verletzt den Wertebereich: %r"
                                % (name, maximum, value))
    return number


def _result(value: Optional[float]) -> dict[str, Any]:
    """Ehrlicher Einzelwert-Bericht: Zahl oder NICHT_GEPRUEFT."""
    if value is None:
        return {"wert": None, "status": NICHT_GEPRUEFT}
    return {"wert": value, "status": "BERECHNET"}


def gesamtnutzen(nutzen: Any, schaden: Any, aufwand: Any) -> dict[str, Any]:
    """max U = Nutzen - Schaden - Aufwand (Kern-Abschnitt 1)."""
    n = _as_float(nutzen, "nutzen", minimum=0.0)
    s = _as_float(schaden, "schaden", minimum=0.0)
    a = _as_float(aufwand, "aufwand", minimum=0.0)
    if n is None or s is None or a is None:
        return _result(None)
    return _result(n - s - a)


def nutzen_pro_aufwand(nutzen: Any, aufwand: Any) -> dict[str, Any]:
    """Wirkung je Ressourceneinheit; Aufwand 0 bleibt NICHT_GEPRUEFT."""
    n = _as_float(nutzen, "nutzen", minimum=0.0)
    a = _as_float(aufwand, "aufwand", minimum=0.0)
    if n is None or a is None:
        return _result(None)
    if a == 0.0:
        return _result(None)  # KEIN Unendlich: Division unbestimmt
    return _result(n / a)


def risiko(wahrscheinlichkeit: Any, schadenshoehe: Any) -> dict[str, Any]:
    """Risiko = Eintrittswahrscheinlichkeit x Schadenshoehe."""
    p = _as_float(wahrscheinlichkeit, "wahrscheinlichkeit",
                  minimum=0.0, maximum=1.0)
    s = _as_float(schadenshoehe, "schadenshoehe", minimum=0.0)
    if p is None or s is None:
        return _result(None)
    return _result(p * s)


def restrisiko(risiko_wert: Any, wirksamkeit: Any) -> dict[str, Any]:
    """Restrisiko = Risiko x (1 - Wirksamkeit), wirksamkeit in [0, 1]."""
    r = _as_float(risiko_wert, "risiko", minimum=0.0)
    w = _as_float(wirksamkeit, "wirksamkeit", minimum=0.0, maximum=1.0)
    if r is None or w is None:
        return _result(None)
    return _result(r * (1.0 - w))


def effizienz(nutzenleistung: Any, aufwand: Any) -> dict[str, Any]:
    """Effizienz = Nutzenleistung / Aufwand; 0-Aufwand NICHT_GEPRUEFT."""
    n = _as_float(nutzenleistung, "nutzenleistung", minimum=0.0)
    a = _as_float(aufwand, "aufwand", minimum=0.0)
    if n is None or a is None:
        return _result(None)
    if a == 0.0:
        return _result(None)
    return _result(n / a)


def vertrauen(evidenz: Any, integritaet: Any,
              kontrollierbarkeit: Any) -> dict[str, Any]:
    """Vertrauen = Evidenz x Integritaet x Kontrollierbarkeit, je [0, 1]."""
    e = _as_float(evidenz, "evidenz", minimum=0.0, maximum=1.0)
    i = _as_float(integritaet, "integritaet", minimum=0.0, maximum=1.0)
    k = _as_float(kontrollierbarkeit, "kontrollierbarkeit",
                  minimum=0.0, maximum=1.0)
    if e is None or i is None or k is None:
        return _result(None)
    return _result(e * i * k)


def berechne(auftrag: Any) -> dict[str, Any]:
    """Berechnet alle Kernformeln aus EINEM strukturierten Auftrag.

    Auftragsform (alle Felder optional, UNKNOWN erlaubt):
    {"gesamtnutzen": {"nutzen":…, "schaden":…, "aufwand":…},
     "risiko": {"wahrscheinlichkeit":…, "schadenshoehe":…},
     "restrisiko": {"risiko":…, "wirksamkeit":…},
     "nutzen_pro_aufwand"/"effizienz": {"nutzen(leistung)":…, "aufwand":…},
     "vertrauen": {"evidenz":…, "integritaet":…, "kontrollierbarkeit":…}}
    """
    if not isinstance(auftrag, dict):
        raise MaxBestInputError("Auftrag muss ein JSON-Objekt sein")
    report: dict[str, Any] = {}
    for key in auftrag:
        if key not in ("gesamtnutzen", "risiko", "restrisiko",
                       "nutzen_pro_aufwand", "effizienz", "vertrauen"):
            raise MaxBestInputError("unbekannter Formelbereich: %r" % key)
        teil = auftrag[key]
        if not isinstance(teil, dict):
            raise MaxBestInputError("%s muss ein Objekt sein" % key)
    if "gesamtnutzen" in auftrag:
        t = auftrag["gesamtnutzen"]
        report["gesamtnutzen"] = gesamtnutzen(
            t.get("nutzen"), t.get("schaden"), t.get("aufwand"))
    if "risiko" in auftrag:
        t = auftrag["risiko"]
        report["risiko"] = risiko(
            t.get("wahrscheinlichkeit"), t.get("schadenshoehe"))
    if "restrisiko" in auftrag:
        t = auftrag["restrisiko"]
        report["restrisiko"] = restrisiko(t.get("risiko"), t.get("wirksamkeit"))
    for key in ("nutzen_pro_aufwand", "effizienz"):
        if key in auftrag:
            t = auftrag[key]
            nutz = t.get("nutzenleistung", t.get("nutzen"))
            report[key] = (nutzen_pro_aufwand if key == "nutzen_pro_aufwand"
                           else effizienz)(nutz, t.get("aufwand"))
    if "vertrauen" in auftrag:
        t = auftrag["vertrauen"]
        report["vertrauen"] = vertrauen(
            t.get("evidenz"), t.get("integritaet"), t.get("kontrollierbarkeit"))
    nicht_geprueft = sum(1 for v in report.values()
                         if v["status"] == NICHT_GEPRUEFT)
    report["bilanz"] = {
        "formeln": len(report),
        "nicht_geprueft": nicht_geprueft,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MAX-BEST-Rechner: Kernformeln maschinenpruefbar, "
                    "UNKNOWN != PASS, RECHNEN != ENTSCHEIDEN")
    parser.add_argument("eingabe", nargs="?", default="-",
                        help="JSON-Datei oder - fuer stdin")
    args = parser.parse_args(argv)

    try:
        if args.eingabe == "-":
            text = sys.stdin.read()
        else:
            text = pathlib.Path(args.eingabe).read_text(encoding="utf-8")
        auftrag = json.loads(text)
        report = berechne(auftrag)
    except (OSError, json.JSONDecodeError, MaxBestInputError) as exc:
        print("MAX-BEST-RECHNER FEHLER (fail-closed): " + str(exc))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # exit 0: alle Formeln berechenbar; 1: mind. ein NICHT_GEPRUEFT
    # (ehrlich sichtbar, KEIN Scheitern); 2: Struktur-/Lesefehler.
    return 0 if report["bilanz"]["nicht_geprueft"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
