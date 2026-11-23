#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Branch-Hygiene-Planer (VIBE-LXXXCI, CLAIM 7088648269):
READ-ONLY PLANER fuer gemergte Branches, PLAN != LOESCHUNG.
- liefert NUR einen Loeschplan (exakte Befehle fuer den BETREIBER);
  dieses Skript loescht SELBST NICHTS: kein 'push --delete', kein
  'branch -D', keine mutierenden git-Befehle, kein Netz, kein Token.
- nutzt ausschliesslich lokale git-LESE-Kommandos (rev-parse,
  branch --merged, for-each-ref) ueber subprocess mit fester
  Befehls-Allowlist; alles andere fail-closed (EXIT 3).
- Remote-Branch-Zustaende sind ohne Netz NICHT belegbar und werden
  ehrlich als UNKNOWN ausgewiesen (UNKNOWN != PASS); der Betreiber
  prueft die Liste vor der Ausfuehrung im GitHub-UI nach.
- kritische Aktionen (Loeschen) bleiben allein beim Betreiber
  (Arbeitsarchitektur-#391-Schutzregel: menschliche Freigabe,
  SCRIPTED != AUTONOM, PLAN != EXECUTION).
Richtlinie: docs/V91-AGENTEN-ARBEITSARCHITEKTUR.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 3

TASK_ID = "VIBE-LXXXCI"

_ALLOWED_GIT_COMMANDS = ("rev-parse", "branch", "for-each-ref")

_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

HONEST_NOTES = (
    "PLAN != LOESCHUNG: dieses Skript loescht nichts, der Betreiber fuehrt die Befehle aus.",
    "REMOTE_STATE_UNKNOWN: ohne Netz/Token ist der Remote-Zustand NICHT belegbar; Liste vor Loeschung im GitHub-UI pruefen.",
    "MERGED_LOCAL != MERGED_REMOTE: 'git branch --merged' prueft lokale Spitzen; Remote-Branches koennen abweichen, UNKNOWN != PASS.",
)

SKIP_PREFIXES = ("HEAD", "refs/HEAD")


class BranchHygieneError(RuntimeError):
    """Fail-closed Fehler des Planers (kein git, kein Repo, ungueltige Eingabe)."""


def validate_branch_name(name):
    """Zulaessige Branch-Namen ohne Pfad-Traversal oder Sonderzeichen."""
    if not isinstance(name, str):
        return False
    if ".." in name or not _BRANCH_RE.match(name):
        return False
    if name.endswith("/") or name.endswith(".lock"):
        return False
    return True


def parse_branch_list(output, base="main"):
    """Parst die Ausgabe von 'git branch --merged <base>' OHNE git.

    Reiner Kern (ohne subprocess), damit die Logik ohne git testbar ist.
    """
    branches = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("* "):
            line = line[2:].strip()
        if line.startswith("+ "):
            line = line[2:].strip()
        if not line or line == base:
            continue
        if not validate_branch_name(line):
            # Ehrlichkeit: unverstehbare Namen werden GEPRUEFT, nie geraten
            # und nie still verworfen -> als invalid gemeldet.
            raise BranchHygieneError("invalid branch name in output: " + repr(line))
        branches.append(line)
    return branches


def build_plan(merged_branches, remote_name="origin"):
    """Baut den Betreiber-Loeschplan aus den gemergten Branches.

    Nur DUENN: jeder Eintrag mappt auf exakt einen Loeschbefehl fuer
    lokal (branch -d, sicher weil --merged geprueft) und einen Vorschlag
    fuer Remote (push --delete, Ausfuehrung + Nachpruefung Betreiber).
    """
    if not isinstance(merged_branches, (list, tuple)):
        raise BranchHygieneError("merged_branches must be a list")
    plan = {}
    for name in merged_branches:
        if not validate_branch_name(name):
            raise BranchHygieneError("invalid branch name: " + repr(name))
    remote_name_ok = validate_branch_name(remote_name) and "/" not in remote_name
    if not remote_name_ok:
        raise BranchHygieneError("invalid remote name: " + repr(remote_name))
    plan["plan_id"] = "v91-branch-hygiene-" + TASK_ID
    plan["operator_commands"] = [
        {
            "branch": name,
            "local_delete": "git branch -d " + name,
            "remote_delete_suggestion": "git push " + remote_name + " --delete " + name,
        }
        for name in merged_branches
    ]
    plan["merged_local_branches"] = list(merged_branches)
    plan["honest_notes"] = list(HONEST_NOTES)
    plan["executed"] = False
    return plan


