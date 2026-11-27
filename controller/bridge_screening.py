"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Stufe-4-Screening fuer den Bridge-Abrufpfad (Bestandsaufnahme
docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md: LUECKE war, dass ein
Secret, Token oder personenbezogener Text in einem oeffentlichen
Bridge-Issue ungefiltert im lokalen Ledger abgelegt wurde).

Vertrag:
- REUSE statt Zweitbau (NO_DUPLICATE_SYSTEMS): die hochsignaligen
  Secret-Muster und die Zuweisungs-Muster werden AUS
  controller/secret_scan.py importiert (PR #140). Dieses Modul baut
  KEINE zweite Pattern-Liste fuer Secrets; neu sind NUR die
  personenbezogenen Formen E-Mail und IBAN (DE-Form, 20 Ziffern),
  die der Datei-Scanner nicht kennt.
- REDAKTION VOR ABLAGE: gefundene Fundstellen werden im abgelegten
  Text durch [REDACTIERT] ersetzt, BEVOR der Rohstoff im Ledger
  landet. Der SHA-256-Nachweis in kern_bridge bleibt eine Hashung
  ueber den ROHTEXT (ABDRUCK != ABLAGE: der Hash bezeugt den
  Rohstoff, die Ablage kann redigiert sein).
- KEINE Previews: Fundstellen werden nur mit Art und Zeilennummer
  gemeldet, NIEMALS mit Ausschnitt - auch die Meldung darf kein
  Geheimnis transportieren (REDAKTION != VERSAND).
- Gate bleibt orthogonal: das Bridge-Gate (drei feste Zustaende)
  klassifiziert destruktive MUSTER, dieses Screening
  vertrauliche MUSTER; beide laufen unabhaengig voneinander
  (GATE != SCREENING, SECRET != DESTRUKTIV).

Ehrliche Grenzen:
- SCREEN == MUSTER != GARANTIE: erkannt werden die bekannten
  hochsignaligen Formen; die Unschaedlichkeit des Rests wird
  NICHT behauptet. Namen, Adressen und freie persoenliche
  Beschreibungen werden NICHT erkannt; Telefonnummern werden
  NUR als deutsche Formen erkannt (27.11.-Erweiterung), mit
  dokumentiertem Over-Blocking (z. B. ISBN mit fuehrender 0
  kann mitredigiert werden: PII-SCHUTZ VOR BEQUEMLICHKEIT,
  die Redaktion ist ueber den Quell-Bezug reversibel).
- Zuweisungen mit Platzhalterwerten (test/example/dummy/...),
  Variablen-Referenzen ($) und Pfadwerten (/) gelten wie im
  Datei-Scanner als Konfiguration, NICHT als Secret-Literal
  (dokumentierte Regel, keine Raterei).
- KEIN Netz, KEINE Speicherung, KEINE Ausfuehrung: dieses Modul
  ist eine reine Textfunktion (FUNKTION != DAEMON).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from controller.secret_scan import (
    ENV_ASSIGNMENT_PATTERN,
    GENERIC_ASSIGNMENT_PATTERN,
    HIGH_SIGNAL_PATTERNS,
    _is_skipped_value,
)

SCREENING_STATUS_CLEAN = "CLEAN"
SCREENING_STATUS_REDACTED = "REDACTED"
REDACTION_MARKER = "[REDACTIERT]"

# Personenbezogene Formen (neu gegenueber controller/secret_scan.py,
# weil der Datei-Scanner repo-Dateien prueft, nicht Issue-Rohtexte).
# Telefon (27.11.-Erweiterung): nur deutsche Formen; internationale
# Form verlangt +49 plus 7-14 weitere Ziffern, nationale Form
# fuehrende 0 plus 6-13 weitere Ziffern (Gesamt 7-14 Ziffern), jeweils
# mit Leerstelle/Bindestrich/Schraegstrich als Trennern. Kuerzere
# Ziffernfolgen (Postleitzahlen, Uhrzeiten, Datumsfragmente) bleiben
# unberuehrt; Over-Blocking (z. B. ISBN mit fuehrender 0) ist
# dokumentiert und bewusst in Kauf genommen (REDAKTION reversibel).
PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email",
     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")),
    ("iban_de", re.compile(r"\bDE[0-9]{2}(?:[ ]?[0-9]{4}){4}[ ]?[0-9]{2}\b")),
    ("tel_international_de",
     re.compile(r"(?<![0-9+])\+49(?:[ \-/]*[0-9]){7,14}(?![0-9])")),
    ("tel_national_de",
     re.compile(r"(?<![0-9+])0(?:[ \-/]*[0-9]){6,13}(?![0-9])")),
)

