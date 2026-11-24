#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tagesbericht-Lagebild-Verkabelung (VIBE-LXXXCXXIX): verbindet die
drei fertigen, CI-geprueften Bausteine Tagesbericht (#130/#411-Vor-
arbeit daily_report), Nachrichten-Lagebild (#411) und Meldungsstrom
(#415) zu EINEM ehrlichen Lagebild (Betreiber-Direktiv 24.11.2026:
Verkabelung vor Neubau, REUSE_BEFORE_BUILD).

Kontrakt (NO_DUPLICATE_SYSTEMS, UNKNOWN != PASS, FAIL-CLOSED):

1. REUSE: Gueltigkeit eines Tagesbericht-Eintrags ist der Vertrag
   daily_report._entry_ok (claim/source/date); Bereichs- und
   Gesamt-Bewertung sind die ECHTEN Funktionen aus
   nachrichten_lagebild (bewerte_bereich, bewerte_gesamt); Strom-
   Zeilen laufen durch die ECHTEN meldungsstrom-Vertraege
   (parse_zeile, _meldung_ok, MAX_LINES_DEFAULT). Dieses Modul
   bewertet NICHTS selbst, es verdrahtet nur.
2. Eine Bewertung (richtung besser/schlechter/neutral) ist
   Menschenarbeit je Eintrag: fehlt sie, ist der Eintrag fuer das
   Lagebild UNGUELTIG (sichtbar gefuehrt), nie neutral geraten
   (BEWERTUNG != FAKT). Eintrag ohne bereich ebenfalls ungueltig.
3. Fail-closed: malformed Wurzel/Struktur oder bare NaN/Infinity =
   INPUT_ERROR (exit 3); ungueltige Einzel-Eintraege werden gefuehrt
   und machen exit 1, nie still unterschlagen.
4. VERKABELT != BETRIEB: kein Timer, kein Daemon, kein Netz;
   Ausgabe-JSON nur auf expliziten --out-Pfad AUSSERHALB des Repos
   (Ragnarok-Phase-1). LAGEBILD != WAHRHEIT. exit 0/1/3, stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
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
from controller.meldungsstrom import (  # REUSE, VIBE-LXXXCVI #415
    MAX_LINES_DEFAULT,
    MeldungsstromError,
    _meldung_ok,
    parse_zeile,
)

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_INPUT_ERROR = 3


class VerkabelungError(Exception):
    """Malformed input, fail-closed (ganzer Lauf)."""


def _reject_constant(value: str):
    raise ValueError("bare " + value + " ist INPUT_ERROR (parse_constant)")


def lade_tagesbericht(text: str) -> dict:
    """Parst die Tagesbericht-Datei fail-closed (kein stilles NaN/Infinity)."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise VerkabelungError("json ungueltig: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise VerkabelungError("wurzel muss objekt sein")
    report_id = data.get("report_id")
    if not isinstance(report_id, str) or not report_id.strip():
        raise VerkabelungError("report_id fehlt oder leer")
    for key in ("global_entries", "local_entries"):
        if not isinstance(data.get(key), list):
            raise VerkabelungError(key + " muss liste sein")
    return data


def _eintrag_fuer_lagebild(entry) -> tuple:
    """(bereit|None, grund) eines Tagesbericht-Eintrags fuer das Lagebild.

    REUSE: claim/source/date via daily_report._entry_ok; richtung und
    bereich sind zusaetzliche Pflichtangaben fuer die Verkabelung.
    """
    if not _entry_ok(entry):
        return (None, "claim_source_date_unvollstaendig")
    if entry.get("richtung") not in RICHTUNGEN:
        return (None, "richtung_fehlt_oder_ungueltig")
    bereich = entry.get("bereich")
    if not isinstance(bereich, str) or not _bereich_ok(bereich):
        return (None, "bereich_fehlt_oder_ungueltig")
    return (
        {
            "claim": entry["claim"].strip(),
            "source": entry["source"].strip(),
            "date": entry["date"].strip(),
            "richtung": entry["richtung"],
            "bereich": bereich,
        },
        "",
    )


def verkabelung_lagebild(daten: dict, strom_zeilen=None) -> dict:
    """Baut ein ehrliches Lagebild aus Tagesbericht (+ optionalem Strom).

    daten: Tagesbericht-dict (report_id, global_entries, local_entries;
           je Eintrag zusaetzlich bereich + richtung als Pflicht fuer
           das Lagebild). strom_zeilen: optional NDJSON-Iterable; jede
           Zeile wird via meldungsstrom.parse_zeile/_meldung_ok REUSE-
           verarbeitet (keine Zweitbewertung, verarbeite_strom liefert
           die Roh-Eintraege bewusst nicht zurueck). Die GEMEINSAME
           Bereichs-/Gesamt-Bewertung laeuft EINMAL ueber alle Quellen.
    Wirft VerkabelungError/MeldungsstromError bei malformed (exit 3).
    """
    bereiche: dict = {}
    ungueltige: list = []
    herkunft = {"tagesbericht": 0, "strom": 0}

    for idx, entry in enumerate(daten.get("global_entries", []) or []):
        bereit, grund = _eintrag_fuer_lagebild(entry)
        if bereit is None:
            ungueltige.append({"stelle": "teil_a:" + str(idx), "grund": grund})
        else:
            bereiche.setdefault(bereit["bereich"], []).append(bereit)
            herkunft["tagesbericht"] += 1

    for idx, entry in enumerate(daten.get("local_entries", []) or []):
        bereit, grund = _eintrag_fuer_lagebild(entry)
        if bereit is None:
            ungueltige.append({"stelle": "teil_b:" + str(idx), "grund": grund})
        else:
            bereiche.setdefault(bereit["bereich"], []).append(bereit)
            herkunft["tagesbericht"] += 1

    strom_report = None
    strom_ungueltige = []
    if strom_zeilen is not None:
        strom_verarbeitet = 0
        strom_gueltig = 0
        for text in strom_zeilen:
            strom_verarbeitet += 1
            if strom_verarbeitet > MAX_LINES_DEFAULT:
                raise MeldungsstromError(
                    "max_lines ueberschritten: mehr als "
                    + str(MAX_LINES_DEFAULT) + " Meldungen, kein stiller Ueberlauf (INPUT_ERROR)"
                )
            if text.strip() == "":
                strom_ungueltige.append({"zeile": strom_verarbeitet, "grund": "leere_zeile"})
                continue
            meldung = parse_zeile(text)  # REUSE: fail-closed NDJSON-Vertrag
            valid, grund = _meldung_ok(meldung)  # REUSE: Gueltigkeits-Vertrag
            if not valid:
                strom_ungueltige.append({"zeile": strom_verarbeitet, "grund": grund})
                continue
            bereiche.setdefault(meldung["bereich"], []).append(meldung)
            herkunft["strom"] += 1
            strom_gueltig += 1
        for eintrag in strom_ungueltige:
            ungueltige.append(
                {"stelle": "strom:zeile_" + str(eintrag["zeile"]), "grund": eintrag["grund"]}
            )
        strom_report = {
            "n_gesamt": strom_verarbeitet,
            "n_gueltig": strom_gueltig,
            "n_ungueltig": len(strom_ungueltige),
        }

    bereich_ergebnisse = {
        name: bewerte_bereich(eintraege) for name, eintraege in bereiche.items()
    }
    gesamt = bewerte_gesamt({k: v["tendenz"] for k, v in bereich_ergebnisse.items()})
    return {
        "bericht_id": daten["report_id"],
        "n_tagesbericht_eintraege": herkunft["tagesbericht"],
        "n_strom_meldungen": herkunft["strom"],
        "bereiche": bereich_ergebnisse,
        "gesamt_tendenz": gesamt,
        "ungueltige": ungueltige,
        "n_ungueltig_gesamt": len(ungueltige),
        "strom_ungueltig": (strom_report or {}).get("n_ungueltig", 0),
        "strom_gesamt": (strom_report or {}).get("n_gesamt", 0),
        "honesty": (
            "LAGEBILD != WAHRHEIT; BEWERTUNG != FAKT; RICHTUNG ist "
            "Menschenarbeit je Eintrag, fehlt = ungueltig, nie neutral "
            "geraten; REUSE daily_report + nachrichten_lagebild + "
            "meldungsstrom (NO_DUPLICATE_SYSTEMS); VERKABELT != BETRIEB"
        ),
    }


def check_dateien(tagesbericht_pfad, strom_pfad=None) -> tuple:
    """Liest Tagesbericht (+ Strom) und bewertet. Gibt (report, exit)."""
    try:
        daten = lade_tagesbericht(Path(tagesbericht_pfad).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return ({"error": "tagesbericht nicht lesbar: " + str(exc)}, EXIT_INPUT_ERROR)
    except VerkabelungError as exc:
        return ({"error": "tagesbericht: " + str(exc)}, EXIT_INPUT_ERROR)

    strom_zeilen = None
    if strom_pfad is not None:
        strom_zeilen = (raw.rstrip("\n").rstrip("\r") for raw in open(
            strom_pfad, "r", encoding="utf-8"))
    try:
        report = verkabelung_lagebild(daten, strom_zeilen)
    except (VerkabelungError, MeldungsstromError) as exc:
        return ({"error": str(exc)}, EXIT_INPUT_ERROR)
    code = EXIT_VIOLATIONS if report["n_ungueltig_gesamt"] > 0 else EXIT_OK
    return (report, code)


def format_text_report(report: dict) -> str:
    lines = [
        "V91 TAGESBERICHT-LAGEBILD " + str(report.get("bericht_id", "?")),
        "=================================================",
        "Tagesbericht-Eintraege (bewertet): " + str(report.get("n_tagesbericht_eintraege", 0)),
        "Strom-Meldungen (bewertet): " + str(report.get("n_strom_meldungen", 0)),
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
    lines.append("Ungueltige gesamt: " + str(report.get("n_ungueltig_gesamt", 0)))
    for eintrag in report.get("ungueltige", [])[:20]:
        lines.append("UNGUELTIG " + str(eintrag["stelle"]) + ": " + eintrag["grund"])
    n_un = len(report.get("ungueltige", []))
    if n_un > 20:
        lines.append("... und weitere " + str(n_un - 20) + " ungueltige")
    lines.append("GRENZE: " + str(report.get("honesty", "")))
    return "\n".join(lines)


def _json_out_verboten(path: str) -> bool:
    """Ragnarok-Phase-1: keine Laufzeit-Artefakte im Repo."""
    ziel = Path(path).resolve()
    for parent in [ziel] + list(ziel.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return True
    return False


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Tagesbericht-Lagebild-Verkabelung: Tagesbericht (+ optionaler "
            "Meldungsstrom) -> ein ehrliches Lagebild (REUSE, keine Zweitbewertung)"
        )
    )
    parser.add_argument("tagesbericht", help="Pfad zur Tagesbericht-JSON-Datei")
    parser.add_argument("--strom", default=None, help="optionaler NDJSON-Meldungsstrom")
    parser.add_argument("--json-out", default=None,
                        help="optionaler JSON-Ausgabepfad AUSSERHALB des Repos")
    args = parser.parse_args(argv)

    if args.json_out and _json_out_verboten(args.json_out):
        print("INPUT_ERROR: --json-out innerhalb des Repos abgewiesen (Ragnarok-Phase-1)")
        return EXIT_INPUT_ERROR

    report, code = check_dateien(args.tagesbericht, args.strom)
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
