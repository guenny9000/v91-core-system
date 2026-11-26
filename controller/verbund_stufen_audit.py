#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Verbund-Stufen-Audit (Verbund-Vertrag #590, ANHANG Abschnitt 10;
Auftrag: "Jede Stufe ist separat zu implementieren und zu
verifizieren. Nicht implementierte Stufen bleiben sichtbar offen.").

Dieses Modul PRUEFT den Stufenplan A-E gegen den echten Bestand:
Es mappt jede Stufe auf ihre Evidenz-Bausteine (Modul + zugehoerige
Testdatei), zaehlt AST-basiert die Test-Funktionen und faellt je
Stufe ein ehrliches Verdikt:

- BELEGT            : alle Evidenz-Bausteine vorhanden, je > 0
                     Test-Funktionen, keine bekannte Luecke.
- TEILWEISE_BELEGT  : Evidenz vorhanden, aber Luecken bleiben offen
                     (fehlende Bausteine oder dokumentierte Luecke).
- NICHT_GEFUNDEN    : kein einziger Evidenz-Baustein im gescannten
                     Pfad. NICHT_GEFUNDEN != NICHT_EXISTIERT.

Disziplin (fail-closed):
- AUDIT != LAUFZEIT: Der Audit sagt NICHTS darueber aus, ob eine
  Stufe IRGENDWO laeuft; er prueft nur Bestand + Tests am Pfad.
  BESTAND != BETRIEB, SCRIPTED != RUNNING.
- NICHT_GEFUNDEN != NICHT_EXISTIERT: ausserhalb des gescannten
  Pfads (andere Repos, private Instanzen) bleibt alles UNKNOWN.
- KEIN Netz, KEIN Daemon, KEINE Schreiboperation, KEIN Merge:
  dieses Modul entscheidet nichts und vollstreckt nichts.
- LUECKEN BLEIBEN OFFEN: dokumentierte Luecken werden NICHT als
  erledigt dargestellt (STATUS_OFFEN ist ein gueltiges Ergebnis).

Ehrliche Grenzen:
- Der Stufenplan-Kanon liegt allein in
  docs/V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP-ANHANG.md;
  dieses Modul PRAEFERT keine eigenen Stufen-Definitionen nach
  (KANON != CODE), es verweist nur.
- Die Evidenz-Map ist ein Stand und altert mit jedem Commit
  (Messtand = Lookup-Zeitpunkt des Aufrufers).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple

VERSION = "v91.verbund_stufen_audit.v1"

KANON_VERWEIS = "docs/V91-BASIC-NEEDS-PEACE-RESOURCE-STEWARDSHIP-ANHANG.md"

# Stufe -> (Kurzbeschreibung, Evidenz-Bausteine [(Modul, Testdatei)],
#           bekannte Luecken)
STUFEN: Tuple[Tuple[str, str, Tuple[Tuple[str, str], ...], Tuple[str, ...]], ...] = (
    (
        "A",
        "lokaler aktiver Zyklus",
        (
            ("controller/verbund_arbeitszyklus.py",
             "tests/test_verbund_arbeitszyklus.py"),
        ),
        (),
    ),
    (
        "B",
        "freiwillige Peer-Koordination",
        (
            ("controller/peer_directory.py", "tests/test_peer_directory.py"),
            ("controller/signed_manifest.py", "tests/test_signed_manifest.py"),
            ("controller/capability_intake.py", "tests/test_capability_intake.py"),
            ("controller/peer_sync.py", "tests/test_peer_sync.py"),
        ),
        (
            "getrennte lokale Testinstanzen NICHT_GEFUNDEN",
            "Ende-zu-Ende-Verbindung aller Primitiven NICHT_GEFUNDEN",
        ),
    ),
    (
        "C",
        "autorisierte Fernsteuerung",
        (),
        (
            "kein autorisierter Fernsteuerungs-Adapter im Bestand",
        ),
    ),
    (
        "D",
        "Wirkungssteuerung",
        (
            ("controller/messmatrix.py", "tests/test_messmatrix.py"),
            ("controller/impact.py", "tests/test_impact.py"),
            ("controller/autarky_metrics.py", "tests/test_autarky_metrics.py"),
        ),
        (
            "Baseline/Vorher-Nachher je Kennzahl nicht flächendeckend",
            "reale Weltwirkung NICHT GEPRUEFT (Messdaten #101/#103 fehlen)",
        ),
    ),
    (
        "E",
        "kontrollierte Skalierung",
        (),
        (
            "Skalierung NICHT_GEFUNDEN (benötigt reproduzierbare Tests, "
            "Sicherheitsreview, Wiederherstellungsübung, Nettonutzen)",
        ),
    ),
)


