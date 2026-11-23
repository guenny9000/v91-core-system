"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Nachrichten-Lagebild: ehrliche Bereichs- und Gesamt-Tendenz aus
Tagesbericht-Teil-A/B-Eintraegen (Betreiber-Direktiv 'ungeschoente
Nachrichten-Einschaetzung eher gut oder schlechter', 22./23.11.2026).

Kontrakt (Rechtigkeit vor Bequemlichkeit, UNKNOWN != PASS):

1. REUSE: Eintrags-Gueltigkeit ist der Vertrag aus daily_report
   (_entry_ok: claim, source, date als nicht-leere Strings). Kein
   Zweitvertrag, keine Dupe-Validierung (NO_DUPLICATE_SYSTEMS).
2. RICHTUNG (besser/schlechter/neutral) ist eine BEWERTUNG des
   Menschen, deutlich getrennt vom Eintrag selbst: BEWERTUNG != FAKT,
   MEINUNG != MESSUNG, LAGEBILD != WAHRHEIT.
3. Ein Bereich ohne gueltige Eintraege ist UNKNOWN, nie gut oder
   schlecht geraten. Eindeutige Summe = Tendenz, uneinige Eintraege
   = GEMISCHT, Widerspruch bleibt sichtbar, nichts wird gedroppt.
4. Gesamt-Tendenz nur aus Bereichs-Tendenzen, UNKNOWN zaehlt mit:
   nur UNKNOWN = UNKNOWN, besser UND schlechter = GEMISCHT.
5. Fail-closed: malformed Wurzel/Bereiche/Eintraege = INPUT_ERROR
   (exit 3), ungueltige EinzelEintraege werden gefuehrt und machen
   exit 1, nie still unterschlagen. bare NaN/Infinity abgelehnt.
6. Stdlib-only, kein Netz, kein Betrieb. LAGEBILD != WAHRHEIT,
   SCRIPTED != BETRIEB. --json-out innerhalb des Repos abgewiesen
   (Ragnarok-Phase-1). exit 0/1/3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repository-Root fuer CLI-Aufrufe (python3 -m controller.nachrichten_lagebild
# funktioniert ohne Shim; der Shim deckt python3 controller/... ab).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from controller.daily_report import _entry_ok  # REUSE, PR #130 Vertrag

RICHTUNGEN = ("besser", "schlechter", "neutral")
BEREICH_RE_Erlaubt = "bereich muss nicht-leerer ASCII-String sein"
EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_INPUT_ERROR = 3


class LagebildError(Exception):
    """Malformed input (fail-closed)."""


def _reject_constant(value: str):
    raise LagebildError("bare " + value + " ist INPUT_ERROR (parse_constant)")


def _bereich_ok(name) -> bool:
    return (
        isinstance(name, str)
        and name.strip() != ""
        and name == name.strip()
        and all(32 <= ord(c) <= 126 for c in name)
    )


def load_lagebild(text: str) -> dict:
    """Parst die Eingabe fail-closed (kein stilles NaN/Infinity)."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise LagebildError("json ungueltig: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise LagebildError("wurzel muss objekt sein")
    bericht_id = data.get("bericht_id")
    if not isinstance(bericht_id, str) or not bericht_id.strip():
        raise LagebildError("bericht_id fehlt oder leer")
    bereiche = data.get("bereiche")
    if not isinstance(bereiche, dict) or not bereiche:
        raise LagebildError("bereiche fehlt, muss nicht-leeres objekt sein")
    for name, body in bereiche.items():
        if not _bereich_ok(name):
            raise LagebildError(BEREICH_RE_Erlaubt)
        if not isinstance(body, dict) or not isinstance(body.get("eintraege"), list):
            raise LagebildError("bereich " + name + ": eintraege muss liste sein")
        for entry in body["eintraege"]:
            if not isinstance(entry, dict):
                raise LagebildError("eintrag muss objekt sein")
            if entry.get("richtung") not in RICHTUNGEN:
                raise LagebildError(
                    "richtung muss besser/schlechter/neutral sein (BEWERTUNG != FAKT)"
                )
    return data


def bewerte_bereich(eintraege: list) -> dict:
    """Bewertet einen Bereich ehrlich: UNKNOWN statt geraten."""
    gueltig = [e for e in eintraege if _entry_ok(e)]
    ungueltig = [
        e for e in eintraege if not _entry_ok(e)
    ]  # sichtbar machen, nie droppen
    if not gueltig:
        return {
            "tendenz": "UNKNOWN",
            "besser": 0,
            "schlechter": 0,
            "neutral": 0,
            "ungueltig": len(ungueltig),
        }
    zaehler = {r: 0 for r in RICHTUNGEN}
    for e in gueltig:
        zaehler[e["richtung"]] += 1
    stimmen = {r for r, n in zaehler.items() if n > 0}
    if zaehler["besser"] and zaehler["schlechter"]:
        tendenz = "GEMISCHT"
    elif zaehler["besser"]:
        tendenz = "BESSER"
    elif zaehler["schlechter"]:
        tendenz = "SCHLECHTER"
    else:
        tendenz = "NEUTRAL"  # nur neutral-Stimmen
    return {
        "tendenz": tendenz,
        "besser": zaehler["besser"],
        "schlechter": zaehler["schlechter"],
        "neutral": zaehler["neutral"],
        "ungueltig": len(ungueltig),
    }


def bewerte_gesamt(bereich_tendenzen: dict) -> str:
    """Gesamt-Tendenz aus Bereichs-Tendenzen, UNKNOWN zaehlt mit."""
    werte = list(bereich_tendenzen.values())
    if not werte:
        return "UNKNOWN"
    if all(w == "UNKNOWN" for w in werte):
        return "UNKNOWN"
    if "BESSER" in werte and "SCHLECHTER" in werte:
        return "GEMISCHT"
    if "SCHLECHTER" in werte:
        return "SCHLECHTER"
    if "BESSER" in werte:
        return "BESSER"
    return "NEUTRAL"


def build_lagebild(data: dict) -> dict:
    bereiche = data["bereiche"]
    ergebnisse = {}
    ungueltige_gesamt = 0
    for name, body in bereiche.items():
        res = bewerte_bereich(body["eintraege"])
        ergebnisse[name] = res
        ungueltige_gesamt += res["ungueltig"]
    gesamt = bewerte_gesamt({k: v["tendenz"] for k, v in ergebnisse.items()})
    return {
        "bericht_id": data["bericht_id"],
        "bereiche": ergebnisse,
        "gesamt_tendenz": gesamt,
        "ungueltige_eintraege": ungueltige_gesamt,
        "honesty": (
            "LAGEBILD != WAHRHEIT; BEWERTUNG != FAKT; RICHTUNG ist "
            "menschliche Einschaetzung je Eintrag; UNKNOWN wird nie geraten"
        ),
    }


def format_text_report(report: dict) -> str:
    lines = [
        "V91 NACHRICHTEN-LAGEBILD " + str(report.get("bericht_id", "?")),
        "=================================================",
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
    lines.append("Ungueltige Eintraege: " + str(report.get("ungueltige_eintraege", 0)))
    lines.append("GRENZE: " + str(report.get("honesty", "")))
    return "\n".join(lines)


def check_lagebildFile(path: Path) -> tuple:
    """Liest und bewertet eine Eingabedatei. Gibt (report, exit_code)."""
    try:
        data = load_lagebild(path.read_text(encoding="utf-8"))
    except (OSError, LagebildError) as exc:
        return ({"error": str(exc)}, EXIT_INPUT_ERROR)
    report = build_lagebild(data)
    code = EXIT_VIOLATIONS if report["ungueltige_eintraege"] > 0 else EXIT_OK
    return (report, code)


def _json_out_verboten(path: str) -> bool:
    """Ragnarok-Phase-1: keine Laufzeit-Artefakte im Repo (.git/pyproject als Marker)."""
    ziel = Path(path).resolve()
    for parent in [ziel] + list(ziel.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return True
    return False


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(description="Nachrichten-Lagebild (ehrlich)")
    parser.add_argument("eingabe", help="Pfad zur Lagebild-JSON-Datei")
    parser.add_argument("--json-out", default=None, help="optionaler JSON-Ausgabepfad")
    args = parser.parse_args(argv)
    if args.json_out and _json_out_verboten(args.json_out):
        print("INPUT_ERROR: --json-out innerhalb des Repos abgewiesen (Ragnarok-Phase-1)")
        return EXIT_INPUT_ERROR
    report, code = check_lagebildFile(Path(args.eingabe))
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
