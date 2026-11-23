#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Meldungsstrom: NDJSON-Stream-Verarbeitung fuer tausende Meldungen
taeglich (VIBE-LXXXCVI, Betreiber-Direktiv 24.11.2026: 'dauerhaft
1000-tausende Meldungen taeglich ueber echte Nachrichten, echte
Wirkung, echte Arbeit').

Kontrakt (UNKNOWN != PASS, CLAIM != EVIDENCE, FAIL-CLOSED):

1. REUSE (NO_DUPLICATE_SYSTEMS): Eintrags-Gueltigkeit ist der
   Vertrag aus daily_report._entry_ok (claim/source/date);
   Bereichs- und Gesamt-Bewertung sind die ECHTEN Funktionen aus
   nachrichten_lagebild (bewerte_bereich, bewerte_gesamt). Dieses
   Modul wertet NICHTS selbst, es verdrahtet nur den Strom.
2. STREAM: zeilenweise NDJSON, kein Voll-Laden in RAM; jede Zeile
   ist eine Meldung {bereich, claim, source, date, richtung}.
   Kein Meldungs-Drop: ungueltige Meldungen werden MIT Zeilennummer
   und Grund gefuehrt und machen exit 1, nie versteckt.
3. Fail-closed: nicht-JSON-Zeile, Nicht-Objekt-Zeile oder bare
   NaN/Infinity = INPUT_ERROR (exit 3, ganzer Lauf). Malformed
   ist CURRENT-Stop, nicht weiterlaufen und schwaechen.
4. MAX_LINES_DEFAULT (1000000) schuetzt ehrlich vor stiller
   Ueberlauf-Fiktion; Ueberschreitung = INPUT_ERROR. Eine leere
   Zeile ist eine ungueltige Meldung (sichtbar, nicht geloescht).
5. SKRIPT != BETRIEB: kein Timer, kein Daemon, keine Netzzugriffe;
   Ausgabe-JSON nur auf expliziten --out-Pfad AUSSERHALB des Repos
   (Ragnarok-Phase-1), sonst nur stdout. STROM != SYSTEM,
   ERFASST != GERETTET: dieses Modul zaehlt ECHTE Meldungen, es
   erzeugt keine Wirkungs-Zahlen. exit 0/1/3, stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from controller.daily_report import _entry_ok  # REUSE, PR #130 Vertrag
from controller.nachrichten_lagebild import (  # REUSE, VIBE-LXXXCIV #411
    RICHTUNGEN,
    _bereich_ok,
    bewerte_bereich,
    bewerte_gesamt,
)

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_INPUT_ERROR = 3

MAX_LINES_DEFAULT = 1_000_000


class MeldungsstromError(Exception):
    """Malformed input, fail-closed (ganzer Lauf)."""


def _reject_constant(value: str):
    raise ValueError("bare " + value + " ist INPUT_ERROR (parse_constant)")


def parse_zeile(text: str) -> dict:
    """Parst EINE NDJSON-Zeile fail-closed. Nur Objekte sind Meldungen."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise MeldungsstromError("zeile ist kein gueltiges JSON: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise MeldungsstromError("zeile muss ein JSON-Objekt sein")
    return data


def _meldung_ok(meldung: dict) -> tuple:
    """(valid, grund) einer Meldung. REUSE _entry_ok + Bereich/Richtung."""
    if not _entry_ok(meldung):
        return (False, "claim_source_date_unvollstaendig")
    bereich = meldung.get("bereich")
    if not isinstance(bereich, str) or not _bereich_ok(bereich):
        return (False, "bereich_ungueltig")
    if meldung.get("richtung") not in RICHTUNGEN:
        return (False, "richtung_ungueltig")
    return (True, "")


def verarbeite_strom(zeilen, bericht_id: str) -> dict:
    """Verarbeitet einen NDJSON-Zeilen-Iterable. Fail-closed.

    zeilen: Iterable von str (ohne Newline). Rueckgabe: Report-dict.
    Wirft MeldungsstromError bei malformed (EXIT 3).
    """
    if not isinstance(bericht_id, str) or not bericht_id.strip():
        raise MeldungsstromError("bericht_id fehlt oder leer")
    bereiche = defaultdict(list)
    ungueltige = []
    n_gesamt = 0
    for text in zeilen:
        n_gesamt += 1
        if n_gesamt > MAX_LINES_DEFAULT:
            raise MeldungsstromError(
                "max_lines ueberschritten: mehr als "
                + str(MAX_LINES_DEFAULT) + " Meldungen, kein stiller Ueberlauf (INPUT_ERROR)"
            )
        if text.strip() == "":
            ungueltige.append({"zeile": n_gesamt, "grund": "leere_zeile"})
            continue
        meldung = parse_zeile(text)
        valid, grund = _meldung_ok(meldung)
        if not valid:
            ungueltige.append({"zeile": n_gesamt, "grund": grund})
            continue
        bereiche[meldung["bereich"]].append(meldung)

    bereich_ergebnisse = {
        name: bewerte_bereich(eintraege) for name, eintraege in bereiche.items()
    }
    gesamt = bewerte_gesamt(
        {k: v["tendenz"] for k, v in bereich_ergebnisse.items()}
    )
    return {
        "bericht_id": bericht_id,
        "n_gesamt": n_gesamt,
        "n_gueltig": n_gesamt - len(ungueltige),
        "n_ungueltig": len(ungueltige),
        "bereiche": bereich_ergebnisse,
        "gesamt_tendenz": gesamt,
        "ungueltige_zeilen": ungueltige,
        "honesty": (
            "STROM != SYSTEM, ERFASST != GERETTET; BEWERTUNG != FAKT; "
            "REUSE daily_report._entry_ok + nachrichten_lagebild "
            "(NO_DUPLICATE_SYSTEMS); ungueltige Zeilen MIT Zeilennummer "
            "gefuehrt, nie gedroppt"
        ),
    }


def _json_out_verboten(path: str) -> bool:
    """Ragnarok-Phase-1: keine Laufzeit-Artefakte im Repo."""
    ziel = Path(path).resolve()
    for parent in [ziel] + list(ziel.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return True
    return False


def check_strom_datei(path, bericht_id: str) -> tuple:
    """Liest NDJSON zeilenweise (Stream) und bewertet. Gibt (report, exit)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            report = verarbeite_strom(
                (raw.rstrip("\n").rstrip("\r") for raw in handle), bericht_id
            )
        code = EXIT_VIOLATIONS if report["n_ungueltig"] > 0 else EXIT_OK
        return (report, code)
    except MeldungsstromError as exc:
        return ({"error": str(exc)}, EXIT_INPUT_ERROR)
    except (OSError, UnicodeDecodeError) as exc:
        return ({"error": "eingabe nicht lesbar: " + str(exc)}, EXIT_INPUT_ERROR)


def format_text_report(report: dict) -> str:
    lines = [
        "V91 MELDUNGSSTROM " + str(report.get("bericht_id", "?")),
        "=================================================",
        "Meldungen gesamt: " + str(report.get("n_gesamt", 0)),
        "gueltig: " + str(report.get("n_gueltig", 0)),
        "ungueltig: " + str(report.get("n_ungueltig", 0)),
        "-------------------------------------------------",
    ]
    for name, res in report.get("bereiche", {}).items():
        lines.append(
            name + ": " + res["tendenz"]
            + " (besser=" + str(res["besser"])
            + ", schlechter=" + str(res["schlechter"])
            + ", neutral=" + str(res["neutral"])
            + ", ungueltig=" + str(res["ungueltig"]) + ")"
        )
    lines.append("-------------------------------------------------")
    lines.append("GESAMT-TENDENZ: " + str(report.get("gesamt_tendenz", "UNKNOWN")))
    for eintrag in report.get("ungueltige_zeilen", [])[:20]:
        lines.append("UNGUELTIG Zeile " + str(eintrag["zeile"]) + ": " + eintrag["grund"])
    n_un = len(report.get("ungueltige_zeilen", []))
    if n_un > 20:
        lines.append("... und weitere " + str(n_un - 20) + " ungueltige")
    lines.append("GRENZE: " + str(report.get("honesty", "")))
    return "\n".join(lines)


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Meldungsstrom: NDJSON-Verarbeitung fuer tausende Meldungen (ehrlich, REUSE)"
    )
    parser.add_argument("eingabe", help="Pfad zur NDJSON-Datei (eine Meldung je Zeile)")
    parser.add_argument("--bericht-id", default=None, help="Berichts-Kennung")
    parser.add_argument("--json-out", default=None,
                        help="optionaler JSON-Ausgabepfad AUSSERHALB des Repos")
    args = parser.parse_args(argv)

    if args.json_out and _json_out_verboten(args.json_out):
        print("INPUT_ERROR: --json-out innerhalb des Repos abgewiesen (Ragnarok-Phase-1)")
        return EXIT_INPUT_ERROR

    bericht_id = args.bericht_id or ("meldungsstrom-" + str(Path(args.eingabe).name))
    report, code = check_strom_datei(args.eingabe, bericht_id)
    if "error" in report:
        print("INPUT_ERROR: " + report["error"])
        return EXIT_INPUT_ERROR
    print(format_text_report(report))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
