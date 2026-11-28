"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Regel-#138-Konsistenzlint fuer den Architektur-Index.
Ehrlich, fail-closed, stdlib-only, ohne Wirkung ueber den eigenen
Rechner hinaus. LINT != WAHRHEIT: geprueft wird Struktur, nicht
inhaltliche Richtigkeit. WARN != FAIL.
Richtlinie: docs/AXIOM_HEADER.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

DATE_FORMAT = "%d.%m.%Y"
YEAR_MIN = 2025
YEAR_MAX = 2026

# Session-Zeile nach Regel #138:
# - 22.11.2026 #359 (VIBE-LXVIII) ... [VIBE-LXVIII]
# Primaer-PR ist der erste PR einer #352/#355-Gruppe.
SESSION_RE = re.compile(
    r"^- (?P<date>\d{2}\.\d{2}\.\d{4}) (?P<prs>#\d+(?:/#\d+)*) "
    r"\(VIBE-(?P<start_tag>[A-Z0-9]+)\) (?P<body>.+) "
    r"\[VIBE-(?P<end_tag>[A-Z0-9]+)\]$"
)

# Neuere Session-Zeile (Format-Drift ab #593): eckiger Einzel-Tag,
# kein Klammer-Start-Tag, kein End-Tag:
# - 28.11.2026 #629 [VIBE-CLVI] NACHWEIS-CHECK-EHRLICH (...)
# Start-Tag == End-Tag (per Definition konsistent, kein
# TAG_START_END_MISMATCH moeglich); geprueft werden BAD_DATE,
# YEAR_OUT_OF_RANGE, DATUM_IN_ZUKUNFT und DUPLICATE_PRIMARY_PR.
SESSION_SQUARE_RE = re.compile(
    r"^- (?P<date>\d{2}\.\d{2}\.\d{4}) (?P<prs>#\d+(?:/#\d+)*) "
    r"\[VIBE-(?P<start_tag>[A-Z0-9]+)\] (?P<body>.+)$"
)

# Zeile mit Start-Tag, aber ohne End-Tag (historisches Format, nur WARN).
START_ONLY_RE = re.compile(
    r"^- (?P<date>\d{2}\.\d{2}\.\d{4}) #\d+(?:/#\d+)* \(VIBE-[A-Z0-9]+\)"
)


@dataclass
class Entry:
    line_number: int
    date: str
    prs: str
    start_tag: str
    end_tag: str


@dataclass
class LintResult:
    entries: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_entry(line: str, line_number: int) -> Entry | None:
    match = SESSION_RE.match(line.rstrip("\n"))
    if match is None:
        match = SESSION_SQUARE_RE.match(line.rstrip("\n"))
        if match is None:
            return None
        # Eckiges Einzel-Tag-Format (Drift ab #593): Start == End.
        return Entry(
            line_number=line_number,
            date=match.group("date"),
            prs=match.group("prs"),
            start_tag=match.group("start_tag"),
            end_tag=match.group("start_tag"),
        )
    return Entry(
        line_number=line_number,
        date=match.group("date"),
        prs=match.group("prs"),
        start_tag=match.group("start_tag"),
        end_tag=match.group("end_tag"),
    )


def _violation(line_number: int, rule: str, detail: str) -> dict:
    return {"line": line_number, "rule": rule, "detail": detail}