def _run_git(args, cwd):
    """Fuehrt NUR erlaubte git-LESE-Kommandos aus, sonst fail-closed."""
    if not args or args[0] not in _ALLOWED_GIT_COMMANDS:
        raise BranchHygieneError("git command not allowed: " + repr(args[:1]))
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise BranchHygieneError("git not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise BranchHygieneError("git timed out") from exc
    if proc.returncode != 0:
        raise BranchHygieneError("git failed: " + (proc.stderr.strip() or "unknown error"))
    return proc.stdout


def is_git_repo(repo_root):
    try:
        _run_git(["rev-parse", "--git-dir"], repo_root)
        return True
    except BranchHygieneError:
        return False


def list_merged_branches(repo_root, base="main"):
    """Liefert lokale, in <base> gemergte Branches (read-only)."""
    if not is_git_repo(repo_root):
        raise BranchHygieneError("no git repository at: " + str(repo_root))
    if not validate_branch_name(base) or ".." in base:
        raise BranchHygieneError("invalid base branch: " + repr(base))
    output = _run_git(["branch", "--merged", base], repo_root)
    return parse_branch_list(output, base=base)


def render_plan(plan):
    """Druckbare, operationssichere Fassung des Plans fuer den Betreiber."""
    lines = [
        "V91 Branch-Hygiene-Plan (" + plan.get("plan_id", "unknown plan") + ")",
        "PLAN != LOESCHUNG: nichts wurde geloescht; Ausfuehrung bleibt dem Betreiber vorbehalten.",
        "",
    ]
    branches = plan.get("merged_local_branches", [])
    if not branches:
        lines.append("KEINE lokal in die Basis gemergten Branches gefunden (leerer Plan, kein Befund ueber Remote).")
    for cmd in plan.get("operator_commands", []):
        lines.append("Branch:   " + cmd["branch"])
        lines.append("  lokal:    " + cmd["local_delete"])
        lines.append("  remote:   " + cmd["remote_delete_suggestion"] + "  (Zustand im GitHub-UI pruefen)")
        lines.append("")
    for note in plan.get("honest_notes", []):
        lines.append("HINWEIS: " + note)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only Loeschplan fuer gemergte Branches; PLAN != LOESCHUNG, Betreiber fuehrt aus")
    parser.add_argument("--repo-root", default=".",
                        help="Wurzelverzeichnis des lokalen git-Checkouts")
    parser.add_argument("--base", default="main",
                        help="Zweig, gegen den gemergt wird (Default: main)")
    parser.add_argument("--json-out", default=None,
                        help="OPTIONALER Ausgabepfad (JSON) AUSSERHALB des Repos")
    args = parser.parse_args(argv)

    try:
        merged = list_merged_branches(args.repo_root, base=args.base)
        plan = build_plan(merged)
    except BranchHygieneError as exc:
        print(json.dumps({"error": "INPUT_ERROR", "detail": str(exc)}, indent=2))
        return EXIT_INPUT_ERROR

    printed = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False)
    print(printed)
    print()
    print(render_plan(plan))
    if args.json_out:
        out_path = Path(args.json_out)
        try:
            inside_repo = out_path.resolve().is_relative_to(Path(args.repo_root).resolve())
        except OSError:
            inside_repo = False
        if inside_repo:
            print(json.dumps({"error": "INPUT_ERROR",
                              "detail": "--json-out liegt IM repository; Laufzeit-Artefakte gehoeren NICHT ins Repo (Ragnarok-Phase-1-Regel)"},
                             indent=2))
            return EXIT_INPUT_ERROR
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(printed + "\n", encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