_PRIVKEY_BEGIN = re.compile("-----BEGIN " + "[A-Z ]*" + "PRIVATE KEY-----")
_PRIVKEY_END = re.compile("-----END " + "[A-Z ]*" + "PRIVATE KEY-----")

SCREENING_HONESTY_LIMITS = (
    "SCREEN == MUSTER != GARANTIE, REDAKTION VOR ABLAGE, "
    "SHA = ROHTEXT, ABLAGE = REDAKTION, KEINE Previews, "
    "Namen/Adressen werden NICHT erkannt, Telefonnummern NUR als "
    "DE-Formen mit dokumentiertem Over-Blocking, "
    "GATE != SCREENING (SECRET != DESTRUKTIV)"
)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.start, s.end))
    merged: list[_Span] = [ordered[0]]
    for span in ordered[1:]:
        last = merged[-1]
        if span.start <= last.end:
            merged[-1] = _Span(last.start, max(last.end, span.end))
        else:
            merged.append(span)
    return merged


def _redact_line(line: str) -> tuple[str, list[_Span], set[str]]:
    """Sammelt Fundstellen EINER Zeile und redigiert sie rechts-nach-links."""
    kinds: set[str] = set()
    spans: list[_Span] = []
    for kind, pattern in HIGH_SIGNAL_PATTERNS:
        for match in pattern.finditer(line):
            spans.append(_Span(match.start(), match.end()))
            kinds.add(kind)
    for kind, pattern in PII_PATTERNS:
        for match in pattern.finditer(line):
            spans.append(_Span(match.start(), match.end()))
            kinds.add(kind)
    for pattern in (GENERIC_ASSIGNMENT_PATTERN, ENV_ASSIGNMENT_PATTERN):
        for match in pattern.finditer(line):
            value = match.group(1)
            if value is None or _is_skipped_value(value):
                continue  # dokumentierte Konfigurations-Regel, kein Literal
            kind = "keyword_assignment" if pattern is GENERIC_ASSIGNMENT_PATTERN \
                else "env_assignment"
            spans.append(_Span(match.start(1), match.end(1)))
            kinds.add(kind)
    merged = _merge_spans(spans)
    for span in sorted(merged, key=lambda s: s.start, reverse=True):
        line = line[:span.start] + REDACTION_MARKER + line[span.end:]
    return line, merged, kinds


def screen_text(body: str) -> dict:
    """Screened EINEN Rohtext; gibt Status, redigierten Text und
    Fundstellen (Art + Zeile, OHNE Ausschnitt) zurueck.

    Fail-closed: Nicht-String-Eingaben sind ein Messfehler und
    werden abgewiesen statt geratet (UNKNOWN != PASS).
    """
    if not isinstance(body, str):
        raise TypeError("screen_text: Eingabe muss ein String sein (FAIL-CLOSED)")

    lines = body.split("\n")
    redacted_lines: list[str] = []
    findings: set[tuple[str, int]] = set()
    redaction_count = 0
    in_privkey = False

    for line_no, line in enumerate(lines, start=1):
        if in_privkey:
            # Schluesselkoerper: ganze Zeile redigieren bis END-Marke
            redacted_lines.append(REDACTION_MARKER)
            redaction_count += 1
            if _PRIVKEY_END.search(line):
                in_privkey = False
            continue
        if _PRIVKEY_BEGIN.search(line):
            findings.add(("private_key_block", line_no))
            redacted_lines.append(REDACTION_MARKER)
            redaction_count += 1
            if not _PRIVKEY_END.search(line):
                in_privkey = True  # mehrzeiliger Block: Folgezeilen redigieren
            continue
        new_line, spans, kinds = _redact_line(line)
        for kind in kinds:
            findings.add((kind, line_no))
        redaction_count += len(spans)
        redacted_lines.append(new_line)

    ordered_findings = [
        {"kind": kind, "line_no": line_no}
        for line_no, kind in sorted(
            ((line_no, kind) for (kind, line_no) in findings)
        )
    ]

    return {
        "status": SCREENING_STATUS_REDACTED if findings else SCREENING_STATUS_CLEAN,
        "redacted_text": "\n".join(redacted_lines),
        "findings": ordered_findings,
        "redaction_count": redaction_count,
        "honesty_limits": SCREENING_HONESTY_LIMITS,
    }