def lint_text(text: str, today: datetime | None = None) -> LintResult:
    """Prueft Index-Text gegen die Regel-#138-Strukturregeln.

    ERROR-Regeln (blockieren):
      TAG_START_END_MISMATCH  - Start-Tag != End-Tag
      BAD_DATE                - Datum kein gueltiges dd.mm.yyyy
      YEAR_OUT_OF_RANGE       - Jahr ausserhalb 2025-2026
      DATUM_IN_ZUKUNFT        - Session-Datum liegt nach dem Pruefzeitpunkt
      DUPLICATE_PRIMARY_PR   - Primaer-PR in zwei Session-Zeilen
    Geprueft werden BEIDE Session-Zeilen-Formate: die Klammer-Form
    (VIBE-...) ... [VIBE-...] und die eckige Einzel-Tag-Form
    [VIBE-...] (Format-Drift ab #593, vormals fuer den Lint
    unsichtbar - LINT-LUECKE != GEPRUEFT).
    WARN-Regeln (blockieren nicht):
      START_TAG_WITHOUT_END_TAG - Zeile mit (VIBE-...) aber ohne [VIBE-...]

    Ehrlichkeit zur Zeitreferenz: Session-Daten werden in Berliner
    Ortszeit geschrieben, CI/CLI pruefen in UTC. Die Referenz verlaengert
    sich deshalb um 2 Stunden Toleranzfenster (UTC+2-Sommerzeit deckt
    das schlimmste Offset ab). Ein Datum mehr als ~2h vor der
    Systemzeit-Zukunft ist ein chronologischer Fehler
    (DATUM != BEHAUPTUNG, MERGE-STEMPEL binden, LINT != WAHRHEIT:
    geprueft wird die Form der Chronologie gegen den kalendariischen
    Pruefzeitpunkt, nicht ob der Merge wirklich an jenem Tag lag - das
    bleibt Git-Nachweis-Aufgabe des Audits). Der Parameter 'today'
    ersetzt die Referenz KOMPLETT (ohne Toleranz, fuer deterministische
    Tests); nur die Default-Referenz (CLI/CI) bekommt das 2-h-Fenster.
    """
    result = LintResult()
    reference = today if today is not None else datetime.now() + timedelta(hours=2)
    primary_pr_first_line: dict = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        entry = parse_entry(line, line_number)
        if entry is not None:
            result.entries.append(entry)
            if entry.start_tag != entry.end_tag:
                result.errors.append(
                    _violation(
                        line_number,
                        "TAG_START_END_MISMATCH",
                        "start=VIBE-%s end=VIBE-%s" % (entry.start_tag, entry.end_tag),
                    )
                )
            try:
                parsed = datetime.strptime(entry.date, DATE_FORMAT)
                if not (YEAR_MIN <= parsed.year <= YEAR_MAX):
                    result.errors.append(
                        _violation(line_number, "YEAR_OUT_OF_RANGE", entry.date)
                    )
                elif parsed.date() > reference.date():
                    result.errors.append(
                        _violation(
                            line_number,
                            "DATUM_IN_ZUKUNFT",
                            "%s liegt nach Pruefzeitpunkt %s (MERGE-STEMPEL binden)"
                            % (entry.date, reference.date().isoformat()),
                        )
                    )
            except ValueError:
                result.errors.append(_violation(line_number, "BAD_DATE", entry.date))
            primary = entry.prs.split("/")[0].lstrip("#")
            if primary in primary_pr_first_line:
                result.errors.append(
                    _violation(
                        line_number,
                        "DUPLICATE_PRIMARY_PR",
                        "%s schon in Zeile %d" % (primary, primary_pr_first_line[primary]),
                    )
                )
            else:
                primary_pr_first_line[primary] = line_number
        elif START_ONLY_RE.match(line):
            result.warnings.append(
                _violation(line_number, "START_TAG_WITHOUT_END_TAG", "historisches Format")
            )
    return result


def check_file(path: str) -> tuple:
    """Liefert (LintResult, exit_code). Exit: 0 sauber, 1 Fehler, 3 Input-Fehler."""
    file_path = Path(path)
    if not file_path.is_file():
        return LintResult(), 3
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return LintResult(), 3
    result = lint_text(text)
    return result, (0 if result.ok else 1)


def build_report(result: LintResult, path: str) -> dict:
    return {
        "file": path,
        "entries": len(result.entries),
        "errors": len(result.errors),
        "warnings": len(result.warnings),
        "ok": result.ok,
        "error_details": result.errors,
        "warning_details": result.warnings,
    }


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regel-#138-Konsistenzlint fuer den Architektur-Index"
    )
    parser.add_argument("index_file", help="Pfad zur Index-Datei")
    parser.add_argument("--json-out", default=None, help="optionaler JSON-Report-Pfad")
    args = parser.parse_args(argv)

    result, code = check_file(args.index_file)
    report = build_report(result, args.index_file)

    if code == 3:
        print("INPUT_ERROR: Datei nicht lesbar: %s" % args.index_file)
        return 3
    if code == 0:
        print(
            "OK: %d Session-Eintraege, 0 Fehler, %d Warnungen (WARN != FAIL)"
            % (report["entries"], report["warnings"])
        )
    else:
        print(
            "FAIL: %d Fehler in %d Session-Eintraege"
            % (report["errors"], report["entries"])
        )
        for error in result.errors:
            print(
                "  Zeile %d %s: %s" % (error["line"], error["rule"], error["detail"])
            )
    for warning in result.warnings:
        print(
            "  Zeile %d %s: %s (WARN)" % (warning["line"], warning["rule"], warning["detail"])
        )

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
