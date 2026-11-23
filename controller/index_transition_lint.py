"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Index-Append-Transition-Lint (VIBE-LXXXCII, CLAIM 7088919860).
Prueft NICHT eine Dateiversion (das macht controller/index_lint.py),
sondern NUR den Base->Head-UEBERGANG zweier Index-Staende. Geboren aus
der Vorfall-Lehre PR #400/#402: zwei Parallelsessions haengten am
selben Index-Punkt je eine Zeile an und erzeugten einen echten
3-Wege-Konflikt, der die Index-PR der anderen Session blockierte.

Regeln (alle fail-closed, ERROR blockiert):
  EXACTLY_ONE_APPEND   - Head fuegt gegenueber Base bei strikter
                         Zeilen-Praefix-Betrachtung NICHT genau die
                         erlaubte Anzahl an Session-Zeilen an
                         (Default: 1; konfigurierbar fuer Batch-
                         Nachtraege, 0 gilt als Fehler).
  BASE_PREFIX_MUTATED  - Base-Zeilen sind kein exakter Praefix von
                         Head (Mutation, Umordnung oder Loeschung in
                         der Basis ist nie Teil eines Appends).
  APPEND_NOT_SESSION   - eine angehaengte Zeile entspricht nicht dem
                         Regel-#138-Session-Format (SESSION_RE aus
                         controller/index_lint.py, Wiederverwendung,
                         kein Duplikat-Parsing).
  NEW_LINE_LINT_FAIL   - die angehaengte Zeile besteht den bestehenden
                         Ein-Zeilen-Regel-#138-Lint nicht (Fehler der
                         neuen Zeile werden 1:1 uebernommen).
  DUPLICATE_NEW_TAG    - der End-Tag einer neuen Zeile existiert in der
                         Basis oder in der neuen Zeilengruppe bereits
                         (Append-Kollision, der PR-#400/#402-Fall).

Bewusst NICHT geprueft (ehrlich, UNKNOWN != PASS):
  TAG-REIHENFOLGE      - der echte Index nutzt keine Standard-Roemisch-
                         Ordnung ('LXXXC', 'LXXXCI') und enthaelt
                         historisch doppelte Tags. Ein Zahlvergleich
                         wuerde raten; die Ordnungsfrage bleibt
                         UNKNOWN und wird ergaenzt, sobald eine
                         belegbare Ordnungsregel existiert.

REUSE (NO_DUPLICATE_SYSTEMS): SESSION_RE und Entry-Parsing stammen aus
controller/index_lint.py (Import, keine Kopie). LINT != WAHRHEIT:
geprueft wird der strukturelle Uebergang, nicht inhaltliche Richtigkeit.
Kein Netz, kein git, keine Laufzeiteffekte. WARN != FAIL.
Richtlinie: docs/AXIOM_HEADER.md; Arbeitsarchitektur #391.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # direkter Skript-Aufruf
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from index_lint import lint_text, parse_entry  # noqa: E402
else:
    from .index_lint import lint_text, parse_entry

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 3

DEFAULT_ALLOWED_APPENDED = 1


@dataclass
class TransitionResult:
    allowed_appended: int = DEFAULT_ALLOWED_APPENDED
    new_entries: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def appended_count(self) -> int:
        return len(self.new_entries)


def _violation(rule: str, detail: str) -> dict:
    return {"rule": rule, "detail": detail}


def _split_lines(text: str) -> list:
    return text.splitlines()


def lint_transition(
    base_text: str,
    head_text: str,
    allowed_appended: int = DEFAULT_ALLOWED_APPENDED,
) -> TransitionResult:
    """Prueft, dass Head == Base + genau N neue Regel-#138-Zeilen ist.

    Deterministisch, stdlib-only, fail-closed: alles, was nicht sicher
    belegbar ist, wird verweigert oder als UNKNOWN markiert.
    """
    result = TransitionResult(allowed_appended=allowed_appended)
    if not isinstance(base_text, str) or not isinstance(head_text, str):
        result.errors.append(_violation("INPUT_ERROR", "text arguments must be strings"))
        return result
    if type(allowed_appended) is not int or allowed_appended < 1:
        result.errors.append(
            _violation("INPUT_ERROR", "allowed_appended must be int >= 1")
        )
        return result

    base_lines = _split_lines(base_text)
    head_lines = _split_lines(head_text)
    appended_lines = head_lines[len(base_lines):]

    if head_lines[: len(base_lines)] != base_lines:
        result.errors.append(
            _violation(
                "BASE_PREFIX_MUTATED",
                "Basis-Zeilen sind kein exakter Praefix von Head "
                "(Mutation/Umordnung/Loeschung), Append-Charakter zerstoert",
            )
        )
        return result

    if len(appended_lines) != allowed_appended:
        result.errors.append(
            _violation(
                "EXACTLY_ONE_APPEND",
                "expect %d appended line(s), got %d"
                % (allowed_appended, len(appended_lines)),
            )
        )
        if not appended_lines:
            return result

    basis_end_tags = set()
    for line in base_lines:
        entry = parse_entry(line, 0)
        if entry is not None:
            basis_end_tags.add(entry.end_tag)

    new_tags_seen: list = []
    for line in appended_lines:
        entry = parse_entry(line, 0)
        if entry is None:
            result.errors.append(
                _violation(
                    "APPEND_NOT_SESSION",
                    "angehaengte Zeile entspricht nicht dem Regel-#138-"
                    "Session-Format: %s" % (line[:80] if line else "<leer>"),
                )
            )
            continue
        result.new_entries.append(entry)
        new_tags_seen.append(entry.end_tag)
        if entry.end_tag in basis_end_tags:
            result.errors.append(
                _violation(
                    "DUPLICATE_NEW_TAG",
                    "End-Tag VIBE-%s existiert bereits in der Basis "
                    "(Append-Kollision, PR-#400/#402-Fall)" % entry.end_tag,
                )
            )

    seen_in_group: set = set()
    for tag in new_tags_seen:
        if tag in seen_in_group:
            result.errors.append(
                _violation(
                    "DUPLICATE_NEW_TAG",
                    "End-Tag VIBE-%s mehrfach in der neuen Zeilengruppe" % tag,
                )
            )
        seen_in_group.add(tag)

    # Ein-Zeilen-Regel-#138-Lint NUR ueber die neuen Zeilen (die Basis
    # wird von index_lint.py selbst geprueft; hier wird kein Urteil
    # ueber alten Bestand gefaellt).
    new_text = "\n".join(appended_lines)
    single = lint_text(new_text)
    for error in single.errors:
        result.errors.append(
            _violation("NEW_LINE_LINT_FAIL", "Zeile %d %s: %s" % (
                error.get("line", 0), error.get("rule", "?"), error.get("detail", "?")))
        )
    for warning in single.warnings:
        result.warnings.append(
            _violation("NEW_LINE_WARN", "Zeile %d %s: %s (WARN)" % (
                warning.get("line", 0), warning.get("rule", "?"), warning.get("detail", "?")))
        )

    # Ehrliche Grenze: Reihenfolge der Tags bleibt UNKNOWN (keine
    # belegbare Ordnungsregel); wird bewusst NICHT geraten.
    result.warnings.append(
        _violation(
            "TAG_ORDERING_UNKNOWN",
            "Reihenfolge des neuen Tags gegenueber der Basis ist UNKNOWN "
            "(keine Standard-Roemisch-Ordnung im Index; UNKNOWN != PASS)",
        )
    )
    return result


def check_transition_files(
    base_path: str, head_path: str, allowed_appended: int
) -> tuple:
    """Liefert (TransitionResult, exit_code). Exit 0/1/3 wie index_lint."""
    base_file, head_file = Path(base_path), Path(head_path)
    if not base_file.is_file() or not head_file.is_file():
        return TransitionResult(allowed_appended=allowed_appended), 3
    try:
        base_text = base_file.read_text(encoding="utf-8")
        head_text = head_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return TransitionResult(allowed_appended=allowed_appended), 3
    result = lint_transition(base_text, head_text, allowed_appended)
    return result, (EXIT_OK if result.ok else EXIT_FAIL)


def build_report(result: TransitionResult, base_path: str, head_path: str) -> dict:
    return {
        "base": base_path,
        "head": head_path,
        "allowed_appended": result.allowed_appended,
        "appended_lines": result.appended_count,
        "new_tags": [e.end_tag for e in result.new_entries],
        "errors": len(result.errors),
        "warnings": len(result.warnings),
        "ok": result.ok,
        "error_details": result.errors,
        "warning_details": result.warnings,
    }


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Index-Append-Transition-Lint: Head muss Base + genau N "
        "neue Regel-#138-Zeilen sein"
    )
    parser.add_argument("base_index", help="Pfad zur Basis-Index-Datei")
    parser.add_argument("head_index", help="Pfad zur Head-Index-Datei")
    parser.add_argument(
        "--allow-appended",
        type=int,
        default=DEFAULT_ALLOWED_APPENDED,
        help="erlaubte Anzahl neuer Zeilen (Default: 1, 0 oder mehr nur bei "
        "dokumentiertem Batch-Beschluss)",
    )
    parser.add_argument("--json-out", default=None, help="optionaler JSON-Report-Pfad")
    args = parser.parse_args(argv)

    result, code = check_transition_files(
        args.base_index, args.head_index, args.allow_appended
    )
    report = build_report(result, args.base_index, args.head_index)

    if code == EXIT_INPUT_ERROR:
        print("INPUT_ERROR: Datei(en) nicht lesbar")
        return EXIT_INPUT_ERROR
    if code == EXIT_OK:
        print(
            "OK: %d neue Zeile(n), Tags %s, 0 Fehler, %d Warnungen (WARN != FAIL)"
            % (report["appended_lines"], ",".join(report["new_tags"]) or "-",
               report["warnings"])
        )
    else:
        print(
            "FAIL: %d Fehler bei %d angehaengten Zeile(n)"
            % (report["errors"], report["appended_lines"])
        )
        for error in result.errors:
            print("  %s: %s" % (error["rule"], error["detail"]))

    if args.json_out:
        out = Path(args.json_out)
        try:
            inside_repo = out.resolve().is_relative_to(
                Path(__file__).resolve().parent.parent
            )
        except OSError:
            inside_repo = False
        if inside_repo:
            print(
                "INPUT_ERROR: --json-out liegt IM repository; Laufzeit-"
                "Artefakte gehoeren NICHT ins Repo (Ragnarok-Phase-1-Regel)"
            )
            return EXIT_INPUT_ERROR
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
