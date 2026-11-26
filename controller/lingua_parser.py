"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
V91-LINGUA Referenzparser (Stufe 3, Schritt 2 nach Anhang #572).
Alleinverbindliche Definition: docs/V91-LINGUA-GRAMMATIK.md.
Subordination: docs/V91-LINGUA-KERN.md (#571) und
docs/V91-LINGUA-SICHERHEITS-ANHANG.md (#572).
Ehrlich, fail-closed, stdlib-only, KEIN Netz, KEIN Dateizugriff
im Parserkern. parse() liefert Daten mit BEFUGNIS: KEINE
(R6: SPRACHE SCHAFFT KEINE BEFUGNIS).
SIGNATUR: NICHT_IMPLEMENTIERT - es wird NUR Struktur geprueft,
KEINE Herkunft, KEINE Identitaet, KEINE Berechtigung. Signatur-,
Identitaets- und Replay-Pruefung bleiben Stufe 3.3/3.4 und den
existierenden Gates vorbehalten (NICHT BEHAUPTET).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime

PARSER_VERSION = "lingua.parser.v1"
GRAMMAR_VERSION = 1

MANDATORY_KEYS = ("TASK", "STATE", "EVID", "NEXT")
OPTIONAL_ENUMS = {
    "GATE": ("HOLD", "OPEN", "FAIL"),
    "GOAL": ("SECURITY", "EFFICIENCY", "UTILITY", "MEASUREMENT", "COOPERATION"),
    "ACTION": ("AUDIT", "VERIFY", "MEAS", "REMEAS", "REV", "REPORT", "COOP", "REC"),
    "STATE": ("VER", "UNV", "DET", "OBS", "MEAS", "REMEAS", "REV", "UNK", "DISPUTED"),
    "NEXT": ("VERIFY", "AUDIT", "REPORT", "HOLD", "CLOSE", "COOP"),
}
SECURITY_KEYS = ("VERSION", "FROM", "TO", "TIME", "MSGID")
KNOWN_KEYS = frozenset(MANDATORY_KEYS + tuple(OPTIONAL_ENUMS) + SECURITY_KEYS)

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")
ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")
VERSION_RE = re.compile(r"^[0-9]{1,3}$")
TIME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
EVID_RE = re.compile(r"^([0-9]{1,4})/([0-9]{1,4})(?: )?::(?: )?([0-9A-Za-z._/-]{1,64})$")

EXAMPLE = (
    "TASK:042\n"
    "GOAL:SECURITY\n"
    "STATE:UNV\n"
    "EVID:0/4 ::offen\n"
    "ACTION:AUDIT\n"
    "GATE:HOLD\n"
    "NEXT:VERIFY\n"
)


class LinguaParseError(Exception):
    """Fail-closed: Code, Zeilennummer, Grundangabe. KEINE Reparatur."""

    def __init__(self, code, zeile, grund):
        super().__init__("%s Zeile %d: %s" % (code, zeile, grund))
        self.code = code
        self.zeile = zeile
        self.grund = grund


def _check_zeichen(text):
    for idx, ch in enumerate(text):
        if ch == "\n" or 0x20 <= ord(ch) <= 0x7E:
            continue
        zeile = text.count("\n", 0, idx) + 1
        raise LinguaParseError(
            "E02", zeile, "Zeichen 0x%02X: zulaessig sind nur 0x20-0x7E plus LF" % ord(ch)
        )


def parse(text):
    """Parst EINE Nachricht oder scheitert fail-closed (KEIN Teilresultat)."""
    if not isinstance(text, str):
        raise LinguaParseError("E01", 0, "Eingabe ist keine Zeichenkette")
    _check_zeichen(text)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # EINE abschliessende Leerzeile am Ende ist erlaubt
    if not lines:
        raise LinguaParseError("E03", 0, "Leere Nachricht")
    fields = {}
    for num, line in enumerate(lines, start=1):
        if line.strip() == "":
            raise LinguaParseError("E04", num, "Leerzeile")
        if ":" not in line:
            raise LinguaParseError("E05", num, "Zeile ohne Doppelpunkt")
        key, _sep, value = line.partition(":")
        if not KEY_RE.match(key):
            raise LinguaParseError("E06", num, "Schluessel entspricht nicht dem Muster")
        if key not in KNOWN_KEYS:
            raise LinguaParseError("E07", num, "Unbekannter Schluessel %s" % key)
        if key in fields:
            raise LinguaParseError("E08", num, "Schluessel %s doppelt" % key)
        if value == "":
            raise LinguaParseError("E09", num, "Wert ist leer")
        if key not in ("EVID", "TIME") and ":" in value:
            raise LinguaParseError("E10", num, "Doppelpunkt im Wert")
        fields[key] = (value, num)
    for key in MANDATORY_KEYS:
        if key not in fields:
            raise LinguaParseError("E11", 0, "Pflichtfeld %s fehlt" % key)
    result = {}
    for key in fields:
        value, zeile = fields[key]
        if key == "EVID":
            match = EVID_RE.match(value)
            if match is None:
                raise LinguaParseError(
                    "E12", zeile, "EVID entspricht nicht n/m ::beleg"
                )
            n, m, beleg = int(match.group(1)), int(match.group(2)), match.group(3)
            if n > m:
                raise LinguaParseError("E13", zeile, "EVID n=%d > m=%d" % (n, m))
            result["evid"] = {"n": n, "m": m, "beleg": beleg}
        elif key in OPTIONAL_ENUMS:
            if value not in OPTIONAL_ENUMS[key]:
                raise LinguaParseError(
                    "E12", zeile, "Wert unzulaessig fuer %s: %s" % (key, value)
                )
            result[key.lower()] = value
        elif key == "TIME":
            if not TIME_RE.match(value):
                raise LinguaParseError("E14", zeile, "TIME entspricht nicht dem Format")
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                raise LinguaParseError("E14", zeile, "TIME kein gueltiger Kalenderwert")
            result["time"] = value
        elif key in ("TASK", "FROM", "TO", "MSGID"):
            if not ID_RE.match(value):
                raise LinguaParseError(
                    "E12", zeile, "Wert unzulaessig fuer %s: %s" % (key, value)
                )
            result[key.lower()] = value
        elif key == "VERSION":
            if not VERSION_RE.match(value):
                raise LinguaParseError("E12", zeile, "VERSION entspricht nicht [0-9]{1,3}")
            result["version"] = int(value)
        else:  # pragma: no cover - KNOWN_KEYS ist vollstaendig behandelt
            raise LinguaParseError("E12", zeile, "Unbehandelter Schluessel %s" % key)
    vorhanden = [k for k in SECURITY_KEYS if k in fields]
    if 0 < len(vorhanden) < len(SECURITY_KEYS):
        fehlend = [k for k in SECURITY_KEYS if k not in fields]
        raise LinguaParseError(
            "E15", 0, "Sicherheitsblock unvollstaendig, fehlt: %s" % ",".join(fehlend)
        )
    ordered = {"schema": PARSER_VERSION, "grammatik_version": GRAMMAR_VERSION}
    for key in sorted(result):
        ordered[key] = result[key]
    ordered["befugnis"] = "KEINE"  # R6: SPRACHE SCHAFFT KEINE BEFUGNIS
    return ordered


def validate(text):
    """Ohne Raise: gueltig plus Ergebnis oder Code, Zeile, Grund."""
    try:
        ergebnis = parse(text)
    except LinguaParseError as err:
        return {
            "gueltig": False,
            "code": err.code,
            "zeile": err.zeile,
            "grund": err.grund,
        }
    return {"gueltig": True, "ergebnis": ergebnis}


def _self_check():
    proben = [
        validate(EXAMPLE)["gueltig"] is True,
        validate("TASK:042")["gueltig"] is False,  # unvollstaendig
        validate("STATE:VER\n")["gueltig"] is False,  # Pflichtfehler
        validate("TASK:A\nSTATE:xVER\nEVID:1/1 ::b\nNEXT:HOLD")["gueltig"] is False,
        parse(EXAMPLE)["befugnis"] == "KEINE",
    ]
    return all(proben)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="V91-LINGUA Referenzparser (fail-closed, keine Befugnis)"
    )
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "datei", nargs="?", help="optional: Datei mit EINER Nachricht"
    )
    args = parser.parse_args(argv)
    if args.self_check:
        if not _self_check():
            print("SELF_CHECK: FAIL")
            return 1
        print(
            json.dumps(
                {
                    "self_check": "PASS",
                    "parser": PARSER_VERSION,
                    "befugnis": "KEINE",
                    "signaturpruefung": "NICHT_IMPLEMENTIERT",
                    "modelltests": "NICHT_GEPRUEFT",
                    "kooperation": "OFFEN",
                },
                sort_keys=True,
            )
        )
        return 0
    if not args.datei:
        print("INPUT_ERROR: --self-check oder Nachrichtendatei angeben")
        return 2
    try:
        text = pathlib.Path(args.datei).read_text(encoding="utf-8")
    except OSError:
        print("INPUT_ERROR: Datei nicht lesbar: %s" % args.datei)
        return 3
    try:
        ergebnis = parse(text)
    except LinguaParseError as err:
        print(
            json.dumps(
                {
                    "gueltig": False,
                    "code": err.code,
                    "zeile": err.zeile,
                    "grund": err.grund,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(ergebnis, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
