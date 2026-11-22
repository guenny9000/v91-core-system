#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Tagesbericht-CLI-Treiber (VIBE-LXXXVII, CLAIM 7085425998):
DUENNER ERSTAUFRUF-INKREMENT der Verkabelung (VIBE-LXXXVI/#395).
- Fuehrt die ECHTEN Bestandsmodule: controller/evidence_bridge.py ->
  controller/repo_report_agent.py (#393) und liefert den belegten
  Teil-C-Check an controller/daily_report.py (#277) (NO_DUPLICATE_SYSTEMS:
  dieser Treiber wertet NICHTS selbst aus, er orchestriert nur den Aufruf).
- Schreibt den Bericht NUR auf expliziten --out-Pfad; KEINE Default-Pfade,
  KEINE Laufzeit-Artefakte im Repository (Lehre Ragnarok-Phase 1, PR #247).
- Ohne belegten Head-SHA bleibt der Bericht ehrlich UNKNOWN bzw. AMBER
  (UNKNOWN != PASS, GREEN nur ohne offene UNKNOWN-Notes, PR #395 Fix 1).
- SKRIPT != BETRIEB: kein Timer, kein Daemon, kein automatischer Lauf.
Richtlinie: docs/V91-TAGESBERICHT-STANDARD.md, docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

_REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[1]

try:
    from controller import evidence_bridge as _bridge
    from controller import daily_report as _daily_report
except ImportError:  # direkter Aufruf aus scripts/ ohne Paketkontext
    _REPO_ACTUAL = Path(__file__).resolve().parents[1]
    if str(_REPO_ACTUAL) not in sys.path:
        sys.path.insert(0, str(_REPO_ACTUAL))
    from controller import evidence_bridge as _bridge
    from controller import daily_report as _daily_report

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 3

_ALLOWED_TOP_KEYS = (
    "report_id",
    "date",
    "global_entries",
    "local_entries",
    "local_next_step",
)


def load_entries(path):
    """Laedt optionale Teil-A/B-Eintraege aus JSON. FAIL-CLOSED bei

    ungueltigem Pfad/JSON. Nur bekannte Schluessel werden uebernommen.
    """
    text = Path(path).read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("entries JSON muss ein Objekt sein")
    unknown = sorted(set(raw) - set(_ALLOWED_TOP_KEYS))
    data = {k: raw[k] for k in _ALLOWED_TOP_KEYS if k in raw}
    return data, unknown


def build_tagesbericht(repo_root, entries=None, runner=None, head_resolver=None):
    """Oeffentlicher Einstieg. Liefert (report_dict, unknown_top_keys, exit_code)."""
    snapshot, bridge_exit = _bridge.build_snapshot(
        repo_root, runner=runner, head_resolver=head_resolver)

    entries_payload = entries or {}
    unknown_top_keys = entries_payload.get("_unknown_top_keys", [])
    entries_clean = {k: v for k, v in entries_payload.items() if k in _ALLOWED_TOP_KEYS}

    # Ehrlicher Default: ein Tagesbericht ist datiert; ohne Betreiber-Vorgabe
    # wird das lokale Kalenderdatum gesetzt (SKRIPT != BETRIEB bleibt gewahrt).
    date_value = entries_clean.get("date") or datetime.date.today().isoformat()
    data = {
        "report_id": entries_clean.get("report_id")
        or ("v91-tagesbericht-" + str(Path(repo_root).resolve())),
        "date": date_value,
        "repo_head_sha": snapshot.get("head_sha") or "",
        "global_entries": entries_clean.get("global_entries", []),
        "local_entries": entries_clean.get("local_entries", []),
        "local_next_step": entries_clean.get("local_next_step"),
    }
    checks = [snapshot["check"]] if snapshot.get("check") else []
    data["checks"] = checks

    report = _daily_report.assemble_daily_report(data)
    if unknown_top_keys:
        report["violations"] = list(report.get("violations", [])) + [
            "entries:unknown_top_key:" + k for k in unknown_top_keys
        ]

    if bridge_exit == _bridge.EXIT_INPUT_ERROR:
        exit_code = EXIT_INPUT_ERROR
    elif snapshot.get("status") == "PASS" and not report.get("violations"):
        exit_code = EXIT_OK
    else:
        exit_code = EXIT_FAIL
    return report, unknown_top_keys, exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Erstaufruf-Tagesbericht aus echten Teil-C-Checks (read-only, SKRIPT != BETRIEB)")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT_DEFAULT),
                        help="Wurzelverzeichnis des Repository-Checkouts (Default: dieses Repo)")
    parser.add_argument("--out", default=None,
                        help="OPTIONALER Ausgabepfad fuer den Bericht (JSON). Ohne --out wird nur gedruckt.")
    parser.add_argument("--entries", default=None,
                        help="OPTIONALE JSON-Datei mit Teil-A/B-Eintraegen (claim/source/date je Eintrag)")
    args = parser.parse_args(argv)

    try:
        entries_payload = None
        if args.entries:
            data, unknown = load_entries(args.entries)
            entries_payload = dict(data)
            entries_payload["_unknown_top_keys"] = unknown
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "INPUT_ERROR", "detail": str(exc)}, indent=2))
        return EXIT_INPUT_ERROR

    if not Path(args.repo_root).is_dir():
        print(json.dumps({"error": "INPUT_ERROR", "detail": "repo_root existiert nicht"}, indent=2))
        return EXIT_INPUT_ERROR

    report, _unknown, exit_code = build_tagesbericht(args.repo_root, entries=entries_payload)
    printed = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    print(printed)
    if args.out:
        out_path = Path(args.out)
        try:
            inside_repo = out_path.resolve().is_relative_to(Path(args.repo_root).resolve())
        except OSError:
            inside_repo = False
        if inside_repo:
            print(json.dumps({"error": "INPUT_ERROR",
                              "detail": "--out liegt IM repository; Laufzeit-Artefakte gehoeren NICHT ins Repo (Ragnarok-Phase-1-Regel)"},
                             indent=2))
            return EXIT_INPUT_ERROR
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(printed + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