class VerbundStufenAuditError(Exception):
    """Fail-closed Fehler des Stufen-Audits."""


def _zaehle_test_funktionen(pfad: str) -> int:
    """AST-basiert: Anzahl der test_*-Funktionen einer Testdatei.

    Syntaxfehler sind MESSFEHLER (fail-closed), kein Sturz ins
    Ungefunde: sie werfen, statt 0 zu behaupten.
    """
    with open(pfad, "r", encoding="utf-8") as handle:
        baum = ast.parse(handle.read(), filename=pfad)
    anzahl = 0
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name.startswith("test_"):
            anzahl += 1
    return anzahl


def _pruefe_baustein(wurzel: str, modul: str, testdatei: str) -> Dict[str, Any]:
    modul_pfad = os.path.join(wurzel, modul)
    test_pfad = os.path.join(wurzel, testdatei)
    befund: Dict[str, Any] = {
        "modul": modul,
        "testdatei": testdatei,
        "modul_vorhanden": os.path.isfile(modul_pfad),
        "testdatei_vorhanden": os.path.isfile(test_pfad),
        "test_funktionen": 0,
    }
    if befund["testdatei_vorhanden"]:
        befund["test_funktionen"] = _zaehle_test_funktionen(test_pfad)
    return befund


def audit_stufe(wurzel: str, stufe: str, beschreibung: str,
                bausteine: Tuple[Tuple[str, str], ...],
                luecken: Tuple[str, ...]) -> Dict[str, Any]:
    """Ein ehrliches Verdikt fuer EINE Stufe."""
    if not os.path.isdir(wurzel):
        raise VerbundStufenAuditError("WURZEL_KEIN_VERZEICHNIS: " + wurzel)
    befunde = [
        _pruefe_baustein(wurzel, modul, testdatei)
        for modul, testdatei in bausteine
    ]
    if not bausteine:
        verdikt = "NICHT_GEFUNDEN"
    elif all(
        b["modul_vorhanden"] and b["testdatei_vorhanden"] and b["test_funktionen"] > 0
        for b in befunde
    ):
        verdikt = "TEILWEISE_BELEGT" if luecken else "BELEGT"
    elif any(b["modul_vorhanden"] or b["testdatei_vorhanden"] for b in befunde):
        verdikt = "TEILWEISE_BELEGT"
    else:
        verdikt = "NICHT_GEFUNDEN"
    return {
        "stufe": stufe,
        "beschreibung": beschreibung,
        "verdikt": verdikt,
        "evidenz": befunde,
        "offene_luecken": list(luecken),
        "verweis_kanon": KANON_VERWEIS,
    }


def audit(wurzel: str) -> Dict[str, Any]:
    """Gesamt-Audit aller Stufen A-E, sichtbar offen statt behauptet."""
    stufen = [
        audit_stufe(wurzel, stufe, beschreibung, bausteine, luecken)
        for stufe, beschreibung, bausteine, luecken in STUFEN
    ]
    return {
        "version": VERSION,
        "wurzel": os.path.abspath(wurzel),
        "stufen": stufen,
        "regeln": [
            "AUDIT != LAUFZEIT",
            "BESTAND != BETRIEB",
            "NICHT_GEFUNDEN != NICHT_EXISTIERT",
            "SCRIPTED != RUNNING",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verbund-Stufen-Audit A-E (ehrlich, fail-closed)")
    parser.add_argument("--path", default=".", help="Wurzelverzeichnis")
    parser.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    parser.add_argument("--self-check", action="store_true",
                        help="synthetischer Selbsttest")
    args = parser.parse_args(argv)

    if args.self_check:
        ergebnis = audit(args.path)
        assert all(s["verdikt"] in
                   ("BELEGT", "TEILWEISE_BELEGT", "NICHT_GEFUNDEN")
                   for s in ergebnis["stufen"])
        print("SELF-CHECK OK " + VERSION)
        return 0

    ergebnis = audit(args.path)
    if args.json:
        print(json.dumps(ergebnis, indent=2, sort_keys=True))
    else:
        for stufe in ergebnis["stufen"]:
            print(f"Stufe {stufe['stufe']} ({stufe['beschreibung']}): "
                  f"{stufe['verdikt']}")
            for luecke in stufe["offene_luecken"]:
                print(f"  OFFEN: {luecke}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
